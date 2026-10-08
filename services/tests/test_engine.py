"""The deterministic safety spine (safety.engine). This is the code that owns every count
and risk call, so it is tested directly and hard, including the branches the end-to-end
tests never reach: an instrument that APPEARS after the case (retained-item signal), and
every cancellation-risk band. Pure functions, no I/O, no model."""
from safety import engine


# ── instrument_diff ───────────────────────────────────────────────────────────
def test_instrument_diff_matching_counts_are_ok():
    diff = engine.instrument_diff({"clamp": 2, "swab": 5}, {"clamp": 2, "swab": 5})
    assert diff["ok"] is True and diff["flags"] == []


def test_instrument_diff_missing_instrument_is_flagged_unaccounted():
    diff = engine.instrument_diff({"clamp": 2, "swab": 5}, {"clamp": 1, "swab": 5})
    assert diff["ok"] is False
    flag = next(f for f in diff["flags"] if f["item"] == "clamp")
    assert flag["kind"] == "unaccounted" and flag["missing"] == 1
    assert "unaccounted" in flag["message"].lower()


def test_instrument_diff_count_rose_is_flagged_discrepancy():
    # a > b: more after than before. The 'else' branch the e2e tests never hit.
    diff = engine.instrument_diff({"clamp": 1}, {"clamp": 2})
    assert diff["ok"] is False
    flag = diff["flags"][0]
    assert flag["kind"] == "discrepancy" and flag["missing"] == 0
    assert "verify" in flag["message"].lower()


def test_instrument_diff_instrument_only_after_is_a_discrepancy():
    # A classic retained-item signal: an item present after but not catalogued before.
    diff = engine.instrument_diff({"clamp": 2}, {"clamp": 2, "needle": 1})
    assert diff["ok"] is False
    flag = next(f for f in diff["flags"] if f["item"] == "needle")
    assert flag["kind"] == "discrepancy" and flag["before"] == 0 and flag["after"] == 1


def test_instrument_diff_instrument_gone_entirely_is_unaccounted():
    diff = engine.instrument_diff({"swab": 3}, {})
    flag = diff["flags"][0]
    assert flag["item"] == "swab" and flag["kind"] == "unaccounted" and flag["missing"] == 3


def test_instrument_diff_two_empty_catalogues_is_ok_but_the_caller_guards_emptiness():
    # The engine itself reports ok on {} vs {} (nothing to compare). The guard against
    # treating an *unread* photo as an empty count lives in actions.ingest_tray_photo,
    # which never stores {}; this test pins the engine's own contract.
    assert engine.instrument_diff({}, {}) == {"ok": True, "flags": []}


# ── readiness ─────────────────────────────────────────────────────────────────
def test_readiness_all_required_done_is_ready():
    status = {"consent": True, "fasting_confirmed": True, "balance_cleared": True,
              "team_confirmed": True}
    r = engine.readiness(status)
    assert r["isReady"] is True and r["outstandingRequired"] == []
    assert 0.0 < r["score"] <= 1.0


def test_readiness_missing_required_item_is_not_ready():
    r = engine.readiness({"consent": True})
    assert r["isReady"] is False
    assert "Fasting confirmed" in r["outstandingRequired"]


# ── cancellation_risk: every band ───────────────────────────────────────────────
def _ready():
    return {"consent": True, "fasting_confirmed": True, "balance_cleared": True,
            "team_confirmed": True}


def test_risk_low_when_nothing_outstanding():
    assert engine.cancellation_risk(_ready(), 2) == "low"


def test_risk_medium_when_time_unknown_and_items_outstanding():
    assert engine.cancellation_risk({"consent": True}, None) == "medium"


def test_risk_high_within_six_hours_with_outstanding():
    assert engine.cancellation_risk({"consent": True}, 4) == "high"


def test_risk_high_within_a_day_when_two_or_more_outstanding():
    # 6-24h: two or more required items missing -> high, one -> medium.
    two_missing = {"consent": True, "team_confirmed": True}      # fasting + balance missing
    one_missing = {"consent": True, "team_confirmed": True, "fasting_confirmed": True}
    assert engine.cancellation_risk(two_missing, 12) == "high"
    assert engine.cancellation_risk(one_missing, 12) == "medium"


def test_risk_medium_when_more_than_a_day_out():
    assert engine.cancellation_risk({"consent": True}, 48) == "medium"


# ── page escalation threshold ───────────────────────────────────────────────────
def test_page_escalate_seconds_reads_config():
    from common import config
    assert engine.page_escalate_seconds() == config.PAGE_ACK_ESCALATE_SECONDS
