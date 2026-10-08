"""Runtime wrappers around the CDS messaging SDKs. One boto3 call each.

- End User Messaging Social -> socialmessaging (WhatsApp text/interactive/audio/document, media)
- Amazon SES v2             -> sesv2 (email)
- End User Messaging Voice  -> pinpoint-sms-voice-v2 (the call page)
- Amazon Polly              -> polly (synthesise the audio note)

The infra here (live/client/set_client/wa_id) is real so tests can stub clients; the
channel sends are filled by the CDS-channels module.
"""
from __future__ import annotations

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


# ── channels (contracts; the CDS-channels module fills the bodies) ────────────
def send_whatsapp_text(to: str, body: str, reply_to_wamid: Optional[str] = None) -> str: raise NotImplementedError
def send_whatsapp_raw(to: str, message: dict) -> str: raise NotImplementedError          # interactive/document/audio
def send_whatsapp_audio(to: str, data: bytes, caption: Optional[str] = None, bucket: Optional[str] = None) -> str: raise NotImplementedError
def send_whatsapp_document(to: str, data: bytes, filename: str, caption: Optional[str] = None, bucket: Optional[str] = None) -> str: raise NotImplementedError
def fetch_whatsapp_media(media_id: str, bucket: str, key: str) -> dict: raise NotImplementedError
def read_s3(bucket: str, key: str) -> bytes: raise NotImplementedError
def send_email(to: str, subject: str, body: str, attachment: Optional[dict] = None,
               from_addr: Optional[str] = None, reply_to: Optional[str] = None) -> str: raise NotImplementedError
def send_voice(to: str, text: str, voice_id: Optional[str] = None) -> str: raise NotImplementedError   # SendVoiceMessage
def synth_mp3(text: str, voice_id: Optional[str] = None) -> bytes: raise NotImplementedError           # Polly -> mp3
