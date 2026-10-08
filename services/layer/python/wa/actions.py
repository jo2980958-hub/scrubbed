"""Write actions for the staff app. Each returns a Reply (or list). Every action that
names a case checks it belongs to the staff member's hospital. Depends on common.db,
services.paging, services.readiness, safety.engine, agent.vision, common.documents,
common.cds, wa.messages. Contract fixed.

The instrument check here is a SECOND count. It surfaces a discrepancy for a human; the
manual WHO surgical count stays the authority. The wording says so, and the code never
presents its figure as the count.
"""
from __future__ import annotations

import os
from typing import Optional

from agent import vision
from common import cds, db, documents
from safety import engine
from services import paging, readiness
from wa import messages
from wa.views import _owned, _not_found, _ticked_indexes, checklist_view, readiness_view

# Phase word -> a readable fragment for the tray wording.
_OTHER_PHASE = {"before": "after", "after": "before"}
_SECOND_COUNT = "This is a second count; the manual WHO count stays the authority."


def run_checklist_item(staff: dict, case_id: str, phase: str, index: int, value: bool) -> dict:
    """Record one checklist tick on the audit log and show the next item, or the summary."""
    case = _owned(staff, case_id)
    if not case:
        return _not_found()
    items = engine.CHECKLIST.get(phase, [])
    item_text = items[index] if 0 <= index < len(items) else ""
    db.add_event(case_id, "checklist", staff["staffId"],
                 {"phase": phase, "index": int(index), "item": item_text, "value": bool(value)})

    confirm = f"{'Ticked' if value else 'Un-ticked'}: {item_text or f'item {index + 1}'}."
    ticked = _ticked_indexes(case_id, phase)
    nxt = next((i for i in range(len(items)) if i not in ticked), None)
    if nxt is None:
        return messages.buttons(
            f"{confirm}\n\nEvery item in this phase is ticked.",
            [(f"case:{case_id}", "Back to case")])
    return messages.buttons(
        f"{confirm}\n\nNext: {items[nxt]}",
        [(f"chk:{case_id}:{phase}:{nxt}:1", "Tick next"),
         (f"check:{case_id}:{phase}", "Show all")])


def page_team(staff: dict, case_id: str, body: Optional[str] = None, urgent: bool = False) -> list[dict]:
    """Fan a page out to the case roster through the paging service."""
    case = _owned(staff, case_id)
    if not case:
        return [_not_found()]
    result = paging.send_page(case_id, staff["staffId"],
                              body or "Please confirm for the case.", urgent)
    sent = len(result.get("recipients", [])) if isinstance(result, dict) else 0
    who = f"{sent} team member{'s' if sent != 1 else ''}" if sent else "the team"
    msg = f"Paged {who} for {case.get('procedure', 'this case')}."
    if urgent:
        msg += " Marked urgent."
    msg += " You can check who has acknowledged from the case."
    return [messages.text(msg)]


def acknowledge(staff: dict, page_id: str) -> dict:
    """Record this staff member's acknowledgement of a page and cancel their escalation.

    Only a recipient of the page may acknowledge it: the staff member's own WhatsApp number
    has to match a recipient row. That check also keeps the write inside the hospital that
    was paged, so a tapped foreign pageId can never pollute another case's ladder."""
    return acknowledge_by_number(staff.get("whatsappNumber", ""), page_id)


def acknowledge_by_number(number: str, page_id: str) -> dict:
    """Acknowledge by WhatsApp number. Used by the in-app tap and by a recipient who taps
    Acknowledge without being logged into the staff app. Verifies the number is an actual
    recipient of the page first, so a stray or foreign pageId is a silent no-op rather than
    an injected recipient row and audit event."""
    if not number or not page_id:
        return messages.text("That page could not be acknowledged.")
    if not db.is_page_recipient(page_id, number):
        return messages.text("I couldn't find that page for this number.")
    paging.on_acknowledge(page_id, number)
    return messages.text("Thanks, acknowledged.")


def set_readiness(staff: dict, case_id: str, item: str, value: bool) -> dict:
    """Record a readiness confirmation and show the updated readiness screen."""
    case = _owned(staff, case_id)
    if not case:
        return _not_found()
    readiness.record_confirmation(case_id, item, bool(value))
    return readiness_view(staff, case_id)


def send_case_brief_pdf(staff: dict, case_id: str, to_number: str) -> dict:
    """Build the case brief PDF and send it as a WhatsApp document."""
    case = _owned(staff, case_id)
    if not case:
        return _not_found()
    team = [m for m in (db.get_staff(s) for s in case.get("team", [])) if m]
    patient = db.get_patient(case.get("patientId")) if case.get("patientId") else {}
    # Score the readiness through the spine so the brief agrees with the board.
    case_for_pdf = {**case, "readiness": engine.readiness(db.get_readiness(case_id))}
    pdf = documents.case_brief_pdf(case_for_pdf, team, patient or {})

    filename = f"case-brief-{case_id[:8]}.pdf"
    cds.send_whatsapp_document(to_number, pdf, filename,
                               caption=f"Case brief: {case.get('procedure', 'case')}")
    if cds.live():
        return messages.text(f"Sent the case brief for {case.get('procedure', 'this case')}.")
    return messages.text(
        f"Prepared the case brief for {case.get('procedure', 'this case')} (dry run, not sent).")


def start_tray_check(staff: dict, case_id: str, phase: str) -> dict:
    """Prompt for a tray photo. The router sets the awaiting_tray context on this reply."""
    case = _owned(staff, case_id)
    if not case:
        return _not_found()
    which = phase if phase in _OTHER_PHASE else "before"
    return messages.text(
        f"Send a photo of the tray now for the {which} count. {_SECOND_COUNT}")


def ingest_tray_photo(case_id: str, phase: str, media: dict) -> dict:
    """Catalogue an inbound tray photo, store it, and compare before/after as a second
    count. A discrepancy escalates to the surgeon with an audit record.

    Called from the webhook once a tray photo lands, so there is no staff context here;
    the case was already resolved from the sender. No login/money is rendered."""
    # The webhook hands the media over as "media_id"; the in-app/test paths use "id"/
    # "mediaId". Accept all three so the photo is actually fetched on every path.
    media_id = media.get("media_id") or media.get("id") or media.get("mediaId")
    mime = media.get("mime") or media.get("mimeType") or "image/jpeg"
    bucket = media.get("bucket") or os.environ.get("MEDIA_BUCKET", "")
    key = media.get("key") or f"inbound/trays/{case_id}/{phase}/{media_id or 'photo'}"

    cds.fetch_whatsapp_media(media_id, bucket, key)
    image = cds.read_s3(bucket, key)
    catalogue = vision.catalogue_tray(image, mime)

    # A second count stays silent on a failed read. An empty catalogue means "could not
    # read the photo", not "zero instruments" - storing {} as a real count would make the
    # other phase diff every item as unaccounted-for (a false escalation), or, if both
    # photos fail, report a false all-clear. So never store an empty catalogue; re-prompt.
    if not catalogue.get("items"):
        note = catalogue.get("notes") or "I couldn't read the tray clearly"
        return messages.text(
            f"I couldn't read the {phase} tray photo clearly ({note}). "
            f"Please send a clearer, straight-on photo for the {phase} count. {_SECOND_COUNT}")

    db.set_tray_catalogue(case_id, phase, catalogue["items"], media.get("key") or key)

    counted = sum(catalogue["items"].values())
    tray = db.get_tray(case_id) or {}
    before = (tray.get("before") or {}).get("catalogue")
    after = (tray.get("after") or {}).get("catalogue")

    # Both phases must be present AND non-empty to run the second count.
    if not (isinstance(before, dict) and before and isinstance(after, dict) and after):
        other = _OTHER_PHASE.get(phase, "other")
        return messages.text(
            f"{phase.capitalize()} tray recorded, {counted} instruments counted. "
            f"Send the {other} photo when you are ready. {_SECOND_COUNT}")

    diff = engine.instrument_diff(before, after)
    if diff["ok"]:
        return messages.text(
            f"Tray read. {counted} instruments after the case, matching the before count. "
            f"No discrepancy. {_SECOND_COUNT}")

    # A discrepancy: record it, escalate to the surgeon, and file the audit PDF.
    flag_line = "; ".join(f["message"] for f in diff["flags"])
    db.add_event(case_id, "instrument_discrepancy", "system",
                 {"phase": phase, "flags": diff["flags"]})
    case = db.get_case(case_id) or {}
    pdf = documents.instrument_audit_pdf(case, before, after, diff)
    surgeon = db.get_staff(case.get("surgeonId")) if case.get("surgeonId") else None
    if surgeon and surgeon.get("whatsappNumber"):
        number = surgeon["whatsappNumber"]
        cds.send_whatsapp_text(
            number,
            f"Instrument second-count flag for {case.get('procedure', 'the case')}: {flag_line}. "
            f"Please complete the manual WHO count. {_SECOND_COUNT}")
        cds.send_whatsapp_document(number, pdf, f"instrument-audit-{case_id[:8]}.pdf",
                                   caption="Instrument second-count audit")
    return messages.text(
        f"Tray read. DISCREPANCY: {flag_line}. Escalated to the surgeon with an audit record. "
        f"{_SECOND_COUNT} Please complete the manual count.")


def send_missed_form(staff: dict, case_id: str, target_staff_id: str) -> dict:
    """Send a team member who missed a page a form to fill in and upload back."""
    case = _owned(staff, case_id)
    if not case:
        return _not_found()
    target = db.get_staff(target_staff_id)
    if not target or target.get("hospitalId") != staff.get("hospitalId"):
        return messages.text("That team member was not found at your hospital.")

    pdf = documents.missed_form_pdf(case, target, "page_missed")
    db.create_form(case_id, target_staff_id, "page_missed")
    number = target.get("whatsappNumber", "")
    cds.send_whatsapp_document(number, pdf, f"follow-up-{case_id[:8]}.pdf",
                               caption="Please complete and send this back")
    if cds.live():
        return messages.text(f"Sent a follow-up form to {target.get('name', 'the team member')}.")
    return messages.text(
        f"Prepared a follow-up form for {target.get('name', 'the team member')} (dry run, not sent).")
