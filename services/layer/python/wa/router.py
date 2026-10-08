"""The staff WhatsApp navigation state machine.

Loads the session; if not AUTHED routes to wa.auth (except global HELP); else maps
commands, interactive taps, the current screen context and free text to wa.menus /
wa.views / wa.actions, with wa.intent (Claude natural language) as the catch-all and a
safe menu fallback. Enforces that a staff member only acts within their own hospital
and permissions. Contract fixed.
"""
from __future__ import annotations


def handle(wa_number: str, inbound: dict) -> list[dict]:
    """inbound = {"text": str|None, "tap_id": str|None, "tap_title": str|None,
    "media": dict|None}. Returns a list of Replies (wa.messages dicts)."""
    raise NotImplementedError
