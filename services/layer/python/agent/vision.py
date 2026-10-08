"""Claude vision on Amazon Bedrock: catalogue a surgical instrument tray from a photo.

Returns a structured count the deterministic safety.instrument_diff compares. The model
only reads the picture; it never decides the final count. Contract fixed.

This is a SECOND CHECK. The model reads one photo and lists what it can see. The real
decision is safety.instrument_diff comparing a before and after catalogue, and the manual
WHO count stays authoritative. We never present this number as the count.
"""
from __future__ import annotations

from agent import llm
from common import config

# Bedrock image content blocks take a bare format, not the MIME type.
FMT = {"image/jpeg": "jpeg", "image/jpg": "jpeg", "image/png": "png",
       "image/webp": "webp", "image/gif": "gif"}

# A line the model is this unsure about is surfaced to the human to verify.
VERIFY_BELOW = 0.5

SYSTEM = ("You catalogue the surgical instruments visible on a tray photo for a "
          "count-verification second check. List each distinct instrument type you can see "
          "and how many. Give a confidence 0-1 per line. Do not guess hidden or overlapping "
          "items; say so in notes. You are a second check, not the official count.")

CATALOGUE_TOOL = {"toolSpec": {
    "name": "catalogue_tray",
    "description": ("Record the instruments visible on the tray photo. One entry per distinct "
                    "instrument type, with how many you can see and how sure you are. "
                    "Do not include items you cannot actually see."),
    "inputSchema": {"json": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "description": "One entry per distinct instrument type visible on the tray.",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "The instrument type, e.g. 'artery forceps'"},
                        "count": {"type": "integer", "minimum": 0,
                                  "description": "How many of this instrument are visible"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1,
                                       "description": "How sure you are about this line, 0 to 1"},
                    },
                    "required": ["name", "count", "confidence"],
                },
            },
            "notes": {"type": "string",
                      "description": "Overlap, angle or anything hidden. Say what you could not read."},
        },
        "required": ["items"],
    }},
}}

_SAFE_DEFAULT = {"items": {}, "confidence": {},
                 "notes": "could not read the tray; please send a clearer photo"}


def catalogue_tray(image_bytes: bytes, mime: str) -> dict:
    """Return {"items": {name: count}, "confidence": {name: 0..1}, "notes": str}.
    Low-confidence lines are marked so the human verifies them.

    The items map (name -> count) is exactly what safety.instrument_diff consumes for the
    before/after compare. This function never decides anything; it only reads the photo.
    """
    fmt = FMT.get((mime or "").lower(), "jpeg")
    content = [
        {"image": {"format": fmt, "source": {"bytes": image_bytes}}},
        {"text": "Catalogue the instruments you can see on this tray. One line per type, "
                 "with a count and a confidence. Do not guess hidden or overlapping items."},
    ]
    try:
        raw = llm.converse_tool(config.BEDROCK_VISION_MODEL, SYSTEM, content, CATALOGUE_TOOL)
    except Exception:
        # The model gave us nothing usable. A second check stays silent rather than guess.
        return dict(_SAFE_DEFAULT)
    return normalise(raw)


def normalise(raw: dict) -> dict:
    """Tool output -> the catalogue shape. Names are lower-cased and stripped, duplicate
    lines summed, and low-confidence lines flagged in notes for a human to verify.

    None of this is a decision. It only tidies what the model read so the deterministic
    diff can compare two catalogues.
    """
    if not isinstance(raw, dict):
        return dict(_SAFE_DEFAULT)

    items: dict = {}
    confidence: dict = {}
    for line in raw.get("items") or []:
        if not isinstance(line, dict):
            continue
        name = str(line.get("name") or "").strip().lower()
        if not name:
            continue
        try:
            count = int(line.get("count"))
        except (TypeError, ValueError):
            continue
        if count <= 0:
            continue
        try:
            conf = float(line.get("confidence"))
        except (TypeError, ValueError):
            conf = 0.0
        conf = max(0.0, min(1.0, conf))
        # A duplicate line for the same instrument adds to the count. Keep the lowest
        # confidence of the two, so the human sees the most cautious figure.
        items[name] = items.get(name, 0) + count
        confidence[name] = min(confidence[name], conf) if name in confidence else conf

    if not items:
        return dict(_SAFE_DEFAULT)

    notes = str(raw.get("notes") or "").strip()
    unsure = [name for name, conf in confidence.items() if conf < VERIFY_BELOW]
    if unsure:
        flag = "please verify: " + ", ".join(sorted(unsure))
        notes = f"{notes} {flag}".strip() if notes else flag

    return {"items": items, "confidence": {k: round(v, 3) for k, v in confidence.items()},
            "notes": notes}
