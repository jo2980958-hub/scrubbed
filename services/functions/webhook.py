"""SNS-triggered WhatsApp inbound handler.

The event is triple wrapped (SNS record -> AWS header -> Meta webhook entry string).
Routing:
  - a known patient number  -> the readiness / post-op follow-up flow
  - everyone else           -> the staff app (login, then menu navigation)
  - delivery status events  -> update the message and the page ladder (read/ack times)
"""
from __future__ import annotations

import json
import logging
import os

from common import cds, db
from services import readiness
from wa import inbound as wa_inbound
from wa import router as wa_router

log = logging.getLogger()
log.setLevel(logging.INFO)

MEDIA_BUCKET = os.environ.get("MEDIA_BUCKET", "")


def parse_sns_event(event):
    """Yield one normalised item per inbound message/status. Every layer is guarded: a
    single malformed record or message is logged and skipped, so one bad payload cannot
    drop the rest of the batch (and with it a real danger-sign reply arriving alongside)."""
    for rec in event.get("Records", []):
        try:
            outer = json.loads(rec["Sns"]["Message"])
            entry = outer.get("whatsAppWebhookEntry")
            entry = json.loads(entry) if isinstance(entry, str) else entry
        except (KeyError, TypeError, ValueError):
            log.warning("skipping unparseable SNS record")
            continue
        for ch in (entry or {}).get("changes", []):
            v = ch.get("value", {}) or {}
            for m in v.get("messages", []) or []:
                try:
                    kind = m.get("type")
                    media = m.get(kind) if kind in ("image", "document", "audio") else None
                    yield {"kind": "message", "from": m["from"], "wamid": m["id"], "type": kind,
                           "text": (m.get("text") or {}).get("body") or (media or {}).get("caption"),
                           "media_id": (media or {}).get("id"), "mime": (media or {}).get("mime_type"),
                           "interactive": wa_inbound.extract_interactive(m),
                           "ts": int(m["timestamp"]), "aws_message_id": outer.get("messageId")}
                except (KeyError, TypeError, ValueError):
                    log.warning("skipping malformed inbound message")
                    continue
            for s in v.get("statuses", []) or []:
                try:
                    yield {"kind": "status", "wamid": s["id"], "status": s["status"],
                           "to": s.get("recipient_id"), "ts": int(s["timestamp"])}
                except (KeyError, TypeError, ValueError):
                    log.warning("skipping malformed status")
                    continue


def _send(to: str, replies) -> list:
    """Send each Reply (a Meta message dict from wa.messages) to the number."""
    ids = []
    for r in replies or []:
        if r.get("type") == "text":
            ids.append(cds.send_whatsapp_text(to, r["text"]["body"]))
        else:
            ids.append(cds.send_whatsapp_raw(to, r))
    return ids


def handle_message(m: dict) -> dict:
    if not db.claim_message(m["wamid"]):
        return {"wamid": m["wamid"], "skipped": "duplicate"}
    number = db.normalise_e164(m["from"])
    inter = m.get("interactive") or {}
    inbound = {"text": m.get("text"), "tap_id": inter.get("id"), "tap_title": inter.get("title"),
               "media": None}
    if m.get("type") in ("image", "document") and m.get("media_id"):
        inbound["media"] = {"media_id": m["media_id"], "mime": m.get("mime"),
                            "bucket": MEDIA_BUCKET, "key": f"inbound/{number}/{m['media_id']}"}

    patient = db.get_patient_by_whatsapp(number)
    if patient and not inbound["tap_id"]:
        replies = readiness.handle_patient_reply(number, m.get("text") or "")
        ids = _send(m["from"], replies)
        return {"wamid": m["wamid"], "role": "patient", "replies": len(replies or []), "ids": ids}

    replies = wa_router.handle(number, inbound)        # staff app (login + navigation)
    ids = _send(m["from"], replies)
    return {"wamid": m["wamid"], "role": "staff", "replies": len(replies or []), "ids": ids}


def handle_status(s: dict) -> dict:
    """Record delivery/read on the message and, when the message was a page, on the
    page ladder so the dashboard shows who saw it and when."""
    msg = db.record_delivery(s["wamid"], s["status"])
    if msg and msg.get("pageId") and s.get("to"):
        try:
            db.record_page_status(msg["pageId"], db.normalise_e164(s["to"]), s["status"])
        except Exception:
            log.exception("page status update failed")
    return {"wamid": s["wamid"], "status": s["status"]}


def handler(event, context=None):
    results = []
    for item in parse_sns_event(event):
        try:
            results.append(handle_message(item) if item["kind"] == "message" else handle_status(item))
        except Exception:
            log.exception("failed handling %s", item.get("wamid"))
            results.append({"wamid": item.get("wamid"), "error": True})
    log.info("webhook results: %s", json.dumps(results))
    return {"results": results}
