"""Read screens for the staff app. Each returns a Reply (wa.messages dict) or a list.
Depends on common.db, safety.engine, common.config, wa.messages. No writes. Contract fixed.
"""
from __future__ import annotations


def my_list(staff: dict, when: str = "today") -> dict: raise NotImplementedError
def case_detail(staff: dict, case_id: str) -> dict: raise NotImplementedError
def checklist_view(staff: dict, case_id: str, phase: str) -> dict: raise NotImplementedError
def readiness_view(staff: dict, case_id: str) -> dict: raise NotImplementedError
def paging_status(staff: dict, case_id: str) -> dict: raise NotImplementedError
