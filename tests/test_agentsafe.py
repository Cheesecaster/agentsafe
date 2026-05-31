"""Tests for agentsafe core safety guards."""

import os
import tempfile
import time
from pathlib import Path

from agentsafe import (
    SafeAgent, BudgetGuard, TrustRegistry,
    AnomalyGuard, TimeLock, BehaviorHash, KillSwitch, AuditChain,
)


def test_budget_guard_daily_reset():
    with tempfile.TemporaryDirectory() as tmpdir:
        guard = BudgetGuard(daily_limit=0.50, storage_path=os.path.join(tmpdir, "budget.json"))
        assert guard.check(0.30)
        guard.record(0.30)
        assert guard.remaining == 0.20
        assert not guard.check(0.25)
        guard.record(0.20)
        assert abs(guard.spent_today - 0.50) < 0.001


def test_trust_registry_auto_promote():
    with tempfile.TemporaryDirectory() as tmpdir:
        reg = TrustRegistry(
            allowlist=["trusted-1"], blocklist=["bad-actor"],
            storage_path=os.path.join(tmpdir, "trust.json")
        )
        assert reg.check("trusted-1") == "TRUSTED"
        assert reg.check("bad-actor") == "BLOCKED"
        assert reg.check("new-guy") == "UNKNOWN"

        for _ in range(5):
            reg.add_interaction("new-guy", success=True)
        assert reg.check("new-guy") == "TRUSTED"


def test_anomaly_guard_tracking():
    with tempfile.TemporaryDirectory() as tmpdir:
        guard = AnomalyGuard(multiplier=3.0, storage_path=os.path.join(tmpdir, "anomaly.json"))
        now = time.time()
        guard.record(now, 0.05)
        guard.record(now, 0.05)
        avg = guard.hourly_average(time.gmtime(now).tm_hour)
        assert avg > 0
        assert guard.count_last_hour() == 2


def test_time_lock_quiet_hours():
    tl = TimeLock(quiet_hours=(1, 6), max_amount=0.10)
    assert tl.is_quiet_hours(3)
    assert not tl.is_quiet_hours(14)
    assert tl.check(0.10, 3)
    assert not tl.check(0.15, 3)
    assert tl.check(100.0, 14)


def test_behavior_hash_detection():
    h = BehaviorHash(registered_hash=BehaviorHash.compute(
        model="gpt-4", system_prompt="you are helpful", tools=["read", "write"]
    ))
    assert h.matches_current(
        model="gpt-4", system_prompt="you are helpful", tools=["read", "write"]
    )
    assert not h.matches_current(
        model="gpt-4", system_prompt="you are EVIL", tools=["read", "write"]
    )


def test_kill_switch_escalation():
    ks = KillSwitch()
    assert not ks.is_active
    ks.activate("suspicious activity")
    assert ks.is_active
    assert ks.reason == "suspicious activity"
    ks.resume()
    assert not ks.is_active


def test_audit_chain_integrity():
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        chain = AuditChain(f.name)
        h1 = chain.log("test_action", {"key": "value"})
        h2 = chain.log("test_action2", {"key2": "value2"})
        assert h1 != h2
        assert chain.verify()
        assert chain.count == 2
    Path(f.name).unlink(missing_ok=True)


def test_safe_agent_end_to_end():
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = SafeAgent(
            daily_budget="1.00",
            currency="USDC",
            allowlist=["trusted-api.com"],
            blocklist=["scammer.evil"],
            quiet_hours=(26, 27),  # Impossible hours — never triggers
            quiet_hours_max="0.05",
            anomaly_multiplier=3.0,
            storage_path=tmpdir,
        )

        # Test approved spend to trusted party
        result = agent.before_spend(to="trusted-api.com", amount=0.10, action="get_data")
        assert result.status == "APPROVED"
        agent.record_spent(0.10, "trusted-api.com")

        # Test denied spend to blocked party
        result = agent.before_spend(to="scammer.evil", amount=0.01)
        assert result.status == "DENIED"
        assert "blocked" in result.reason.lower()

        # Test unknown counterparty escalation
        result = agent.before_spend(to="unknown-new.io", amount=0.50)
        assert result.status == "ESCALATE"
        assert "Unknown counterparty" in result.reason

        # Test status
        status = agent.status()
        assert status["spent_today"] == "0.1000 USDC"
        assert status["kill_switch"] == False

        # Test kill switch
        agent.kill_switch.activate("emergency")
        result = agent.before_spend(to="trusted-api.com", amount=0.05)
        assert result.status == "DENIED"
        assert "Kill switch" in result.reason

        # Verify audit
        assert agent.audit.verify()

