"""The scheduler tick: page escalation, the not-ready sweep, and due follow-ups."""
from datetime import datetime, timedelta, timezone

import pytest

from common import cds, config, db
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


def test_fresh_page_is_not_escalated_before_the_real_deadline(no_live_sends):
    # The real 30-min horizon, not monkeypatched to 0: a page created just now is inside
    # its acknowledgement window, so the deadline check must leave it alone.
    case, s1, s2, _ = _case_with_team()
    paging.send_page(case["caseId"], s1["staffId"], "Please confirm.")
    result = scheduler.handler({})
    assert result["escalatedPages"] == 0
    assert no_live_sends["voice"] == [] and no_live_sends["audio"] == []


def test_page_escalates_once_past_the_real_deadline(no_live_sends):
    # Backdate the page's createdAt beyond the real horizon (threshold untouched), so the
    # deadline maths itself is what decides to escalate.
    case, s1, s2, _ = _case_with_team()
    page = paging.send_page(case["caseId"], s1["staffId"], "Please confirm.")
    old = datetime.now(timezone.utc) - timedelta(seconds=safety.page_escalate_seconds() + 60)
    db._update(config.TBL_PAGES, {"pageId": page["pageId"], "sk": "meta"},
               {"createdAt": old.isoformat(timespec="microseconds").replace("+00:00", "Z")})
    result = scheduler.handler({})
    assert result["escalatedPages"] == 1
    # Nobody acknowledged, so both roster members were escalated.
    assert set(no_live_sends["voice"]) == {s1["whatsappNumber"], s2["whatsappNumber"]}
    assert scheduler.handler({})["escalatedPages"] == 0        # escalationDone, no repeat


def test_worklist_is_emailed_to_coordinators_for_at_risk_cases(no_live_sends):
    case, s1, s2, _ = _case_with_team(hours_from_now=4)        # required items outstanding, 4h out
    db.create_staff({"name": "Coord", "role": "coordinator", "email": "coord@h.test",
                     "hospitalId": "hosp-1"})
    result = scheduler.handler({})
    assert result["atRiskCases"] >= 1
    assert result["worklistsEmailed"] >= 1                     # SES worklist actually sent


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
