"""Pure builders for Meta WhatsApp message JSON. No I/O, no 'to' field.

The send layer (common.cds.send_whatsapp_raw) adds 'to'. These return the dict that
goes under the Meta message body. Pure, so they are trivial to unit-test.

WhatsApp limits we enforce by truncation: body 1024, button title 20, list button 20,
row title 24, row description 72, 3 buttons, 10 rows total.
"""
from __future__ import annotations

from typing import Optional

BODY_MAX = 1024
BTN_TITLE_MAX = 20
ROW_TITLE_MAX = 24
ROW_DESC_MAX = 72


def _clip(s: Optional[str], n: int) -> str:
    s = "" if s is None else str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


def text(body: str) -> dict:
    return {"type": "text", "text": {"preview_url": False, "body": _clip(body, 4096)}}


def buttons(body: str, buttons: list[tuple[str, str]], header: Optional[str] = None) -> dict:
    """Interactive reply buttons. `buttons` is up to 3 (id, title) pairs."""
    action = {"buttons": [{"type": "reply", "reply": {"id": str(i), "title": _clip(t, BTN_TITLE_MAX)}}
                          for i, t in buttons[:3]]}
    interactive = {"type": "button", "body": {"text": _clip(body, BODY_MAX)}, "action": action}
    if header:
        interactive["header"] = {"type": "text", "text": _clip(header, 60)}
    return {"type": "interactive", "interactive": interactive}


def list_message(body: str, button_label: str, sections: list[dict],
                 header: Optional[str] = None) -> dict:
    """Interactive list. `sections` = [{"title", "rows": [{"id","title","description"?}]}].
    At most 10 rows across all sections (WhatsApp's cap)."""
    budget = 10
    out_sections = []
    for sec in sections:
        if budget <= 0:
            break
        rows = []
        for row in sec.get("rows", []):
            if budget <= 0:
                break
            r = {"id": str(row["id"]), "title": _clip(row["title"], ROW_TITLE_MAX)}
            if row.get("description"):
                r["description"] = _clip(row["description"], ROW_DESC_MAX)
            rows.append(r)
            budget -= 1
        if rows:
            out_sections.append({"title": _clip(sec.get("title", " "), 24), "rows": rows})
    interactive = {"type": "list", "body": {"text": _clip(body, BODY_MAX)},
                   "action": {"button": _clip(button_label, BTN_TITLE_MAX), "sections": out_sections}}
    if header:
        interactive["header"] = {"type": "text", "text": _clip(header, 60)}
    return {"type": "interactive", "interactive": interactive}


def document(media_id_or_link: str, filename: str, caption: Optional[str] = None,
             by_id: bool = True) -> dict:
    doc = {("id" if by_id else "link"): media_id_or_link, "filename": filename}
    if caption:
        doc["caption"] = _clip(caption, BODY_MAX)
    return {"type": "document", "document": doc}
