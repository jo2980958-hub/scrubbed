"""Full-surface audit: walk the whole staff app through the real router, so we know the
modules integrate end to end (menu, my list, case, checklist, page, the tray second-count,
natural language, guards). Deep per-module behaviour is in the module tests; this proves
the wiring."""
from datetime import datetime, timezone

import pytest

from agent import vision
from common import cds, db
from wa import intent, router, session

NUM = "+233200000001"
TODAY_2PM = datetime.now(timezone.utc).date().isoformat() + "T14:00:00Z"


@pytest.fixture(autouse=True)
def no_live(monkeypatch):
    sent = {"text": [], "doc": [], "audio": [], "voice": []}
    monkeypatch.setattr(cds, "send_whatsapp_text", lambda to, body, **k: sent["text"].append((to, body)) or "w")
    monkeypatch.setattr(cds, "send_whatsapp_raw", lambda to, msg, **k: "w")
    monkeypatch.setattr(cds, "send_whatsapp_document", lambda to, data, fn, **k: sent["doc"].append(to) or "w")
    monkeypatch.setattr(cds, "send_whatsapp_audio", lambda to, data, **k: sent["audio"].append(to) or "w")
    monkeypatch.setattr(cds, "send_voice", lambda to, text, **k: sent["voice"].append(to) or "v")
    monkeypatch.setattr(cds, "synth_mp3", lambda *a, **k: b"mp3")
    monkeypatch.setattr(cds, "fetch_whatsapp_media", lambda *a, **k: {"mimeType": "image/jpeg"})
    monkeypatch.setattr(cds, "read_s3", lambda *a, **k: b"img")
    return sent


def _setup():
    surgeon = db.create_staff({"name": "Dr Ada", "role": "surgeon", "email": "ada@h.test",
                               "whatsappNumber": NUM, "hospitalId": "hosp-1"})
    nurse = db.create_staff({"name": "Nurse B", "role": "scrub nurse", "email": "b@h.test",
                             "whatsappNumber": "+233200000002", "hospitalId": "hosp-1"})
    patient = db.create_patient({"name": "Pat", "whatsappNumber": "+233200000009", "hospitalId": "hosp-1"})
    case = db.create_case({"hospitalId": "hosp-1", "surgeonId": surgeon["staffId"],
                           "patientId": patient["patientId"], "procedure": "Cholecystectomy",
                           "theatre": "Theatre 2", "scheduledAt": TODAY_2PM,
                           "team": [surgeon["staffId"], nurse["staffId"]]})
    session.link(NUM, surgeon["staffId"])
    return surgeon, nurse, patient, case


def _ids(reply):
    if reply.get("type") != "interactive":
        return []
    i = reply["interactive"]
    if i["type"] == "button":
        return [b["reply"]["id"] for b in i["action"]["buttons"]]
    return [r["id"] for s in i["action"]["sections"] for r in s["rows"]]


def body(reply):
    if reply.get("type") == "text":
        return reply["text"]["body"]
    if reply.get("type") == "interactive":
        return reply["interactive"]["body"]["text"]
    return ""


def test_menu_mylist_and_case_detail():
    _, _, _, case = _setup()
    assert any(r.get("type") == "interactive" for r in router.handle(NUM, {"tap_id": "menu"}))
    [lst] = router.handle(NUM, {"tap_id": "mylist"})
    assert f"case:{case['caseId']}" in _ids(lst)
    [detail] = router.handle(NUM, {"tap_id": f"case:{case['caseId']}"})
    ids = _ids(detail)
    assert f"check:{case['caseId']}:sign_in" in ids and f"page:{case['caseId']}" in ids


def test_checklist_and_tick():
    _, _, _, case = _setup()
    [cl] = router.handle(NUM, {"tap_id": f"check:{case['caseId']}:sign_in"})
    assert _ids(cl)
    out = router.handle(NUM, {"tap_id": f"chk:{case['caseId']}:sign_in:0:1"})
    assert any("Ticked" in body(r) for r in out)


def test_page_team_and_acknowledge(no_live):
    _, _, _, case = _setup()
    [r] = router.handle(NUM, {"tap_id": f"page:{case['caseId']}"})
    assert "paged" in body(r).lower()
    assert len(no_live["text"]) == 0 and len(db.list_pages_for_case(case["caseId"])) == 1
    page = db.list_pages_for_case(case["caseId"])[0]
    [ack] = router.handle(NUM, {"tap_id": f"ack:{page['pageId']}"})
    assert "acknowledg" in body(ack).lower()


def test_instrument_second_count_flags_and_escalates(no_live, monkeypatch):
    surgeon, nurse, _, case = _setup()
    catalogues = [{"items": {"clamp": 2, "swab": 5}, "confidence": {}, "notes": ""},
                  {"items": {"clamp": 1, "swab": 5}, "confidence": {}, "notes": ""}]
    monkeypatch.setattr(vision, "catalogue_tray", lambda img, mime: catalogues.pop(0))
    media = {"id": "m1", "mime": "image/jpeg", "bucket": "b", "key": "k"}

    router.handle(NUM, {"tap_id": f"tray:{case['caseId']}:before"})
    [before] = router.handle(NUM, {"media": media})
    assert "before" in body(before).lower()

    router.handle(NUM, {"tap_id": f"tray:{case['caseId']}:after"})
    after = router.handle(NUM, {"media": media})
    assert any("clamp" in body(r).lower() for r in after)         # discrepancy named
    types = [e["type"] for e in db.list_events(case["caseId"])]
    assert "instrument_discrepancy" in types                      # recorded
    assert no_live["doc"] == [surgeon["whatsappNumber"]]          # audit PDF to the surgeon


def test_natural_language_routes(monkeypatch):
    _, _, _, case = _setup()
    monkeypatch.setattr(intent, "resolve", lambda text, staff, screen=None: {"kind": "route", "tap_id": f"case:{case['caseId']}"})
    out = router.handle(NUM, {"text": "open the gallbladder case"})
    assert any(f"page:{case['caseId']}" in _ids(r) for r in out)


def test_other_hospital_case_is_refused():
    _setup()
    other = db.create_case({"hospitalId": "hosp-2", "surgeonId": "x", "patientId": "y",
                            "procedure": "X", "theatre": "T1", "scheduledAt": "2026-10-09T09:00:00Z"})
    [r] = router.handle(NUM, {"tap_id": f"case:{other['caseId']}"})
    assert r.get("type") == "interactive"        # falls back to the menu, no case data


def test_logged_out_number_sees_only_login():
    [r] = router.handle("+233200000055", {"text": "hi"})
    assert _ids(r) == ["login"]
