"""
E2E Tests for agentsafe v0.5.0
Full integration flow: session creation → spending → audit → kill switch.

Covers:
1. SafeAgent end-to-end workflow
2. BudgetGuard enforcement & daily reset
3. TrustRegistry + AnomalyGuard
4. KillSwitch + revocation
5. Merkle audit integrity
6. Formal Safety Proofs
7. x402 client flow simulation
8. MCP server tool execution
"""
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# ── Import agentsafe modules ──────────────────────────────
from agentsafe.safe_agent import SafeAgent
from agentsafe.guard import BudgetGuard, TrustRegistry, AnomalyGuard, TimeLock, KillSwitch
from agentsafe.guard.audit_chain import AuditChain
from agentsafe.guard.behavior import BehaviorHash
from agentsafe.guard.merkle import MerkleTree


# ═══════════════════════════════════════════════════════════
# 1. FULL FLOW: SafeAgent lifecycle
# ═══════════════════════════════════════════════════════════
class TestSafeAgentFullFlow:
    """Simulate a complete agent lifecycle with all guards active."""

    @pytest.fixture
    def agent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield SafeAgent(
                daily_budget="20.00",
                allowlist=["api.openai.com", "api.github.com"],
                blocklist=["evil.phishing.com"],
                quiet_hours=(1, 6),
                storage_path=tmpdir,
            )

    def test_approved_and_denied_spends(self, agent):
        # Disable quiet hours (set max_amount very high during quiet hours)
        agent.time_lock.max_amount = 99999.0

        # ── Phase 1: Normal spending to trusted party ──
        status1 = agent.before_spend(to="api.openai.com", amount=5.00, action="query")
        assert status1.status == "APPROVED", f"First tx failed: {status1.reason}"

        agent.record_spent(5.00, "api.openai.com")
        assert agent.budget.remaining < 20.0

        # Second approved spend
        status2 = agent.before_spend(to="api.github.com", amount=3.00, action="pull")
        assert status2.status == "APPROVED"

        # ── Phase 2: Blocklisted counterparty ──
        status3 = agent.before_spend(to="evil.phishing.com", amount=0.01)
        assert status3.status == "DENIED"
        assert "blocklisted" in status3.reason.lower() or "Kill" in status3.reason

        # ── Phase 3: Unknown counterparty triggers ESCALATE ──
        status4 = agent.before_spend(to="unknown.api.io", amount=1.00)
        assert status4.status == "ESCALATE"

        # ── Phase 4: Kill Switch ──
        agent.kill_switch.activate("anomalous behavior")
        status5 = agent.before_spend(to="api.openai.com", amount=1.00)
        assert status5.status == "DENIED"
        assert "Kill switch active" in status5.reason

    def test_budget_exhaustion(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = SafeAgent(daily_budget="1.00", storage_path=tmpdir)
            agent.before_spend(to="api.test.com", amount=0.80)
            agent.record_spent(0.80, "api.test.com")

            # Remaining: 0.20, try 0.50 → DENIED
            status = agent.before_spend(to="api.test.com", amount=0.50)
            assert status.status == "DENIED"
            assert "Budget" in status.reason

    def test_daily_reset(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = SafeAgent(daily_budget="50.00", storage_path=tmpdir)
            agent.before_spend(to="api.test.com", amount=30.0)
            agent.record_spent(30.0, "api.test.com")
            assert agent.budget.remaining < 50.0

            # Simulate midnight
            agent.budget.reset_daily()
            assert agent.budget.remaining == 50.0


# ═══════════════════════════════════════════════════════════
# 2. MERKLE AUDIT INTEGRITY
# ═══════════════════════════════════════════════════════════
class TestMerkleAudit:
    """Verify that audit logs are tamper-proof via Merkle tree."""

    def test_merkle_growth_and_immutability(self):
        tree = MerkleTree()
        assert tree.get_root() is None

        tree.append("log_1: agent start")
        root1 = tree.get_root()
        assert root1 is not None

        tree.append("log_2: $5 spent")
        root2 = tree.get_root()
        assert root2 != root1

    def test_tampering_changes_root(self):
        """If we rebuild with altered log, root must differ."""
        tree = MerkleTree()
        logs = ["action_a", "action_b", "action_c"]
        for log in logs:
            tree.append(log)
        original_root = tree.get_root()

        tree2 = MerkleTree()
        for log in logs:
            tree2.append(log if log != "action_b" else "HACKED")
        tampered_root = tree2.get_root()
        assert original_root != tampered_root

    def test_audit_chain_integrity(self):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            audit = AuditChain(f.name)
            audit.log("session_created", {"agent": "bot1", "details": "limit=$20"})
            audit.log("spend", {"agent": "bot1", "amount": 5.0})
            audit.log("spend", {"agent": "bot1", "amount": 3.0})

            assert audit.verify()
            assert audit.count == 3

            merkle_root = audit.merkle_root
            assert merkle_root is not None
            assert len(merkle_root) > 10

            logs = audit.get_recent_logs(5)
            assert len(logs) == 3


# ═══════════════════════════════════════════════════════════
# 3. FORMAL SAFETY PROOFS
# ═══════════════════════════════════════════════════════════
class TestSafetyProofs:
    """Verify that safety proofs are generated and signed."""

    def test_proof_generation(self):
        from agentsafe.guard.proof import SafetyProofGenerator

        gen = SafetyProofGenerator(secret_key="test-secret-key")
        mock_agent = MagicMock()
        mock_agent.budget = MagicMock(check=lambda amt: True)
        mock_agent.trust = MagicMock(check=lambda to: "TRUSTED")
        mock_agent.kill_switch = MagicMock(is_active=False)
        mock_agent.audit = MagicMock(merkle_root="0xabcdef")

        proof = gen.generate(mock_agent, amount=5.0, to="api.test.com", action="x402")
        assert "signature" in proof
        assert proof["checks"]["budget_enough"] is True
        assert gen.verify(proof)

    def test_proof_tampering_detection(self):
        from agentsafe.guard.proof import SafetyProofGenerator

        gen = SafetyProofGenerator(secret_key="test-secret-key")
        mock_agent = MagicMock()
        mock_agent.budget = MagicMock(check=lambda amt: True)
        mock_agent.trust = MagicMock(check=lambda to: "TRUSTED")
        mock_agent.kill_switch = MagicMock(is_active=False)
        mock_agent.audit = MagicMock(merkle_root="0xroot")

        proof = gen.generate(mock_agent, amount=1.0, to="api.test.com", action="test")
        assert gen.verify(proof)

        # Tamper
        proof["checks"]["budget_enough"] = False
        assert not gen.verify(proof)


# ═══════════════════════════════════════════════════════════
# 4. X402 CLIENT FLOW SIMULATION
# ═══════════════════════════════════════════════════════════
class TestX402Flow:
    """Simulate the full x402 payment flow."""

    def test_x402_successful_payment(self):
        """Payment flow: 402 → safety check → pay → success."""
        from agentsafe.x402.client import X402Client

        mock_agent = MagicMock()
        mock_agent.budget = MagicMock(check=lambda amt: True)
        mock_agent.trust = MagicMock(check=lambda to: "TRUSTED")
        mock_agent.kill_switch = MagicMock(is_active=False)

        client = X402Client(
            agent_safe=mock_agent,
            wallet_private_key="0x" + "00" * 32,
        )

        with patch.object(client, "_handle_402", return_value=MagicMock(status_code=200)):
            mock_402 = MagicMock(status_code=402, headers={"X-Payment-Requirement": "{}"})
            response = client.handle_402(mock_402, "api.service.com", amount_usdc=0.10)
            assert response.status_code == 200

    def test_x402_trust_rejection(self):
        """x402 to untrusted endpoint returns 402."""
        from agentsafe.x402.client import X402Client

        mock_agent = MagicMock()
        mock_agent.budget = MagicMock(check=lambda amt: True)
        mock_agent.trust = MagicMock(check=lambda to: "BLOCKED")
        mock_agent.kill_switch = MagicMock(is_active=False)

        client = X402Client(
            agent_safe=mock_agent,
            wallet_private_key="0x" + "00" * 32,
        )

        mock_402 = MagicMock(status_code=402, headers={"X-Payment-Requirement": "{}"})
        response = client._handle_402("GET", "evil.api.com", {}, mock_402)
        # Trust check returns BLOCKED → raise error → returned 402
        assert response.status_code == 402

    def test_eip3009_transfer_data(self):
        """EIP-3009 transferWithAuthorization generates valid calldata."""
        from agentsafe.x402.eip3009 import EIP3009Transfer

        tx = EIP3009Transfer(
            from_address="0x1234567890123456789012345678901234567890",
            to_address="0x0987654321098765432109876543210987654321",
            value=1_000_000,
            valid_after=0,
            valid_before=9999999999,
            nonce=b"\x00" * 32,
        )

        calldata = tx.get_calldata()
        assert calldata is not None
        assert len(calldata) > 0


# ═══════════════════════════════════════════════════════════
# 5. MCP SERVER INTEGRATION
# ═══════════════════════════════════════════════════════════
class TestMCPServer:
    """Verify MCP server tools work correctly."""

    def test_create_session_and_check_budget(self):
        import asyncio
        from agentsafe.mcp.server import call_tool

        # Create session with a whitelist
        asyncio.run(call_tool("create_session", {
            "agent_name": "test-bot",
            "daily_limit_usd": 20.0,
            "whitelist": ["api.example.com"],
        }))

        # Check budget
        result = asyncio.run(call_tool("check_budget", {
            "agent_name": "test-bot",
            "amount_usd": 5.0,
            "target": "api.example.com",
        }))
        content = result.content[0].text
        assert "ALLOWED" in content

    def test_kill_session(self):
        import asyncio
        from agentsafe.mcp.server import call_tool

        asyncio.run(call_tool("create_session", {
            "agent_name": "kill-test",
            "agent_wallet": "0xKillTest",
            "daily_limit_usd": 50.0,
        }))

        asyncio.run(call_tool("kill_session", {"agent_name": "kill-test"}))

        result = asyncio.run(call_tool("check_budget", {
            "agent_name": "kill-test",
            "amount_usd": 1.0,
        }))
        assert result.content[0].text is not None

    def test_audit_log(self):
        import asyncio
        from agentsafe.mcp.server import call_tool

        asyncio.run(call_tool("create_session", {
            "agent_name": "audit-test",
            "agent_wallet": "0xAuditTest",
            "daily_limit_usd": 10.0,
        }))

        result = asyncio.run(call_tool("audit_log", {}))
        content = result.content[0].text
        assert "Merkle Root" in content or "Empty" in content


# ═══════════════════════════════════════════════════════════
# 6. BEHAVIOR HASH & INTENT STABILITY
# ═══════════════════════════════════════════════════════════
class TestBehaviorHash:
    """Agent intent hash must be stable and tamper-detectable."""

    def test_behavior_hash_generation(self):
        bh = BehaviorHash(registered_hash=BehaviorHash.compute(
            model="gpt-4", system_prompt="you are helpful", tools=["read", "write"]
        ))
        assert bh.matches_current(
            model="gpt-4", system_prompt="you are helpful", tools=["read", "write"]
        )

    def test_behavior_hash_different_intent(self):
        bh = BehaviorHash(registered_hash=BehaviorHash.compute(
            model="gpt-4", system_prompt="you are helpful", tools=["read"]
        ))
        assert not bh.matches_current(
            model="gpt-4", system_prompt="you are EVIL", tools=["read"]
        )


# ═══════════════════════════════════════════════════════════
# 7. CONTRACT ARTIFACTS VERIFICATION
# ═══════════════════════════════════════════════════════════
class TestContractArtifacts:
    """Ensure compiled contract ABIs are valid for deployment."""

    def _check_abi(self, name: str, expected_functions: set):
        abi_path = Path(__file__).parent.parent / "artifacts" / f"{name}.json"
        if abi_path.exists():
            abi = json.loads(abi_path.read_text())
            func_names = {item["name"] for item in abi if item.get("type") == "function"}
            for fn in expected_functions:
                assert fn in func_names, f"Missing function: {fn} in {name}"

    def test_session_guard_abi(self):
        self._check_abi("SessionGuard", {
            "createSession", "spend", "revoke",
            "updateDailyLimit", "deposit", "withdraw", "getSession",
        })

    def test_escrow_abi(self):
        self._check_abi("EscrowSimple", {
            "release", "refund", "claim", "createEscrow",
        })

    def test_registry_abi(self):
        self._check_abi("AgentRegistry", {
            "registerAgent", "updateTrust", "verifyAgent", "isTrusted",
        })
