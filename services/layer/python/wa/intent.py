"""Natural-language intent for the staff app (Claude Haiku on Bedrock).

Free text that is not a tap or an expected answer is mapped to an action, answered in
words, or falls back to the menu. Claude only decides WHERE to go and WHAT was meant;
the spine owns every rule and record, and any case it names is validated against the
staff member in the router before anything happens. Contract fixed.
"""
from __future__ import annotations

from typing import Optional


def resolve(text: str, staff: dict, screen: Optional[str] = None) -> dict:
    """Returns one of: {"kind":"route","tap_id":...} | {"kind":"answer","text":...}
    | a typed action dict | {"kind":"menu"} (safe fallback)."""
    raise NotImplementedError
