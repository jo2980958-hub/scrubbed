"""The scheduler tick: page escalation, the not-ready sweep, and due follow-ups."""
import pytest

from common import cds, db
from safety import engine as safety
from services import paging
import scheduler


@pytest.fixture(autouse=True)
def no_live_sends(monkeypatch):
    """Capture every outbound so nothing hits AWS, and make Polly a no-op."""
    sent = {"text": [], "audio": [], "voice": [], "email": []}
    monkeypatch.setattr(cds, "send_whatsapp_text", lambda to, body, **k: sent["text"].append((to, body)) or "wamid")
    monkeypatch.setattr(cds, "send_whatsapp_raw", lambda to, msg, **k: "wamid")
    monkeypatch.setattr(cds, "send_whatsapp_audio", lambda to, data, **k: sent["audio"].append(to) or "wamid")
    monkeypatch.setattr(cds, "send_voice", lambda to, text, **k: sent["voice"].append(to) or "voice-id")
    monkeypatch.setattr(cds, "send_email", lambda *a, **k: sent["email"].append(a) or "ses-id")
    monkeypatch.setattr(cds, "synth_mp3", lambda text, **k: b"mp3")
    return sent


def _case_with_team(hours_from_now=4):
    from datetime import datetime, timedelta, timezone
    s1 = db.create_staff({"name": "Dr A", "role": "surgeon", "email": "a@h.test",
                          "whatsappNumber": "+233200000001", "hospitalId": "hosp-1"})
    s2 = db.create_staff({"name": "Nurse B", "role": "scrub nurse", "email": "b@h.test",
                          "whatsappNumber": "+233200000002", "hospitalId": "hosp-1"})
    p = db.create_patient({"name": "Pat", "whatsappNumber": "+233200000009", "hospitalId": "hosp-1"})
    sched = (datetime.now(timezone.utc) + timedelta(hours=hours_from_now)).isoformat(
        timespec="seconds").replace("+00:00", "Z")
    case = db.create_case({"hospitalId": "hosp-1", "surgeonId": s1["staffId"], "patientId": p["patientId"],
                           "procedure": "Cholecystectomy", "theatre": "Theatre 2", "scheduledAt": sched,
                           "team": [s1["staffId"], s2["staffId"]]})
    return case, s1, s2, p


def test_overdue_page_escalates_to_unacknowledged_only(no_live_sends, monkeypatch):
    case, s1, s2, _ = _case_with_team()
    monkeypatch.setattr(safety, "page_escalate_seconds", lambda: 0)   # any page is immediately overdue
    page = paging.send_page(case["caseId"], s1["staffId"], "Please confirm for the 2pm.")
    paging.on_acknowledge(page["pageId"], s1["whatsappNumber"])       # surgeon acks; nurse does not

    result = scheduler.handler({})
    assert result["escalatedPages"] == 1
    # only the nurse (unacknowledged) was escalated, by audio note + voice
    assert no_live_sends["voice"] == ["+233200000002"]
    assert no_live_sends["audio"] == ["+233200000002"]
    # a second tick does not re-escalate (escalationDone)
    assert scheduler.handler({})["escalatedPages"] == 0


def test_not_ready_sweep_flags_at_risk_case(no_live_sends):
    case, *_ = _case_with_team(hours_from_now=4)
    db.set_readiness_item(case["caseId"], "balance_cleared", False)   # a required item outstanding, 4h out
    result = scheduler.handler({})
    assert result["atRiskCases"] >= 1


def test_due_followup_is_sent_once(no_live_sends):
    case, *_ = _case_with_team(hours_from_now=-2)   # already operated
    db.update_case(case["caseId"], {"followupDueAt": "2000-01-01T00:00:00Z"})
    result = scheduler.handler({})
    assert result["followupsSent"] == 1
    assert scheduler.handler({})["followupsSent"] == 0   # marked sent, not repeated
