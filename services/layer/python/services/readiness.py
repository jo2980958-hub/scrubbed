"""Patient readiness and post-op follow-up.

Pre-op instructions, confirmations (fasting/consent/balance), the readiness score and
cancellation-risk band (via safety.engine), the not-ready sweep, and post-op follow-up
with danger-sign escalation (via agent.classify). Depends on common.db, common.cds,
safety.engine, agent.classify, common.config. Contract fixed.

Everything the patient reads is logistics or an acknowledgement. We never diagnose and
never reassure: a recognised danger sign or a reported problem is escalated to the team,
and the patient is told we have passed it on and to call emergency services if urgent.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from agent import classify
from common import cds, config, db, documents
from safety import engine
from wa import messages


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    """Parse a stored ISO time (e.g. '2026-10-09T14:00:00Z') to an aware datetime."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _hours_to_surgery(case: Optional[dict]) -> Optional[float]:
    """Hours from now until the case's scheduled time, or None if unknown."""
    if not case:
        return None
    scheduled = _parse_iso(case.get("scheduledAt"))
    if not scheduled:
        return None
    return (scheduled - datetime.now(timezone.utc)).total_seconds() / 3600.0


def _format_dt(dt: datetime) -> str:
    """A plain, readable time for a patient message, e.g. 'Friday 09 October at 14:00'."""
    return dt.strftime("%A %d %B at %H:%M")


def _current_case_for_patient(patient: Optional[dict]) -> Optional[dict]:
    """The patient's case nearest to now (most recent past or next upcoming). A patient has
    one case at a time in the demo; nearest-in-time is the safe pick either side of surgery."""
    if not patient:
        return None
    cases = [c for c in db.list_cases(hospital_id=patient.get("hospitalId"))
             if c.get("patientId") == patient.get("patientId")]
    if not cases:
        return None
    now = datetime.now(timezone.utc)

    def distance(case: dict) -> float:
        scheduled = _parse_iso(case.get("scheduledAt"))
        return abs((scheduled - now).total_seconds()) if scheduled else float("inf")

    return min(cases, key=distance)


def send_preop_instructions(case_id: str) -> dict:
    """Send the patient their plain pre-op instructions and mark instructions_sent.

    Logistics only: fast from midnight, the arrival time, and what to bring. Returns a
    result dict with the recipient and the message id.
    """
    case = db.get_case(case_id)
    if not case:
        raise ValueError(f"no case {case_id}")
    patient = db.get_patient(case.get("patientId")) if case.get("patientId") else None
    if not patient or not patient.get("whatsappNumber"):
        raise ValueError(f"case {case_id} has no patient to message")

    name = patient.get("name") or "there"
    scheduled = _parse_iso(case.get("scheduledAt"))
    when = _format_dt(scheduled) if scheduled else "the scheduled time"
    arrive = _format_dt(scheduled - timedelta(hours=2)) if scheduled else "two hours before"
    theatre = case.get("theatre")
    procedure = case.get("procedure") or "your operation"
    place = f"{procedure}, {theatre}" if theatre else procedure

    body = (
        f"Hi {name}. Here are your instructions for your operation.\n\n"
        f"Operation: {place}.\n"
        f"When: {when}.\n\n"
        "Before you come in:\n"
        "- Do not eat or drink anything from midnight the night before. "
        "No water either, unless your team tells you otherwise.\n"
        f"- Please arrive by {arrive}.\n"
        "- Bring a photo ID, any medicines you take (in their boxes), "
        "a dressing gown and slippers, and this message.\n\n"
        "Reply here if anything worries you, or if you cannot make it."
    )

    number = patient["whatsappNumber"]
    message_id = cds.send_whatsapp_text(number, body)
    db.set_readiness_item(case_id, "instructions_sent", True)
    db.add_message(number, "out", message_id, body=body, kind="preop_instructions")
    db.add_event(case_id, "preop_instructions_sent", actor="system",
                 detail={"to": number, "messageId": message_id})
    return {"caseId": case_id, "to": number, "messageId": message_id,
            "item": "instructions_sent"}


def record_confirmation(case_id: str, item: str, value: bool) -> dict:
    """Record a readiness confirmation (fasting/consent/balance/...) and return the fresh
    readiness view."""
    db.set_readiness_item(case_id, item, bool(value))
    db.add_event(case_id, "readiness_confirmed", actor="system",
                 detail={"item": item, "value": bool(value)})
    return case_readiness(case_id)


def case_readiness(case_id: str) -> dict:
    """The deterministic readiness view for a case: score, readiness, cancellation risk,
    and the outstanding items. All of it from safety.engine; no model in the loop."""
    case = db.get_case(case_id)
    status = db.get_readiness(case_id)
    r = engine.readiness(status)
    hours = _hours_to_surgery(case)
    risk = engine.cancellation_risk(status, hours)
    return {
        "caseId": case_id,
        "score": r["score"],
        "isReady": r["isReady"],
        "risk": risk,
        "outstanding": r["outstanding"],
        "outstandingRequired": r["outstandingRequired"],
        "hoursToSurgery": round(hours, 1) if hours is not None else None,
    }


def not_ready_sweep(hospital_id: Optional[str] = None) -> list[dict]:
    """Every upcoming case at medium or high cancellation risk, for the scheduler to flag on
    the worklist and email the coordinator. Past, cancelled and completed cases are skipped."""
    at_risk = []
    for case in db.list_cases(hospital_id=hospital_id):
        if case.get("status") in ("cancelled", "completed"):
            continue
        hours = _hours_to_surgery(case)
        if hours is None or hours < 0:
            continue
        r = case_readiness(case["caseId"])
        if r["risk"] in ("medium", "high"):
            at_risk.append({
                "caseId": case["caseId"],
                "hospitalId": case.get("hospitalId"),
                "surgeonId": case.get("surgeonId"),
                "patientId": case.get("patientId"),
                "procedure": case.get("procedure"),
                "theatre": case.get("theatre"),
                "scheduledAt": case.get("scheduledAt"),
                "risk": r["risk"],
                "score": r["score"],
                "isReady": r["isReady"],
                "outstanding": r["outstanding"],
                "outstandingRequired": r["outstandingRequired"],
                "hoursToSurgery": r["hoursToSurgery"],
            })
    at_risk.sort(key=lambda c: (c["risk"] != "high", c["hoursToSurgery"] if c["hoursToSurgery"] is not None else 1e9))
    return at_risk


def email_worklists() -> int:
    """Email each hospital's coordinators the day's not-ready worklist as a PDF over SES.
    Called by the scheduler tick. Returns how many emails were sent (zero when nothing is
    at risk or no coordinator has an email on file)."""
    at_risk = not_ready_sweep()
    if not at_risk:
        return 0

    by_hospital: dict = {}
    for case in at_risk:
        by_hospital.setdefault(case.get("hospitalId") or "", []).append(case)

    sent = 0
    for hospital_id, cases in by_hospital.items():
        if not hospital_id:
            continue
        coordinators = [s for s in db.list_staff(hospital_id)
                        if s.get("email") and any(w in (s.get("role") or "").lower()
                                                  for w in ("coordinator", "charge", "admin"))]
        if not coordinators:
            continue
        pdf = documents.worklist_pdf({"name": hospital_id, "hospitalId": hospital_id}, cases)
        high = sum(1 for c in cases if c.get("risk") == "high")
        body = (f"{len(cases)} case(s) need attention before theatre today"
                + (f", {high} at high risk" if high else "") + ".\n\n"
                "The attached worklist lists each one and what is still outstanding. "
                f"Open {config.BRAND} to action them.")
        for coord in coordinators:
            cds.send_email(
                to=coord["email"],
                subject=f"{config.BRAND}: {len(cases)} case(s) at risk today",
                body=body,
                attachment={"filename": "worklist.pdf", "content": pdf,
                            "content_type": "application/pdf"})
            sent += 1
    return sent


def send_followup(case_id: str) -> dict:
    """Send the post-op check-in. It asks how they feel and lists nothing clinical; a reply
    is classified and escalated by handle_patient_reply. Returns a result dict."""
    case = db.get_case(case_id)
    if not case:
        raise ValueError(f"no case {case_id}")
    patient = db.get_patient(case.get("patientId")) if case.get("patientId") else None
    if not patient or not patient.get("whatsappNumber"):
        raise ValueError(f"case {case_id} has no patient to message")

    name = patient.get("name") or "there"
    body = (
        f"Hi {name}. This is a check-in after your operation. How are you feeling?\n\n"
        "You can reply in your own words. Reply here if anything worries you and the team "
        "will see it. If this is an emergency, call your hospital or emergency services."
    )

    number = patient["whatsappNumber"]
    message_id = cds.send_whatsapp_text(number, body)
    db.add_message(number, "out", message_id, body=body, kind="postop_followup")
    db.add_event(case_id, "postop_followup_sent", actor="system",
                 detail={"to": number, "messageId": message_id})
    return {"caseId": case_id, "to": number, "messageId": message_id}


def _phase_for(case: Optional[dict]) -> str:
    """Pre-op before the scheduled time, post-op after it. Unknown time -> post-op (the
    conservative default: a post-op check-in treats worries as danger signs)."""
    hours = _hours_to_surgery(case)
    if hours is None:
        return "post-op"
    return "pre-op" if hours > 0 else "post-op"


def _should_notify(result: dict) -> bool:
    """When a patient reply needs a human pushed to, not just recorded: any escalation, a
    stated inability to attend, or a question."""
    return bool(result.get("escalate")) or result.get("intent") in ("cannot_attend", "question")


def _clinicians_for(case: Optional[dict], patient: Optional[dict]) -> list[dict]:
    """Who to push a patient escalation to, best first: the case surgeon, then the rest of
    the case team, then any clinician or coordinator at the hospital. De-duplicated, each
    with a WhatsApp number, so a missing surgeon number falls back rather than dropping."""
    seen: set = set()
    out: list[dict] = []

    def add(member: Optional[dict]) -> None:
        number = (member or {}).get("whatsappNumber")
        if number and number not in seen:
            seen.add(number)
            out.append(member)

    if case:
        if case.get("surgeonId"):
            add(db.get_staff(case["surgeonId"]))
        for sid in case.get("team") or []:
            add(db.get_staff(sid))

    hospital_id = (case or {}).get("hospitalId") or (patient or {}).get("hospitalId")
    if hospital_id:
        def rank(member: dict) -> int:
            role = (member.get("role") or "").lower()
            if "surgeon" in role:
                return 0
            if "coordinator" in role or "charge" in role or "admin" in role:
                return 1
            return 2
        for member in sorted(db.list_staff(hospital_id), key=rank):
            add(member)
    return out


def _notify_team(case: Optional[dict], patient: Optional[dict], result: dict) -> bool:
    """Push a patient's escalation, absence or question to the responsible clinician.
    Returns True only if a clinician was actually messaged. Always records the attempt (and
    whether it was delivered) on the case timeline, so an undelivered escalation is
    auditable for a coordinator to chase, never silently dropped. Names what was seen; adds
    no judgement."""
    who = (patient or {}).get("name") or "the patient"
    signs = result.get("dangerSigns") or []
    intent = result.get("intent")
    if result.get("escalate"):
        if signs:
            line = "reports: " + "; ".join(signs)
        elif result.get("classifierError"):
            line = "sent a reply the assistant could not read automatically; please read it"
        else:
            line = "reports a problem in a message"
        event_type, subject = "danger_sign_escalated", "Follow-up flag"
    elif intent == "cannot_attend":
        line, event_type, subject = "says they cannot attend", "patient_cannot_attend", "Patient message"
    else:
        line, event_type, subject = "has a question", "patient_question", "Patient message"

    procedure = (case or {}).get("procedure") or "their case"
    body = (f"{subject} for {procedure}: {who} {line}. "
            "Please review and contact the patient. This is a flag, not an assessment.")

    delivered_to = None
    recipients = _clinicians_for(case, patient)
    if recipients:
        number = recipients[0]["whatsappNumber"]
        message_id = cds.send_whatsapp_text(number, body)
        db.add_message(number, "out", message_id, body=body, kind="patient_escalation")
        delivered_to = number

    if case:
        db.add_event(case["caseId"], event_type, actor="system",
                     detail={"intent": intent, "dangerSigns": signs,
                             "patientId": (patient or {}).get("patientId"),
                             "notifiedNumber": delivered_to, "delivered": bool(delivered_to)})
    return bool(delivered_to)


def _acknowledgement(result: dict, notified: bool) -> str:
    """The patient-facing acknowledgement. It confirms we heard them and says truthfully
    what happened next. It never diagnoses and never reassures, and it never claims the
    team was told when no clinician could be reached."""
    if result.get("escalate"):
        if notified:
            return ("Thanks, I've let the team know and they will be in touch. "
                    "If this is an emergency, call your hospital or emergency services.")
        return ("Thanks for telling me. I couldn't reach your care team automatically just now, "
                "so please call your hospital now. If this is an emergency, call emergency services.")
    intent = result.get("intent")
    if intent == "cannot_attend":
        if notified:
            return ("Thanks for letting us know. I've told the team you cannot attend and they "
                    "will be in touch.")
        return ("Thanks for letting us know. Please also call your hospital to confirm, "
                "as I couldn't reach the team automatically.")
    if intent == "question":
        if notified:
            return ("Thanks for your message. I've passed your question to the team and they "
                    "will get back to you.")
        return ("Thanks for your message. Please call your hospital with your question, "
                "as I couldn't reach the team automatically.")
    if intent == "confirm":
        return "Thanks, noted. The team can see your message."
    return "Thanks, I've noted your message for the team."


def handle_patient_reply(number: str, text: str) -> list[dict]:
    """A patient's inbound reply: record it, classify it, push a danger sign / problem /
    absence / question to a clinician, and return the acknowledgement(s) to send back.

    Returns a list of wa.messages builder dicts (the webhook sends and records them). The
    reply only acknowledges; it never diagnoses, never reassures, and only claims the team
    was told when a clinician was actually reached.
    """
    patient = db.get_patient_by_whatsapp(number)
    case = _current_case_for_patient(patient)

    context = {"phase": _phase_for(case)}
    if case and case.get("procedure"):
        context["procedure"] = case["procedure"]
    result = classify.classify_reply(text, context)

    db.add_message(number, "in", db.new_id(), body=text,
                   kind="patient_reply", intent=result.get("intent"),
                   escalate=result.get("escalate"))

    notified = _notify_team(case, patient, result) if _should_notify(result) else False

    if case:
        db.add_event(case["caseId"], "patient_reply", actor="patient",
                     detail={"intent": result.get("intent"),
                             "dangerSigns": result.get("dangerSigns"),
                             "escalate": result.get("escalate"),
                             "confidence": result.get("confidence"), "notified": notified})

    return [messages.text(_acknowledgement(result, notified))]
