"""Tests for the staff WhatsApp login (wa.auth) over the real wa.session.

common.db.get_staff_by_email and common.cds.send_email are monkeypatched so these
tests do not depend on the data-model or channels modules being finished. The OTP code
is never stored in the clear, so the tests pull the six digits out of the captured
email body and submit those.
"""
import re
from datetime import datetime, timedelta, timezone

import pytest

from common import cds, db
from wa import auth, session

NUM = "447700900001"

STAFF = {"staffId": "s1", "name": "Dr Ada Lovelace", "role": "surgeon",
         "email": "ada@hospital.test"}


def _iso_ago(seconds: int) -> str:
    t = datetime.now(timezone.utc) - timedelta(seconds=seconds)
    return t.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _body(reply: dict) -> str:
    return reply["text"]["body"]


@pytest.fixture
def known_staff(monkeypatch):
    """get_staff_by_email returns the fake staff for the known address, else None."""
    def fake_lookup(email):
        return STAFF if (email or "").strip().lower() == STAFF["email"] else None

    monkeypatch.setattr(db, "get_staff_by_email", fake_lookup)
    return STAFF


@pytest.fixture
def capture_email(monkeypatch):
    """Capture every send_email call so a test can read back the OTP code."""
    sent = []

    def fake_send_email(to, subject, body, **kwargs):
        sent.append({"to": to, "subject": subject, "body": body})
        return "ses-stub"

    monkeypatch.setattr(cds, "send_email", fake_send_email)
    return sent


def _code_from(sent) -> str:
    match = re.search(r"\b(\d{6})\b", sent[-1]["body"])
    assert match, f"no 6-digit code in email body: {sent[-1]['body']!r}"
    return match.group(1)


# ── unknown email ──────────────────────────────────────────────────────────────
def test_unknown_email_stays_awaiting_email(known_staff, capture_email):
    auth.start_login(NUM)
    reply = auth.submit_email(NUM, "nobody@nowhere.test")
    assert "couldn't find" in _body(reply)
    assert session.get(NUM)["state"] == session.AWAITING_EMAIL
    assert len(capture_email) == 0


# ── happy path ───────────────────────────────────────────────────────────────
def test_happy_path_links_and_persists(known_staff, capture_email):
    auth.start_login(NUM)
    assert session.get(NUM)["state"] == session.AWAITING_EMAIL

    reply = auth.submit_email(NUM, STAFF["email"])
    assert "emailed" in _body(reply)
    assert session.get(NUM)["state"] == session.AWAITING_OTP

    code = _code_from(capture_email)
    done = auth.submit_otp(NUM, code)
    assert done == {"type": "text", "text": {"preview_url": False,
                                             "body": "You're logged in as Dr Ada Lovelace, surgeon."}}

    # the link persists across a fresh read
    s = session.get(NUM)
    assert s["state"] == session.AUTHED
    assert s["staffId"] == STAFF["staffId"]
    assert "otpHash" not in s and "pendingStaffId" not in s
    assert "pendingStaffName" not in s and "pendingStaffRole" not in s


def test_email_goes_to_the_staff_address(known_staff, capture_email):
    auth.start_login(NUM)
    auth.submit_email(NUM, STAFF["email"])
    assert capture_email[-1]["to"] == STAFF["email"]


# ── wrong then right ──────────────────────────────────────────────────────────
def test_wrong_code_then_correct(known_staff, capture_email):
    auth.start_login(NUM)
    auth.submit_email(NUM, STAFF["email"])
    code = _code_from(capture_email)

    wrong = "000000" if code != "000000" else "111111"
    reply = auth.submit_otp(NUM, wrong)
    assert "didn't match" in _body(reply) and "2 attempts left" in _body(reply)
    assert session.get(NUM)["state"] == session.AWAITING_OTP

    ok = auth.submit_otp(NUM, code)
    assert "logged in as Dr Ada Lovelace, surgeon" in _body(ok)
    assert session.get(NUM)["state"] == session.AUTHED
    assert session.get(NUM)["staffId"] == STAFF["staffId"]


# ── three wrong restart ───────────────────────────────────────────────────────
def test_three_wrong_codes_restart(known_staff, capture_email):
    auth.start_login(NUM)
    auth.submit_email(NUM, STAFF["email"])
    code = _code_from(capture_email)
    wrong = "000000" if code != "000000" else "111111"

    auth.submit_otp(NUM, wrong)
    auth.submit_otp(NUM, wrong)
    reply = auth.submit_otp(NUM, wrong)
    assert "start over" in _body(reply)
    assert session.get(NUM)["state"] == session.AWAITING_EMAIL
    assert "otpHash" not in session.get(NUM)
    assert "pendingStaffId" not in session.get(NUM)


# ── expired ──────────────────────────────────────────────────────────────────
def test_expired_code_returns_to_email(known_staff, capture_email):
    auth.start_login(NUM)
    auth.submit_email(NUM, STAFF["email"])
    code = _code_from(capture_email)
    # force the code to have expired
    session.set_state(NUM, session.AWAITING_OTP, otpExpiresAt=_iso_ago(10))

    reply = auth.submit_otp(NUM, code)
    assert "expired" in _body(reply)
    assert session.get(NUM)["state"] == session.AWAITING_EMAIL


# ── resend throttle ───────────────────────────────────────────────────────────
def test_resend_throttle_blocks_second_request(known_staff, capture_email):
    auth.start_login(NUM)
    auth.submit_email(NUM, STAFF["email"])
    reply = auth.submit_email(NUM, STAFF["email"])
    assert "Give it a minute" in _body(reply)
    assert len(capture_email) == 1   # no second email went out


# ── hourly cap ───────────────────────────────────────────────────────────────
def test_hourly_cap_blocks_sixth_request(known_staff, capture_email):
    auth.start_login(NUM)
    # five requests inside the hour but all older than the 60s throttle
    session.set_state(NUM, session.AWAITING_EMAIL,
                      otpRequests=[_iso_ago(s) for s in (120, 240, 360, 480, 600)])
    reply = auth.submit_email(NUM, STAFF["email"])
    assert "too many code requests" in _body(reply)
    assert len(capture_email) == 0   # capped before sending


# ── email masking ────────────────────────────────────────────────────────────
def test_email_is_masked_in_reply(known_staff, capture_email):
    auth.start_login(NUM)
    reply = auth.submit_email(NUM, STAFF["email"])
    assert "a***@hospital.test" in _body(reply)
    assert STAFF["email"] not in _body(reply)


# ── no plaintext code at rest ────────────────────────────────────────────────
def test_code_is_not_stored_in_plaintext(known_staff, capture_email):
    auth.start_login(NUM)
    auth.submit_email(NUM, STAFF["email"])
    code = _code_from(capture_email)
    s = session.get(NUM)
    assert code not in str(s)
    assert s["otpHash"] and s["otpSalt"]


# ── logout ───────────────────────────────────────────────────────────────────
def test_logout_unlinks(known_staff):
    session.link(NUM, STAFF["staffId"])
    assert session.get(NUM)["state"] == session.AUTHED
    reply = auth.logout(NUM)
    assert _body(reply) == "You're logged out."
    out = session.get(NUM)
    assert out["state"] == session.LOGGED_OUT
    assert "staffId" not in out
