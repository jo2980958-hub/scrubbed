"""DynamoDB access. Generic helpers here are the stable base; domain accessors
(staff, cases, patients, trays, readiness, pages, forms, events, conversations) are
added by the data-model module against these. Tests swap the resource with moto via
set_resource().
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

import boto3

from common import config

_resource = None


def resource():
    global _resource
    if _resource is None:
        _resource = boto3.resource("dynamodb", region_name=config.REGION)
    return _resource


def set_resource(res) -> None:
    """Swap the DynamoDB resource (tests point this at a moto one)."""
    global _resource
    _resource = res


def table(name: str):
    return resource().Table(name)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def new_id() -> str:
    return str(uuid.uuid4())


def _to_ddb(value: Any) -> Any:
    """Python -> DynamoDB: floats become Decimal; empty strings/None are dropped."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _to_ddb(v) for k, v in value.items() if v is not None and v != ""}
    if isinstance(value, (list, tuple)):
        return [_to_ddb(v) for v in value if v is not None]
    return value


def _clean(value: Any) -> Any:
    """DynamoDB -> Python: Decimal -> int when whole, else float."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean(v) for v in value]
    return value


def _put(tbl: str, item: dict, **kw) -> dict:
    item = _to_ddb(item)
    table(tbl).put_item(Item=item, **kw)
    return _clean(item)


def _update(tbl: str, key: dict, fields: dict) -> dict:
    """SET the given fields (None removes the attribute) and return the new item."""
    fields = {k: v for k, v in fields.items() if k not in key}
    sets, removes, names, values = [], [], {}, {}
    for i, (k, v) in enumerate(fields.items()):
        names[f"#f{i}"] = k
        if v is None or v == "":
            removes.append(f"#f{i}")
        else:
            sets.append(f"#f{i} = :v{i}")
            values[f":v{i}"] = _to_ddb(v)
    expr = ""
    if sets:
        expr += "SET " + ", ".join(sets)
    if removes:
        expr += (" " if expr else "") + "REMOVE " + ", ".join(removes)
    kw = {"Key": key, "UpdateExpression": expr, "ExpressionAttributeNames": names,
          "ReturnValues": "ALL_NEW"}
    if values:
        kw["ExpressionAttributeValues"] = values
    return _clean(table(tbl).update_item(**kw)["Attributes"])


def _query_all(tbl: str, **kw) -> list[dict]:
    items, start = [], None
    while True:
        if start:
            kw["ExclusiveStartKey"] = start
        r = table(tbl).query(**kw)
        items += r.get("Items", [])
        start = r.get("LastEvaluatedKey")
        if not start:
            return [_clean(i) for i in items]


def _scan_all(tbl: str, **kw) -> list[dict]:
    items, start = [], None
    while True:
        if start:
            kw["ExclusiveStartKey"] = start
        r = table(tbl).scan(**kw)
        items += r.get("Items", [])
        start = r.get("LastEvaluatedKey")
        if not start:
            return [_clean(i) for i in items]


def normalise_e164(number: str) -> str:
    """WhatsApp 'from' values arrive as bare digits; the data model stores +E.164."""
    digits = "".join(c for c in str(number) if c.isdigit())
    return f"+{digits}" if digits else ""


# ── domain accessors (contracts; the data-model module fills the bodies) ──────
# Staff
def create_staff(data: dict) -> dict: raise NotImplementedError
def get_staff(staff_id: str) -> Optional[dict]: raise NotImplementedError
def get_staff_by_email(email: str) -> Optional[dict]: raise NotImplementedError
def get_staff_by_whatsapp(number: str) -> Optional[dict]: raise NotImplementedError
def update_staff(staff_id: str, fields: dict) -> dict: raise NotImplementedError
def list_staff(hospital_id: Optional[str] = None) -> list[dict]: raise NotImplementedError

# Cases
def create_case(data: dict) -> dict: raise NotImplementedError
def get_case(case_id: str) -> Optional[dict]: raise NotImplementedError
def update_case(case_id: str, fields: dict) -> dict: raise NotImplementedError
def list_cases(hospital_id: Optional[str] = None, day: Optional[str] = None) -> list[dict]: raise NotImplementedError
def list_cases_for_surgeon(staff_id: str, day: Optional[str] = None) -> list[dict]: raise NotImplementedError

# Patients
def create_patient(data: dict) -> dict: raise NotImplementedError
def get_patient(patient_id: str) -> Optional[dict]: raise NotImplementedError
def get_patient_by_whatsapp(number: str) -> Optional[dict]: raise NotImplementedError
def update_patient(patient_id: str, fields: dict) -> dict: raise NotImplementedError

# Trays (instrument catalogues per case: phase 'before'|'after')
def set_tray_catalogue(case_id: str, phase: str, catalogue: dict, photo_key: Optional[str] = None) -> dict: raise NotImplementedError
def get_tray(case_id: str) -> Optional[dict]: raise NotImplementedError

# Readiness (per case: item key -> bool)
def get_readiness(case_id: str) -> dict: raise NotImplementedError
def set_readiness_item(case_id: str, item: str, value: bool) -> dict: raise NotImplementedError

# Pages (a page to a case's roster; per-recipient delivery/read/ack state)
def create_page(case_id: str, created_by: str, body: str, urgent: bool = False) -> dict: raise NotImplementedError
def add_page_recipient(page_id: str, staff_id: str, number: str) -> dict: raise NotImplementedError
def record_page_status(page_id: str, number: str, status: str) -> dict: raise NotImplementedError  # sent/delivered/read
def acknowledge_page(page_id: str, number: str) -> dict: raise NotImplementedError
def list_page_recipients(page_id: str) -> list[dict]: raise NotImplementedError
def list_pages_for_case(case_id: str) -> list[dict]: raise NotImplementedError
def pending_page_recipients(page_id: str) -> list[dict]: raise NotImplementedError  # not acknowledged

# Forms (a form sent to a staff member, filled and uploaded back)
def create_form(case_id: str, staff_id: str, kind: str) -> dict: raise NotImplementedError
def attach_form_upload(form_id: str, s3_key: str) -> dict: raise NotImplementedError
def get_form(form_id: str) -> Optional[dict]: raise NotImplementedError
def list_forms_for_case(case_id: str) -> list[dict]: raise NotImplementedError

# Events (audit timeline per case)
def add_event(case_id: str, type_: str, actor: str = "system", detail: Optional[dict] = None) -> dict: raise NotImplementedError
def list_events(case_id: str) -> list[dict]: raise NotImplementedError

# Conversations (every message in/out, per person, timestamped)
def add_message(number: str, direction: str, message_id: str, body: Optional[str] = None, **extra) -> dict: raise NotImplementedError
def list_messages(number: str, limit: int = 50) -> list[dict]: raise NotImplementedError
def record_delivery(message_id: str, status: str) -> Optional[dict]: raise NotImplementedError
def claim_message(message_id: str, ttl_days: int = 7) -> bool: raise NotImplementedError
