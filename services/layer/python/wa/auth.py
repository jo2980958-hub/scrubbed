"""Staff WhatsApp login: work email -> emailed OTP (SES) -> verify -> link the number
to the staff record. No passwords in chat; hashed, expiring, rate-limited; one number,
one staff. Depends on wa.session, common.db.get_staff_by_email, common.cds.send_email,
common.config. Each function returns a Reply (wa.messages dict). Contract fixed.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from common import cds, config, db
from wa import messages, session

OTP_TTL_SECONDS = 10 * 60
MAX_ATTEMPTS = 3
RESEND_THROTTLE_SECONDS = 60
MAX_REQUESTS_PER_HOUR = 5

CODE_DIGITS = 6


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _gen_code() -> str:
    """A 6-digit code from a cryptographic source, zero-padded."""
    return f"{secrets.randbelow(10 ** CODE_DIGITS):0{CODE_DIGITS}d}"


def _hash(code: str, salt: str) -> str:
    """Salted SHA-256 of the code. The code itself is never stored."""
    return hashlib.sha256((salt + code).encode("utf-8")).hexdigest()


def _staff_email(staff: dict) -> str:
    for field in ("email", "workEmail", "contactEmail"):
        value = staff.get(field)
        if value:
            return str(value)
    return ""


def _mask_email(email: str) -> str:
    name, sep, domain = email.partition("@")
    if not sep or not name:
        return email
    return f"{name[0]}***@{domain}"


def _clear_pending() -> dict:
    """The working fields to drop when a login attempt ends or restarts."""
    return {
        "otpHash": None, "otpSalt": None, "otpExpiresAt": None, "otpAttempts": None,
        "pendingStaffId": None, "pendingEmail": None,
        "pendingStaffName": None, "pendingStaffRole": None,
    }


def start_login(wa_number: str) -> dict:
    """Set AWAITING_EMAIL and ask for the staff member's work email."""
    session.set_state(wa_number, session.AWAITING_EMAIL)
    return messages.text(
        "Let's log you in. What's your work email? "
        "Send it and I'll email you a 6-digit code."
    )


def submit_email(wa_number: str, email: str) -> dict:
    """Resolve the staff account; on a hit issue and email an OTP and set AWAITING_OTP,
    on a miss report it and stay AWAITING_EMAIL."""
    staff = db.get_staff_by_email((email or "").strip())
    if not staff:
        return messages.text(
            "I couldn't find a staff account for that email. "
            "Ask your coordinator to add you, then try again."
        )

    current = session.get(wa_number)
    now = _now()
    requests = [r for r in (current.get("otpRequests") or [])
                if (now - _parse_iso(r)).total_seconds() < 3600]

    if requests:
        last = max(_parse_iso(r) for r in requests)
        if (now - last).total_seconds() < RESEND_THROTTLE_SECONDS:
            return messages.text("I just sent a code. Give it a minute before asking for another.")

    if len(requests) >= MAX_REQUESTS_PER_HOUR:
        return messages.text("That's too many code requests for now. Please try again in an hour.")

    code = _gen_code()
    salt = secrets.token_hex(16)
    requests.append(db.now_iso())
    expires = (now + timedelta(seconds=OTP_TTL_SECONDS)).isoformat(
        timespec="microseconds").replace("+00:00", "Z")

    to_email = _staff_email(staff)
    session.set_state(
        wa_number, session.AWAITING_OTP,
        otpHash=_hash(code, salt), otpSalt=salt, otpExpiresAt=expires,
        otpAttempts=0, otpRequests=requests,
        pendingStaffId=staff["staffId"], pendingEmail=to_email,
        pendingStaffName=staff.get("name"), pendingStaffRole=staff.get("role"),
    )

    cds.send_email(
        to=to_email,
        subject=f"Your {config.BRAND} login code",
        body=(f"Your {config.BRAND} login code is {code}.\n\n"
              "It expires in 10 minutes. If you didn't ask to log in, you can ignore this email."),
    )
    return messages.text(
        f"I've emailed a 6-digit code to {_mask_email(to_email)}. It's good for 10 minutes. "
        "Send it back to me here."
    )


def submit_otp(wa_number: str, code: str) -> dict:
    """Verify the code; on success link the number, on failure count the attempt
    and return a retry, or restart after MAX_ATTEMPTS."""
    current = session.get(wa_number)
    expires = current.get("otpExpiresAt")

    if not expires or _now() > _parse_iso(expires):
        session.set_state(wa_number, session.AWAITING_EMAIL, **_clear_pending())
        return messages.text("That code has expired. Send your work email and I'll send a fresh one.")

    typed = "".join(ch for ch in str(code) if ch.isdigit())
    expected = current.get("otpHash") or ""
    candidate = _hash(typed, current.get("otpSalt") or "")

    if expected and hmac.compare_digest(candidate, expected):
        staff_id = current.get("pendingStaffId")
        name = current.get("pendingStaffName") or "your account"
        role = current.get("pendingStaffRole")
        session.link(wa_number, staff_id)
        # link() clears the OTP fields; drop the two pending labels it doesn't know about.
        session.set_state(wa_number, session.AUTHED,
                          pendingStaffName=None, pendingStaffRole=None)
        who = f"{name}, {role}" if role else name
        return messages.text(f"You're logged in as {who}.")

    attempts = int(current.get("otpAttempts") or 0) + 1
    if attempts >= MAX_ATTEMPTS:
        session.set_state(wa_number, session.AWAITING_EMAIL, **_clear_pending())
        return messages.text(
            "That code was wrong too many times. Send your work email to start over."
        )

    session.set_state(wa_number, session.AWAITING_OTP, otpAttempts=attempts)
    remaining = MAX_ATTEMPTS - attempts
    plural = "attempt" if remaining == 1 else "attempts"
    return messages.text(f"That code didn't match. You have {remaining} {plural} left.")


def logout(wa_number: str) -> dict:
    session.unlink(wa_number)
    return messages.text("You're logged out.")
