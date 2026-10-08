"""EventBridge tick (every 5 minutes).

Three sweeps, each defensive so one failure does not stop the others:
  1. escalate pages whose acknowledgement deadline has passed and who still have
     recipients who have not acknowledged
  2. flag cases at risk of cancellation (the not-ready sweep)
  3. send any post-op follow-ups that are due
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from common import config, db
from safety import engine as safety
from services import paging, readiness

log = logging.getLogger()
log.setLevel(logging.INFO)


def _parse(iso) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _escalate_overdue_pages(now_dt: datetime) -> int:
    """A page is overdue once it is older than the acknowledgement window. The meta row
    carries createdAt, so we compute the deadline here rather than relying on a stored one."""
    done = 0
    horizon = safety.page_escalate_seconds()
    for page in db._scan_all(config.TBL_PAGES):
        if page.get("sk") != "meta" or page.get("escalationDone"):
            continue
        created = _parse(page.get("createdAt"))
        if not created or (now_dt - created).total_seconds() < horizon:
            continue
        try:
            if db.pending_page_recipients(page["pageId"]):
                paging.escalate_unacknowledged(page["pageId"])
            db._update(config.TBL_PAGES, {"pageId": page["pageId"], "sk": "meta"},
                       {"escalationDone": True})
            done += 1
        except Exception:
            log.exception("escalation failed for page %s", page.get("pageId"))
    return done


def _not_ready_sweep() -> int:
    try:
        at_risk = readiness.not_ready_sweep()
        return len(at_risk or [])
    except Exception:
        log.exception("not-ready sweep failed")
        return 0


def _due_followups(now: str) -> int:
    sent = 0
    for case in db._scan_all(config.TBL_CASES):
        due = case.get("followupDueAt")
        if not due or due > now or case.get("followupSentAt"):
            continue
        try:
            readiness.send_followup(case["caseId"])
            db.update_case(case["caseId"], {"followupSentAt": now})
            sent += 1
        except Exception:
            log.exception("follow-up failed for case %s", case.get("caseId"))
    return sent


def handler(event, context=None):
    now = db.now_iso()                       # string, for comparing stored ISO fields
    now_dt = datetime.now(timezone.utc)      # datetime, for the page-age maths
    result = {
        "escalatedPages": _escalate_overdue_pages(now_dt),
        "atRiskCases": _not_ready_sweep(),
        "followupsSent": _due_followups(now),
    }
    log.info("scheduler tick: %s", result)
    return result
