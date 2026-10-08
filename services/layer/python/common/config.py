"""Central configuration. Every service reads from here.

APP_SLUG is the internal, stable identifier (table prefix, resource names). BRAND is
the display name and may be finalised from a name check without touching internals.
"""
import os

# ── identity ────────────────────────────────────────────────────────────────
APP_SLUG = "scrubbed"                         # internal, STABLE
BRAND = os.environ.get("BRAND", "Scrubbed")   # display name (provisional)
TAGLINE = "The agent that keeps every operation on track, before and after."

# ── AWS ─────────────────────────────────────────────────────────────────────
REGION = os.environ.get("AWS_REGION", "us-east-1")
ACCOUNT_ID = "854924711083"                   # build/demo on Brownshift for now

# Bedrock — inference-profile IDs (bare model IDs are rejected; use us.*)
BEDROCK_REASONING_MODEL = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"   # drafting
BEDROCK_VISION_MODEL = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"      # tray compare (vision)
BEDROCK_FAST_MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"         # read/classify/intent

# WhatsApp (AWS End User Messaging Social) — reuse the Brownshift WABA for build/demo
WABA_ID = "waba-fc7e800db8f4433ab28a07f47089a226"
ORIGINATION_PHONE_NUMBER_ID = "phone-number-id-0d66a9b3b8fc463bb9bf999932643060"
WHATSAPP_SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:854924711083:brownshift-whatsapp-events"
WHATSAPP_SENDER_DISPLAY = "+233 55 906 2312"

# AWS End User Messaging Voice (pinpoint-sms-voice-v2) — the call escalation.
# No voice origination number is provisioned yet; the code path is built and the call
# is disclosed if it cannot reach the demo number. The WhatsApp voice note is primary.
VOICE_ORIGINATION_NUMBER_ID = os.environ.get("VOICE_ORIGINATION_NUMBER_ID", "")
VOICE_ID = os.environ.get("VOICE_ID", "Amy")          # Polly voice (en-GB)

# Cognito (dashboard sign-in) + SES sender
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID", "")
SES_SENDER = os.environ.get("SES_SENDER", "billing@brownshift.com")   # verified domain

# ── escalation ladder ────────────────────────────────────────────────────────
PAGE_ACK_ESCALATE_SECONDS = int(os.environ.get("PAGE_ACK_ESCALATE_SECONDS", str(30 * 60)))

# ── DynamoDB tables (prefix is APP_SLUG, stable) ────────────────────────────
TBL_STAFF = f"{APP_SLUG}-staff"
TBL_CASES = f"{APP_SLUG}-cases"
TBL_PATIENTS = f"{APP_SLUG}-patients"
TBL_TRAYS = f"{APP_SLUG}-trays"                # instrument sets + per-case before/after catalogues
TBL_READINESS = f"{APP_SLUG}-readiness"        # per-case readiness items
TBL_PAGES = f"{APP_SLUG}-pages"                # per page, per recipient delivery/read/ack state
TBL_FORMS = f"{APP_SLUG}-forms"                # uploaded forms filed against a case
TBL_EVENTS = f"{APP_SLUG}-events"              # audit timeline
TBL_CONVERSATIONS = f"{APP_SLUG}-conversations"  # every message in/out, per person, timestamped
TBL_WA_SESSIONS = f"{APP_SLUG}-wa-sessions"    # staff WhatsApp login/link + nav state
