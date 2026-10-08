"""Claude on Bedrock: classify a patient reply and recognise post-op danger signs.

Recognises danger signs (safety.DANGER_SIGNS) and sets escalate=True; it never diagnoses
and never reassures. Contract fixed.
"""
from __future__ import annotations

from typing import Optional


def classify_reply(text: str, context: Optional[dict] = None) -> dict:
    """Return {"intent": str, "dangerSigns": [str], "escalate": bool, "confidence": float}."""
    raise NotImplementedError
