"""Data-model tests for Scrubbed. Each group exercises create/get/update, the
GSIs, and the edge cases that matter at runtime (case-insensitive email, +E.164
normalisation, the page ladder, the tray before/after merge, event ordering and
WhatsApp idempotency). The aws fixture (conftest) gives every test fresh moto
tables; staff/case/patient are the shared fixtures.
"""
from common import db


# ── staff ─────────────────────────────────────────────────────────────────────
def test_staff_create_get_and_normalisation():
    s = db.create_staff({"name": "Dr Grace Hopper", "role": "surgeon",
                         "email": "  GRACE@Hospital.Test  ", "whatsappNumber": "233200000020",
                         "hospitalId": "hosp-1"})
    assert s["staffId"]
    assert s["email"] == "grace@hospital.test"          # trimmed and lowercased
    assert s["whatsappNumber"] == "+233200000020"       # bare digits -> +E.164
    assert db.get_staff(s["staffId"])["name"] == "Dr Grace Hopper"
    assert db.get_staff("nope") is None


def test_staff_lookup_by_email_is_case_insensitive(staff):
    assert db.get_staff_by_email("ADA@HOSPITAL.TEST")["staffId"] == staff["staffId"]
    assert db.get_staff_by_email("ada@hospital.test")["staffId"] == staff["staffId"]
    assert db.get_staff_by_email("missing@hospital.test") is None
    assert db.get_staff_by_email("") is None


def test_staff_lookup_by_whatsapp_accepts_bare_digits(staff):
    assert db.get_staff_by_whatsapp("233200000001")["staffId"] == staff["staffId"]
    assert db.get_staff_by_whatsapp("+233200000001")["staffId"] == staff["staffId"]
    assert db.get_staff_by_whatsapp("000") is None


def test_staff_update_renormalises_and_relocates_gsis(staff):
    db.update_staff(staff["staffId"], {"email": "Ada.NEW@Hospital.Test",
                                       "whatsappNumber": "233200000099", "role": "lead surgeon"})
    assert db.get_staff(staff["staffId"])["role"] == "lead surgeon"
    assert db.get_staff_by_email("ada.new@hospital.test")["staffId"] == staff["staffId"]
    assert db.get_staff_by_whatsapp("233200000099")["staffId"] == staff["staffId"]
    assert db.get_staff_by_email("ada@hospital.test") is None   # old email no longer resolves


def test_list_staff_filters_by_hospital(staff):
    db.create_staff({"name": "Other Hosp", "role": "nurse", "email": "n@other.test",
                     "whatsappNumber": "+233200000030", "hospitalId": "hosp-2"})
    here = db.list_staff("hosp-1")
    assert [s["staffId"] for s in here] == [staff["staffId"]]
    assert len(db.list_staff()) == 2                     # no filter returns everyone


# ── cases ──────────────────────────────────────────────────────────────────────
def test_case_create_requires_core_fields(staff, patient):
    for missing in ({"surgeonId": "x", "scheduledAt": "t"},
                    {"hospitalId": "h", "scheduledAt": "t"},
                    {"hospitalId": "h", "surgeonId": "x"}):
        try:
            db.create_case(missing)
            assert False, f"expected ValueError for {missing}"
        except ValueError:
            pass


def test_case_get_update(case):
    assert db.get_case(case["caseId"])["procedure"] == "Laparoscopic cholecystectomy"
    assert db.get_case(case["caseId"])["status"] == "scheduled"
    db.update_case(case["caseId"], {"status": "ready", "theatre": "Theatre 5"})
    got = db.get_case(case["caseId"])
    assert got["status"] == "ready" and got["theatre"] == "Theatre 5"
    assert db.get_case("nope") is None


def test_list_cases_by_hospital_with_day_filter(staff, patient):
    db.create_case({"hospitalId": "hosp-1", "surgeonId": staff["staffId"],
                    "patientId": patient["patientId"], "scheduledAt": "2026-10-09T08:00:00Z"})
    db.create_case({"hospitalId": "hosp-1", "surgeonId": staff["staffId"],
                    "patientId": patient["patientId"], "scheduledAt": "2026-10-10T09:00:00Z"})
    db.create_case({"hospitalId": "hosp-2", "surgeonId": staff["staffId"],
                    "patientId": patient["patientId"], "scheduledAt": "2026-10-09T10:00:00Z"})
    all_h1 = db.list_cases("hosp-1")
    assert len(all_h1) == 2
    assert [c["scheduledAt"] for c in all_h1] == sorted(c["scheduledAt"] for c in all_h1)  # ascending
    day = db.list_cases("hosp-1", day="2026-10-09")
    assert [c["scheduledAt"] for c in day] == ["2026-10-09T08:00:00Z"]


def test_list_cases_for_surgeon(staff, patient):
    other = db.create_staff({"name": "Dr Two", "role": "surgeon", "email": "two@hospital.test",
                             "whatsappNumber": "+233200000040", "hospitalId": "hosp-1"})
    mine = db.create_case({"hospitalId": "hosp-1", "surgeonId": staff["staffId"],
                           "patientId": patient["patientId"], "scheduledAt": "2026-10-09T14:00:00Z"})
    db.create_case({"hospitalId": "hosp-1", "surgeonId": other["staffId"],
                    "patientId": patient["patientId"], "scheduledAt": "2026-10-09T15:00:00Z"})
    rows = db.list_cases_for_surgeon(staff["staffId"])
    assert [c["caseId"] for c in rows] == [mine["caseId"]]
    assert db.list_cases_for_surgeon(staff["staffId"], day="2026-10-10") == []


# ── patients ───────────────────────────────────────────────────────────────────
def test_patient_create_get_update_and_whatsapp_gsi(patient):
    assert db.get_patient(patient["patientId"])["name"] == "John Doe"
    assert db.get_patient_by_whatsapp("233200000009")["patientId"] == patient["patientId"]
    db.update_patient(patient["patientId"], {"balancePence": 4500, "whatsappNumber": "233200000011"})
    assert db.get_patient(patient["patientId"])["balancePence"] == 4500
    assert db.get_patient_by_whatsapp("+233200000011")["patientId"] == patient["patientId"]
    assert db.get_patient_by_whatsapp("233200000009") is None   # moved off the old number
    assert db.get_patient_by_whatsapp("") is None


# ── trays ──────────────────────────────────────────────────────────────────────
def test_tray_before_after_merge(case):
    assert db.get_tray(case["caseId"]) is None
    db.set_tray_catalogue(case["caseId"], "before", {"artery forceps": 6, "scalpel handle": 2},
                          photo_key="s3://trays/before.jpg")
    tray = db.set_tray_catalogue(case["caseId"], "after", {"artery forceps": 5, "scalpel handle": 2})
    assert tray["before"]["catalogue"] == {"artery forceps": 6, "scalpel handle": 2}
    assert tray["before"]["photoKey"] == "s3://trays/before.jpg"
    assert tray["after"]["catalogue"] == {"artery forceps": 5, "scalpel handle": 2}
    assert tray["after"].get("photoKey") in (None,)      # no key supplied, dropped
    assert tray["before"]["at"] and tray["after"]["at"]
    # setting a phase again replaces only that phase
    db.set_tray_catalogue(case["caseId"], "before", {"artery forceps": 7})
    again = db.get_tray(case["caseId"])
    assert again["before"]["catalogue"] == {"artery forceps": 7}
    assert again["after"]["catalogue"] == {"artery forceps": 5, "scalpel handle": 2}


# ── readiness ──────────────────────────────────────────────────────────────────
def test_readiness_items(case):
    assert db.get_readiness(case["caseId"]) == {}
    db.set_readiness_item(case["caseId"], "fasting", True)
    db.set_readiness_item(case["caseId"], "consent", False)
    items = db.set_readiness_item(case["caseId"], "balanceCleared", True)
    assert items == {"fasting": True, "consent": False, "balanceCleared": True}
    assert db.get_readiness(case["caseId"]) == {"fasting": True, "consent": False, "balanceCleared": True}
    db.set_readiness_item(case["caseId"], "consent", True)   # flip one
    assert db.get_readiness(case["caseId"])["consent"] is True


# ── pages: the per-recipient ladder ─────────────────────────────────────────────
def test_page_recipient_lifecycle(case, staff):
    page = db.create_page(case["caseId"], created_by=staff["staffId"], body="Theatre 2 at 14:00",
                          urgent=True)
    assert page["sk"] == "meta" and page["urgent"] is True
    db.add_page_recipient(page["pageId"], staff["staffId"], "233200000001")
    db.add_page_recipient(page["pageId"], "staff-2", "+233200000002")
    recips = db.list_page_recipients(page["pageId"])
    assert len(recips) == 2
    assert all(r["status"] == "sent" and r["sentAt"] for r in recips)
    assert {r["number"] for r in recips} == {"+233200000001", "+233200000002"}

    # one recipient walks sent -> delivered -> read -> acknowledged
    db.record_page_status(page["pageId"], "233200000001", "delivered")
    db.record_page_status(page["pageId"], "233200000001", "read")
    acked = db.acknowledge_page(page["pageId"], "233200000001")
    assert acked["status"] == "acknowledged"
    assert acked["deliveredAt"] and acked["readAt"] and acknowledged_time(acked)

    pending = db.pending_page_recipients(page["pageId"])
    assert [p["number"] for p in pending] == ["+233200000002"]   # the other one still owes an ack


def acknowledged_time(r):
    return r.get("acknowledgedAt")


def test_list_pages_for_case_returns_only_meta(case, staff):
    p1 = db.create_page(case["caseId"], staff["staffId"], "first")
    db.add_page_recipient(p1["pageId"], staff["staffId"], "+233200000001")
    p2 = db.create_page(case["caseId"], staff["staffId"], "second")
    pages = db.list_pages_for_case(case["caseId"])
    assert {p["pageId"] for p in pages} == {p1["pageId"], p2["pageId"]}
    assert all(p["sk"] == "meta" for p in pages)        # recipient rows excluded
    assert [p["createdAt"] for p in pages] == sorted(p["createdAt"] for p in pages)


# ── forms ──────────────────────────────────────────────────────────────────────
def test_form_lifecycle_and_case_gsi(case, staff):
    form = db.create_form(case["caseId"], staff["staffId"], kind="handover")
    assert form["status"] == "sent" and form["kind"] == "handover"
    db.create_form(case["caseId"], staff["staffId"], kind="status")
    assert len(db.list_forms_for_case(case["caseId"])) == 2
    uploaded = db.attach_form_upload(form["formId"], "s3://forms/handover.pdf")
    assert uploaded["status"] == "uploaded"
    assert uploaded["s3Key"] == "s3://forms/handover.pdf" and uploaded["uploadedAt"]
    assert db.get_form(form["formId"])["status"] == "uploaded"
    assert db.get_form("nope") is None


# ── events: audit timeline ───────────────────────────────────────────────────────
def test_events_ordered_ascending(case):
    for t in ("case.created", "team.paged", "readiness.updated", "tray.flagged"):
        db.add_event(case["caseId"], t, actor="agent", detail={"n": 1})
    events = db.list_events(case["caseId"])
    assert [e["type"] for e in events] == ["case.created", "team.paged", "readiness.updated", "tray.flagged"]
    assert all(e["actor"] == "agent" for e in events)
    assert db.list_events("other-case") == []


def test_events_same_timestamp_keep_insertion_order(case, monkeypatch):
    monkeypatch.setattr(db, "now_iso", lambda: "2026-10-09T14:00:00.000000Z")
    for t in ("a", "b", "c"):
        db.add_event(case["caseId"], t)
    assert [e["type"] for e in db.list_events(case["caseId"])] == ["a", "b", "c"]


# ── conversations + idempotency ──────────────────────────────────────────────────
def test_conversation_add_and_list_newest_last():
    db.add_message("233200000009", "in", "wamid.1", "hello", intent="greeting")
    db.add_message("+233200000009", "out", "wamid.2", "instructions sent")
    msgs = db.list_messages("233200000009")
    assert [m["body"] for m in msgs] == ["hello", "instructions sent"]   # oldest first, newest last
    assert msgs[0]["intent"] == "greeting"
    assert msgs[0]["messageId"] == "wamid.1"


def test_conversation_list_respects_limit():
    for i in range(5):
        db.add_message("233200000009", "in", f"wamid.{i}", f"m{i}")
    recent = db.list_messages("233200000009", limit=2)
    assert [m["body"] for m in recent] == ["m3", "m4"]   # the two newest, newest last


def test_record_delivery_finds_by_message_id():
    db.add_message("233200000009", "out", "wamid.D", "page")
    updated = db.record_delivery("wamid.D", "delivered")
    assert updated["status"] == "delivered" and updated["deliveredAt"]
    db.record_delivery("wamid.D", "read")
    row = db.list_messages("233200000009")[-1]
    assert row["status"] == "read" and row["readAt"]
    assert db.record_delivery("wamid.unknown", "delivered") is None


def test_claim_message_idempotency():
    assert db.claim_message("wamid.CLAIM") is True
    assert db.claim_message("wamid.CLAIM") is False     # second delivery is a no-op
    assert db.claim_message("wamid.OTHER") is True
