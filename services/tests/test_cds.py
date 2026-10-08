"""Channel-layer tests for common.cds.

Two kinds of assertion:
  - dry mode (SEND_MODE unset, the conftest default): every send returns a dry-run id
    and makes no AWS call at all. The Stubbers have no queued responses, so any call
    would raise.
  - live mode: the client is a botocore Stubber and we assert the exact request shape
    that reaches AWS (mirrors ../arrearo/services/tests/test_cds.py).

The autouse `aws` fixture in conftest runs under moto and clears cds._clients before each
test, so a Stubbed client we inject with cds.set_client is the one the code uses.
"""
import io
import json

import boto3
import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber

from common import cds, config


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setenv("SEND_MODE", "live")


def stubbed(service):
    c = boto3.client(service, region_name="us-east-1")
    cds.set_client(service, c)
    return c, Stubber(c)


def streaming(data: bytes) -> StreamingBody:
    return StreamingBody(io.BytesIO(data), len(data))


# ── dry mode: no AWS call, a dry-run id ───────────────────────────────────────
def test_dry_text_never_calls_aws():
    _, st = stubbed("socialmessaging")          # nothing queued: any call raises
    with st:
        assert cds.send_whatsapp_text("447700900123", "Hi").startswith("dry-run-")
        st.assert_no_pending_responses()


def test_dry_raw_never_calls_aws():
    _, st = stubbed("socialmessaging")
    with st:
        out = cds.send_whatsapp_raw("447700900123", {"type": "interactive", "interactive": {}})
        assert out.startswith("dry-run-")


def test_dry_document_never_calls_aws():
    _, ss = stubbed("socialmessaging")
    _, s3 = stubbed("s3")
    with ss, s3:
        assert cds.send_whatsapp_document("447700900123", b"%PDF", "brief.pdf").startswith("dry-run-")


def test_dry_audio_never_calls_aws():
    _, ss = stubbed("socialmessaging")
    _, s3 = stubbed("s3")
    with ss, s3:
        assert cds.send_whatsapp_audio("447700900123", b"ID3mp3").startswith("dry-run-")


def test_dry_email_never_calls_aws():
    _, st = stubbed("sesv2")
    with st:
        assert cds.send_email("a@b.test", "s", "b").startswith("dry-run-")


def test_dry_voice_with_number(monkeypatch):
    """A number is provisioned but SEND_MODE is dry: a dry-run id, no call."""
    monkeypatch.setattr(config, "VOICE_ORIGINATION_NUMBER_ID", "phone-number-id-voice")
    _, st = stubbed("pinpoint-sms-voice-v2")
    with st:
        assert cds.send_voice("447700900123", "Please acknowledge").startswith("dry-run-")


# ── WhatsApp text (E.164 '+') ─────────────────────────────────────────────────
def test_send_whatsapp_text_exact_shape(live):
    c, st = stubbed("socialmessaging")
    msg = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": "+447700900123",
           "type": "text", "text": {"preview_url": False, "body": "Hi"}}
    st.add_response("send_whatsapp_message", {"messageId": "wamid.OUT"},
                    {"originationPhoneNumberId": config.ORIGINATION_PHONE_NUMBER_ID,
                     "message": json.dumps(msg).encode(), "metaApiVersion": "v20.0"})
    with st:
        assert cds.send_whatsapp_text("+44 7700 900123", "Hi") == "wamid.OUT"
        st.assert_no_pending_responses()


def test_send_whatsapp_text_threads_reply(live):
    c, st = stubbed("socialmessaging")
    msg = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": "+233200000001",
           "type": "text", "text": {"preview_url": False, "body": "ack"},
           "context": {"message_id": "wamid.IN"}}
    st.add_response("send_whatsapp_message", {"messageId": "wamid.R"},
                    {"originationPhoneNumberId": config.ORIGINATION_PHONE_NUMBER_ID,
                     "message": json.dumps(msg).encode(), "metaApiVersion": "v20.0"})
    with st:
        assert cds.send_whatsapp_text("233200000001", "ack", reply_to_wamid="wamid.IN") == "wamid.R"
        st.assert_no_pending_responses()


# ── WhatsApp raw / interactive ────────────────────────────────────────────────
def test_send_whatsapp_raw_interactive_exact_shape(live):
    c, st = stubbed("socialmessaging")
    interactive = {"type": "interactive", "interactive": {
        "type": "button", "body": {"text": "Acknowledge the 2pm page?"},
        "action": {"buttons": [{"type": "reply", "reply": {"id": "ack", "title": "Acknowledge"}}]}}}
    msg = {"messaging_product": "whatsapp", "recipient_type": "individual",
           "to": "+447700900123", **interactive}
    st.add_response("send_whatsapp_message", {"messageId": "wamid.INT"},
                    {"originationPhoneNumberId": config.ORIGINATION_PHONE_NUMBER_ID,
                     "message": json.dumps(msg).encode(), "metaApiVersion": "v20.0"})
    with st:
        assert cds.send_whatsapp_raw("447700900123", interactive) == "wamid.INT"
        st.assert_no_pending_responses()


# ── WhatsApp document (S3 put -> PostMedia -> send) ───────────────────────────
def test_send_whatsapp_document_full_flow(live, monkeypatch):
    monkeypatch.setattr(cds.uuid, "uuid4", lambda: _FixedUUID())
    _, ss = stubbed("socialmessaging")
    _, s3 = stubbed("s3")
    bucket = "media-bkt"
    key = f"outbound/{_FixedUUID.hex}/brief.pdf"
    s3.add_response("put_object", {}, {"Bucket": bucket, "Key": key, "Body": b"%PDF",
                                        "ContentType": "application/pdf"})
    ss.add_response("post_whatsapp_message_media", {"mediaId": "m-doc"},
                    {"originationPhoneNumberId": config.ORIGINATION_PHONE_NUMBER_ID,
                     "sourceS3File": {"bucketName": bucket, "key": key}})
    doc = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": "+447700900123",
           "type": "document", "document": {"id": "m-doc", "filename": "brief.pdf", "caption": "Case brief"}}
    ss.add_response("send_whatsapp_message", {"messageId": "wamid.DOC"},
                    {"originationPhoneNumberId": config.ORIGINATION_PHONE_NUMBER_ID,
                     "message": json.dumps(doc).encode(), "metaApiVersion": "v20.0"})
    with ss, s3:
        out = cds.send_whatsapp_document("447700900123", b"%PDF", "brief.pdf",
                                         caption="Case brief", bucket=bucket)
        assert out == "wamid.DOC"
        ss.assert_no_pending_responses()
        s3.assert_no_pending_responses()


# ── WhatsApp audio (S3 put -> PostMedia -> send audio) ────────────────────────
def test_send_whatsapp_audio_full_flow(live, monkeypatch):
    monkeypatch.setattr(cds.uuid, "uuid4", lambda: _FixedUUID())
    _, ss = stubbed("socialmessaging")
    _, s3 = stubbed("s3")
    bucket = "media-bkt"
    key = f"outbound/{_FixedUUID.hex}/page.mp3"
    s3.add_response("put_object", {}, {"Bucket": bucket, "Key": key, "Body": b"ID3mp3",
                                        "ContentType": "audio/mpeg"})
    ss.add_response("post_whatsapp_message_media", {"mediaId": "m-aud"},
                    {"originationPhoneNumberId": config.ORIGINATION_PHONE_NUMBER_ID,
                     "sourceS3File": {"bucketName": bucket, "key": key}})
    audio = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": "+447700900123",
             "type": "audio", "audio": {"id": "m-aud"}}
    ss.add_response("send_whatsapp_message", {"messageId": "wamid.AUD"},
                    {"originationPhoneNumberId": config.ORIGINATION_PHONE_NUMBER_ID,
                     "message": json.dumps(audio).encode(), "metaApiVersion": "v20.0"})
    with ss, s3:
        out = cds.send_whatsapp_audio("447700900123", b"ID3mp3", bucket=bucket)
        assert out == "wamid.AUD"
        ss.assert_no_pending_responses()
        s3.assert_no_pending_responses()


def test_send_whatsapp_audio_caption_sends_text_first(live, monkeypatch):
    """A caption has no home on a WhatsApp audio message, so it goes out as a short text
    before the audio. Two send_whatsapp_message calls: the text, then the audio."""
    monkeypatch.setattr(cds.uuid, "uuid4", lambda: _FixedUUID())
    _, ss = stubbed("socialmessaging")
    _, s3 = stubbed("s3")
    bucket = "media-bkt"
    key = f"outbound/{_FixedUUID.hex}/page.mp3"
    s3.add_response("put_object", {}, {"Bucket": bucket, "Key": key, "Body": b"ID3mp3",
                                        "ContentType": "audio/mpeg"})
    ss.add_response("post_whatsapp_message_media", {"mediaId": "m-aud"},
                    {"originationPhoneNumberId": config.ORIGINATION_PHONE_NUMBER_ID,
                     "sourceS3File": {"bucketName": bucket, "key": key}})
    text = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": "+447700900123",
            "type": "text", "text": {"preview_url": False, "body": "Urgent page for the 2pm"}}
    ss.add_response("send_whatsapp_message", {"messageId": "wamid.TXT"},
                    {"originationPhoneNumberId": config.ORIGINATION_PHONE_NUMBER_ID,
                     "message": json.dumps(text).encode(), "metaApiVersion": "v20.0"})
    audio = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": "+447700900123",
             "type": "audio", "audio": {"id": "m-aud"}}
    ss.add_response("send_whatsapp_message", {"messageId": "wamid.AUD"},
                    {"originationPhoneNumberId": config.ORIGINATION_PHONE_NUMBER_ID,
                     "message": json.dumps(audio).encode(), "metaApiVersion": "v20.0"})
    with ss, s3:
        out = cds.send_whatsapp_audio("447700900123", b"ID3mp3",
                                      caption="Urgent page for the 2pm", bucket=bucket)
        assert out == "wamid.AUD"
        ss.assert_no_pending_responses()
        s3.assert_no_pending_responses()


# ── inbound media + S3 read ───────────────────────────────────────────────────
def test_fetch_media_writes_to_s3(live):
    c, st = stubbed("socialmessaging")
    st.add_response("get_whatsapp_message_media", {"mimeType": "image/jpeg", "fileSize": 10},
                    {"mediaId": "m1", "originationPhoneNumberId": config.ORIGINATION_PHONE_NUMBER_ID,
                     "destinationS3File": {"bucketName": "bkt", "key": "k"}})
    with st:
        assert cds.fetch_whatsapp_media("m1", "bkt", "k")["mimeType"] == "image/jpeg"
        st.assert_no_pending_responses()


def test_read_s3_round_trips_bytes():
    """read_s3 is not gated by SEND_MODE; exercise it against moto S3."""
    s3 = boto3.client("s3", region_name="us-east-1")
    cds.set_client("s3", s3)
    s3.create_bucket(Bucket="tray-bkt")
    s3.put_object(Bucket="tray-bkt", Key="photos/before.jpg", Body=b"JPEGBYTES")
    assert cds.read_s3("tray-bkt", "photos/before.jpg") == b"JPEGBYTES"


# ── email ─────────────────────────────────────────────────────────────────────
def test_send_email_with_pdf_attachment(live):
    c, st = stubbed("sesv2")
    st.add_response("send_email", {"MessageId": "ses-1"}, {
        "FromEmailAddress": f"{config.BRAND} <{config.SES_SENDER}>",
        "Destination": {"ToAddresses": ["a@b.test"]},
        "Content": {"Simple": {
            "Subject": {"Data": "Worklist", "Charset": "UTF-8"},
            "Body": {"Text": {"Data": "body", "Charset": "UTF-8"}},
            "Attachments": [{"RawContent": b"%PDF", "FileName": "L.pdf", "ContentType": "application/pdf",
                             "ContentDisposition": "ATTACHMENT", "ContentTransferEncoding": "BASE64"}]}}})
    with st:
        assert cds.send_email("a@b.test", "Worklist", "body",
                              attachment={"filename": "L.pdf", "content": b"%PDF"}) == "ses-1"
        st.assert_no_pending_responses()


def test_send_email_reply_to(live):
    c, st = stubbed("sesv2")
    st.add_response("send_email", {"MessageId": "ses-2"}, {
        "FromEmailAddress": f"{config.BRAND} <{config.SES_SENDER}>",
        "Destination": {"ToAddresses": ["coord@hospital.test"]},
        "Content": {"Simple": {
            "Subject": {"Data": "Not ready", "Charset": "UTF-8"},
            "Body": {"Text": {"Data": "see board", "Charset": "UTF-8"}}}},
        "ReplyToAddresses": ["ops@hospital.test"]})
    with st:
        assert cds.send_email("coord@hospital.test", "Not ready", "see board",
                              reply_to="ops@hospital.test") == "ses-2"
        st.assert_no_pending_responses()


# ── Polly ─────────────────────────────────────────────────────────────────────
def test_synth_mp3_calls_polly(live):
    c, st = stubbed("polly")
    st.add_response("synthesize_speech",
                    {"AudioStream": streaming(b"MP3BYTES"), "ContentType": "audio/mpeg",
                     "RequestCharacters": 3},
                    {"Text": "Page", "OutputFormat": "mp3", "VoiceId": "Amy", "Engine": "neural"})
    with st:
        assert cds.synth_mp3("Page") == b"MP3BYTES"
        st.assert_no_pending_responses()


def test_synth_mp3_honours_voice_override(live):
    c, st = stubbed("polly")
    st.add_response("synthesize_speech",
                    {"AudioStream": streaming(b"x"), "ContentType": "audio/mpeg", "RequestCharacters": 1},
                    {"Text": "Hi", "OutputFormat": "mp3", "VoiceId": "Brian", "Engine": "neural"})
    with st:
        assert cds.synth_mp3("Hi", voice_id="Brian") == b"x"
        st.assert_no_pending_responses()


# ── Voice (SendVoiceMessage) ──────────────────────────────────────────────────
def test_send_voice_no_number_sentinel(monkeypatch, live):
    """No origination number provisioned: a sentinel, never a raise, even when live."""
    monkeypatch.setattr(config, "VOICE_ORIGINATION_NUMBER_ID", "")
    _, st = stubbed("pinpoint-sms-voice-v2")        # nothing queued: a call would raise
    with st:
        assert cds.send_voice("447700900123", "Acknowledge the 2pm") == "no-voice-number"
        st.assert_no_pending_responses()


def test_send_voice_live_exact_shape(monkeypatch, live):
    monkeypatch.setattr(config, "VOICE_ORIGINATION_NUMBER_ID", "phone-number-id-voice")
    c, st = stubbed("pinpoint-sms-voice-v2")
    st.add_response("send_voice_message", {"MessageId": "voice-1"}, {
        "DestinationPhoneNumber": "+447700900123",
        "OriginationIdentity": "phone-number-id-voice",
        "MessageBody": "Please acknowledge the 2pm page",
        "MessageBodyTextType": "TEXT",
        "VoiceId": "AMY"})
    with st:
        assert cds.send_voice("44 7700 900123", "Please acknowledge the 2pm page") == "voice-1"
        st.assert_no_pending_responses()


class _FixedUUID:
    """Deterministic stand-in so the S3 key in document/audio sends is predictable."""
    hex = "00000000000000000000000000000000"
