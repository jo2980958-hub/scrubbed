"""Staff WhatsApp login: work email -> emailed OTP (SES) -> verify -> link the number
to the staff record. No passwords in chat; hashed, expiring, rate-limited; one number,
one staff. Depends on wa.session, common.db.get_staff_by_email, common.cds.send_email,
common.config. Each function returns a Reply (wa.messages dict). Contract fixed.
"""
from __future__ import annotations

OTP_TTL_SECONDS = 10 * 60
MAX_ATTEMPTS = 3
RESEND_THROTTLE_SECONDS = 60
MAX_REQUESTS_PER_HOUR = 5


def start_login(wa_number: str) -> dict: raise NotImplementedError
def submit_email(wa_number: str, email: str) -> dict: raise NotImplementedError
def submit_otp(wa_number: str, code: str) -> dict: raise NotImplementedError
def logout(wa_number: str) -> dict: raise NotImplementedError
