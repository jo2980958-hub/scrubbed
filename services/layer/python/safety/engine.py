"""The deterministic safety spine. Scrubbed's equivalent of Arrearo's legal engine:
plain, tested code that owns every rule, count and score. Claude never makes these
calls. Pure functions, no I/O.

- Readiness: which items a case needs, the score, and whether it is ready.
- Cancellation risk: a band from the outstanding items and the time to surgery.
- Instrument second-count: compare a before and after tray catalogue and flag anything
  unaccounted for. This flags for a human; the manual WHO count stays authoritative.
- The WHO Surgical Safety Checklist content.
- The page escalation threshold.
"""
from __future__ import annotations

from common import config

# Readiness items: key, label, required-for-ready.
READINESS_ITEMS = [
    ("consent", "Consent signed", True),
    ("fasting_confirmed", "Fasting confirmed", True),
    ("balance_cleared", "Balance cleared", True),
    ("team_confirmed", "Team acknowledged", True),
    ("instructions_sent", "Pre-op instructions sent", False),
    ("site_marked", "Surgical site marked", False),
]
_LABEL = {k: label for k, label, _ in READINESS_ITEMS}
_REQUIRED = [k for k, _, req in READINESS_ITEMS if req]


def readiness(status: dict) -> dict:
    """status maps item key -> bool. Returns the score, whether it is ready (all
    required items done), and the outstanding item labels."""
    done = [k for k, _, _ in READINESS_ITEMS if status.get(k)]
    outstanding = [_LABEL[k] for k, _, _ in READINESS_ITEMS if not status.get(k)]
    outstanding_required = [_LABEL[k] for k in _REQUIRED if not status.get(k)]
    total = len(READINESS_ITEMS)
    return {
        "doneCount": len(done),
        "total": total,
        "score": round(len(done) / total, 2),
        "isReady": not outstanding_required,
        "outstanding": outstanding,
        "outstandingRequired": outstanding_required,
    }


def cancellation_risk(status: dict, hours_to_surgery: float | None) -> str:
    """'low' | 'medium' | 'high'. A case with required items outstanding gets riskier
    as the operation approaches."""
    r = readiness(status)
    outstanding = r["outstandingRequired"]
    if not outstanding:
        return "low"
    if hours_to_surgery is None:
        return "medium"
    if hours_to_surgery < 6:
        return "high"
    if hours_to_surgery < 24:
        return "high" if len(outstanding) >= 2 else "medium"
    return "medium"


def instrument_diff(before: dict, after: dict) -> dict:
    """before/after map an instrument name -> count. Flags items whose after-count is
    below the before-count (possible retained item), and any count that rose or appeared
    (a discrepancy to verify). Returns {'ok', 'flags'} where ok means nothing to check."""
    names = list(dict.fromkeys(list(before.keys()) + list(after.keys())))
    flags = []
    for name in names:
        b = int(before.get(name, 0))
        a = int(after.get(name, 0))
        if a < b:
            flags.append({"item": name, "before": b, "after": a, "missing": b - a,
                          "kind": "unaccounted", "message": f"{b - a} {name} unaccounted for after the case"})
        elif a > b:
            flags.append({"item": name, "before": b, "after": a, "missing": 0,
                          "kind": "discrepancy", "message": f"{name} count rose from {b} to {a}, please verify"})
    return {"ok": not flags, "flags": flags}


# WHO Surgical Safety Checklist (2009), the three phases.
CHECKLIST = {
    "sign_in": [
        "Patient has confirmed identity, site, procedure and consent",
        "Site marked, or not applicable",
        "Anaesthesia safety check complete",
        "Pulse oximeter on the patient and working",
        "Known allergy?",
        "Difficult airway or aspiration risk?",
        "Risk of >500ml blood loss (7ml/kg in children)?",
    ],
    "time_out": [
        "All team members have introduced themselves by name and role",
        "Surgeon, anaesthetist and nurse confirm patient, site and procedure",
        "Anticipated critical events reviewed (surgeon, anaesthetist, nurse)",
        "Antibiotic prophylaxis given in the last 60 minutes, or not indicated",
        "Essential imaging displayed, or not needed",
    ],
    "sign_out": [
        "Nurse verbally confirms the name of the procedure recorded",
        "Instrument, sponge and needle counts are correct",
        "Specimen labelled (including patient name)",
        "Any equipment problems to address",
        "Key concerns for recovery and management reviewed",
    ],
}

# Post-op danger signs to recognise and ESCALATE (never diagnose, never reassure).
DANGER_SIGNS = [
    "heavy or increasing bleeding", "fever or chills", "spreading redness or pus at the wound",
    "wound opening", "severe or worsening pain", "shortness of breath or chest pain",
    "unable to pass urine", "persistent vomiting", "fainting or confusion",
]


def page_escalate_seconds() -> int:
    """How long to wait for an acknowledgement before escalating to a voice note/call."""
    return config.PAGE_ACK_ESCALATE_SECONDS
