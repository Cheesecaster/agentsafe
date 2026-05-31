# `agentsafe`

> **The seatbelt for autonomous agents that spend money via x402.**

![agentsafe Logo](assets/agentsafe_logo.svg)

[![Base](https://img.shields.io/badge/Base-USDC-0052FF)](https://base.org)
[![x402](https://img.shields.io/badge/x402-Payment--Required-5200FF)](https://x402.org)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

See the [interactive flow diagram](assets/flow_diagram.html) for a visual breakdown.

---

## Base MCP Agent Wallet Philosophy

> **"Narasi base MCP harus punya walletnya jangan pernah hilang"**
> *(Every Base MCP agent MUST have its own wallet — it must never disappear.)*

This is the core philosophy behind agentsafe. When autonomous AI agents operate on Base, each one needs its own wallet with its own identity, budget constraints, and safety controls. Without safety infrastructure, an agent's wallet is either completely free (and exploitable) or completely locked (and useless).

agentsafe provides the safety kit that makes autonomous agent wallets viable. It sits between the agent and the internet/blockchain, enforcing budget caps, trust rules, anomaly detection, and kill switches before any funds leave the wallet.

**Credit:** This philosophy and project vision were pioneered by [@gerryfishers](https://x.com/gerryfishers) — the idea that every Base MCP agent deserves its own protected wallet, and that safety infrastructure should be invisible to the agent developer.

---

## The Problem

Base & Coinbase are pushing **Agent MCP = every agent gets its own wallet.**
Agent can sign transactions, spend USDC, lease modules, pay APIs — all autonomously.

**But who stops the agent when it goes rogue?**

- Loop bug → 400 requests → $20 gone in 20 minutes
- Lease malicious module → poisoned instincts → broken code
- `.env` leaked → wallet drained
- No audit trail → owner can't verify what happened
- No kill switch → agent can't be paused

Every project is building "how to **accept** x402 payments."
Nobody's building "how to **spend** x402 payments **safely**."

Until now.

---

## What Is `agentsafe`?

A **drop-in safety layer** for any autonomous agent that holds a wallet and spends via x402.

```python
from agentsafe import SafeAgent

agent = SafeAgent(
    daily_budget="0.50 USDC",
    behavior_hash=compute_behavior(model, prompt, tools),
    allowlist=["arch-tools.api", "blockrun.ai"],
    anomaly_threshold=3.0,  # 3x from avg → flag
)

result = agent.before_spend(
    to="api.example.com",
    amount=0.05,
    action="lease react-module",
)
# → APPROVED / ESCALATE / DENIED
```

**6 Core Guards:**

| Guard | What It Does |
|-------|-------------|
| **BudgetGuard** | Daily cap, auto-reset, non-overridable |
| **TrustRegistry** | Allowlist/blocklist + auto-promote after N successes |
| **BehaviorHash** | Detects model/prompt/tool drift at runtime |
| **AnomalyGuard** | Time-aware, volume-aware, pattern-aware spending guard |
| **AuditChain** | Hash-chain JSONL log (tamper-evident, verifiable) |
| **KillSwitch** | Owner pause/resume (agent can't self-unpause) |

---

## Philosophy

> **Base says:** "Your agent should have its own wallet."
> **We say:** "Your agent should have its own wallet **and sleep well at night.**"

`agentsafe` doesn't replace the wallet. It **protects** it.

### Design Principles

1. **Non-overridable** — Budget and safety checks can't be bypassed by the agent (even if the agent controls its own code)
2. **Graceful degradation** — When budget is exhausted, fall back to free mode (no error thrown, no retry loop)
3. **Zero-trust by default** — Unknown counterparties → ESCALATE (require owner approval)
4. **Tamper-evident** — Every action is hash-chained. Rewrite is detectable
5. **Kill switch always works** — Owner can pause at any time, even mid-transaction

---

## Installation

```bash
pip install agentsafe                  # Core SDK
pip install agentsafe[dev,mcp,api]    # Full stack
```

**Dependencies:** Python 3.10+

Optional extras:
```bash
pip install agentsafe[mcp]     # MCP server
pip install agentsafe[api]     # FastAPI REST server
pip install agentsafe[x402]    # x402 payment client (web3, eth-account)
```

---

## Quick Start

### 1. Create a SafeAgent

```python
from agentsafe import SafeAgent

agent = SafeAgent(
    daily_budget="0.50",        # 0.50 USDC/day max
    currency="USDC",
    allowlist=["trusted-api-1", "known-agent-2"],
    blocklist=["scammer-bot-42"],
    quiet_hours=(1, 6),         # 1 AM - 6 AM UTC
    quiet_hours_max="0.10",     # Max $0.10/tx during quiet hours
    anomaly_multiplier=3.0,     # 3x from hourly avg → flag
)
```

### 2. Check Before Every Spend

```python
# Agent wants to pay $0.05 for an API call
result = agent.before_spend(
    to="api.example.com",
    amount=0.05,
    action="get_weather_data",
)

if result.status == "APPROVED":
    # Proceed with payment
    api_call(headers={"X-Payment": result.payment_header})
    agent.record_spent(0.05, "api.example.com")

elif result.status == "ESCALATE":
    # Unknown counterparty or anomalous pattern
    # Notify owner via Telegram/webhook
    notify_owner(result.reason)

elif result.status == "DENIED":
    # Budget exceeded, blocklisted, kill switch active
    log(f"Payment blocked: {result.reason}")
    fall_back_to_free_mode()
```

### 3. Monitor Status

```python
print(agent.status())
# {
#     "session_id": "sess-agent-default-abc123",
#     "spent_today": "0.3200 USDC",
#     "budget_remaining": "0.1800 USDC",
#     "daily_budget": "0.50 USDC",
#     "kill_switch": False,
#     "merkle_root": "0xabcdef1234567890...",
#     "entry_count": 47,
# }
```

### 4. Pause in Emergency

```python
agent.kill_switch.activate("suspicious spending pattern")
# All future before_spend() calls → DENIED
```

---

## Architecture

```
┌─────────────────────────────────────┐
│         Agent (any MCP agent)       │
│  mind.lease("react-module", $0.05)  │
├─────────────────────────────────────┤
│          agentsafe Gate             │
│                                     │
│  before_spend()                     │
│  ├── 1. KillSwitch     → paused?    │
│  ├── 2. TrustGuard     → trusted?   │
│  ├── 3. BudgetGuard    → within budget? │
│  ├── 4. TimeLock       → quiet hours? │
│  ├── 5. AnomalyGuard   → anomalous? │
│  └── 6. AuditChain     → log hash   │
│                                     │
│  → APPROVED / ESCALATE / DENIED     │
├─────────────────────────────────────┤
│          Payment Layer              │
│  x402 + Escrow + Base USDC          │
└─────────────────────────────────────┘
```

---

## MCP Integration

Add to your agent's MCP config:

```json
{
  "mcpServers": {
    "agentsafe-guard": {
      "command": "agentsafe-mcp"
    }
  }
}
```

Exposed tools: `create_session`, `check_budget`, `kill_session`, `audit_log`.

---

## Smart Contracts

Solidity contracts deployed on Base Mainnet:

| Contract | Description |
|----------|-------------|
| **SessionGuard** | Per-session budget management, storage-packed (uint128/uint48) |
| **EscrowSimple** | Agent escrow with seller `claim()` after timeout |
| **AgentRegistry** | DID identity, trust scores 0-100 |

Deployment:
```bash
cp .env.example .env
python scripts/deploy.py base
```

---

## API Reference

### `SafeAgent`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `daily_budget` | str | `"20.00"` | Max spend per day (in currency units) |
| `allowlist` | list[str] | `[]` | Trusted counterparties (auto-approved) |
| `blocklist` | list[str] | `[]` | Blocked counterparties (auto-denied) |
| `quiet_hours` | tuple[int, int] | `(1, 6)` | UTC hours where stricter limits apply |
| `quiet_hours_max` | str | `"0.10"` | Max per-tx during quiet hours |
| `anomaly_multiplier` | float | `3.0` | Multiplier from avg → flag |
| `currency` | str | `"USDC"` | Currency code |
| `storage_path` | str | auto | Path for persistent state |

### `before_spend()` Returns `SpendResult`

| Field | Type | Description |
|-------|------|-------------|
| `status` | str | `"APPROVED"`, `"ESCALATE"`, `"DENIED"`, or `"KILLED"` |
| `reason` | str | Human-readable reason for the decision |
| `remaining_budget` | float | Budget left after this spend |
| `session_id` | str | Unique session identifier |
| `merkle_root` | str | Current Merkle root of audit log |

---

## Development

```bash
make install       # Install with all extras
make test          # Run full test suite
make test-e2e      # E2E tests only
make deploy        # Deploy contracts to Base
make mcp           # Start MCP server
make clean         # Clean artifacts
```

**Tests:** 46 passing (29 unit + 8 e2e + 9 web3 auth)

---

## Roadmap

| Version | Status | Features |
|---------|--------|----------|
| v0.1 | ✅ | Core safety guards, AuditChain JSONL |
| v0.2 | ✅ | Merkle tree, x402 client, CLI |
| v0.3 | ✅ | Live Web3 dashboard, SiWE auth |
| v0.4 | ✅ | Formal Safety Proofs, Merkle anchoring |
| v0.5 | ✅ | MCP server, E2E test suite, contract optimization |
| v1.0 | 🔜 | Mainnet deployment, adaptive learning, full SaaS |

---

## License

MIT. Open-source, free to use, free to audit.

---

## Contributing

PRs welcome. This is early-stage — we're figuring it out together.

If you're building x402 agents and hit a safety edge case, open an issue. We want `agentsafe` to cover every real scenario.

---

*Built for the agentic economy. Because agents that spend should spend safely.*
