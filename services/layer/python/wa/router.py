"""The staff WhatsApp navigation state machine.

Loads the session; if not AUTHED routes to wa.auth (except global HELP); else maps
commands, interactive taps, the current screen context and free text to wa.menus /
wa.views / wa.actions, with wa.intent (Claude natural language) as the catch-all and a
safe menu fallback. Enforces that a staff member only acts within their own hospital
and permissions. Contract fixed.
"""
from __future__ import annotations

from common import db
from wa import actions, auth, intent, menus, messages, session, views

_TRUTHY = {"1", "true", "yes", "y", "ok", "done", "ready"}


def _as_list(reply) -> list[dict]:
    if reply is None:
        return []
    return reply if isinstance(reply, list) else [reply]


def _truthy(value) -> bool:
    return str(value or "").strip().lower() in _TRUTHY


def _owned(staff: dict, case_id: str) -> bool:
    """A case is actionable only inside the staff member's own hospital."""
    if not case_id:
        return False
    case = db.get_case(case_id)
    return bool(case and case.get("hospitalId") == staff.get("hospitalId"))


def handle(wa_number: str, inbound: dict) -> list[dict]:
    """inbound = {"text": str|None, "tap_id": str|None, "tap_title": str|None,
    "media": dict|None}. Returns a list of Replies (wa.messages dicts)."""
    inbound = inbound or {}
    text = inbound.get("text")
    tap_id = inbound.get("tap_id")
    media = inbound.get("media")
    cmd = menus.parse_command(text)

    # Help is available in any state.
    if cmd == menus.HELP:
        return [menus.help_text()]

    sess = session.get(wa_number)
    state = sess.get("state", session.LOGGED_OUT)
    if state != session.AUTHED:
        return _unauthed(wa_number, state, text, tap_id)

    staff = db.get_staff(sess.get("staffId"))
    if not staff:
        # The linked staff record is gone; unlink and start clean.
        return _as_list(auth.logout(wa_number))

    # Global commands first.
    if cmd in (menus.MENU, menus.START):
        return [menus.main_menu(staff)]
    if cmd == menus.MYLIST:
        return _as_list(views.my_list(staff))
    if cmd == menus.LOGOUT:
        return _as_list(auth.logout(wa_number))

    # An explicit tap wins over loose text.
    if tap_id:
        return _dispatch(wa_number, staff, tap_id)

    # No tap: a photo during a tray check goes to the instrument ingest; any other free
    # text goes to the smart layer, which gets the current screen as a hint.
    ctx = sess.get("context") or {}
    screen = ctx.get("screen")
    if media:
        return _ingest_media(wa_number, staff, screen, media)
    if text:
        return _resolve_freetext(wa_number, staff, text, screen)
    return [menus.main_menu(staff)]


def _ingest_media(wa_number: str, staff: dict, screen, media: dict) -> list[dict]:
    """A photo only means something while a tray check is awaited. The screen carries
    the case and phase: 'awaiting_tray:<caseId>:<phase>'."""
    session.clear_context(wa_number)
    if screen and screen.startswith("awaiting_tray:"):
        _, _, rest = screen.partition(":")
        case_id, _, phase = rest.partition(":")
        if _owned(staff, case_id):
            return _as_list(actions.ingest_tray_photo(case_id, phase, media))
    return [menus.main_menu(staff)]


def _resolve_freetext(wa_number: str, staff: dict, text: str, screen=None) -> list[dict]:
    """Hand free text to Claude: route to a screen or action, answer in words, or fall
    back to the menu. Claude only chooses where to go; the spine owns every rule and the
    caseId is validated against the staff member's hospital in wa.intent and again here."""
    r = intent.resolve(text, staff, screen=screen)
    kind = r.get("kind")
    if kind == "route":
        return _dispatch(wa_number, staff, r["tap_id"])
    if kind == "answer":
        return [messages.text(r["text"])]
    return [menus.main_menu(staff)]   # safe fallback


def _case_dispatch(staff: dict, case_id: str, fn) -> list[dict]:
    """Run a case-scoped view/action only when the case is in the staff's hospital."""
    if _owned(staff, case_id):
        return _as_list(fn())
    return [menus.main_menu(staff)]


def _dispatch(wa_number: str, staff: dict, tap_id: str) -> list[dict]:
    key, _, rest = (tap_id or "").partition(":")

    # Navigation and account.
    if key == "menu":
        return [menus.main_menu(staff)]
    if key == "settings":
        return [menus.settings_text(staff)]
    if key == "help":
        return [menus.help_text()]
    if key == "logout":
        return _as_list(auth.logout(wa_number))
    if key == "mylist":
        return _as_list(views.my_list(staff, rest or "today"))

    # Acknowledge a page: the pageId is not a case; the action re-checks ownership.
    if key == "ack":
        return _as_list(actions.acknowledge(staff, rest))

    # Case-scoped views.
    if key == "case":
        return _case_dispatch(staff, rest, lambda: views.case_detail(staff, rest))
    if key == "paging":
        return _case_dispatch(staff, rest, lambda: views.paging_status(staff, rest))
    if key == "readiness":
        return _case_dispatch(staff, rest, lambda: views.readiness_view(staff, rest))
    if key == "check":
        case_id, _, phase = rest.partition(":")
        return _case_dispatch(staff, case_id,
                              lambda: views.checklist_view(staff, case_id, phase))

    # Case-scoped actions.
    if key == "chk":
        parts = rest.split(":")
        if len(parts) >= 4:
            case_id, phase, idx, val = parts[0], parts[1], parts[2], parts[3]
            try:
                idx = int(idx)
            except (TypeError, ValueError):
                idx = 0
            return _case_dispatch(staff, case_id,
                                  lambda: actions.run_checklist_item(staff, case_id, phase,
                                                                     idx, _truthy(val)))
        return [menus.main_menu(staff)]
    if key == "page":
        return _case_dispatch(staff, rest, lambda: actions.page_team(staff, rest))
    if key == "brief":
        return _case_dispatch(staff, rest,
                              lambda: actions.send_case_brief_pdf(staff, rest, wa_number))
    if key == "tray":
        case_id, _, phase = rest.partition(":")
        if not _owned(staff, case_id):
            return [menus.main_menu(staff)]
        # Arm the next photo to land on this case's tray check for this phase.
        session.set_context(wa_number, f"awaiting_tray:{case_id}:{phase or 'before'}")
        return _as_list(actions.start_tray_check(staff, case_id, phase or "before"))
    if key == "ready":
        parts = rest.split(":")
        if len(parts) >= 3:
            case_id, item, val = parts[0], parts[1], parts[2]
            return _case_dispatch(staff, case_id,
                                  lambda: actions.set_readiness(staff, case_id, item, _truthy(val)))
        return [menus.main_menu(staff)]

    return [menus.main_menu(staff)]   # unknown tap -> menu


def _unauthed(wa_number: str, state: str, text, tap_id) -> list[dict]:
    key, _, rest = (tap_id or "").partition(":")
    # A paged recipient can acknowledge without being logged into the staff app. The
    # Acknowledge button carries the pageId; acknowledge_by_number verifies the sender is a
    # recipient of that page before writing, so this opens no unauthenticated write path.
    if key == "ack" and rest:
        return _as_list(actions.acknowledge_by_number(wa_number, rest))
    if state == session.AWAITING_EMAIL:
        if text:
            return _as_list(auth.submit_email(wa_number, text.strip()))
        return [messages.text("Please send the work email on your Scrubbed staff account.")]
    if state == session.AWAITING_OTP:
        if text:
            replies = _as_list(auth.submit_otp(wa_number, text.strip()))
            fresh = session.get(wa_number)
            if fresh.get("state") == session.AUTHED:
                staff = db.get_staff(fresh.get("staffId"))
                if staff:
                    replies.append(menus.main_menu(staff))
            return replies
        return [messages.text("Please type the 6-digit code I emailed you.")]
    # LOGGED_OUT or unknown
    if key == "login":
        return _as_list(auth.start_login(wa_number))
    return [menus.welcome_logged_out()]
