"""Per-number WhatsApp session state and staff link (ported from Arrearo).

Owns DynamoDB table config.TBL_WA_SESSIONS (PK waNumber): the login state machine, the
persisted number->staff link, and the transient navigation context. Reads/writes through
common.db.table so tests stub the resource with db.set_resource.
"""
from __future__ import annotations

from typing import Optional

from common import config, db

LOGGED_OUT = "logged_out"
AWAITING_EMAIL = "awaiting_email"
AWAITING_OTP = "awaiting_otp"
AUTHED = "authed"

CONTEXT_TTL_SECONDS = 30 * 60
_LINK_FIELDS = ("staffId", "linkedAt")
_OTP_FIELDS = ("otpHash", "otpSalt", "otpExpiresAt", "otpAttempts", "otpRequests",
               "pendingStaffId", "pendingEmail")
_CONTEXT_FIELD = "context"


def _table():
    return db.table(config.TBL_WA_SESSIONS)


def get(wa_number: str) -> dict:
    item = _table().get_item(Key={"waNumber": wa_number}).get("Item")
    return db._clean(item) if item else {"waNumber": wa_number, "state": LOGGED_OUT}


def save(session: dict) -> None:
    item = dict(session)
    item.setdefault("state", LOGGED_OUT)
    item["updatedAt"] = db.now_iso()
    _table().put_item(Item=db._to_ddb(item))


def set_state(wa_number: str, state: str, **fields) -> dict:
    session = get(wa_number)
    session["state"] = state
    for key, value in fields.items():
        if value is None:
            session.pop(key, None)
        else:
            session[key] = value
    save(session)
    return session


def set_context(wa_number: str, screen: str, params: Optional[dict] = None) -> dict:
    session = get(wa_number)
    session[_CONTEXT_FIELD] = {"screen": screen, "params": params or {}, "contextAt": db.now_iso()}
    save(session)
    return session


def clear_context(wa_number: str) -> None:
    session = get(wa_number)
    session.pop(_CONTEXT_FIELD, None)
    save(session)


def link(wa_number: str, staff_id: str) -> dict:
    """Persist the number->staff link and set state AUTHED. Clears OTP working fields."""
    session = get(wa_number)
    session["state"] = AUTHED
    session["staffId"] = staff_id
    session["linkedAt"] = db.now_iso()
    for field in _OTP_FIELDS:
        session.pop(field, None)
    save(session)
    return session


def unlink(wa_number: str) -> dict:
    session = get(wa_number)
    session["state"] = LOGGED_OUT
    for field in _LINK_FIELDS + _OTP_FIELDS + (_CONTEXT_FIELD,):
        session.pop(field, None)
    save(session)
    return session
