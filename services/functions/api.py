"""Dashboard API (HTTP API payload v2 + Cognito JWT).

The signed-in user is a coordinator/admin; we resolve them to a staff record by the
email claim and scope every read to their hospital. Serves the case board, case detail
(with the instrument second-count audit), the paging ladder, conversations, forms and
the follow-up queue.
"""
from __future__ import annotations

import json
import logging

from common import config, db
from services import paging, readiness

log = logging.getLogger()
log.setLevel(logging.INFO)

_CORS = {"Access-Control-Allow-Origin": "*",
         "Access-Control-Allow-Headers": "authorization,content-type",
         "Access-Control-Allow-Methods": "GET,POST,PATCH,PUT,DELETE,OPTIONS"}


def _resp(code: int, body) -> dict:
    return {"statusCode": code, "headers": {"Content-Type": "application/json", **_CORS},
            "body": json.dumps(body, default=str)}


def _claims(event) -> dict:
    return (((event.get("requestContext") or {}).get("authorizer") or {}).get("jwt") or {}).get("claims") or {}


def _staff(event):
    email = _claims(event).get("email")
    return db.get_staff_by_email(email) if email else None


def _case_summary(c: dict) -> dict:
    return {"caseId": c["caseId"], "procedure": c.get("procedure"), "theatre": c.get("theatre"),
            "scheduledAt": c.get("scheduledAt"), "surgeonId": c.get("surgeonId"),
            "status": c.get("status"), "readiness": readiness.case_readiness(c["caseId"])}


def _team(case: dict) -> list:
    out = []
    for sid in case.get("team") or []:
        s = db.get_staff(sid)
        if s:
            out.append({"staffId": s["staffId"], "name": s.get("name"), "role": s.get("role")})
    return out


def _case_full(case: dict) -> dict:
    patient = db.get_patient(case.get("patientId")) if case.get("patientId") else None
    return {"case": case, "team": _team(case), "patient": patient,
            "readiness": readiness.case_readiness(case["caseId"]),
            "tray": db.get_tray(case["caseId"])}


def _pages(case_id: str) -> list:
    out = []
    for page in db.list_pages_for_case(case_id):
        recips = []
        for r in db.list_page_recipients(page["pageId"]):
            s = db.get_staff(r.get("staffId")) if r.get("staffId") else None
            recips.append({"name": (s or {}).get("name"), "role": (s or {}).get("role"),
                           "status": r.get("status"), "sentAt": r.get("sentAt"),
                           "deliveredAt": r.get("deliveredAt"), "readAt": r.get("readAt"),
                           "acknowledgedAt": r.get("acknowledgedAt"), "escalated": r.get("escalated")})
        out.append({"pageId": page["pageId"], "body": page.get("body"),
                    "createdAt": page.get("createdAt"), "urgent": page.get("urgent"),
                    "recipients": recips})
    return out


def _conversations(case: dict) -> list:
    numbers = []
    patient = db.get_patient(case.get("patientId")) if case.get("patientId") else None
    if patient and patient.get("whatsappNumber"):
        numbers.append(patient["whatsappNumber"])
    for sid in case.get("team") or []:
        s = db.get_staff(sid)
        if s and s.get("whatsappNumber"):
            numbers.append(s["whatsappNumber"])
    msgs = []
    for n in set(numbers):
        for m in db.list_messages(n):
            if m.get("caseId") == case["caseId"]:
                msgs.append(m)
    return sorted(msgs, key=lambda m: m.get("createdAt", ""))


def handler(event, context=None):
    method = (event.get("requestContext", {}).get("http", {}).get("method") or "").upper()
    path = (event.get("rawPath") or "/").rstrip("/") or "/"
    if method == "OPTIONS":
        return {"statusCode": 204, "headers": _CORS}

    staff = _staff(event)
    if not staff:
        return _resp(401, {"message": "Sign in with a registered staff email."})
    hosp = staff.get("hospitalId")
    parts = [p for p in path.split("/") if p]

    try:
        if path == "/me":
            return _resp(200, {"staff": staff})

        if parts[:1] == ["staff"]:
            if method == "GET":
                return _resp(200, {"staff": db.list_staff(hosp)})
            if method == "POST":
                data = json.loads(event.get("body") or "{}")
                data["hospitalId"] = hosp
                return _resp(200, {"staff": db.create_staff(data)})

        if path == "/followups" and method == "GET":
            return _resp(200, {"cases": readiness.not_ready_sweep(hosp)})

        if parts[:1] == ["cases"] and len(parts) == 1:
            if method == "GET":
                day = (event.get("queryStringParameters") or {}).get("day")
                return _resp(200, {"cases": [_case_summary(c) for c in db.list_cases(hosp, day)]})
            if method == "POST":
                data = json.loads(event.get("body") or "{}")
                data["hospitalId"] = hosp
                return _resp(200, {"case": db.create_case(data)})

        if parts[:1] == ["cases"] and len(parts) >= 2:
            case = db.get_case(parts[1])
            if not case or case.get("hospitalId") != hosp:
                return _resp(404, {"message": "Case not found."})
            case_id = parts[1]
            if len(parts) == 2:
                if method == "GET":
                    return _resp(200, _case_full(case))
                if method == "PATCH":
                    return _resp(200, {"case": db.update_case(case_id, json.loads(event.get("body") or "{}"))})
            sub = parts[2]
            if sub == "pages" and method == "GET":
                return _resp(200, {"pages": _pages(case_id)})
            if sub == "conversations" and method == "GET":
                return _resp(200, {"messages": _conversations(case)})
            if sub == "forms" and method == "GET":
                return _resp(200, {"forms": db.list_forms_for_case(case_id)})
            if sub == "page" and method == "POST":
                b = json.loads(event.get("body") or "{}")
                paging.send_page(case_id, staff["staffId"], b.get("body", "Please confirm for the case."),
                                 bool(b.get("urgent")))
                return _resp(200, {"ok": True})

        return _resp(404, {"message": "Not found."})
    except Exception:
        log.exception("api error on %s %s", method, path)
        return _resp(500, {"message": "Something went wrong."})
