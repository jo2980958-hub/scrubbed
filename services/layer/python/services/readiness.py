"""Patient readiness and post-op follow-up.

Pre-op instructions, confirmations (fasting/consent/balance), the readiness score and
cancellation-risk band (via safety.engine), the not-ready sweep, and post-op follow-up
with danger-sign escalation (via agent.classify). Depends on common.db, common.cds,
safety.engine, agent.classify, common.config. Contract fixed.
"""
from __future__ import annotations

from typing import Optional


def send_preop_instructions(case_id: str) -> dict: raise NotImplementedError
def record_confirmation(case_id: str, item: str, value: bool) -> dict: raise NotImplementedError
def case_readiness(case_id: str) -> dict: raise NotImplementedError          # {score, isReady, risk, outstanding}
def not_ready_sweep(hospital_id: Optional[str] = None) -> list[dict]: raise NotImplementedError   # scheduler
def send_followup(case_id: str) -> dict: raise NotImplementedError           # scheduler
def handle_patient_reply(number: str, text: str) -> list[dict]: raise NotImplementedError   # webhook -> classify -> escalate
