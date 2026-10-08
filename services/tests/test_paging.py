"""The page ladder (services.paging).

Every CDS send is monkeypatched to capture its call, so nothing touches AWS. The moto
tables from conftest hold the real per-recipient page records, and we assert the ladder
against them: a row per team member, the Acknowledge button id, the urgent audio note,
the acknowledgement flip, and that escalation reaches only the people who never acked.
"""
import pytest

from common import cds, db
from services import paging

BODY = "Theatre 2, 14:00 — Laparoscopic cholecystectomy. Please acknowledge."


@pytest.fixture
def sends(monkeypatch):
    """Capture the CDS sends; return dry wamids. No live AWS."""
    calls = {"raw": [], "audio": [], "voice": [], "synth": []}

    def fake_raw(to, message):
        wamid = f"wamid-{len(calls['raw'])}"
        calls["raw"].append({"to": to, "message": message, "wamid": wamid})
        return wamid

    def fake_audio(to, data, caption=None, bucket=None):
        calls["audio"].append({"to": to, "data": data})
        return f"audio-{len(calls['audio'])}"

    def fake_voice(to, text, voice_id=None):
        calls["voice"].append({"to": to, "text": text})
        return "no-voice-number"

    def fake_synth(text, voice_id=None):
        calls["synth"].append(text)
        return b"MP3:" + text.encode()

    monkeypatch.setattr(cds, "send_whatsapp_raw", fake_raw)
    monkeypatch.setattr(cds, "send_whatsapp_audio", fake_audio)
    monkeypatch.setattr(cds, "send_voice", fake_voice)
    monkeypatch.setattr(cds, "synth_mp3", fake_synth)
    return calls


@pytest.fixture
def scrub_nurse():
    return db.create_staff({"name": "Grace Hopper", "role": "scrub_nurse",
                            "email": "grace@hospital.test", "whatsappNumber": "+233200000002",
                            "hospitalId": "hosp-1"})


@pytest.fixture
def team_case(case, staff, scrub_nurse):
    """The seeded case with a two-person roster: the surgeon plus a scrub nurse."""
    db.update_case(case["caseId"], {"team": [staff["staffId"], scrub_nurse["staffId"]]})
    return db.get_case(case["caseId"])


def _ack_id(message: dict) -> str:
    return message["interactive"]["action"]["buttons"][0]["reply"]["id"]


# ── fan-out ───────────────────────────────────────────────────────────────────
def test_one_recipient_row_per_team_member(sends, team_case, staff, scrub_nurse):
    page = paging.send_page(team_case["caseId"], "coord-1", BODY)

    recips = db.list_page_recipients(page["pageId"])
    assert {r["staffId"] for r in recips} == {staff["staffId"], scrub_nurse["staffId"]}
    assert all(r["status"] == "sent" for r in recips)
    assert all(r.get("sentAt") for r in recips)
    assert len(sends["raw"]) == 2
    assert {c["to"] for c in sends["raw"]} == {staff["whatsappNumber"], scrub_nurse["whatsappNumber"]}


def test_acknowledge_button_id_is_ack_page_id(sends, team_case):
    page = paging.send_page(team_case["caseId"], "coord-1", BODY)

    expected = f"ack:{page['pageId']}"
    for call in sends["raw"]:
        assert _ack_id(call["message"]) == expected
        assert call["message"]["interactive"]["action"]["buttons"][0]["reply"]["title"] == "Acknowledge"


def test_page_body_logged_to_each_conversation(sends, team_case, staff):
    page = paging.send_page(team_case["caseId"], "coord-1", BODY)

    msgs = db.list_messages(staff["whatsappNumber"])
    out = [m for m in msgs if m.get("pageId") == page["pageId"]]
    assert len(out) == 1
    assert out[0]["direction"] == "out" and out[0]["body"] == BODY
    assert out[0]["caseId"] == team_case["caseId"]


# ── urgency ───────────────────────────────────────────────────────────────────
def test_urgent_also_sends_an_audio_note(sends, team_case):
    paging.send_page(team_case["caseId"], "coord-1", BODY, urgent=True)

    assert len(sends["audio"]) == 2            # one spoken note per recipient
    assert sends["synth"] == [BODY, BODY]      # synthesised from the page body


def test_non_urgent_sends_no_audio(sends, team_case):
    paging.send_page(team_case["caseId"], "coord-1", BODY, urgent=False)

    assert sends["audio"] == []
    assert sends["synth"] == []


# ── acknowledgement ───────────────────────────────────────────────────────────
def test_on_acknowledge_flips_status(sends, team_case, staff):
    page = paging.send_page(team_case["caseId"], "coord-1", BODY)

    rec = paging.on_acknowledge(page["pageId"], staff["whatsappNumber"])
    assert rec["status"] == "acknowledged" and rec.get("acknowledgedAt")

    recips = {r["staffId"]: r for r in db.list_page_recipients(page["pageId"])}
    assert recips[staff["staffId"]]["status"] == "acknowledged"
    # The other member is untouched.
    others = [r for sid, r in recips.items() if sid != staff["staffId"]]
    assert all(r["status"] == "sent" for r in others)


# ── escalation ───────────────────────────────────────────────────────────────
def test_escalation_reaches_only_the_unacknowledged(sends, team_case, staff, scrub_nurse):
    page = paging.send_page(team_case["caseId"], "coord-1", BODY)
    paging.on_acknowledge(page["pageId"], staff["whatsappNumber"])   # surgeon acks

    sends["audio"].clear()
    sends["synth"].clear()
    summary = paging.escalate_unacknowledged(page["pageId"])

    assert summary["escalatedCount"] == 1
    # audio note AND voice call, to the scrub nurse only.
    assert [c["to"] for c in sends["audio"]] == [scrub_nurse["whatsappNumber"]]
    assert [c["to"] for c in sends["voice"]] == [scrub_nurse["whatsappNumber"]]
    assert sends["synth"] == ["Urgent: " + BODY]
    assert sends["voice"][0]["text"] == "Urgent: " + BODY
    # No voice number is provisioned on this build, which is reported, not fatal.
    assert summary["escalated"][0]["voiceProvisioned"] is False


def test_escalation_of_fully_acknowledged_page_is_a_no_op(sends, team_case, staff, scrub_nurse):
    page = paging.send_page(team_case["caseId"], "coord-1", BODY)
    paging.on_acknowledge(page["pageId"], staff["whatsappNumber"])
    paging.on_acknowledge(page["pageId"], scrub_nurse["whatsappNumber"])

    sends["audio"].clear()
    summary = paging.escalate_unacknowledged(page["pageId"])
    assert summary["escalatedCount"] == 0
    assert sends["audio"] == [] and sends["voice"] == []


def test_escalation_marks_the_ladder_state(sends, team_case, staff, scrub_nurse):
    page = paging.send_page(team_case["caseId"], "coord-1", BODY)
    paging.on_acknowledge(page["pageId"], staff["whatsappNumber"])
    paging.escalate_unacknowledged(page["pageId"])

    recips = {r["staffId"]: r for r in db.list_page_recipients(page["pageId"])}
    assert recips[scrub_nurse["staffId"]]["status"] == "escalated"
    assert recips[scrub_nurse["staffId"]].get("escalatedAt")


# ── edge cases ───────────────────────────────────────────────────────────────
def test_empty_team_pages_nobody(sends, case):
    db.update_case(case["caseId"], {"team": []})
    page = paging.send_page(case["caseId"], "coord-1", BODY)

    assert page["recipients"] == []
    assert db.list_page_recipients(page["pageId"]) == []
    assert sends["raw"] == []


def test_member_without_a_whatsapp_number_is_skipped(sends, case, staff):
    no_number = db.create_staff({"name": "Alan Turing", "role": "anaesthetist",
                                 "email": "alan@hospital.test", "hospitalId": "hosp-1"})
    db.update_case(case["caseId"], {"team": [staff["staffId"], no_number["staffId"]]})
    page = paging.send_page(case["caseId"], "coord-1", BODY)

    recips = db.list_page_recipients(page["pageId"])
    assert [r["staffId"] for r in recips] == [staff["staffId"]]
    assert len(sends["raw"]) == 1
    # The skip is on the audit timeline.
    skips = [e for e in db.list_events(case["caseId"]) if e["type"] == "page_recipient_skipped"]
    assert len(skips) == 1 and skips[0]["detail"]["staffId"] == no_number["staffId"]


def test_send_page_unknown_case_raises(sends):
    with pytest.raises(ValueError):
        paging.send_page("no-such-case", "coord-1", BODY)


# ── status view ───────────────────────────────────────────────────────────────
def test_page_status_is_a_flat_per_recipient_list(sends, team_case, staff, scrub_nurse):
    page = paging.send_page(team_case["caseId"], "coord-1", BODY)
    paging.on_acknowledge(page["pageId"], staff["whatsappNumber"])

    status = paging.page_status(team_case["caseId"])
    assert len(status) == 2
    assert all(row["pageId"] == page["pageId"] for row in status)
    assert all(row["caseId"] == team_case["caseId"] for row in status)
    by_staff = {row["staffId"]: row for row in status}
    assert by_staff[staff["staffId"]]["status"] == "acknowledged"
    assert by_staff[staff["staffId"]]["acknowledgedAt"]
    assert by_staff[scrub_nurse["staffId"]]["status"] == "sent"
    assert {"number", "sentAt", "readAt", "deliveredAt", "escalatedAt"} <= set(status[0])


def test_page_status_spans_multiple_pages(sends, team_case):
    p1 = paging.send_page(team_case["caseId"], "coord-1", "First page")
    p2 = paging.send_page(team_case["caseId"], "coord-1", "Second page")

    status = paging.page_status(team_case["caseId"])
    assert {row["pageId"] for row in status} == {p1["pageId"], p2["pageId"]}
    assert len(status) == 4            # two members on each of two pages
