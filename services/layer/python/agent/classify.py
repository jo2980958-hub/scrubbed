"""Claude on Bedrock: classify a patient reply and recognise post-op danger signs.

Recognises danger signs (safety.DANGER_SIGNS) and sets escalate=True; it never diagnoses
and never reassures. Contract fixed.

This only reads the reply and flags it. It picks an intent, lists any danger signs it
recognises from the agreed phrasing, and gives a confidence. The decision to act lives in
the caller: a recognised danger sign or a reported problem escalates to the team. The model
never says the patient is fine and never names a diagnosis.
"""
from __future__ import annotations

from typing import Optional

from agent import llm
from common import config
from safety import engine

INTENTS = ["confirm", "question", "cannot_attend", "reports_problem", "other"]

# The exact danger-sign phrasings the model may report, so the list it returns maps onto
# safety.DANGER_SIGNS and nothing invented slips through.
_DANGER_SET = set(engine.DANGER_SIGNS)

# When the classifier cannot run or returns nothing usable, we cannot tell a benign reply
# from a danger sign. In a safety product that fails CLOSED: escalate to the team and let
# a human read the original message, rather than silently deciding "no escalation".
_FAILED = {"intent": "other", "dangerSigns": [], "escalate": True, "confidence": 0.0,
           "classifierError": True}

CLASSIFY_TOOL = {"toolSpec": {
    "name": "classify_reply",
    "description": ("Classify a patient's WhatsApp reply to a pre-op or post-op check-in, and "
                    "list any danger signs it describes. Recognise and flag only. Never diagnose, "
                    "never reassure, never say the patient is fine."),
    "inputSchema": {"json": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "enum": INTENTS,
                "description": ("confirm: acknowledges or confirms they are on track. "
                                "question: asks something. cannot_attend: says they cannot make "
                                "the operation or appointment. reports_problem: describes a symptom, "
                                "worry or something wrong. other: anything else."),
            },
            "dangerSigns": {
                "type": "array",
                "description": ("Each post-op danger sign the reply describes, copied verbatim from "
                                "the allowed list. Empty if none are described."),
                "items": {"type": "string", "enum": list(engine.DANGER_SIGNS)},
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1,
                           "description": "How sure you are about the intent, 0 to 1."},
        },
        "required": ["intent", "confidence"],
    }},
}}

SYSTEM = (
    "You read a patient's WhatsApp reply to a check-in from a surgical team and classify it. "
    "You are not a clinician. You only recognise and flag; you never diagnose, never reassure, "
    "and never tell the patient they are fine. "
    "Pick one intent. List every danger sign the reply describes, using only the allowed phrasings. "
    "The danger signs to recognise are: " + "; ".join(engine.DANGER_SIGNS) + ". "
    "If the reply describes any of them, list them; otherwise leave the list empty. "
    "Output only through the tool."
)


def classify_reply(text: str, context: Optional[dict] = None) -> dict:
    """Return {"intent": str, "dangerSigns": [str], "escalate": bool, "confidence": float}.

    escalate is True when the reply describes any danger sign, or the intent is
    reports_problem. On any model error or unusable result we FAIL CLOSED: escalate so a
    human reads the message, rather than silently deciding not to.
    """
    ctx = ""
    if context:
        procedure = context.get("procedure")
        phase = context.get("phase")
        bits = []
        if procedure:
            bits.append(f"procedure {procedure}")
        if phase:
            bits.append(f"{phase} check-in")
        if bits:
            ctx = "Context: " + ", ".join(bits) + ".\n"

    try:
        raw = llm.converse_tool(
            config.BEDROCK_FAST_MODEL, SYSTEM,
            [{"text": f"{ctx}Patient reply: {text!r}"}],
            CLASSIFY_TOOL, max_tokens=300)
    except Exception:
        return dict(_FAILED)

    if not isinstance(raw, dict):
        return dict(_FAILED)

    intent = raw.get("intent")
    if intent not in INTENTS:
        intent = "other"

    # Keep only recognised danger-sign phrasings, in the canonical order, no duplicates.
    reported = raw.get("dangerSigns") or []
    if not isinstance(reported, list):
        reported = []
    reported_set = {s for s in reported if isinstance(s, str) and s in _DANGER_SET}
    danger_signs = [s for s in engine.DANGER_SIGNS if s in reported_set]

    try:
        confidence = float(raw.get("confidence"))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    escalate = bool(danger_signs) or intent == "reports_problem"
    return {"intent": intent, "dangerSigns": danger_signs,
            "escalate": escalate, "confidence": confidence}
