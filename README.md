# `agentsafe`

> **The seatbelt for autonomous agents that spend money via x402.**

[![Base](https://img.shields.io/badge/Base-USDC-0052FF)](https://base.org)
[![x402](https://img.shields.io/badge/x402-Payment--Required-5200FF)](https://x402.org)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

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
pip install agentsafe
```

**Dependencies:** Python 3.12+ (stdlib only — no external deps for core guards)

Optional extras:
```bash
pip install agentsafe[x402]    # x402 payment client
pip install agentsafe[cli]     # CLI dashboard
pip install agentsafe[full]    # Everything
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
#     "daily_budget": "0.50 USDC",
#     "spent_today": "0.32 USDC",
#     "remaining": "0.18 USDC",
#     "status": "ACTIVE",
#     "kill_switch": False,
#     "trust_stats": {"trusted": 12, "unknown": 3, "blocked": 1},
#     "audit_entries": 47,
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
│  ├── 1. BudgetGuard    → đủ tiền?   │
│  ├── 2. TrustRegistry  → tin cậy?   │
│  ├── 3. AnomalyGuard   → lạ không?  │
│  ├── 4. TimeLock       → giờ lạ?    │
│  ├── 5. BehaviorHash   → drift không│
│  ├── 6. KillSwitch     → paused?    │
│  └── 7. AuditChain     → log hash   │
│                                     │
│  → APPROVED / ESCALATE / DENIED     │
├─────────────────────────────────────┤
│          Payment Layer              │
│  x402 + Escrow + Base USDC          │
└─────────────────────────────────────┘
```

---

## API Reference

### `SafeAgent`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `daily_budget` | str | `"0.50"` | Max spend per day (in currency units) |
| `currency` | str | `"USDC"` | Currency code (USDC, ETH, etc.) |
| `allowlist` | list[str] | `[]` | Trusted counterparties (auto-approved) |
| `blocklist` | list[str] | `[]` | Blocked counterparties (auto-denied) |
| `quiet_hours` | tuple[int, int] | `(1, 6)` | UTC hours where stricter limits apply |
| `quiet_hours_max` | str | `"0.10"` | Max per-tx during quiet hours |
| `anomaly_multiplier` | float | `3.0` | Multiplier from avg hourly spend → flag |
| `behavior_hash` | str | `None` | Hash of model+prompt+tools (anti-drift) |
| `on_escalate` | callable | `None` | Callback when ESCALATE triggered |
| `storage_path` | str | `"~/.agentsafe"` | Path for persistent state |

### `before_spend()`

Returns `SpendResult`:

| Field | Type | Description |
|-------|------|-------------|
| `status` | str | `"APPROVED"`, `"ESCALATE"`, or `"DENIED"` |
| `reason` | str | Human-readable reason for the decision |
| `remaining_budget` | str | Budget left after this spend |
| `payment_header` | str | x402 X-Payment header (if APPROVED) |
| `risk_score` | float | 0.0 (safe) to 1.0 (dangerous) |

### `record_spent()`

After a successful payment, call this to update budget and trust stats:

```python
agent.record_spent(0.05, "api.example.com", action="get_weather_data")
```

### `audit_log()`

Export the hash-chain audit log:

```python
# Get last 24h entries
entries = agent.audit.entries(hours=24)

# Verify integrity
ok = agent.audit.verify()

# Export to JSON
agent.audit.export("audit_2025-05-30.json")
```

### Kill Switch

```python
# Activate (pause all spending)
agent.kill_switch.activate("suspicious activity")

# Check if paused
agent.kill_switch.is_active()  # → True

# Resume (requires owner auth — not implemented by agent)
agent.kill_switch.resume(owner_signature)
```

---

## Integration with x402

`agentsafe` works with any x402-compatible payment flow:

```python
from agentsafe import SafeAgent
from agentsafe.x402 import x402_client

agent = SafeAgent(daily_budget="1.00")
client = x402_client(agent_wallet, base_network)

# Call a paid API
result = agent.before_spend(to="weather-api.com", amount=0.01)

if result.status == "APPROVED":
    response = client.get(
        "https://weather-api.com/data",
        payment=0.01,  # x402 handles the rest
    )
    agent.record_spent(0.01, "weather-api.com")
```

---



---

## Roadmap

### ✅ v0.1 (Current)
- Core safety guards (Budget, Trust, Anomaly, TimeLock, BehaviorHash, KillSwitch)
- AuditChain with hash-chain JSONL
- Python library (stdlib only)

### 🔜 v0.2
- x402 client integration (`agentsafe[x402]`)
- CLI dashboard (`agentsafe status`, `agentsafe audit`)
- Telegram bot for owner escalation

### 🔮 v1.0
- Smart contracts on Base (SessionGuard, EscrowSimple, TrustRegistry on-chain)
- MCP server (12 tools)
- Adaptive policy learning
- Mainnet deployment

---

## License

MIT. Open-source, free to use, free to audit.

---

## Contributing

PRs welcome. This is early-stage — we're figuring it out together.

If you're building x402 agents and hit a safety edge case, open an issue. We want `agentsafe` to cover every real scenario.

---

*Built for the agentic economy. Because agents that spend should spend safely.*
