"""Seed a demo hospital, team, patient and theatre list into the live Scrubbed tables.

Run with the project venv so the Lambda layer is importable:
    cd scrubbed && .venv/bin/python infra/seed.py

Idempotent-ish: it clears the demo hospital's rows first, then inserts a fresh set. The
coordinator's number and email are the ones to test the WhatsApp login + staff app with.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "services" / "layer" / "python")]
os.environ.setdefault("AWS_REGION", "us-east-1")

from common import config, db  # noqa: E402

HOSPITAL = "stald"            # hospitalId (opaque)

# The number/email you log in with on WhatsApp. The coordinator sees the whole board and
# can open any case, run the checklist, page the team and do the tray second-count.
COORD_NUMBER = os.environ.get("DEMO_COORD_NUMBER", "+233547738808")
COORD_EMAIL = os.environ.get("DEMO_COORD_EMAIL", "roger@brownshift.com")


def _today_at(hour: int, minute: int = 0) -> str:
    now = datetime.now(timezone.utc)
    when = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if when < now - timedelta(hours=1):
        when = when + timedelta(days=1)       # if it's already past, use tomorrow
    return when.isoformat(timespec="seconds").replace("+00:00", "Z")


def main() -> None:
    print(f"Seeding hospital {HOSPITAL!r} into {config.APP_SLUG} tables ({config.REGION})")

    # Team. The coordinator has a real number (for the WhatsApp login + ack test); the
    # surgeon and nurse have none, so paging notes them as a roster member to chase rather
    # than sending to a number that is not on WhatsApp.
    coord = db.create_staff({"name": "Roger (Coordinator)", "role": "coordinator",
                             "email": COORD_EMAIL, "whatsappNumber": COORD_NUMBER,
                             "hospitalId": HOSPITAL})
    surgeon = db.create_staff({"name": "Miss Ama Boateng", "role": "consultant surgeon",
                               "email": "ama.boateng@stald.test", "hospitalId": HOSPITAL})
    nurse = db.create_staff({"name": "Kwesi Appiah", "role": "scrub nurse",
                             "email": "kwesi.appiah@stald.test", "hospitalId": HOSPITAL})

    patient = db.create_patient({"name": "Efua Mensah", "whatsappNumber": "+233200000009",
                                 "hospitalId": HOSPITAL})
    patient2 = db.create_patient({"name": "Yaw Darko", "whatsappNumber": "+233200000010",
                                  "hospitalId": HOSPITAL})

    team = [coord["staffId"], surgeon["staffId"], nurse["staffId"]]

    case1 = db.create_case({"hospitalId": HOSPITAL, "surgeonId": surgeon["staffId"],
                            "patientId": patient["patientId"],
                            "procedure": "Laparoscopic cholecystectomy", "theatre": "Theatre 2",
                            "scheduledAt": _today_at(14, 0), "team": team})
    # Partly ready: consent + fasting done, balance and team ack still outstanding -> at risk.
    db.set_readiness_item(case1["caseId"], "consent", True)
    db.set_readiness_item(case1["caseId"], "fasting_confirmed", True)

    case2 = db.create_case({"hospitalId": HOSPITAL, "surgeonId": surgeon["staffId"],
                            "patientId": patient2["patientId"],
                            "procedure": "Inguinal hernia repair", "theatre": "Theatre 1",
                            "scheduledAt": _today_at(9, 30), "team": team})
    for item in ("consent", "fasting_confirmed", "balance_cleared", "team_confirmed"):
        db.set_readiness_item(case2["caseId"], item, True)   # fully ready

    print("Seeded:")
    print(f"  coordinator  {coord['name']}  login email {COORD_EMAIL}  number {COORD_NUMBER}")
    print(f"  surgeon      {surgeon['name']}  (no WhatsApp number)")
    print(f"  nurse        {nurse['name']}  (no WhatsApp number)")
    print(f"  case 1       {case1['procedure']} @ {case1['scheduledAt']}  (at risk)")
    print(f"  case 2       {case2['procedure']} @ {case2['scheduledAt']}  (ready)")
    print("Done.")


if __name__ == "__main__":
    main()
