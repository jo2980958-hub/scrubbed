"""DynamoDB access. Generic helpers here are the stable base; domain accessors
(staff, cases, patients, trays, readiness, pages, forms, events, conversations) are
added by the data-model module against these. Tests swap the resource with moto via
set_resource().
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

import boto3
from boto3.dynamodb.conditions import Key

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


def _plus_hours(iso: str, hours: float) -> Optional[str]:
    """ISO time + hours, back as the same stored ISO shape, or None if unparseable."""
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (dt + timedelta(hours=hours)).isoformat(timespec="microseconds").replace("+00:00", "Z")


# ── domain accessors ──────────────────────────────────────────────────────────
# A single get-by-id helper keeps the many lookups below short and consistent.
def _get(tbl: str, key: dict) -> Optional[dict]:
    r = table(tbl).get_item(Key=key)
    return _clean(r["Item"]) if "Item" in r else None


def _first(items: list[dict]) -> Optional[dict]:
    return items[0] if items else None


# Staff. Email is stored lowercased and the WhatsApp number as +E.164, so both
# GSIs can be queried with the raw value the caller holds.
def create_staff(data: dict) -> dict:
    item = {"staffId": new_id(), "createdAt": now_iso(), **data}
    if item.get("email"):
        item["email"] = str(item["email"]).strip().lower()
    if item.get("whatsappNumber"):
        item["whatsappNumber"] = normalise_e164(item["whatsappNumber"])
    return _put(config.TBL_STAFF, item)


def get_staff(staff_id: str) -> Optional[dict]:
    return _get(config.TBL_STAFF, {"staffId": staff_id})


def get_staff_by_email(email: str) -> Optional[dict]:
    if not email:
        return None
    return _first(_query_all(config.TBL_STAFF, IndexName="byEmail",
                             KeyConditionExpression=Key("email").eq(str(email).strip().lower())))


def get_staff_by_whatsapp(number: str) -> Optional[dict]:
    num = normalise_e164(number)
    if not num:
        return None
    return _first(_query_all(config.TBL_STAFF, IndexName="byWhatsapp",
                             KeyConditionExpression=Key("whatsappNumber").eq(num)))


def update_staff(staff_id: str, fields: dict) -> dict:
    fields = dict(fields)
    if fields.get("email"):
        fields["email"] = str(fields["email"]).strip().lower()
    if fields.get("whatsappNumber"):
        fields["whatsappNumber"] = normalise_e164(fields["whatsappNumber"])
    return _update(config.TBL_STAFF, {"staffId": staff_id}, fields)


def list_staff(hospital_id: Optional[str] = None) -> list[dict]:
    """No GSI on hospitalId, so this scans and filters in memory."""
    items = _scan_all(config.TBL_STAFF)
    if hospital_id is not None:
        items = [s for s in items if s.get("hospitalId") == hospital_id]
    return items


# Cases. byHospital and bySurgeon both range on scheduledAt, so a day prefix
# (YYYY-MM-DD) narrows a query to one theatre day.
def create_case(data: dict) -> dict:
    for required in ("hospitalId", "surgeonId", "scheduledAt"):
        if not data.get(required):
            raise ValueError(f"create_case requires {required}")
    item = {"caseId": new_id(), "status": "scheduled", "createdAt": now_iso(), **data}
    # Arm the post-op follow-up a few hours after the scheduled time unless the caller set
    # one. The scheduler sends it once that time passes; without this the follow-up loop
    # has no producer and never fires.
    if not item.get("followupDueAt") and item.get("scheduledAt"):
        due = _plus_hours(item["scheduledAt"], 4)
        if due:
            item["followupDueAt"] = due
    return _put(config.TBL_CASES, item)


def get_case(case_id: str) -> Optional[dict]:
    return _get(config.TBL_CASES, {"caseId": case_id})


def update_case(case_id: str, fields: dict) -> dict:
    return _update(config.TBL_CASES, {"caseId": case_id}, fields)


def list_cases(hospital_id: Optional[str] = None, day: Optional[str] = None) -> list[dict]:
    if hospital_id is None:
        items = _scan_all(config.TBL_CASES)
        if day:
            items = [c for c in items if str(c.get("scheduledAt", "")).startswith(day)]
        return sorted(items, key=lambda c: str(c.get("scheduledAt", "")))
    cond = Key("hospitalId").eq(hospital_id)
    if day:
        cond = cond & Key("scheduledAt").begins_with(day)
    return _query_all(config.TBL_CASES, IndexName="byHospital", KeyConditionExpression=cond)


def list_cases_for_surgeon(staff_id: str, day: Optional[str] = None) -> list[dict]:
    cond = Key("surgeonId").eq(staff_id)
    if day:
        cond = cond & Key("scheduledAt").begins_with(day)
    return _query_all(config.TBL_CASES, IndexName="bySurgeon", KeyConditionExpression=cond)


# Patients. Keyed by patientId; looked up by WhatsApp number for the readiness
# and follow-up flow.
def create_patient(data: dict) -> dict:
    item = {"patientId": new_id(), "createdAt": now_iso(), **data}
    if item.get("whatsappNumber"):
        item["whatsappNumber"] = normalise_e164(item["whatsappNumber"])
    return _put(config.TBL_PATIENTS, item)


def get_patient(patient_id: str) -> Optional[dict]:
    return _get(config.TBL_PATIENTS, {"patientId": patient_id})


def get_patient_by_whatsapp(number: str) -> Optional[dict]:
    num = normalise_e164(number)
    if not num:
        return None
    return _first(_query_all(config.TBL_PATIENTS, IndexName="byWhatsapp",
                             KeyConditionExpression=Key("whatsappNumber").eq(num)))


def update_patient(patient_id: str, fields: dict) -> dict:
    fields = dict(fields)
    if fields.get("whatsappNumber"):
        fields["whatsappNumber"] = normalise_e164(fields["whatsappNumber"])
    return _update(config.TBL_PATIENTS, {"patientId": patient_id}, fields)


# Trays. One row per case holds both phases of the instrument second-count; each
# call merges its own phase and leaves the other untouched.
def set_tray_catalogue(case_id: str, phase: str, catalogue: dict,
                       photo_key: Optional[str] = None) -> dict:
    tray = get_tray(case_id) or {"caseId": case_id}
    tray[phase] = {"catalogue": catalogue, "photoKey": photo_key, "at": now_iso()}
    tray["updatedAt"] = now_iso()
    return _put(config.TBL_TRAYS, tray)


def get_tray(case_id: str) -> Optional[dict]:
    return _get(config.TBL_TRAYS, {"caseId": case_id})


# Readiness. One row per case with a single map of item -> bool.
def get_readiness(case_id: str) -> dict:
    row = _get(config.TBL_READINESS, {"caseId": case_id})
    return row.get("items", {}) if row else {}


def set_readiness_item(case_id: str, item: str, value: bool) -> dict:
    items = get_readiness(case_id)
    items[item] = bool(value)
    _put(config.TBL_READINESS, {"caseId": case_id, "items": items, "updatedAt": now_iso()})
    return items


# Pages. A page is a 'meta' row plus one 'recip#<number>' row per team member,
# all under the same pageId, so a single query returns the whole ladder.
def create_page(case_id: str, created_by: str, body: str, urgent: bool = False) -> dict:
    item = {"pageId": new_id(), "sk": "meta", "caseId": case_id, "createdAt": now_iso(),
            "createdBy": created_by, "body": body, "urgent": bool(urgent)}
    return _put(config.TBL_PAGES, item)


def add_page_recipient(page_id: str, staff_id: str, number: str) -> dict:
    num = normalise_e164(number)
    item = {"pageId": page_id, "sk": f"recip#{num}", "staffId": staff_id, "number": num,
            "status": "sent", "sentAt": now_iso()}
    return _put(config.TBL_PAGES, item)


# Ladder order. A delivery/read callback can arrive out of order (WhatsApp does not
# guarantee ordering), so the headline status only ever advances; the per-status
# timestamp is always stamped so we keep every receipt time.
_PAGE_LADDER = {"sent": 0, "delivered": 1, "read": 2, "escalated": 3, "acknowledged": 4}


def get_page(page_id: str) -> Optional[dict]:
    """The page's meta row (body, caseId, urgent, createdAt)."""
    return _get(config.TBL_PAGES, {"pageId": page_id, "sk": "meta"})


def is_page_recipient(page_id: str, number: str) -> bool:
    """True if this number was actually paged for this page. Gate on this before
    acknowledging, so a stray or foreign pageId cannot inject a recipient row."""
    num = normalise_e164(number)
    if not page_id or not num:
        return False
    return _get(config.TBL_PAGES, {"pageId": page_id, "sk": f"recip#{num}"}) is not None


def record_page_status(page_id: str, number: str, status: str) -> dict:
    """Move a recipient along the ladder (sent/delivered/read/escalated) and stamp the time.
    The headline status never regresses: a late 'read' receipt arriving after an
    acknowledgement (or an escalation) stamps readAt but leaves the recipient acknowledged,
    so the scheduler does not re-escalate an already-handled page."""
    key = {"pageId": page_id, "sk": f"recip#{normalise_e164(number)}"}
    current = _get(config.TBL_PAGES, key)
    fields: dict = {f"{status}At": now_iso()}
    if _PAGE_LADDER.get(status, 0) >= _PAGE_LADDER.get((current or {}).get("status"), -1):
        fields["status"] = status
    return _update(config.TBL_PAGES, key, fields)


def acknowledge_page(page_id: str, number: str) -> dict:
    key = {"pageId": page_id, "sk": f"recip#{normalise_e164(number)}"}
    return _update(config.TBL_PAGES, key, {"status": "acknowledged", "acknowledgedAt": now_iso()})


def list_page_recipients(page_id: str) -> list[dict]:
    return _query_all(config.TBL_PAGES,
                      KeyConditionExpression=Key("pageId").eq(page_id) & Key("sk").begins_with("recip#"))


def list_pages_for_case(case_id: str) -> list[dict]:
    """The 'meta' rows for a case, oldest first. Recipient rows carry no createdAt
    and so never enter the byCase index, but we filter to be explicit."""
    rows = _query_all(config.TBL_PAGES, IndexName="byCase",
                      KeyConditionExpression=Key("caseId").eq(case_id))
    return [r for r in rows if r.get("sk") == "meta"]


def pending_page_recipients(page_id: str) -> list[dict]:
    return [r for r in list_page_recipients(page_id) if r.get("status") != "acknowledged"]


# Forms. A form is sent to one staff member, filled, and uploaded back to S3.
def create_form(case_id: str, staff_id: str, kind: str) -> dict:
    item = {"formId": new_id(), "caseId": case_id, "staffId": staff_id, "kind": kind,
            "status": "sent", "createdAt": now_iso()}
    return _put(config.TBL_FORMS, item)


def attach_form_upload(form_id: str, s3_key: str) -> dict:
    return _update(config.TBL_FORMS, {"formId": form_id},
                   {"s3Key": s3_key, "status": "uploaded", "uploadedAt": now_iso()})


def get_form(form_id: str) -> Optional[dict]:
    return _get(config.TBL_FORMS, {"formId": form_id})


def list_forms_for_case(case_id: str) -> list[dict]:
    return _query_all(config.TBL_FORMS, IndexName="byCase",
                      KeyConditionExpression=Key("caseId").eq(case_id))


# Events. Audit timeline per case. The sort key is createdAt plus a per-process counter
# and a short random suffix: the counter keeps insertion order within one Lambda
# container, and the random part stops two containers that fire in the same microsecond
# from colliding on the sort key and overwriting each other's event.
_event_seq = 0


def add_event(case_id: str, type_: str, actor: str = "system",
              detail: Optional[dict] = None) -> dict:
    global _event_seq
    _event_seq += 1
    created = now_iso()
    sort = f"{created}#{_event_seq:06d}#{uuid.uuid4().hex[:6]}"
    item = {"caseId": case_id, "createdAt#seq": sort,
            "type": type_, "actor": actor, "detail": detail or {}, "createdAt": created}
    return _put(config.TBL_EVENTS, item)


def list_events(case_id: str) -> list[dict]:
    return _query_all(config.TBL_EVENTS, KeyConditionExpression=Key("caseId").eq(case_id))


# Conversations. Every message in and out, per person, timestamped. byMessageId
# resolves a delivery-status callback back to its stored row.
def add_message(number: str, direction: str, message_id: str, body: Optional[str] = None,
                **extra) -> dict:
    num = normalise_e164(number)
    created = now_iso()
    item = {"whatsappNumber": num, "createdAt#messageId": f"{created}#{message_id}",
            "createdAt": created, "direction": direction, "messageId": message_id,
            "body": body, **extra}
    return _put(config.TBL_CONVERSATIONS, item)


def list_messages(number: str, limit: int = 50) -> list[dict]:
    """The most recent `limit` messages, oldest first (newest last)."""
    r = table(config.TBL_CONVERSATIONS).query(
        KeyConditionExpression=Key("whatsappNumber").eq(normalise_e164(number)),
        ScanIndexForward=False, Limit=limit)
    items = [_clean(i) for i in r.get("Items", [])]
    items.reverse()
    return items


def record_delivery(message_id: str, status: str) -> Optional[dict]:
    rows = _query_all(config.TBL_CONVERSATIONS, IndexName="byMessageId",
                      KeyConditionExpression=Key("messageId").eq(message_id))
    if not rows:
        return None
    row = rows[0]
    key = {"whatsappNumber": row["whatsappNumber"], "createdAt#messageId": row["createdAt#messageId"]}
    return _update(config.TBL_CONVERSATIONS, key, {"status": status, f"{status}At": now_iso()})


def claim_message(message_id: str, ttl_days: int = 7) -> bool:
    """Idempotency guard for SNS redelivery: True the first time a message id is
    seen, False on any repeat. Backed by a conditional put of a claim row."""
    from botocore.exceptions import ClientError
    try:
        table(config.TBL_EVENTS).put_item(
            Item={"caseId": f"claim#{message_id}", "createdAt#seq": "0",
                  "ttl": int(datetime.now(timezone.utc).timestamp()) + ttl_days * 86400},
            ConditionExpression="attribute_not_exists(caseId)")
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise
