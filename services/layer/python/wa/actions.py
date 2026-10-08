"""Write actions for the staff app. Each returns a Reply (or list). Every action checks
the case belongs to the staff member's hospital. Depends on common.db, services.paging,
services.readiness, safety.engine, agent.vision, common.documents, common.cds, wa.messages.
Contract fixed.
"""
from __future__ import annotations

from typing import Optional


def run_checklist_item(staff: dict, case_id: str, phase: str, index: int, value: bool) -> dict: raise NotImplementedError
def page_team(staff: dict, case_id: str, body: Optional[str] = None, urgent: bool = False) -> list[dict]: raise NotImplementedError
def acknowledge(staff: dict, page_id: str) -> dict: raise NotImplementedError
def set_readiness(staff: dict, case_id: str, item: str, value: bool) -> dict: raise NotImplementedError
def send_case_brief_pdf(staff: dict, case_id: str, to_number: str) -> dict: raise NotImplementedError
def start_tray_check(staff: dict, case_id: str, phase: str) -> dict: raise NotImplementedError
def ingest_tray_photo(case_id: str, phase: str, media: dict) -> dict: raise NotImplementedError
def send_missed_form(staff: dict, case_id: str, target_staff_id: str) -> dict: raise NotImplementedError
