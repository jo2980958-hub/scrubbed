"""The page ladder.

Fan a page out to a case's roster, write a per-recipient page record (sent/delivered/
read/acknowledged), handle the Acknowledge tap, and arm/cancel the escalation. The 30-min
timer itself is an EventBridge schedule the lead wires; escalate_unacknowledged is what it
calls. Depends on common.db, common.cds, safety.engine, common.config. Contract fixed.
"""
from __future__ import annotations


def send_page(case_id: str, created_by: str, body: str, urgent: bool = False) -> dict:
    """Send the page to every roster member, record per-recipient status, arm the
    escalation. Returns the page record."""
    raise NotImplementedError


def on_acknowledge(page_id: str, number: str) -> dict:
    """Mark a recipient acknowledged; cancel their escalation. Returns the page record."""
    raise NotImplementedError


def escalate_unacknowledged(page_id: str) -> dict:
    """Called after PAGE_ACK_ESCALATE_SECONDS: for anyone not acknowledged, send a
    WhatsApp voice note (and a voice call when a number is provisioned)."""
    raise NotImplementedError


def page_status(case_id: str) -> list[dict]:
    raise NotImplementedError
