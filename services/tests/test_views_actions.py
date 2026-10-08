"""The staff app read screens (wa.views) and write actions (wa.actions).

The views only render and the actions own the writes; the spine (safety.engine) owns the
readiness score, the risk band and the instrument-count diff. These tests stub the
parallel services (paging, readiness), the channel sends (common.cds) and Claude vision
(agent.vision), so what is asserted is this module's own behaviour.
"""
import pytest

from agent import vision
from common import cds, config, db, documents
from safety import engine
from services import paging, readiness
from wa import actions, views


# ── fixtures: a second surgeon, a nurse, a patient and a few cases ────────────
@pytest.fixture
def surgeon():
    return db.create_staff({"name": "Dr Ada Lovelace", "role": "surgeon",
                            "email": "ada@hospital.test", "whatsappNumber": "+233200000001",
                            "hospitalId": "hosp-1"})


@pytest.fixture
def nurse():
    return db.create_staff({"name": "Nurse Grace Hopper", "role": "scrub nurse",
                            "email": "grace@hospital.test", "whatsappNumber": "+233200000002",
                            "hospitalId": "hosp-1"})


@pytest.fixture
def other_surgeon():
    return db.create_staff({"name": "Dr Elsewhere", "role": "surgeon",
                            "email": "e@other.test", "whatsappNumber": "+233200000050",
                            "hospitalId": "hosp-2"})


@pytest.fixture
def pt():
    return db.create_patient({"name": "John Doe", "whatsappNumber": "+233200000009",
                              "hospitalId": "hosp-1", "balancePence": 0})


@pytest.fixture
def one_case(surgeon, nurse, pt):
    return db.create_case({"hospitalId": "hosp-1", "surgeonId": surgeon["staffId"],
                           "patientId": pt["patientId"], "procedure": "Laparoscopic cholecystectomy",
                           "theatre": "Theatre 2", "scheduledAt": "2026-10-09T14:00:00Z",
                           "team": [surgeon["staffId"], nurse["staffId"]]})


def _rows(reply):
    return reply["interactive"]["action"]["sections"][0]["rows"]


# ── my_list ───────────────────────────────────────────────────────────────────
def test_my_list_rows_and_ids_for_a_surgeon(surgeon, pt):
    db.create_case({"hospitalId": "hosp-1", "surgeonId": surgeon["staffId"],
                    "patientId": pt["patientId"], "procedure": "Hernia repair",
                    "theatre": "Theatre 1", "scheduledAt": "2026-10-09T09:00:00Z",
                    "team": [surgeon["staffId"]]})
    db.create_case({"hospitalId": "hosp-1", "surgeonId": surgeon["staffId"],
                    "patientId": pt["patientId"], "procedure": "Appendicectomy",
                    "theatre": "Theatre 3", "scheduledAt": "2026-10-09T11:30:00Z",
                    "team": [surgeon["staffId"]]})

    reply = views.my_list(surgeon, when="2026-10-09")
    rows = _rows(reply)
    assert len(rows) == 2
    # Sorted by time: the 09:00 case comes first.
    assert rows[0]["title"].startswith("09:00 Hernia repair")
    assert rows[1]["title"].startswith("11:30 Appendicectomy")
    assert all(r["id"].startswith("case:") for r in rows)
    assert "Theatre 1" in rows[0]["description"]


def test_my_list_empty_is_a_calm_text(surgeon):
    reply = views.my_list(surgeon, when="2026-10-09")
    assert reply["type"] == "text"
    assert "No cases" in reply["text"]["body"]


def test_my_list_for_non_surgeon_uses_the_hospital_board(nurse, one_case):
    reply = views.my_list(nurse, when="2026-10-09")
    rows = _rows(reply)
    assert any(r["id"] == f"case:{one_case['caseId']}" for r in rows)


# ── case_detail ────────────────────────────────────────────────────────────────
def test_case_detail_guard_blocks_another_hospital(other_surgeon, one_case):
    reply = views.case_detail(other_surgeon, one_case["caseId"])
    assert reply["type"] == "text"
    assert "not found" in reply["text"]["body"]


def test_case_detail_shows_the_four_action_rows(surgeon, one_case):
    cid = one_case["caseId"]
    reply = views.case_detail(surgeon, cid)
    ids = [r["id"] for r in _rows(reply)]
    assert ids == [f"check:{cid}:sign_in", f"page:{cid}", f"brief:{cid}", f"tray:{cid}:before"]
    body = reply["interactive"]["body"]["text"]
    assert "Laparoscopic cholecystectomy" in body
    assert "Theatre 2" in body
    # Both team members are named.
    assert "Ada Lovelace" in body and "Grace Hopper" in body


def test_case_detail_readiness_line_tracks_the_spine(surgeon, one_case):
    db.set_readiness_item(one_case["caseId"], "consent", True)
    reply = views.case_detail(surgeon, one_case["caseId"])
    body = reply["interactive"]["body"]["text"]
    assert "1 of 6 done" in body
    assert "Consent signed" not in body.split("Outstanding:")[0]  # consent no longer outstanding


# ── checklist_view ───────────────────────────────────────────────────────────
def test_checklist_view_renders_toggle_rows(surgeon, one_case):
    cid = one_case["caseId"]
    reply = views.checklist_view(surgeon, cid, "sign_in")
    rows = _rows(reply)
    assert len(rows) == len(engine.CHECKLIST["sign_in"])
    assert rows[0]["id"] == f"chk:{cid}:sign_in:0:1"
    assert rows[0]["description"] == engine.CHECKLIST["sign_in"][0]


def test_checklist_view_marks_a_ticked_item(surgeon, one_case):
    cid = one_case["caseId"]
    db.add_event(cid, "checklist", surgeon["staffId"],
                 {"phase": "sign_in", "index": 0, "value": True})
    rows = _rows(views.checklist_view(surgeon, cid, "sign_in"))
    # A ticked item flips to value 0 so the next tap un-ticks it.
    assert rows[0]["id"] == f"chk:{cid}:sign_in:0:0"
    assert rows[0]["title"].startswith("Done")


# ── readiness_view ───────────────────────────────────────────────────────────
def test_readiness_view_lists_items_with_risk(surgeon, one_case):
    db.set_readiness_item(one_case["caseId"], "consent", True)
    reply = views.readiness_view(surgeon, one_case["caseId"])
    rows = _rows(reply)
    assert len(rows) == len(engine.READINESS_ITEMS)
    consent_row = next(r for r in rows if r["id"].endswith(":consent:0"))
    assert consent_row["description"] == "Done"
    assert "Risk" in reply["interactive"]["body"]["text"]


# ── paging_status ────────────────────────────────────────────────────────────
def test_paging_status_renders_one_line_per_person(monkeypatch, surgeon, nurse, one_case):
    def fake_status(case_id):
        return [
            {"staffId": surgeon["staffId"], "status": "acknowledged", "acknowledgedAt": "t"},
            {"staffId": nurse["staffId"], "status": "sent"},
        ]
    monkeypatch.setattr(paging, "page_status", fake_status)
    reply = views.paging_status(surgeon, one_case["caseId"])
    body = reply["text"]["body"]
    assert "Ada Lovelace: acknowledged" in body
    assert "Grace Hopper: sent" in body


# ── run_checklist_item ───────────────────────────────────────────────────────
def test_run_checklist_item_logs_and_offers_the_next(surgeon, one_case):
    cid = one_case["caseId"]
    reply = actions.run_checklist_item(surgeon, cid, "sign_in", 0, True)
    events = [e for e in db.list_events(cid) if e.get("type") == "checklist"]
    assert events and events[0]["detail"]["value"] is True
    btns = reply["interactive"]["action"]["buttons"]
    # The first button ticks the next item (index 1).
    assert btns[0]["reply"]["id"] == f"chk:{cid}:sign_in:1:1"


def test_run_checklist_item_guard(other_surgeon, one_case):
    reply = actions.run_checklist_item(other_surgeon, one_case["caseId"], "sign_in", 0, True)
    assert reply["type"] == "text" and "not found" in reply["text"]["body"]


# ── page_team / acknowledge ──────────────────────────────────────────────────
def test_page_team_calls_the_service(monkeypatch, surgeon, one_case):
    calls = []

    def fake_send(case_id, created_by, body, urgent):
        calls.append((case_id, created_by, body, urgent))
        return {"pageId": "p1", "recipients": [{"staffId": "a"}, {"staffId": "b"}]}
    monkeypatch.setattr(paging, "send_page", fake_send)

    reply = actions.page_team(surgeon, one_case["caseId"], urgent=True)
    assert calls == [(one_case["caseId"], surgeon["staffId"], "Please confirm for the case.", True)]
    assert reply[0]["type"] == "text"
    assert "2 team members" in reply[0]["text"]["body"]
    assert "urgent" in reply[0]["text"]["body"].lower()


def test_page_team_guard(other_surgeon, one_case):
    reply = actions.page_team(other_surgeon, one_case["caseId"])
    assert isinstance(reply, list) and "not found" in reply[0]["text"]["body"]


def test_acknowledge_requires_being_a_recipient(monkeypatch, surgeon, one_case):
    calls = []
    monkeypatch.setattr(paging, "on_acknowledge", lambda pid, num: calls.append((pid, num)))

    # A page the surgeon was actually sent: a real recipient row exists.
    page = db.create_page(one_case["caseId"], surgeon["staffId"], "Confirm please")
    db.add_page_recipient(page["pageId"], surgeon["staffId"], surgeon["whatsappNumber"])
    reply = actions.acknowledge(surgeon, page["pageId"])
    assert calls == [(page["pageId"], surgeon["whatsappNumber"])]
    assert reply["text"]["body"] == "Thanks, acknowledged."

    # A page the surgeon is not a recipient of (stray or foreign pageId) is refused with no
    # write to the ladder - the old pass-through would have injected a recipient row.
    calls.clear()
    reply = actions.acknowledge(surgeon, "page-not-mine")
    assert calls == []
    assert "couldn't find that page" in reply["text"]["body"].lower()


# ── set_readiness ────────────────────────────────────────────────────────────
def test_set_readiness_records_and_returns_the_view(monkeypatch, surgeon, one_case):
    def fake_record(case_id, item, value):
        return db.set_readiness_item(case_id, item, value)
    monkeypatch.setattr(readiness, "record_confirmation", fake_record)

    reply = actions.set_readiness(surgeon, one_case["caseId"], "consent", True)
    rows = _rows(reply)
    consent_row = next(r for r in rows if "consent" in r["id"])
    assert consent_row["description"] == "Done"


# ── send_case_brief_pdf ──────────────────────────────────────────────────────
def test_send_case_brief_pdf_builds_the_document_and_sends(monkeypatch, surgeon, one_case):
    sent = []
    seen = {}

    real_brief = documents.case_brief_pdf

    def spy_brief(case, team, patient):
        seen["team"] = team
        seen["patient"] = patient
        return real_brief(case, team, patient)
    monkeypatch.setattr(documents, "case_brief_pdf", spy_brief)

    def fake_doc(to, data, filename, caption=None, bucket=None):
        sent.append((to, filename, data[:4]))
        return "dry-run-x"
    monkeypatch.setattr(cds, "send_whatsapp_document", fake_doc)

    reply = actions.send_case_brief_pdf(surgeon, one_case["caseId"], "+233200000077")
    assert len(sent) == 1
    to, filename, head = sent[0]
    assert to == "+233200000077"
    assert filename == f"case-brief-{one_case['caseId'][:8]}.pdf"
    assert head == b"%PDF"
    # The team was resolved to staff records, not left as ids.
    assert any(m.get("name") == "Dr Ada Lovelace" for m in seen["team"])
    assert "dry run" in reply["text"]["body"]


# ── ingest_tray_photo: the instrument second count ───────────────────────────
class _Vision:
    """A fake agent.vision.catalogue_tray that returns queued catalogues in order."""

    def __init__(self, *catalogues):
        self.queue = list(catalogues)

    def __call__(self, image, mime):
        items = self.queue.pop(0)
        return {"items": dict(items), "confidence": {}, "notes": ""}


def _stub_media(monkeypatch, cat_vision):
    monkeypatch.setattr(vision, "catalogue_tray", cat_vision)
    monkeypatch.setattr(cds, "fetch_whatsapp_media", lambda mid, bucket, key: {"mimeType": "image/jpeg"})
    monkeypatch.setattr(cds, "read_s3", lambda bucket, key: b"\xff\xd8")


def test_ingest_before_then_after_flags_a_removed_clamp(monkeypatch, surgeon, one_case):
    cid = one_case["caseId"]
    # Before has two clamps; after has one. The deterministic diff flags the missing clamp.
    _stub_media(monkeypatch, _Vision(
        {"artery forceps": 6, "clamp": 2},
        {"artery forceps": 6, "clamp": 1},
    ))
    texts, docs = [], []
    monkeypatch.setattr(cds, "send_whatsapp_text", lambda to, body, **kw: texts.append((to, body)) or "id")
    monkeypatch.setattr(cds, "send_whatsapp_document",
                        lambda to, data, filename, **kw: docs.append((to, filename, data[:4])) or "id")

    before_reply = actions.ingest_tray_photo(cid, "before", {"id": "m1", "mime": "image/jpeg", "key": "k/b"})
    assert before_reply["type"] == "text"
    assert "Before tray recorded" in before_reply["text"]["body"]
    assert "second count" in before_reply["text"]["body"].lower()

    after_reply = actions.ingest_tray_photo(cid, "after", {"id": "m2", "mime": "image/jpeg", "key": "k/a"})
    body = after_reply["text"]["body"]
    assert "DISCREPANCY" in body and "clamp" in body
    assert "manual" in body.lower()

    # The surgeon was flagged, an audit PDF was sent, and an event was recorded.
    assert texts and texts[0][0] == surgeon["whatsappNumber"]
    assert docs and docs[0][1] == f"instrument-audit-{cid[:8]}.pdf"
    assert docs[0][2] == b"%PDF"
    assert any(e["type"] == "instrument_discrepancy" for e in db.list_events(cid))


def test_ingest_matching_trays_report_no_discrepancy(monkeypatch, one_case):
    cid = one_case["caseId"]
    _stub_media(monkeypatch, _Vision({"clamp": 2}, {"clamp": 2}))
    monkeypatch.setattr(cds, "send_whatsapp_text", lambda *a, **k: "id")
    monkeypatch.setattr(cds, "send_whatsapp_document", lambda *a, **k: "id")

    actions.ingest_tray_photo(cid, "before", {"id": "m1", "key": "k/b"})
    reply = actions.ingest_tray_photo(cid, "after", {"id": "m2", "key": "k/a"})
    assert "No discrepancy" in reply["text"]["body"]
    assert not any(e["type"] == "instrument_discrepancy" for e in db.list_events(cid))


# ── send_missed_form ─────────────────────────────────────────────────────────
def test_send_missed_form_builds_and_files(monkeypatch, surgeon, nurse, one_case):
    sent = []
    monkeypatch.setattr(cds, "send_whatsapp_document",
                        lambda to, data, filename, **kw: sent.append((to, filename)) or "id")
    reply = actions.send_missed_form(surgeon, one_case["caseId"], nurse["staffId"])
    assert sent and sent[0][0] == nurse["whatsappNumber"]
    forms = db.list_forms_for_case(one_case["caseId"])
    assert forms and forms[0]["staffId"] == nurse["staffId"] and forms[0]["kind"] == "page_missed"
    assert "dry run" in reply["text"]["body"]
