"""The webhook: route inbound WhatsApp to the patient flow or the staff app, and record
delivery/read on the page ladder."""
import json

import pytest

from agent import classify
from common import cds, db
import webhook


@pytest.fixture(autouse=True)
def no_live_sends(monkeypatch):
    monkeypatch.setattr(cds, "send_whatsapp_text", lambda to, body, **k: "wamid")
    monkeypatch.setattr(cds, "send_whatsapp_raw", lambda to, msg, **k: "wamid")
    monkeypatch.setattr(cds, "send_whatsapp_audio", lambda *a, **k: "wamid")
    monkeypatch.setattr(cds, "send_voice", lambda *a, **k: "voice")
    monkeypatch.setattr(cds, "synth_mp3", lambda *a, **k: b"mp3")


def _sns(message):
    entry = {"changes": [{"value": {"messages": [message]}}]}
    outer = {"messageId": "aws-" + message.get("id", "x"), "whatsAppWebhookEntry": json.dumps(entry)}
    return {"Records": [{"Sns": {"Message": json.dumps(outer)}}]}


def _status(wamid, status, to):
    entry = {"changes": [{"value": {"statuses": [{"id": wamid, "status": status,
                                                  "recipient_id": to, "timestamp": "1760000001"}]}}]}
    outer = {"messageId": "aws-s", "whatsAppWebhookEntry": json.dumps(entry)}
    return {"Records": [{"Sns": {"Message": json.dumps(outer)}}]}


def _text(wamid, frm, body):
    return _sns({"from": frm, "id": wamid, "type": "text", "text": {"body": body}, "timestamp": "1760000000"})


def test_patient_reply_goes_to_the_patient_flow(monkeypatch):
    db.create_patient({"name": "Pat", "whatsappNumber": "+233200000009", "hospitalId": "hosp-1"})
    monkeypatch.setattr(classify, "classify_reply",
                        lambda text, context=None: {"intent": "confirm", "dangerSigns": [],
                                                    "escalate": False, "confidence": 0.9})
    [r] = webhook.handler(_text("w1", "233200000009", "all good thanks"))["results"]
    assert r["role"] == "patient"


def test_unknown_number_enters_the_staff_app():
    [r] = webhook.handler(_text("w2", "233999999999", "hi"))["results"]
    assert r["role"] == "staff" and r["replies"] >= 1   # welcome + Log in


def test_duplicate_delivery_is_ignored():
    ev = _text("w3", "233999999999", "hi")
    webhook.handler(ev)
    [again] = webhook.handler(ev)["results"]
    assert again.get("skipped") == "duplicate"


def test_status_event_is_recorded_without_error():
    [r] = webhook.handler(_status("wamid.X", "delivered", "233999999999"))["results"]
    assert r["status"] == "delivered"
