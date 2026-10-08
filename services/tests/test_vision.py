"""The instrument-tray second check: Claude vision reads a photo into a structured catalogue.

The model only reads the picture. safety.instrument_diff decides, and the manual WHO count
is authoritative. These tests pin the reading and the normalising, not any count decision.
"""
from agent import llm, vision


class FakeBedrock:
    """A fake bedrock-runtime client: returns queued tool inputs. Mirrors Arrearo's fake."""

    def __init__(self, tool_inputs=(), texts=()):
        self.tool_inputs, self.texts, self.calls = list(tool_inputs), list(texts), []

    def converse(self, **kw):
        self.calls.append(kw)
        if "toolConfig" in kw:
            name = kw["toolConfig"]["tools"][0]["toolSpec"]["name"]
            return {"output": {"message": {"content": [{"toolUse": {"name": name, "input": self.tool_inputs.pop(0)}}]}},
                    "stopReason": "tool_use"}
        return {"output": {"message": {"content": [{"text": self.texts.pop(0)}]}}, "stopReason": "end_turn"}


def test_catalogue_normalises_items_and_confidence():
    fake = FakeBedrock([{"items": [
        {"name": "Artery forceps", "count": 6, "confidence": 0.92},
        {"name": "scalpel handle", "count": 2, "confidence": 0.88},
        {"name": "swab", "count": 10, "confidence": 0.8},
    ], "notes": "tray laid out clearly"}])
    llm.set_client(fake)

    r = vision.catalogue_tray(b"\xff\xd8", "image/jpeg")

    assert r["items"] == {"artery forceps": 6, "scalpel handle": 2, "swab": 10}
    assert r["confidence"] == {"artery forceps": 0.92, "scalpel handle": 0.88, "swab": 0.8}
    assert r["notes"] == "tray laid out clearly"


def test_names_are_lowercased_and_duplicate_lines_summed():
    fake = FakeBedrock([{"items": [
        {"name": "Artery Forceps", "count": 4, "confidence": 0.9},
        {"name": " artery forceps ", "count": 2, "confidence": 0.7},
        {"name": "SCALPEL HANDLE", "count": 1, "confidence": 0.95},
    ]}])
    llm.set_client(fake)

    r = vision.catalogue_tray(b"\xff\xd8", "image/jpeg")

    # The two artery-forceps lines fold into one summed entry.
    assert r["items"] == {"artery forceps": 6, "scalpel handle": 1}
    # The lowest confidence of the folded lines is kept, as the cautious figure.
    assert r["confidence"]["artery forceps"] == 0.7


def test_low_confidence_lines_are_flagged_for_a_human():
    fake = FakeBedrock([{"items": [
        {"name": "artery forceps", "count": 6, "confidence": 0.95},
        {"name": "needle holder", "count": 1, "confidence": 0.3},
        {"name": "mosquito clamp", "count": 2, "confidence": 0.41},
    ], "notes": "some overlap at the back"}])
    llm.set_client(fake)

    r = vision.catalogue_tray(b"\xff\xd8", "image/jpeg")

    # Everything the model saw is still catalogued; the uncertain lines are only flagged.
    assert r["items"] == {"artery forceps": 6, "needle holder": 1, "mosquito clamp": 2}
    assert "please verify" in r["notes"]
    assert "needle holder" in r["notes"] and "mosquito clamp" in r["notes"]
    assert "artery forceps" not in r["notes"].split("please verify")[1]
    assert r["notes"].startswith("some overlap at the back")


def test_empty_items_returns_the_safe_default():
    llm.set_client(FakeBedrock([{"items": [], "notes": "blurred photo"}]))
    r = vision.catalogue_tray(b"\xff\xd8", "image/jpeg")
    assert r == {"items": {}, "confidence": {},
                 "notes": "could not read the tray; please send a clearer photo"}


def test_garbage_lines_are_dropped_and_fall_back_to_default():
    # No usable name, a zero count, and a non-numeric count: none survive.
    llm.set_client(FakeBedrock([{"items": [
        {"name": "", "count": 5, "confidence": 0.9},
        {"name": "swab", "count": 0, "confidence": 0.9},
        {"name": "clamp", "count": "lots", "confidence": 0.9},
    ]}]))
    r = vision.catalogue_tray(b"\xff\xd8", "image/jpeg")
    assert r == vision._SAFE_DEFAULT
    assert r["items"] == {}


def test_model_returning_no_tool_call_is_safe():
    # converse_tool raises when the model returns no tool use; the check stays silent.
    llm.set_client(FakeBedrock(tool_inputs=[]))
    r = vision.catalogue_tray(b"\xff\xd8", "image/png")
    assert r["items"] == {} and "clearer photo" in r["notes"]


def test_request_sends_an_image_block_and_forces_the_tool():
    fake = FakeBedrock([{"items": [{"name": "swab", "count": 3, "confidence": 0.9}]}])
    llm.set_client(fake)
    vision.catalogue_tray(b"\xff\xd8\x11\x22", "image/png")

    content = fake.calls[0]["messages"][0]["content"]
    img = content[0]["image"]
    assert img["format"] == "png"
    assert img["source"]["bytes"] == b"\xff\xd8\x11\x22"
    # The tool is forced, so the model must answer in the catalogue schema.
    assert fake.calls[0]["toolConfig"]["toolChoice"] == {"tool": {"name": "catalogue_tray"}}


def test_unknown_mime_falls_back_to_jpeg_rather_than_crashing():
    fake = FakeBedrock([{"items": [{"name": "swab", "count": 1, "confidence": 0.9}]}])
    llm.set_client(fake)
    vision.catalogue_tray(b"\xff\xd8", "application/octet-stream")
    assert fake.calls[0]["messages"][0]["content"][0]["image"]["format"] == "jpeg"


def test_catalogue_feeds_the_deterministic_diff():
    # The output map is exactly what safety.instrument_diff compares. A clamp removed
    # after the case must show up as unaccounted. The model never makes this call.
    from safety import engine

    llm.set_client(FakeBedrock([{"items": [
        {"name": "artery forceps", "count": 6, "confidence": 0.95},
        {"name": "clamp", "count": 2, "confidence": 0.95},
    ]}]))
    before = vision.catalogue_tray(b"\xff\xd8", "image/jpeg")

    llm.set_client(FakeBedrock([{"items": [
        {"name": "artery forceps", "count": 6, "confidence": 0.95},
        {"name": "clamp", "count": 1, "confidence": 0.95},
    ]}]))
    after = vision.catalogue_tray(b"\xff\xd8", "image/jpeg")

    diff = engine.instrument_diff(before["items"], after["items"])
    assert diff["ok"] is False
    assert any(f["item"] == "clamp" and f["missing"] == 1 for f in diff["flags"])
