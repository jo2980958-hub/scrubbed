"""Patient readiness, post-op follow-up and reply classification.

The readiness score and cancellation risk come from safety.engine; classification is a
forced Bedrock tool call, stubbed here. Every patient-facing message is logistics or an
acknowledgement: these tests pin that nothing diagnoses or reassures, and that a danger
sign escalates to the team.
"""
from datetime import datetime, timedelta, timezone

import pytest

from agent import classify, llm
from common import cds, db
from services import readiness


class FakeBedrock:
    """A fake bedrock-runtime client: returns queued tool inputs. Mirrors Arrearo's fake."""

    def __init__(self, tool_inputs=(), texts=()):
        self.tool_inputs, self.texts, self.calls = list(tool_inputs), list(texts), []

    def converse(self, **kw):
        self.calls.append(kw)
        if "toolConfig" in kw:
            name = kw["toolConfig"]["tools"][0]["toolSpec"]["name"]
            return {"output": {"message": {"content": [{"toolUse": {"name": name, "input": self.tool_inputs.pop(0)}}]}},
                    "stopReason": "tool_use"}
        return {"output": {"message": {"content": [{"text": self.texts.pop(0)}]}}, "stopReason": "end_turn"}


# Phrases that would mean we diagnosed or reassured. No patient-facing text may contain them.
_BANNED = ["you are fine", "you're fine", "don't worry", "do not worry", "nothing to worry",
           "it's normal", "it is normal", "that's normal", "that is normal", "you'll be fine",
           "you will be fine", "no cause for concern"]


def _assert_clean(body: str) -> None:
    low = body.lower()
    for phrase in _BANNED:
        assert phrase not in low, f"patient text reassured/diagnosed: {phrase!r} in {body!r}"


@pytest.fixture
def sends(monkeypatch):
    """Capture every WhatsApp text send instead of hitting AWS. Returns the list of
    (to, body) tuples, newest last."""
    captured = []

    def fake_send(to, body, reply_to_wamid=None):
        captured.append((to, body))
        return f"wamid-{len(captured)}"

    monkeypatch.setattr(cds, "send_whatsapp_text", fake_send)
    return captured


def _mk_case(staff, patient, hours_from_now, **extra):
    when = datetime.now(timezone.utc) + timedelta(hours=hours_from_now)
    data = {"hospitalId": "hosp-1", "surgeonId": staff["staffId"], "patientId": patient["patientId"],
            "procedure": "Laparoscopic cholecystectomy", "theatre": "Theatre 2",
            "scheduledAt": when.isoformat().replace("+00:00", "Z"), "team": [staff["staffId"]]}
    data.update(extra)
    return db.create_case(data)


# ── readiness scoring + cancellation risk ─────────────────────────────────────
def test_readiness_scoring_and_high_risk_when_balance_outstanding_near_surgery(staff, patient):
    case = _mk_case(staff, patient, hours_from_now=4)
    for item in ("consent", "fasting_confirmed", "team_confirmed"):
        db.set_readiness_item(case["caseId"], item, True)
    # Balance still outstanding, 4 hours out.
    r = readiness.case_readiness(case["caseId"])

    assert r["isReady"] is False
    assert "Balance cleared" in r["outstandingRequired"]
    assert r["risk"] == "high"
    assert r["score"] == round(3 / 6, 2)
    assert 3.5 < r["hoursToSurgery"] <= 4.0


def test_fully_confirmed_case_is_ready_and_low_risk(staff, patient):
    case = _mk_case(staff, patient, hours_from_now=4)
    for item in ("consent", "fasting_confirmed", "team_confirmed", "balance_cleared"):
        db.set_readiness_item(case["caseId"], item, True)

    r = readiness.case_readiness(case["caseId"])
    assert r["isReady"] is True
    assert r["outstandingRequired"] == []
    assert r["risk"] == "low"


def test_record_confirmation_updates_the_item_and_returns_the_view(staff, patient):
    case = _mk_case(staff, patient, hours_from_now=48)
    out = readiness.record_confirmation(case["caseId"], "consent", True)

    assert db.get_readiness(case["caseId"])["consent"] is True
    assert "Consent signed" not in out["outstandingRequired"]
    assert out["caseId"] == case["caseId"]


# ── pre-op instructions ───────────────────────────────────────────────────────
def test_send_preop_instructions_sets_the_readiness_item(staff, patient, sends):
    case = _mk_case(staff, patient, hours_from_now=24)
    result = readiness.send_preop_instructions(case["caseId"])

    assert db.get_readiness(case["caseId"])["instructions_sent"] is True
    assert result["item"] == "instructions_sent"
    assert result["to"] == patient["whatsappNumber"]
    # One message to the patient, plain logistics, nothing clinical/reassuring.
    assert len(sends) == 1
    to, body = sends[0]
    assert to == patient["whatsappNumber"]
    assert "midnight" in body.lower()
    assert "arrive" in body.lower()
    _assert_clean(body)
    # It is recorded on the timeline.
    types = [e["type"] for e in db.list_events(case["caseId"])]
    assert "preop_instructions_sent" in types


# ── the not-ready sweep ───────────────────────────────────────────────────────
def test_not_ready_sweep_returns_only_at_risk_upcoming_cases(staff, patient):
    at_risk = _mk_case(staff, patient, hours_from_now=4)       # balance outstanding -> high
    for item in ("consent", "fasting_confirmed", "team_confirmed"):
        db.set_readiness_item(at_risk["caseId"], item, True)

    ready = _mk_case(staff, patient, hours_from_now=4)          # fully confirmed -> low
    for item in ("consent", "fasting_confirmed", "team_confirmed", "balance_cleared"):
        db.set_readiness_item(ready["caseId"], item, True)

    past = _mk_case(staff, patient, hours_from_now=-4)          # already happened -> skipped

    rows = readiness.not_ready_sweep(hospital_id="hosp-1")
    ids = {row["caseId"] for row in rows}
    assert at_risk["caseId"] in ids
    assert ready["caseId"] not in ids
    assert past["caseId"] not in ids
    assert all(row["risk"] in ("medium", "high") for row in rows)


# ── post-op follow-up ─────────────────────────────────────────────────────────
def test_send_followup_asks_how_they_feel_and_lists_nothing_clinical(staff, patient, sends):
    case = _mk_case(staff, patient, hours_from_now=-6)
    result = readiness.send_followup(case["caseId"])

    assert result["to"] == patient["whatsappNumber"]
    assert len(sends) == 1
    _, body = sends[0]
    assert "how are you feeling" in body.lower()
    # No clinical list: none of the danger-sign phrasings appear in the check-in.
    from safety import engine
    for sign in engine.DANGER_SIGNS:
        assert sign not in body.lower()
    _assert_clean(body)
    assert "postop_followup_sent" in [e["type"] for e in db.list_events(case["caseId"])]


# ── classification ────────────────────────────────────────────────────────────
def test_classify_recognises_a_danger_sign_and_escalates():
    llm.set_client(FakeBedrock([{"intent": "reports_problem",
                                 "dangerSigns": ["heavy or increasing bleeding"],
                                 "confidence": 0.93}]))
    r = classify.classify_reply("my wound is bleeding a lot and getting worse")

    assert r["intent"] == "reports_problem"
    assert r["dangerSigns"] == ["heavy or increasing bleeding"]
    assert r["escalate"] is True
    assert r["confidence"] == 0.93


def test_classify_reports_problem_escalates_even_without_a_named_sign():
    llm.set_client(FakeBedrock([{"intent": "reports_problem", "dangerSigns": [], "confidence": 0.6}]))
    r = classify.classify_reply("something feels off at the incision")
    assert r["escalate"] is True


def test_classify_confirm_does_not_escalate():
    llm.set_client(FakeBedrock([{"intent": "confirm", "dangerSigns": [], "confidence": 0.9}]))
    r = classify.classify_reply("yes, all set for tomorrow, thank you")
    assert r["intent"] == "confirm"
    assert r["escalate"] is False


def test_classify_drops_invented_signs_and_clamps_confidence():
    llm.set_client(FakeBedrock([{"intent": "other",
                                 "dangerSigns": ["heavy or increasing bleeding", "feeling grumpy"],
                                 "confidence": 5}]))
    r = classify.classify_reply("hello")
    # Only the recognised phrasing survives; confidence is clamped into 0..1.
    assert r["dangerSigns"] == ["heavy or increasing bleeding"]
    assert r["confidence"] == 1.0
    assert r["escalate"] is True


def test_classify_fails_closed_on_a_bad_model_result():
    # Empty queue -> converse_tool raises. In a safety product we cannot tell a benign
    # reply from a danger sign when the model fails, so we FAIL CLOSED: escalate for a
    # human to read, and mark it a classifier error so the audit shows why.
    llm.set_client(FakeBedrock(tool_inputs=[]))
    r = classify.classify_reply("anything")
    assert r["escalate"] is True
    assert r["classifierError"] is True
    assert r["intent"] == "other" and r["dangerSigns"] == [] and r["confidence"] == 0.0


# ── handle_patient_reply ──────────────────────────────────────────────────────
def test_handle_patient_reply_escalates_and_never_diagnoses(staff, patient, sends):
    case = _mk_case(staff, patient, hours_from_now=-6)
    llm.set_client(FakeBedrock([{"intent": "reports_problem",
                                 "dangerSigns": ["fever or chills"],
                                 "confidence": 0.9}]))

    replies = readiness.handle_patient_reply(patient["whatsappNumber"], "I have a fever and chills")

    # The patient gets one acknowledgement that passes it on, never diagnoses or reassures.
    assert len(replies) == 1
    body = replies[0]["text"]["body"]
    assert "team" in body.lower()
    assert "emergency" in body.lower()
    _assert_clean(body)

    # The surgeon was paged with the sign named, and nothing else was sent to the patient.
    assert len(sends) == 1
    to, surgeon_body = sends[0]
    assert to == staff["whatsappNumber"]
    assert "fever or chills" in surgeon_body.lower()
    _assert_clean(surgeon_body)

    # It is on the timeline and the inbound reply is recorded.
    types = [e["type"] for e in db.list_events(case["caseId"])]
    assert "patient_reply" in types and "danger_sign_escalated" in types
    inbound = db.list_messages(patient["whatsappNumber"])
    assert any(m["direction"] == "in" and "fever" in (m.get("body") or "") for m in inbound)


def test_handle_patient_reply_without_escalation_just_acknowledges(staff, patient, sends):
    _mk_case(staff, patient, hours_from_now=24)
    llm.set_client(FakeBedrock([{"intent": "confirm", "dangerSigns": [], "confidence": 0.95}]))

    replies = readiness.handle_patient_reply(patient["whatsappNumber"], "yes all good, see you then")

    assert len(replies) == 1
    body = replies[0]["text"]["body"]
    assert "team" in body.lower()
    _assert_clean(body)
    # No escalation means nothing was sent to the surgeon.
    assert sends == []


def test_handle_patient_reply_for_unknown_number_stays_safe(sends):
    # No patient on file: still classify, still acknowledge safely, escalate nowhere.
    llm.set_client(FakeBedrock([{"intent": "reports_problem",
                                 "dangerSigns": ["severe or worsening pain"],
                                 "confidence": 0.8}]))
    replies = readiness.handle_patient_reply("+233299999999", "the pain is getting much worse")

    assert len(replies) == 1
    body = replies[0]["text"]["body"]
    assert "emergency" in body.lower()
    _assert_clean(body)
    # Nobody to page, so no outbound send.
    assert sends == []
