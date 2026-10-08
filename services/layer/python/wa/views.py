"""Read screens for the staff app. Each returns a Reply (wa.messages dict) or a list.
Depends on common.db, safety.engine, common.config, wa.messages. No writes. Contract fixed.

Every screen that names a case checks it belongs to the staff member's own hospital; a
case at another hospital reads back as not found. The screens only render; the spine
(safety.engine) owns the readiness score, the risk band and the checklist content.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from common import db
from safety import engine
from wa import messages

# How the three WHO phases read in a sentence.
_PHASE_LABEL = {"sign_in": "sign-in", "time_out": "time-out", "sign_out": "sign-out"}
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _day_for(when: str) -> str:
    """Resolve a 'today'/'tomorrow' word (or a YYYY-MM-DD string) to a day prefix."""
    today = datetime.now(timezone.utc).date()
    if when == "tomorrow":
        return (today + timedelta(days=1)).isoformat()
    if when == "today" or not when:
        return today.isoformat()
    if len(when) >= 10 and when[4] == "-" and when[7] == "-":
        return when[:10]
    return today.isoformat()


def _hhmm(value) -> str:
    """Just the time of day from an ISO timestamp."""
    s = str(value or "")
    if "T" in s:
        return ":".join(s.split("T")[1].replace("Z", "").split(":")[:2]) or "--:--"
    return "--:--"


def _clock(value) -> str:
    """'2026-10-09T14:00:00Z' -> '09 Oct 2026, 14:00'."""
    s = str(value or "").strip()
    if not s:
        return "To be confirmed"
    try:
        d, t = s.replace("Z", "").split("T")
        y, m, day = d.split("-")
        hhmm = ":".join(t.split(":")[:2])
        return f"{int(day):02d} {_MONTHS[int(m) - 1]} {y}, {hhmm}"
    except (ValueError, IndexError):
        return s


def _hours_to(scheduled_at) -> float | None:
    """Hours from now until the scheduled time, or None if it cannot be read."""
    s = str(scheduled_at or "").strip()
    if not s:
        return None
    try:
        when = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return (when - datetime.now(timezone.utc)).total_seconds() / 3600


def _status_and_risk(case: dict) -> tuple[dict, str]:
    """The readiness score (via the spine) and the cancellation-risk band for a case."""
    status = db.get_readiness(case.get("caseId", ""))
    r = engine.readiness(status)
    risk = engine.cancellation_risk(status, _hours_to(case.get("scheduledAt")))
    return r, risk


def _short_state(r: dict, risk: str) -> str:
    """A one-phrase readiness/risk label for a list row."""
    if r["isReady"]:
        return "Ready"
    return {"high": "High risk", "medium": "Medium risk", "low": "At risk"}.get(risk, "Not ready")


def _owned(staff: dict, case_id: str):
    """Return the case if it belongs to the staff member's hospital, else None."""
    case = db.get_case(case_id)
    if not case or case.get("hospitalId") != staff.get("hospitalId"):
        return None
    return case


def _not_found() -> dict:
    return messages.text("That case was not found, or it is not at your hospital.")


def _ticked_indexes(case_id: str, phase: str) -> set:
    """Which checklist items in this phase are currently ticked, from the event log.
    The latest event for an item wins, so an item can be ticked then un-ticked."""
    latest: dict = {}
    for ev in db.list_events(case_id):
        if ev.get("type") != "checklist":
            continue
        detail = ev.get("detail") or {}
        if detail.get("phase") != phase or "index" not in detail:
            continue
        latest[int(detail["index"])] = bool(detail.get("value"))
    return {i for i, done in latest.items() if done}


def my_list(staff: dict, when: str = "today") -> dict:
    """A surgeon's own list, or the hospital's board for everyone else, for one day."""
    day = _day_for(when)
    if "surgeon" in (staff.get("role") or "").lower():
        cases = db.list_cases_for_surgeon(staff["staffId"], day)
    else:
        cases = db.list_cases(staff.get("hospitalId"), day)
    cases = sorted(cases, key=lambda c: str(c.get("scheduledAt", "")))

    label = {"today": "today", "tomorrow": "tomorrow"}.get(when, day)
    if not cases:
        return messages.text(f"No cases for {label}.")

    rows = []
    for case in cases:
        r, risk = _status_and_risk(case)
        rows.append({
            "id": f"case:{case['caseId']}",
            "title": f"{_hhmm(case.get('scheduledAt'))} {case.get('procedure', '')}".strip(),
            "description": f"{case.get('theatre', 'Theatre TBC')} · {_short_state(r, risk)}",
        })
    return messages.list_message(
        body=f"Your list for {label}. {len(cases)} case{'s' if len(cases) != 1 else ''}.",
        button_label="Open a case",
        sections=[{"title": "Cases", "rows": rows}],
        header="My list",
    )


def case_detail(staff: dict, case_id: str) -> dict:
    """One case: the facts, the team, the patient, readiness and risk, and the actions."""
    case = _owned(staff, case_id)
    if not case:
        return _not_found()

    team = []
    for sid in case.get("team", []):
        member = db.get_staff(sid)
        if member:
            team.append(f"{member.get('name', 'Unknown')} ({member.get('role', 'team')})")
    patient = db.get_patient(case.get("patientId")) if case.get("patientId") else None

    r, risk = _status_and_risk(case)
    if r["isReady"]:
        ready_line = f"Readiness: ready, {r['doneCount']} of {r['total']} items done."
    else:
        ready_line = f"Readiness: not ready, {r['doneCount']} of {r['total']} done. Risk {risk}."
        if r["outstandingRequired"]:
            ready_line += " Outstanding: " + "; ".join(r["outstandingRequired"]) + "."

    lines = [
        case.get("procedure", "Case"),
        f"Theatre: {case.get('theatre', 'TBC')}",
        f"Scheduled: {_clock(case.get('scheduledAt'))}",
    ]
    if patient:
        lines.append(f"Patient: {patient.get('name', 'Unknown')}")
    lines.append(f"Team: {', '.join(team) if team else 'none assigned yet'}")
    lines.append(ready_line)

    rows = [
        {"id": f"check:{case_id}:sign_in", "title": "Run checklist",
         "description": "WHO sign-in"},
        {"id": f"page:{case_id}", "title": "Page the team",
         "description": "Send a page to the roster"},
        {"id": f"brief:{case_id}", "title": "Case brief PDF",
         "description": "Get the brief as a PDF"},
        {"id": f"tray:{case_id}:before", "title": "Tray check",
         "description": "Start the instrument second count"},
    ]
    return messages.list_message(
        body="\n".join(lines),
        button_label="Case actions",
        sections=[{"title": "Actions", "rows": rows}],
        header=case.get("theatre", "Case"),
    )


def checklist_view(staff: dict, case_id: str, phase: str) -> dict:
    """The WHO checklist for one phase, as toggle rows the surgeon taps in chat."""
    case = _owned(staff, case_id)
    if not case:
        return _not_found()
    items = engine.CHECKLIST.get(phase)
    if not items:
        return messages.text("That checklist phase is not recognised.")

    ticked = _ticked_indexes(case_id, phase)
    rows = []
    for idx, item in enumerate(items):
        done = idx in ticked
        rows.append({
            "id": f"chk:{case_id}:{phase}:{idx}:{0 if done else 1}",
            "title": f"{'Done' if done else 'Tick'} {idx + 1}",
            "description": item,
        })
    label = _PHASE_LABEL.get(phase, phase)
    return messages.list_message(
        body=f"WHO {label} checklist for {case.get('procedure', 'this case')}. "
             f"{len(ticked)} of {len(items)} ticked. Tap an item to toggle it.",
        button_label="Tick an item",
        sections=[{"title": label.title(), "rows": rows}],
        header="Checklist",
    )


def readiness_view(staff: dict, case_id: str) -> dict:
    """The readiness items (done and outstanding) with the score and risk band."""
    case = _owned(staff, case_id)
    if not case:
        return _not_found()
    status = db.get_readiness(case_id)
    r = engine.readiness(status)
    risk = engine.cancellation_risk(status, _hours_to(case.get("scheduledAt")))

    rows = []
    for key, item_label, required in engine.READINESS_ITEMS:
        done = bool(status.get(key))
        desc = "Done" if done else ("Outstanding, required" if required else "Outstanding")
        rows.append({
            "id": f"ready:{case_id}:{key}:{0 if done else 1}",
            "title": item_label,
            "description": desc,
        })

    head = ("Ready" if r["isReady"] else "Not ready")
    body = (f"{head}. {r['doneCount']} of {r['total']} items done. Risk {risk}. "
            "Tap an item to change it.")
    return messages.list_message(
        body=body,
        button_label="Change an item",
        sections=[{"title": "Readiness", "rows": rows}],
        header="Readiness",
    )


def paging_status(staff: dict, case_id: str) -> dict:
    """The paging ladder for a case, one line per person, as text."""
    case = _owned(staff, case_id)
    if not case:
        return _not_found()
    from services import paging

    people = paging.page_status(case_id)
    if not people:
        return messages.text(f"No one has been paged yet for {case.get('procedure', 'this case')}.")

    lines = [f"Paging status for {case.get('procedure', 'this case')}:"]
    for person in people:
        name = person.get("name")
        if not name and person.get("staffId"):
            member = db.get_staff(person["staffId"])
            name = member.get("name") if member else None
        name = name or person.get("number") or "Unknown"
        state = str(person.get("status", "sent"))
        bits = [state]
        if person.get("readAt"):
            bits.append("read")
        if person.get("acknowledgedAt"):
            bits.append("acknowledged")
        if person.get("status") == "escalated" or person.get("escalatedAt"):
            bits.append("escalated to a call")
        lines.append(f"- {name}: {', '.join(bits)}")
    return messages.text("\n".join(lines))
