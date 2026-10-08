"""The page ladder.

Fan a page out to a case's roster, write a per-recipient page record (sent/delivered/
read/acknowledged), handle the Acknowledge tap, and arm/cancel the escalation. The 30-min
timer itself is an EventBridge schedule the lead wires; escalate_unacknowledged is what it
calls. Depends on common.db, common.cds, safety.engine, common.config. Contract fixed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from common import cds, config, db
from safety import engine as safety
from wa import messages as wa_messages


def _escalate_at() -> str:
    """When this page becomes due for a voice escalation. ISO-8601, same shape as
    db.now_iso so the two read the same on the dashboard."""
    due = datetime.now(timezone.utc) + timedelta(seconds=safety.page_escalate_seconds())
    return due.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _page_meta(page_id: str) -> dict | None:
    """Read the page's 'meta' row (body, caseId, urgent). The db exposes no get_page by
    id, so we read the meta row directly; see the contract note in the module report."""
    row = db.table(config.TBL_PAGES).get_item(Key={"pageId": page_id, "sk": "meta"})
    return row.get("Item")


def send_page(case_id: str, created_by: str, body: str, urgent: bool = False) -> dict:
    """Send the page to every roster member, record per-recipient status, arm the
    escalation. Returns the page record."""
    case = db.get_case(case_id)
    if not case:
        raise ValueError(f"send_page: case {case_id} not found")

    page = db.create_page(case_id, created_by, body, urgent)
    page_id = page["pageId"]
    ack_button = [(f"ack:{page_id}", "Acknowledge")]

    recipients: list[dict] = []
    for staff_id in case.get("team") or []:
        staff = db.get_staff(staff_id)
        number = staff.get("whatsappNumber") if staff else None
        if not number:
            # A roster member with no linked WhatsApp number cannot be paged. Note it on
            # the case timeline rather than drop it silently; the coordinator can chase.
            db.add_event(case_id, "page_recipient_skipped", actor=created_by,
                         detail={"pageId": page_id, "staffId": staff_id,
                                 "reason": "missing staff" if not staff else "no WhatsApp number"})
            continue

        db.add_page_recipient(page_id, staff_id, number)
        message = wa_messages.buttons(body, ack_button)
        wamid = cds.send_whatsapp_raw(number, message)
        db.record_page_status(page_id, number, "sent")
        db.add_message(number, "out", wamid, body, caseId=case_id, pageId=page_id)
        if urgent:
            cds.send_whatsapp_audio(number, cds.synth_mp3(body))
        recipients.append({"staffId": staff_id, "number": number, "wamid": wamid})

    escalate_at = _escalate_at()
    db.add_event(case_id, "page_sent", actor=created_by,
                 detail={"pageId": page_id, "urgent": bool(urgent),
                         "recipientCount": len(recipients), "escalateAt": escalate_at})

    # The db has no accessor to stamp escalateAt onto the meta row, so it rides on the
    # returned record and the audit event; see the contract note in the module report.
    page["escalateAt"] = escalate_at
    page["recipients"] = recipients
    return page


def on_acknowledge(page_id: str, number: str) -> dict:
    """Mark a recipient acknowledged; cancel their escalation. Returns the acknowledged
    recipient record."""
    recipient = db.acknowledge_page(page_id, number)
    meta = _page_meta(page_id)
    if meta and meta.get("caseId"):
        db.add_event(meta["caseId"], "page_acknowledged",
                     actor=recipient.get("staffId", "system"),
                     detail={"pageId": page_id, "staffId": recipient.get("staffId"),
                             "number": recipient.get("number")})
    return recipient


def escalate_unacknowledged(page_id: str) -> dict:
    """Called after PAGE_ACK_ESCALATE_SECONDS: for anyone not acknowledged, send a
    WhatsApp voice note (and a voice call when a number is provisioned)."""
    meta = _page_meta(page_id)
    if not meta:
        return {"pageId": page_id, "escalatedCount": 0, "escalated": [],
                "note": "page not found"}

    case_id = meta.get("caseId")
    spoken = "Urgent: " + str(meta.get("body") or "")

    escalated: list[dict] = []
    for recipient in db.pending_page_recipients(page_id):
        number = recipient.get("number")
        if not number:
            continue
        audio_id = cds.send_whatsapp_audio(number, cds.synth_mp3(spoken))
        voice_id = cds.send_voice(number, spoken)
        # Keep the ladder state on the row so the dashboard can show who was escalated;
        # the recipient is still unacknowledged, so they stay in the pending set.
        db.record_page_status(page_id, number, "escalated")
        if case_id:
            db.add_event(case_id, "page_escalated",
                         detail={"pageId": page_id, "staffId": recipient.get("staffId"),
                                 "number": number, "audioMessageId": audio_id,
                                 "voiceMessageId": voice_id})
        escalated.append({"staffId": recipient.get("staffId"), "number": number,
                          "audioMessageId": audio_id, "voiceMessageId": voice_id,
                          "voiceProvisioned": voice_id != "no-voice-number"})

    return {"pageId": page_id, "caseId": case_id,
            "escalatedCount": len(escalated), "escalated": escalated}


def page_status(case_id: str) -> list[dict]:
    """A flat row per recipient across all of a case's pages, for the views and the
    dashboard paging ladder. Each row carries the recipient's current status and every
    ladder timestamp the db has stamped."""
    rows: list[dict] = []
    for page in db.list_pages_for_case(case_id):
        page_id = page.get("pageId")
        for recipient in db.list_page_recipients(page_id):
            rows.append({
                "pageId": page_id,
                "caseId": case_id,
                "staffId": recipient.get("staffId"),
                "number": recipient.get("number"),
                "status": recipient.get("status"),
                "sentAt": recipient.get("sentAt"),
                "deliveredAt": recipient.get("deliveredAt"),
                "readAt": recipient.get("readAt"),
                "acknowledgedAt": recipient.get("acknowledgedAt"),
                "escalatedAt": recipient.get("escalatedAt"),
                "body": page.get("body"),
                "urgent": page.get("urgent"),
                "createdAt": page.get("createdAt"),
            })
    return rows
