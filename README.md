# `agentsafe`

> **The seatbelt for autonomous agents that spend money via x402.**

[![Base](https://img.shields.io/badge/Base-USDC-0052FF)](https://base.org)
[![x402](https://img.shields.io/badge/x402-Payment--Required-5200FF)](https://x402.org)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB)](https://python.org)
[![Solidity](https://img.shields.io/badge/Solidity-0.8.24-363636)](contracts/)
[![Rust](https://img.shields.io/badge/Rust-0.1.0-DEA584)](rust/)
[![v0.3.0](https://img.shields.io/badge/Version-0.3.0-green)](https://github.com/Cheesecaster/agentsafe/releases)
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

Every project is building "how to **accept** x402 payments."
Nobody's building "how to **spend** x402 payments **safely**."

Until now.

## Philosophy

> **Base says:** "Your agent should have its own wallet."
> **We say:** "Your agent should have its own wallet **and sleep well at night.**"

`agentsafe` doesn't replace the wallet. It **protects** it.

---

## What Is `agentsafe`?

v0.3.0 is a complete stack for safe autonomous spending on Base Network:

1. **Python Guard Library**: 6 safety layers (Budget, Trust, Anomaly, TimeLock, Behavior, Audit).
2. **x402 Client (Base USDC)**: Detects 402 tags, checks safety, pays via EIP-3009.
3. **Smart Contracts**: On-chain enforcement (`SessionGuard` daily caps).
4. **Web Dashboard**: Real-time Base Mainnet monitoring via Metamask.
5. **Rust Core**: Zero-cost safety checks (`agentsafe-rs`).

---

## Installation

```bash
# Core Library
pip install agentsafe

# With x402 Client (Base USDC payments)
pip install agentsafe[x402]

# With Web API & Dashboard
pip install agentsafe[api]
```

---

## 1. Python API: The Safety Engine

The core logic that sits between your agent and the internet.

```python
from agentsafe import SafeAgent

agent = SafeAgent(
    daily_budget="20.00",  # Max $20/day
    currency="USDC",
    allowlist=["trusted-api.com"],
)

# Agent wants to pay $0.05
result = agent.before_spend(to="api.com", amount=0.05, action="lease_module")

if result.status == "APPROVED":
    agent.record_spent(0.05, "api.com")
    # ... proceed with payment ...
```

**6 Active Guards:**
- **BudgetGuard**: Daily cap (e.g. $20), auto-reset at midnight UTC.
- **TrustRegistry**: Allow/Block lists. Auto-promote after 5 successes.
- **AnomalyGuard**: Flags spending >3x average or >10 tx/hour.
- **TimeLock**: Stricter limits during quiet hours (e.g. 3 AM).
- **BehaviorHash**: Detects if the agent's model or prompt changes silently.
- **KillSwitch**: Owner pauses agent instantly. Agent cannot self-resume.

---

## 2. x402 Client: Autonomous Payments

Automatically pays for protected resources (APIs, Data) via Base USDC.

```python
from agentsafe import SafeAgent
from agentsafe.x402 import X402Client

agent = SafeAgent(daily_budget="20.00")
client = X402Client(agent_safe=agent, wallet_private_key="0x...")

# Automatically handles 402 challenges + Safety Checks + EIP-3009 Signatures
response = client.get("https://api.example.com/premium-data")
```

---

## 3. Smart Contracts: On-Chain Enforcement

Solidity contracts ready for **Base Mainnet**.

### `SessionGuard`
Manages session keys for agents with daily spending limits.
- **Adjustable**: Owner can increase/decrease daily caps (e.g. $20 -> $50) instantly.
- **Auto-Reset**: `spentToday` clears at Midnight UTC.
- **Revokeable**: Instant access kill-switch.

```solidity
// Example: Deploy & Set $20/day limit
SessionGuard guard = new SessionGuard(0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913);
guard.createSession(agentAddress, 20_000_000, 30 days); // 20 USDC
```

---

## 4. Web Dashboard (v0.3.0+)

A live "Control Center" for your agents on Base Mainnet.

```bash
agentsafe serve
# Opens http://localhost:8050
```

**Features:**
- **Wallet Connect**: Connect MetaMask/Base Wallet via Ethers.js.
- **Live Data**: See real-time USDC/ETH balance & Session status.
- **Control**: "Pause Agent" & "Set Limit" buttons that interact directly with the Base Chain.

---

## 5. Agentsafe-Rust (Foundation)

A `rust/` workspace is prepared for high-performance safety checks.
- **Zero-cost**: Guard checks in <100ns.
- **Memory Safe**: No GC, deterministic allocation.
- **Bindings**: Planned PyO3 export for Python users.

---

## License

MIT. Open-source, free to use, free to audit.

---

*Built for the agentic economy. Because agents that spend should spend safely.*
