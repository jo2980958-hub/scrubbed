"""Claude vision on Amazon Bedrock: catalogue a surgical instrument tray from a photo.

Returns a structured count the deterministic safety.instrument_diff compares. The model
only reads the picture; it never decides the final count. Contract fixed.
"""
from __future__ import annotations


def catalogue_tray(image_bytes: bytes, mime: str) -> dict:
    """Return {"items": {name: count}, "confidence": {name: 0..1}, "notes": str}.
    Low-confidence lines are marked so the human verifies them."""
    raise NotImplementedError
