"""Normalise inbound interactive taps from a raw Meta message object."""
from __future__ import annotations

from typing import Optional


def extract_interactive(message: dict) -> Optional[dict]:
    """If `message` is an interactive button/list reply, return
    {"kind": "button"|"list", "id": <row/button id>, "title": <title>}; else None."""
    if not isinstance(message, dict) or message.get("type") != "interactive":
        return None
    inter = message.get("interactive") or {}
    kind = inter.get("type")
    if kind == "button_reply":
        r = inter.get("button_reply") or {}
        return {"kind": "button", "id": r.get("id"), "title": r.get("title")}
    if kind == "list_reply":
        r = inter.get("list_reply") or {}
        return {"kind": "list", "id": r.get("id"), "title": r.get("title")}
    return None
