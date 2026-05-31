"""End-to-end tests for SafeAgent lifecycle."""

import pytest
from unittest.mock import MagicMock
from agentsafe.safe_agent import SafeAgent


class TestSafeAgentE2E:
    """Full lifecycle integration tests."""

    def _make_agent(self, **kwargs):
        """Create a SafeAgent with TimeLock effectively disabled."""
        agent = SafeAgent(**kwargs)
        # Disable time lock by setting max_amount very high and using impossible quiet hours
        agent.time_lock.max_amount = 99999.0
        agent.time_lock.quiet_hours = (26, 27)
        return agent

    def test_create_agent(self):
        agent = self._make_agent(daily_budget="20.00")
        assert agent.budget == 20.0
        assert agent.session_id is not None
        assert len(agent.session_id) == 64
        assert agent.kill_switch.is_active() is False

    def test_before_spend_approve(self):
        agent = self._make_agent(daily_budget="100.00", allowlist=["0xabc"])
        result = agent.before_spend("0xabc", 5.0, "transfer")
        assert result.approved is True
        assert result.fingerprint != ""
        assert result.proof is not None
        assert "signature" in result.proof

    def test_before_spend_trust_block(self):
        agent = self._make_agent(daily_budget="100.00", allowlist=["0xabc"])
        result = agent.before_spend("0xdef", 5.0, "transfer")
        assert result.approved is False
        assert "trusted" in result.reason.lower() or "trust" in result.reason.lower()

    def test_before_spend_budget_exceeded(self):
        agent = self._make_agent(daily_budget="10.00")
        r1 = agent.before_spend("0xabc", 8.0, "transfer")
        assert r1.approved is True
        r2 = agent.before_spend("0xabc", 5.0, "transfer")
        assert r2.approved is False
        assert "budget" in r2.reason.lower()

    def test_kill_switch_blocks(self):
        agent = self._make_agent(daily_budget="100.00")
        agent.kill_switch.activate()
        result = agent.before_spend("0xabc", 1.0, "transfer")
        assert result.approved is False
        assert "kill" in result.reason.lower() or "Kill" in result.reason

    def test_audit_log_grows(self):
        agent = self._make_agent(daily_budget="100.00")
        initial_len = len(agent.audit)
        agent.before_spend("0xabc", 1.0, "transfer")
        assert len(agent.audit) == initial_len + 1

    def test_merkle_tracks(self):
        agent = self._make_agent(daily_budget="100.00")
        root_before = agent.merkle.get_root()
        agent.before_spend("0xabc", 1.0, "transfer")
        root_after = agent.merkle.get_root()
        assert root_before != root_after

    def test_trust_allow_then_deny(self):
        agent = self._make_agent(daily_budget="100.00")
        agent.trust.allow("0xbob")
        assert agent.trust.check("0xbob") is True
        agent.trust.deny("0xbob")
        assert agent.trust.check("0xbob") is False
