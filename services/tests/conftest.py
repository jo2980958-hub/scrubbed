"""Shared test harness: moto DynamoDB for every Scrubbed table (mirrors infra/template.yaml),
the layer on the path, and a few fixtures. The data-model module builds accessors to these keys.
"""
import os
import sys
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "layer" / "python"), str(ROOT / "functions")]
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.pop("SEND_MODE", None)

from common import cds, config, db  # noqa: E402


def _gsi(name, hash_key, range_key=None):
    keys = [{"AttributeName": hash_key, "KeyType": "HASH"}]
    if range_key:
        keys.append({"AttributeName": range_key, "KeyType": "RANGE"})
    return {"IndexName": name, "KeySchema": keys, "Projection": {"ProjectionType": "ALL"}}


# (attrs, key schema, gsis, extra gsi attrs) per table — the data model is built to these.
SCHEMAS = {
    config.TBL_STAFF: ([("staffId", "S")], [("staffId", "HASH")],
                       [_gsi("byEmail", "email"), _gsi("byWhatsapp", "whatsappNumber")],
                       [("email", "S"), ("whatsappNumber", "S")]),
    config.TBL_CASES: ([("caseId", "S")], [("caseId", "HASH")],
                       [_gsi("byHospital", "hospitalId", "scheduledAt"),
                        _gsi("bySurgeon", "surgeonId", "scheduledAt")],
                       [("hospitalId", "S"), ("scheduledAt", "S"), ("surgeonId", "S")]),
    config.TBL_PATIENTS: ([("patientId", "S")], [("patientId", "HASH")],
                          [_gsi("byWhatsapp", "whatsappNumber")], [("whatsappNumber", "S")]),
    config.TBL_TRAYS: ([("caseId", "S")], [("caseId", "HASH")], [], []),
    config.TBL_READINESS: ([("caseId", "S")], [("caseId", "HASH")], [], []),
    config.TBL_PAGES: ([("pageId", "S"), ("sk", "S")], [("pageId", "HASH"), ("sk", "RANGE")],
                       [_gsi("byCase", "caseId", "createdAt")], [("caseId", "S"), ("createdAt", "S")]),
    config.TBL_FORMS: ([("formId", "S")], [("formId", "HASH")],
                       [_gsi("byCase", "caseId", "createdAt")], [("caseId", "S"), ("createdAt", "S")]),
    config.TBL_EVENTS: ([("caseId", "S"), ("createdAt#seq", "S")],
                        [("caseId", "HASH"), ("createdAt#seq", "RANGE")], [], []),
    config.TBL_CONVERSATIONS: ([("whatsappNumber", "S"), ("createdAt#messageId", "S")],
                               [("whatsappNumber", "HASH"), ("createdAt#messageId", "RANGE")],
                               [_gsi("byMessageId", "messageId")], [("messageId", "S")]),
    config.TBL_WA_SESSIONS: ([("waNumber", "S")], [("waNumber", "HASH")], [], []),
}


@pytest.fixture(autouse=True)
def aws():
    with mock_aws():
        res = boto3.resource("dynamodb", region_name="us-east-1")
        for name, (attrs, keys, gsis, gsi_attrs) in SCHEMAS.items():
            defs = {a: t for a, t in attrs + gsi_attrs}
            kw = dict(TableName=name, BillingMode="PAY_PER_REQUEST",
                      AttributeDefinitions=[{"AttributeName": a, "AttributeType": t} for a, t in defs.items()],
                      KeySchema=[{"AttributeName": a, "KeyType": k} for a, k in keys])
            if gsis:
                kw["GlobalSecondaryIndexes"] = gsis
            res.create_table(**kw)
        db.set_resource(res)
        cds._clients.clear()
        yield res


# Shared fixtures (available once the data-model accessors are implemented). The
# data-model module builds create_staff/create_patient/create_case to accept these fields.
@pytest.fixture
def staff():
    return db.create_staff({"name": "Dr Ada Lovelace", "role": "surgeon", "email": "ada@hospital.test",
                            "whatsappNumber": "+233200000001", "hospitalId": "hosp-1"})


@pytest.fixture
def patient():
    return db.create_patient({"name": "John Doe", "whatsappNumber": "+233200000009",
                              "hospitalId": "hosp-1", "balancePence": 0})


@pytest.fixture
def case(staff, patient):
    return db.create_case({"hospitalId": "hosp-1", "surgeonId": staff["staffId"],
                           "patientId": patient["patientId"], "procedure": "Laparoscopic cholecystectomy",
                           "theatre": "Theatre 2", "scheduledAt": "2026-10-09T14:00:00Z",
                           "team": [staff["staffId"]]})
