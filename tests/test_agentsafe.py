"""Unit tests for agentsafe guard modules."""

import pytest
from agentsafe.guard.budget import BudgetGuard
from agentsafe.guard.trust import TrustGuard
from agentsafe.guard.anomaly import AnomalyGuard
from agentsafe.guard.kill_switch import KillSwitch
from agentsafe.guard.timelock import TimeLock
from agentsafe.guard.merkle import MerkleTree
from agentsafe.guard.audit_chain import AuditChain
from agentsafe.guard.behavior import BehaviorHash
from agentsafe.guard.proof import SafetyProofGenerator
from agentsafe.safe_agent import SafeAgent, ApprovalResult


# ---- BudgetGuard ----

class TestBudgetGuard:
    def test_approve_under_limit(self):
        guard = BudgetGuard(daily_limit=20.0)
        assert guard.check(5.0) is True

    def test_deny_over_limit(self):
        guard = BudgetGuard(daily_limit=10.0)
        guard.deduct(8.0)
        assert guard.check(3.0) is False

    def test_deduct_exact_limit(self):
        guard = BudgetGuard(daily_limit=10.0)
        guard.deduct(5.0)
        guard.deduct(5.0)
        assert guard.remaining == 0.0

    def test_deduct_raises_over_limit(self):
        guard = BudgetGuard(daily_limit=10.0)
        guard.deduct(7.0)
        with pytest.raises(ValueError):
            guard.deduct(4.0)

    def test_reset_daily(self):
        guard = BudgetGuard(daily_limit=10.0)
        guard.deduct(8.0)
        guard.reset_daily()
        assert guard.check(10.0) is True
        assert guard.remaining == 10.0


# ---- TrustGuard ----

class TestTrustGuard:
    def test_allowlist_check(self):
        tg = TrustGuard(initial_allowlist=["0xabc", "0xdef"])
        assert tg.check("0xabc") is True
        assert tg.check("0x123") is False

    def test_empty_allowlist_allows_all(self):
        tg = TrustGuard()
        assert tg.check("0xany") is True

    def test_deny_overrides_allow(self):
        tg = TrustGuard(initial_allowlist=["0xabc"])
        tg.deny("0xabc")
        assert tg.check("0xabc") is False

    def test_add_to_allowlist(self):
        tg = TrustGuard()
        tg.add_to_allowlist("0xnew")
        assert tg.check("0xnew") is True


# ---- AnomalyGuard ----

class TestAnomalyGuard:
    def test_no_data_allows(self):
        ag = AnomalyGuard()
        assert ag.check(100.0) is True

    def test_with_data(self):
        ag = AnomalyGuard()
        ag.record(1.0, 10.0)
        ag.record(2.0, 12.0)
        ag.record(3.0, 11.0)
        avg = ag.get_avg()
        assert 10.0 <= avg <= 12.0
        # 30 * avg should allow normal amounts
        assert ag.check(15.0) is True


# ---- KillSwitch ----

class TestKillSwitch:
    def test_inactive_by_default(self):
        ks = KillSwitch()
        assert ks.is_active() is False

    def test_activate_deactivate(self):
        ks = KillSwitch()
        ks.activate()
        assert ks.is_active() is True
        ks.deactivate()
        assert ks.is_active() is False


# ---- TimeLock ----

class TestTimeLock:
    def test_outside_quiet_hours(self):
        tl = TimeLock(max_amount=20.0, quiet_hours=(1, 6))
        # Hour 12 is outside quiet hours
        assert tl.check(10.0, current_hour=12) is True

    def test_during_quiet_hours(self):
        tl = TimeLock(max_amount=20.0, quiet_hours=(1, 6))
        # Hour 3 is inside quiet hours
        assert tl.check(5.0, current_hour=3) is False

    def test_disabled_by_invalid_hours(self):
        tl = TimeLock(max_amount=20.0, quiet_hours=(26, 27))
        # Hours 26-27 are never valid, so never in quiet hours
        assert tl.check(10.0, current_hour=12) is True

    def test_max_amount_enforced(self):
        tl = TimeLock(max_amount=10.0, quiet_hours=(1, 6))
        # Hour 12 is outside quiet hours, but amount > max_amount
        assert tl.check(15.0, current_hour=12) is False


# ---- MerkleTree ----

class TestMerkleTree:
    def test_empty_tree(self):
        mt = MerkleTree()
        root = mt.get_root()
        assert isinstance(root, str)
        assert len(root) == 64  # SHA-256 hex

    def test_append_and_root(self):
        mt = MerkleTree()
        mt.append("data1")
        mt.append("data2")
        root = mt.get_root()
        assert root == MerkleTree.get_root_of(["data1", "data2"])

    def test_different_data_different_root(self):
        mt1 = MerkleTree()
        mt1.append("a")
        mt2 = MerkleTree()
        mt2.append("b")
        assert mt1.get_root() != mt2.get_root()


# ---- AuditChain ----

class TestAuditChain:
    def test_log_entry(self):
        ac = AuditChain()
        ac.log("transfer", "to=0xabc amount=5.0")
        assert len(ac) == 1

    def test_merkle_root_is_property(self):
        ac = AuditChain()
        ac.log("transfer", "to=0xabc amount=5.0")
        root = ac.merkle_root  # no parens — property
        assert isinstance(root, str)
        assert len(root) == 64

    def test_get_recent_logs(self):
        ac = AuditChain()
        for i in range(15):
            ac.log(f"action_{i}", f"details_{i}")
        recent = ac.get_recent_logs(5)
        assert len(recent) == 5
        assert recent[0]["id"] == 11  # 1-based IDs, last 5 are 11-15

    def test_merkle_root_grows(self):
        ac = AuditChain()
        ac.log("a", "x")
        root1 = ac.merkle_root
        ac.log("b", "y")
        root2 = ac.merkle_root
        assert root1 != root2


# ---- BehaviorHash ----

class TestBehaviorHash:
    def test_compute_returns_hex(self):
        fp = BehaviorHash.compute("transfer", "0xabc")
        assert isinstance(fp, str)
        assert len(fp) == 64

    def test_deterministic(self):
        fp1 = BehaviorHash.compute("transfer", "0xabc")
        fp2 = BehaviorHash.compute("transfer", "0xabc")
        assert fp1 == fp2

    def test_different_inputs(self):
        fp1 = BehaviorHash.compute("transfer", "0xabc")
        fp2 = BehaviorHash.compute("transfer", "0xdef")
        assert fp1 != fp2


# ---- SafetyProofGenerator ----

class TestSafetyProof:
    def test_generate_returns_dict(self):
        pg = SafetyProofGenerator()
        result = pg.generate("s1", "deadbeef", {"budget": True, "trust": True})
        assert isinstance(result, dict)
        assert "signature" in result
        assert result["session_id"] == "s1"
        assert result["merkle_root"] == "deadbeef"

    def test_deterministic_signature(self):
        pg = SafetyProofGenerator(secret="test")
        r1 = pg.generate("sid", "root", {"a": True})
        r2 = pg.generate("sid", "root", {"a": True})
        assert r1["signature"] == r2["signature"]
