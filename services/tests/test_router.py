"""Tests for the staff WhatsApp navigation: wa.router, wa.intent, wa.menus.

These cover ROUTING, not the screens themselves: wa.views and wa.actions (built by
another agent in parallel) are monkeypatched to sentinel recorders, and wa.intent is
monkeypatched for the free-text tests. The real wa.session and real common.db run over
moto (the autouse `aws` fixture in conftest). For intent's own tests, agent.llm.converse_tool
is stubbed so no Bedrock call is made and only the validation/tap-building logic runs.
"""
import re

import pytest

from agent import llm
from common import cds, config, db
from wa import actions, auth, intent, menus, messages, router, session, views

NUM = "233200000001"            # bare digits, as WhatsApp delivers the 'from'
EMAIL = "ada@hospital.test"


# ── helpers ──────────────────────────────────────────────────────────────────
def _make_staff(hospital="hosp-1", role="surgeon", email=EMAIL):
    return db.create_staff({"name": "Dr Ada Lovelace", "role": role, "email": email,
                            "whatsappNumber": "+233200000001", "hospitalId": hospital})


def _authed_staff(**kw):
    staff = _make_staff(**kw)
    session.link(NUM, staff["staffId"])
    return staff


def _case(hospital="hosp-1", surgeon_id="surg-x", scheduled="2026-10-09T14:00:00Z",
          procedure="Laparoscopic cholecystectomy", theatre="Theatre 2"):
    return db.create_case({"hospitalId": hospital, "surgeonId": surgeon_id,
                           "scheduledAt": scheduled, "procedure": procedure, "theatre": theatre})


def _call(calls, name):
    for c in calls:
        if c[0] == name:
            return c
    return None


def _is_list_menu(reply) -> bool:
    return reply.get("type") == "interactive" and reply["interactive"]["type"] == "list"


@pytest.fixture
def rec(monkeypatch):
    """Replace every wa.views / wa.actions function with a recorder that logs its call
    and returns a sentinel reply, so the router tests exercise only the routing."""
    calls = []

    def make(module, name):
        def fake(*args, **kwargs):
            calls.append((name, args, kwargs))
            return {"type": "stub", "name": name}
        monkeypatch.setattr(module, name, fake)

    for name in ("my_list", "case_detail", "checklist_view", "readiness_view", "paging_status"):
        make(views, name)
    for name in ("run_checklist_item", "page_team", "acknowledge", "set_readiness",
                 "send_case_brief_pdf", "start_tray_check", "ingest_tray_photo", "send_missed_form"):
        make(actions, name)
    return calls


# ── logged out ───────────────────────────────────────────────────────────────
def test_logged_out_shows_welcome_with_login_only(rec):
    out = router.handle(NUM, {"text": "hello"})
    assert len(out) == 1
    buttons = out[0]["interactive"]["action"]["buttons"]
    assert [b["reply"]["id"] for b in buttons] == ["login"]
    assert not rec                      # no view/action dispatched while logged out


def test_login_tap_starts_login(rec):
    out = router.handle(NUM, {"tap_id": "login"})
    assert out[0]["type"] == "text"
    assert session.get(NUM)["state"] == session.AWAITING_EMAIL


def test_help_is_available_logged_out(rec):
    out = router.handle(NUM, {"text": "help"})
    assert out[0]["type"] == "text"
    assert "MENU" in out[0]["text"]["body"]
    assert session.get(NUM)["state"] == session.LOGGED_OUT


# ── the login handshake reaches AUTHED and appends the menu ──────────────────
def test_login_handshake_authes_and_appends_menu(monkeypatch):
    staff = _make_staff()
    monkeypatch.setattr(db, "get_staff_by_email",
                        lambda e: staff if (e or "").strip().lower() == EMAIL else None)
    sent = []
    monkeypatch.setattr(cds, "send_email",
                        lambda to, subject, body, **k: sent.append(body) or "ses-stub")

    router.handle(NUM, {"tap_id": "login"})
    router.handle(NUM, {"text": EMAIL})
    assert session.get(NUM)["state"] == session.AWAITING_OTP

    code = re.search(r"\b(\d{6})\b", sent[-1]).group(1)
    out = router.handle(NUM, {"text": code})

    assert session.get(NUM)["state"] == session.AUTHED
    assert session.get(NUM)["staffId"] == staff["staffId"]
    # the confirmation plus the menu
    assert len(out) == 2
    assert _is_list_menu(out[-1])


# ── each tap dispatches to the right view/action ─────────────────────────────
def test_taps_dispatch_to_views_and_actions(rec):
    staff = _authed_staff()
    cid = _case(surgeon_id=staff["staffId"])["caseId"]

    router.handle(NUM, {"tap_id": "mylist"})
    router.handle(NUM, {"tap_id": f"case:{cid}"})
    router.handle(NUM, {"tap_id": "ack:page-7"})
    router.handle(NUM, {"tap_id": f"check:{cid}:signin"})
    router.handle(NUM, {"tap_id": f"chk:{cid}:signin:2:1"})
    router.handle(NUM, {"tap_id": f"page:{cid}"})
    router.handle(NUM, {"tap_id": f"brief:{cid}"})
    router.handle(NUM, {"tap_id": f"tray:{cid}:before"})
    router.handle(NUM, {"tap_id": f"ready:{cid}:consent:0"})
    router.handle(NUM, {"tap_id": f"paging:{cid}"})
    router.handle(NUM, {"tap_id": f"readiness:{cid}"})

    mylist = _call(rec, "my_list")
    assert mylist[1][0]["staffId"] == staff["staffId"] and mylist[1][1] == "today"
    assert _call(rec, "case_detail")[1][1] == cid
    assert _call(rec, "acknowledge")[1][1] == "page-7"
    assert _call(rec, "checklist_view")[1][1:] == (cid, "signin")
    chk = _call(rec, "run_checklist_item")[1]
    assert chk[1:] == (cid, "signin", 2, True)
    assert _call(rec, "page_team")[1][1] == cid
    brief = _call(rec, "send_case_brief_pdf")[1]
    assert brief[1] == cid and brief[2] == NUM
    assert _call(rec, "start_tray_check")[1][1:] == (cid, "before")
    ready = _call(rec, "set_readiness")[1]
    assert ready[1:] == (cid, "consent", False)
    assert _call(rec, "paging_status")[1][1] == cid
    assert _call(rec, "readiness_view")[1][1] == cid


def test_account_taps(rec):
    _authed_staff()
    assert _is_list_menu(router.handle(NUM, {"tap_id": "menu"})[0])
    assert router.handle(NUM, {"tap_id": "settings"})[0]["type"] == "text"
    assert router.handle(NUM, {"tap_id": "help"})[0]["type"] == "text"
    router.handle(NUM, {"tap_id": "logout"})
    assert session.get(NUM)["state"] == session.LOGGED_OUT


def test_unknown_tap_falls_back_to_menu(rec):
    _authed_staff()
    out = router.handle(NUM, {"tap_id": "wibble:42"})
    assert _is_list_menu(out[0])
    assert not rec


# ── global commands ──────────────────────────────────────────────────────────
def test_global_commands(rec):
    _authed_staff()
    assert _is_list_menu(router.handle(NUM, {"text": "menu"})[0])
    router.handle(NUM, {"text": "my list"})
    assert _call(rec, "my_list") is not None
    router.handle(NUM, {"text": "logout"})
    assert session.get(NUM)["state"] == session.LOGGED_OUT


# ── free text goes through intent ────────────────────────────────────────────
def test_freetext_route_dispatches(monkeypatch, rec):
    _authed_staff()
    cid = _case()["caseId"]
    monkeypatch.setattr(intent, "resolve",
                        lambda text, staff, screen=None: {"kind": "route", "tap_id": f"case:{cid}"})
    router.handle(NUM, {"text": "open the gallbladder case"})
    assert _call(rec, "case_detail")[1][1] == cid


def test_freetext_answer_returns_text(monkeypatch, rec):
    _authed_staff()
    monkeypatch.setattr(intent, "resolve",
                        lambda *a, **k: {"kind": "answer", "text": "You have two cases today."})
    out = router.handle(NUM, {"text": "how many cases do I have"})
    assert out == [messages.text("You have two cases today.")]


def test_freetext_menu_fallback(monkeypatch, rec):
    _authed_staff()
    monkeypatch.setattr(intent, "resolve", lambda *a, **k: {"kind": "menu"})
    out = router.handle(NUM, {"text": "asdf qwer"})
    assert _is_list_menu(out[0])


# ── a case from another hospital is refused ──────────────────────────────────
def test_tap_for_other_hospital_case_is_refused(rec):
    _authed_staff(hospital="hosp-1")
    other = _case(hospital="hosp-2")["caseId"]

    view_out = router.handle(NUM, {"tap_id": f"case:{other}"})
    assert _call(rec, "case_detail") is None
    assert _is_list_menu(view_out[0])

    action_out = router.handle(NUM, {"tap_id": f"page:{other}"})
    assert _call(rec, "page_team") is None
    assert _is_list_menu(action_out[0])


def test_freetext_route_to_other_hospital_is_refused(monkeypatch, rec):
    _authed_staff(hospital="hosp-1")
    other = _case(hospital="hosp-2")["caseId"]
    # even if intent were to emit a foreign caseId, the router re-checks ownership
    monkeypatch.setattr(intent, "resolve",
                        lambda *a, **k: {"kind": "route", "tap_id": f"case:{other}"})
    out = router.handle(NUM, {"text": "open that case"})
    assert _call(rec, "case_detail") is None
    assert _is_list_menu(out[0])


# ── media: the tray photo ingest ─────────────────────────────────────────────
def test_media_during_tray_check_ingests(rec):
    _authed_staff()
    cid = _case()["caseId"]
    session.set_context(NUM, f"awaiting_tray:{cid}:before")
    media = {"id": "media-1", "mime_type": "image/jpeg"}

    router.handle(NUM, {"media": media})

    ingest = _call(rec, "ingest_tray_photo")
    assert ingest[1] == (cid, "before", media)
    assert "context" not in session.get(NUM)      # context cleared after ingest


def test_media_without_tray_context_goes_to_menu(rec):
    _authed_staff()
    out = router.handle(NUM, {"media": {"id": "m"}})
    assert _call(rec, "ingest_tray_photo") is None
    assert _is_list_menu(out[0])


def test_media_tray_for_other_hospital_is_refused(rec):
    _authed_staff(hospital="hosp-1")
    other = _case(hospital="hosp-2")["caseId"]
    session.set_context(NUM, f"awaiting_tray:{other}:after")
    out = router.handle(NUM, {"media": {"id": "m"}})
    assert _call(rec, "ingest_tray_photo") is None
    assert _is_list_menu(out[0])


# ── menus unit tests ─────────────────────────────────────────────────────────
def test_parse_command_variants():
    assert menus.parse_command("start") == menus.START
    assert menus.parse_command("Hi") == menus.START
    assert menus.parse_command("Show Menu") == menus.MENU
    assert menus.parse_command("options") == menus.MENU
    assert menus.parse_command("my list") == menus.MYLIST
    assert menus.parse_command("MYLIST") == menus.MYLIST
    assert menus.parse_command("my cases") == menus.MYLIST
    assert menus.parse_command("help") == menus.HELP
    assert menus.parse_command("log out") == menus.LOGOUT
    assert menus.parse_command("sign out") == menus.LOGOUT
    assert menus.parse_command("random noise") is None
    assert menus.parse_command(None) is None


def test_welcome_logged_out_has_login_button():
    w = menus.welcome_logged_out()
    assert w["type"] == "interactive"
    assert w["interactive"]["action"]["buttons"][0]["reply"]["id"] == "login"


def test_main_menu_rows_for_surgeon():
    rows = menus.main_menu({"role": "surgeon", "name": "Ada"})["interactive"]["action"]["sections"][0]["rows"]
    assert [r["id"] for r in rows] == ["mylist", "settings", "help", "logout"]


def test_main_menu_role_aware_for_coordinator():
    rows = menus.main_menu({"role": "coordinator"})["interactive"]["action"]["sections"][0]["rows"]
    ids = [r["id"] for r in rows]
    assert ids == ["mylist", "settings", "help", "logout"]


def test_settings_text_shows_the_linked_record():
    body = menus.settings_text({"name": "Dr Ada", "role": "surgeon",
                                "hospitalId": "hosp-1", "email": EMAIL})["text"]["body"]
    assert "surgeon" in body and "hosp-1" in body


def test_help_text_is_plain_and_has_no_em_dash():
    body = menus.help_text()["text"]["body"]
    assert config.BRAND in body
    assert "—" not in body


# ── intent unit tests (llm stubbed) ──────────────────────────────────────────
def _intent_staff():
    return db.create_staff({"name": "S", "role": "surgeon", "email": "s@h.test",
                            "whatsappNumber": "+233200000002", "hospitalId": "hosp-1"})


def test_intent_open_case_validates_hospital(monkeypatch):
    staff = _intent_staff()
    case = db.create_case({"hospitalId": "hosp-1", "surgeonId": staff["staffId"],
                           "scheduledAt": "2026-10-09T14:00:00Z", "procedure": "Lap chole",
                           "theatre": "T2"})
    monkeypatch.setattr(llm, "converse_tool",
                        lambda *a, **k: {"action": "open_case", "caseId": case["caseId"]})
    assert intent.resolve("the gallbladder case", staff) == {
        "kind": "route", "tap_id": f"case:{case['caseId']}"}


def test_intent_foreign_case_falls_back_to_menu(monkeypatch):
    staff = _intent_staff()
    other = db.create_case({"hospitalId": "hosp-2", "surgeonId": "x",
                            "scheduledAt": "2026-10-09T09:00:00Z", "procedure": "X", "theatre": "T1"})
    monkeypatch.setattr(llm, "converse_tool",
                        lambda *a, **k: {"action": "open_case", "caseId": other["caseId"]})
    assert intent.resolve("open it", staff) == {"kind": "menu"}


def test_intent_readiness_builds_item_tap(monkeypatch):
    staff = _intent_staff()
    case = db.create_case({"hospitalId": "hosp-1", "surgeonId": staff["staffId"],
                           "scheduledAt": "2026-10-09T14:00:00Z", "procedure": "Lap chole",
                           "theatre": "T2"})
    monkeypatch.setattr(llm, "converse_tool", lambda *a, **k: {
        "action": "readiness", "caseId": case["caseId"], "item": "consent", "ready": False})
    assert intent.resolve("flag the cholecystectomy as not ready, no consent yet", staff) == {
        "kind": "route", "tap_id": f"ready:{case['caseId']}:consent:0"}


def test_intent_mylist_with_when(monkeypatch):
    staff = _intent_staff()
    monkeypatch.setattr(llm, "converse_tool",
                        lambda *a, **k: {"action": "mylist", "when": "tomorrow"})
    assert intent.resolve("what's on tomorrow", staff) == {
        "kind": "route", "tap_id": "mylist:tomorrow"}


def test_intent_answer_passes_through(monkeypatch):
    staff = _intent_staff()
    monkeypatch.setattr(llm, "converse_tool",
                        lambda *a, **k: {"action": "answer", "answer": "You have two cases."})
    assert intent.resolve("how many", staff) == {"kind": "answer", "text": "You have two cases."}


def test_intent_llm_error_falls_back_to_menu(monkeypatch):
    staff = _intent_staff()

    def boom(*a, **k):
        raise RuntimeError("bedrock unavailable")

    monkeypatch.setattr(llm, "converse_tool", boom)
    assert intent.resolve("anything at all", staff) == {"kind": "menu"}
