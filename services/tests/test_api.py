"""The dashboard API (functions/api.py). It is the one surface where a signed-in
coordinator reads patient PHI, so its tenancy guards are tested directly: an unregistered
caller is refused, every read is scoped to the caller's own hospital, a case cannot leak a
cross-hospital patient, staff creation is role-gated, and case writes are field-allowlisted
so the body cannot move a case to another hospital."""
import json

import pytest

from common import db
import api


def _event(method, path, email, body=None, query=None):
    return {
        "requestContext": {"http": {"method": method},
                           "authorizer": {"jwt": {"claims": {"email": email} if email else {}}}},
        "rawPath": path,
        "queryStringParameters": query,
        "body": json.dumps(body) if body is not None else None,
    }


def _json(resp):
    return json.loads(resp["body"])


@pytest.fixture
def coord():
    return db.create_staff({"name": "Coordinator Carol", "role": "coordinator",
                            "email": "carol@h1.test", "hospitalId": "hosp-1"})


@pytest.fixture
def nurse():
    return db.create_staff({"name": "Nurse Nia", "role": "scrub nurse",
                            "email": "nia@h1.test", "hospitalId": "hosp-1"})


def test_unregistered_email_is_401():
    resp = api.handler(_event("GET", "/cases", "stranger@nowhere.test"))
    assert resp["statusCode"] == 401


def test_no_email_claim_is_401():
    resp = api.handler(_event("GET", "/cases", None))
    assert resp["statusCode"] == 401


def test_options_preflight_bypasses_auth():
    resp = api.handler(_event("OPTIONS", "/cases", None))
    assert resp["statusCode"] == 204


def test_cases_list_is_scoped_to_the_callers_hospital(coord):
    mine = db.create_case({"hospitalId": "hosp-1", "surgeonId": "s1",
                           "scheduledAt": "2026-10-09T09:00:00Z", "procedure": "Mine"})
    db.create_case({"hospitalId": "hosp-2", "surgeonId": "s2",
                    "scheduledAt": "2026-10-09T09:00:00Z", "procedure": "Theirs"})
    resp = api.handler(_event("GET", "/cases", coord["email"]))
    assert resp["statusCode"] == 200
    ids = [c["caseId"] for c in _json(resp)["cases"]]
    assert ids == [mine["caseId"]]


def test_other_hospitals_case_detail_is_404(coord):
    other = db.create_case({"hospitalId": "hosp-2", "surgeonId": "s2",
                            "scheduledAt": "2026-10-09T09:00:00Z", "procedure": "Theirs"})
    resp = api.handler(_event("GET", f"/cases/{other['caseId']}", coord["email"]))
    assert resp["statusCode"] == 404


def test_case_detail_does_not_leak_a_cross_hospital_patient(coord):
    # The attack: an owned case whose patientId points at another hospital's patient.
    victim = db.create_patient({"name": "Other-Hospital Patient", "whatsappNumber": "+233200000044",
                                "hospitalId": "hosp-2"})
    case = db.create_case({"hospitalId": "hosp-1", "surgeonId": "s1",
                           "scheduledAt": "2026-10-09T09:00:00Z", "procedure": "Mine",
                           "patientId": victim["patientId"]})
    resp = api.handler(_event("GET", f"/cases/{case['caseId']}", coord["email"]))
    assert resp["statusCode"] == 200
    # Case is owned (hosp-1) so it is visible, but the cross-hospital patient is withheld.
    assert _json(resp)["patient"] is None


def test_post_staff_is_role_gated(coord, nurse):
    body = {"name": "New Person", "role": "scrub nurse", "email": "new@h1.test"}
    # A nurse cannot add staff.
    assert api.handler(_event("POST", "/staff", nurse["email"], body))["statusCode"] == 403
    # A coordinator can, and the new record is stamped to the coordinator's hospital.
    resp = api.handler(_event("POST", "/staff", coord["email"], body))
    assert resp["statusCode"] == 200
    assert _json(resp)["staff"]["hospitalId"] == "hosp-1"


def test_post_case_rejects_a_cross_hospital_patient(coord):
    victim = db.create_patient({"name": "Theirs", "hospitalId": "hosp-2"})
    resp = api.handler(_event("POST", "/cases", coord["email"],
                              {"surgeonId": "s1", "scheduledAt": "2026-10-09T09:00:00Z",
                               "procedure": "X", "patientId": victim["patientId"]}))
    assert resp["statusCode"] == 400


def test_patch_case_cannot_move_it_to_another_hospital(coord):
    case = db.create_case({"hospitalId": "hosp-1", "surgeonId": "s1",
                           "scheduledAt": "2026-10-09T09:00:00Z", "procedure": "Mine"})
    resp = api.handler(_event("PATCH", f"/cases/{case['caseId']}", coord["email"],
                              {"hospitalId": "hosp-2", "procedure": "Renamed"}))
    assert resp["statusCode"] == 200
    assert _json(resp)["case"]["hospitalId"] == "hosp-1"       # hospitalId not in the allowlist
    assert _json(resp)["case"]["procedure"] == "Renamed"
