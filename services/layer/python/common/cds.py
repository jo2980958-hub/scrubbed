"""Runtime wrappers around the CDS messaging SDKs. One boto3 call each.

- End User Messaging Social -> socialmessaging (WhatsApp text/interactive/audio/document, media)
- Amazon SES v2             -> sesv2 (email)
- End User Messaging Voice  -> pinpoint-sms-voice-v2 (the call page)
- Amazon Polly              -> polly (synthesise the audio note)

The infra here (live/client/set_client/wa_id) is real so tests can stub clients; the
channel sends are filled by the CDS-channels module.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Optional

import boto3

from common import config

META_API_VERSION = "v20.0"
log = logging.getLogger(__name__)
_clients: dict = {}


def live() -> bool:
    """Sends are real only when SEND_MODE=live."""
    return os.environ.get("SEND_MODE", "dry") == "live"


def client(service: str):
    if service not in _clients:
        _clients[service] = boto3.client(service, region_name=config.REGION)
    return _clients[service]


def set_client(service: str, c) -> None:
    _clients[service] = c


def wa_id(number: str) -> str:
    """AWS SendWhatsAppMessage needs E.164 with a leading '+'."""
    digits = "".join(ch for ch in str(number) if ch.isdigit())
    return "+" + digits if digits else ""


# ── WhatsApp (AWS End User Messaging Social) ──────────────────────────────────
def send_whatsapp_text(to: str, body: str, reply_to_wamid: Optional[str] = None) -> str:
    """Send a free-form text over the WABA. Only valid inside the 24h customer-service
    window. Returns the wamid (or a dry-run id when SEND_MODE != live)."""
    msg = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": wa_id(to),
        "type": "text",
        "text": {"preview_url": False, "body": body[:4096]},
    }
    if reply_to_wamid:
        msg["context"] = {"message_id": reply_to_wamid}
    if not live():
        log.info("DRY-RUN whatsapp to=%s body=%s", msg["to"], body)
        return f"dry-run-{uuid.uuid4().hex[:12]}"
    resp = client("socialmessaging").send_whatsapp_message(
        originationPhoneNumberId=config.ORIGINATION_PHONE_NUMBER_ID,
        message=json.dumps(msg).encode("utf-8"),
        metaApiVersion=META_API_VERSION,
    )
    return resp["messageId"]


def send_whatsapp_raw(to: str, message: dict) -> str:
    """Send a pre-built Meta WhatsApp message (interactive buttons/list, document, audio,
    etc.) built elsewhere. The builder omits 'to'; we add the envelope here. Valid only
    inside the 24h window. Returns the wamid (or a dry-run id when SEND_MODE != live)."""
    msg = {"messaging_product": "whatsapp", "recipient_type": "individual",
           "to": wa_id(to), **message}
    if not live():
        log.info("DRY-RUN whatsapp(raw) to=%s type=%s", msg["to"], message.get("type"))
        return f"dry-run-{uuid.uuid4().hex[:12]}"
    resp = client("socialmessaging").send_whatsapp_message(
        originationPhoneNumberId=config.ORIGINATION_PHONE_NUMBER_ID,
        message=json.dumps(msg).encode("utf-8"),
        metaApiVersion=META_API_VERSION,
    )
    return resp["messageId"]


def send_whatsapp_document(to: str, data: bytes, filename: str, caption: Optional[str] = None,
                           bucket: Optional[str] = None) -> str:
    """Send a file (a case brief, worklist or instrument-count PDF) as a WhatsApp document:
    stage it in S3, register it with PostWhatsAppMessageMedia for a media id, then send it.
    Valid only inside the 24h window. Returns the wamid (or a dry-run id when not live)."""
    if not live():
        log.info("DRY-RUN whatsapp document to=%s file=%s (%d bytes)", wa_id(to), filename, len(data))
        return f"dry-run-{uuid.uuid4().hex[:12]}"
    bucket = bucket or os.environ.get("MEDIA_BUCKET", "")
    key = f"outbound/{uuid.uuid4().hex}/{filename}"
    client("s3").put_object(Bucket=bucket, Key=key, Body=data, ContentType="application/pdf")
    media_id = client("socialmessaging").post_whatsapp_message_media(
        originationPhoneNumberId=config.ORIGINATION_PHONE_NUMBER_ID,
        sourceS3File={"bucketName": bucket, "key": key},
    )["mediaId"]
    doc = {"type": "document", "document": {"id": media_id, "filename": filename}}
    if caption:
        doc["document"]["caption"] = caption[:1024]
    return send_whatsapp_raw(to, doc)


def send_whatsapp_audio(to: str, data: bytes, caption: Optional[str] = None,
                        bucket: Optional[str] = None) -> str:
    """Send an MP3 (the spoken page) as a WhatsApp audio message: stage it in S3, register
    it with PostWhatsAppMessageMedia for a media id, then send it. WhatsApp audio carries no
    caption, so if one is given we send it as a short text first. Valid only inside the 24h
    window. Returns the audio wamid (or a dry-run id when SEND_MODE != live)."""
    if not live():
        log.info("DRY-RUN whatsapp audio to=%s (%d bytes) caption=%s", wa_id(to), len(data), bool(caption))
        return f"dry-run-{uuid.uuid4().hex[:12]}"
    bucket = bucket or os.environ.get("MEDIA_BUCKET", "")
    key = f"outbound/{uuid.uuid4().hex}/page.mp3"
    client("s3").put_object(Bucket=bucket, Key=key, Body=data, ContentType="audio/mpeg")
    media_id = client("socialmessaging").post_whatsapp_message_media(
        originationPhoneNumberId=config.ORIGINATION_PHONE_NUMBER_ID,
        sourceS3File={"bucketName": bucket, "key": key},
    )["mediaId"]
    if caption:
        send_whatsapp_text(to, caption)
    return send_whatsapp_raw(to, {"type": "audio", "audio": {"id": media_id}})


def fetch_whatsapp_media(media_id: str, bucket: str, key: str) -> dict:
    """Ask the service to write an inbound media file (a tray photo, an uploaded form) to S3.
    The call does not return the bytes: it returns {mimeType, fileSize}; read the object
    from S3 afterwards."""
    return client("socialmessaging").get_whatsapp_message_media(
        mediaId=media_id,
        originationPhoneNumberId=config.ORIGINATION_PHONE_NUMBER_ID,
        destinationS3File={"bucketName": bucket, "key": key},
    )


def read_s3(bucket: str, key: str) -> bytes:
    return client("s3").get_object(Bucket=bucket, Key=key)["Body"].read()


# ── Email (Amazon SES v2) ─────────────────────────────────────────────────────
def send_email(to: str, subject: str, body: str, attachment: Optional[dict] = None,
               from_addr: Optional[str] = None, reply_to: Optional[str] = None) -> str:
    """Send a plain-text email through SES v2. `attachment` is
    {"filename", "content": bytes, "content_type"} (e.g. a worklist or case-brief PDF).
    Returns the SES MessageId (or a dry-run id when SEND_MODE != live)."""
    simple = {
        "Subject": {"Data": subject, "Charset": "UTF-8"},   # UTF-8 so a pound sign is safe
        "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
    }
    if attachment:
        simple["Attachments"] = [{
            "RawContent": attachment["content"],
            "FileName": attachment["filename"],
            "ContentType": attachment.get("content_type", "application/pdf"),
            "ContentDisposition": "ATTACHMENT",
            "ContentTransferEncoding": "BASE64",
        }]
    params = {
        "FromEmailAddress": from_addr or f"{config.BRAND} <{config.SES_SENDER}>",
        "Destination": {"ToAddresses": [to]},
        "Content": {"Simple": simple},
    }
    if reply_to:
        params["ReplyToAddresses"] = [reply_to]
    if not live():
        log.info("DRY-RUN email to=%s subject=%s attachment=%s", to, subject, bool(attachment))
        return f"dry-run-{uuid.uuid4().hex[:12]}"
    return client("sesv2").send_email(**params)["MessageId"]


# ── Voice (AWS End User Messaging Voice) + Polly ──────────────────────────────
def synth_mp3(text: str, voice_id: Optional[str] = None) -> bytes:
    """Synthesise `text` to MP3 bytes with Amazon Polly (neural). This makes the spoken
    page that goes out as a WhatsApp audio note. `voice_id` is a Polly voice id (title
    case, e.g. 'Amy'), defaulting to config.VOICE_ID."""
    resp = client("polly").synthesize_speech(
        Text=text,
        OutputFormat="mp3",
        VoiceId=voice_id or config.VOICE_ID,
        Engine="neural",
    )
    return resp["AudioStream"].read()


def send_voice(to: str, text: str, voice_id: Optional[str] = None) -> str:
    """Place a real phone call that speaks `text`, via End User Messaging Voice
    (SendVoiceMessage, Polly text-to-speech). The escalation page when a team member has
    not acknowledged.

    No voice origination number is provisioned yet, so when VOICE_ORIGINATION_NUMBER_ID is
    empty we log and return a 'no-voice-number' sentinel rather than raising: the call path
    is built and disclosed, and the WhatsApp audio page is primary. Returns the MessageId
    (or a dry-run id when SEND_MODE != live).

    Note: SendVoiceMessage VoiceId is an upper-case enum ('AMY'), unlike Polly's title-case
    'Amy', so we upper-case it here."""
    if not config.VOICE_ORIGINATION_NUMBER_ID:
        log.info("no voice origination number provisioned; skipping voice call to=%s", wa_id(to))
        return "no-voice-number"
    if not live():
        log.info("DRY-RUN voice call to=%s text=%s", wa_id(to), text)
        return f"dry-run-{uuid.uuid4().hex[:12]}"
    resp = client("pinpoint-sms-voice-v2").send_voice_message(
        DestinationPhoneNumber=wa_id(to),
        OriginationIdentity=config.VOICE_ORIGINATION_NUMBER_ID,
        MessageBody=text,
        MessageBodyTextType="TEXT",
        VoiceId=(voice_id or config.VOICE_ID).upper(),
    )
    return resp["MessageId"]
