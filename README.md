# agentsafe

![agentsafe Logo](assets/agentsafe_logo.svg)

**The Invisible Safety Layer for Autonomous AI Agents.**

[![PyPI version](https://img.shields.io/pypi/v/agentsafe.svg)](https://pypi.org/project/agentsafe/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Solidity](https://img.shields.io/badge/Solidity-0.8.20-363636.svg)](https://soliditylang.org/)
[![Rust](https://img.shields.io/badge/Rust-1.70+-orange.svg)](https://www.rust-lang.org/)
[![Base Mainnet](https://img.shields.io/badge/Network-Base%20(8453)-0052ff.svg)](https://base.org/)
**v0.5.0 — SaaS Middleware SDK**

---

`agentsafe` is a drop-in **safety middleware** for AI agents that pay for resources via **x402 micropayments**.
Instead of building complex blockchain logic, simply connect your agent to Agentsafe. We handle budget enforcement, trust verification, and audit trails in real-time.

**Stop worrying about runaway agents. Start building.**

## ⚡ Quick Start (SaaS Mode)
No smart contract deployment needed. No gas fees to manage.

### 1. Get API Key
Sign up at [app.agentsafe.com](https://app.agentsafe.com) and create an Agent profile.
Set your limits (e.g., "$5/day") and whitelist domains.

### 2. Install SDK
```bash
pip install agentsafe
```

### 3. Integrate (1 Line of Code)
```python
from agentsafe import AgentsafeClient

# Initialize with your Dashboard API Key
agent = AgentsafeClient(api_key="sk-age-...")

# Wrap your API requests.
# Agentsafe blocks unauthorized payments automatically.
response = agent.get(
    url="https://api.openai.com/v1/chat/completions",
    max_spend_usd=0.05
)

print(response.json())
```

## 🚀 Philosophy: Every Base MCP Agent Needs Its Own Wallet
Base is pushing a future where **every AI Agent has its own on-chain identity and wallet**.
This is powerful, but dangerous without safety rails:
- 🐇 **True Autonomy**: Agents should pay for their own compute/data via x402 without asking permission for every $0.05.
- 🛑 **The "Runaway" Risk**: An agent with a wallet and no limits is a liability. One loop error = drained funds. One prompt injection = stolen assets.

**`agentsafe` bridges this gap.** 
It provides the **safety kit** that makes independent Agent Wallets viable for production. We ensure agents stay within budget, behave normally, and can be stopped instantly—so developers can trust their MCP agents to transact autonomously on Base.

## 🛡️ Under the Hood: Enterprise-Grade Architecture
We blend **Python flexibility** with **Rust performance** and **Solidity enforcement**.

### 1. 🧠 Python Guard Core
Deterministic safety policy engine running <1ms checks:
- `BudgetGuard`: Enforces daily/total spend limits (e.g., $20/day).
- `TrustRegistry`: Whitelists verified x402 endpoints.
- `AnomalyGuard`: Detects spending velocity spikes (3σ deviation).
- `TimeLock`: Prevents burst spending; enforces cool-downs.

### 2. 🌳 Merkle Audit Chain (v0.4.0)
Enterprise-grade verification (inspired by Layer 6 Financial protocols):
- Every agent action is logged in a **Merkle Tree**.
- The **Merkle Root** is available on-chain, making logs tamper-proof.
- Changing a single log entry invalidates the root hash: **Immediate fraud detection**.

### 3. 🛡️ Formal Safety Proofs
Before an x402 payment is released, agentsafe generates a **Signed Safety Proof**:
```json
{
  "agent_id": "agent_0x123",
  "checks": { "budget_ok": true, "trust_verified": true },
  "merkle_root": "0x789...",
  "signature": "0xdead..."
}
```
This proof is attached to the x402 transaction, satisfying high-compliance environments.

### 4. 🤝 Smart Contracts (On-Chain Enforcement)
Gas-optimized contracts for Base Mainnet:
- `SessionGuard.sol`: Non-custodial session mgmt + daily limits. `ReentrancyGuard` + `SafeERC20` + `deposit/withdraw`.
- `EscrowSimple.sol`: x402 escrow with buyer-release, timeout-refund, and **seller auto-claim** fallback.
- `AgentRegistry.sol`: DID-style identity with trust scores (0-100) and metadata.

### 5. ⚡ Rust Core (`crates/agentsafe-core/`)
Zero-cost abstractions for high-frequency loops. Guards ported to Rust for <100ns latency and zero allocation.

## 🛑 Architecture Flow

See the [interactive flow diagram](assets/flow_diagram.html) for a visual breakdown.

```text
[ Agent Request ] → [ agentsafe SDK ] → [ ☁️ Cloud Check ] → [ 🟦 Base Settlement ]
                           │                      │
                    intercept &            Budget, Trust,
                    ask permission        KillSwitch gates
```

We support multiple ways to integrate:

| Platform | Integration Method | Docs |
|---|---|---|
| **Python (LangChain, CrewAI)** | `pip install agentsafe` | [Python SDK](examples/basic_usage.py) |
| **Claude Desktop / Cursor** | MCP Server Config | `mcpServers` JSON snippet |
| **API / Webhooks** | REST API (JWT Auth) | Coming Soon |

## 🧪 Development
```bash
git clone https://github.com/Cheesecaster/agentsafe.git
cd agentsafe
pip install -e ".[dev]"
make test  # Run 27 E2E & Unit Tests
```

## 🗺️ Roadmap
- [x] **v0.1.0:** Python Guard Core.
- [x] **v0.2.0:** Web Dashboard & API.
- [x] **v0.3.0:** x402 Client & Base Contracts.
- [x] **v0.4.0:** Merkle Audit & Formal Proofs.
- [x] **v0.4.1:** Base MCP Server.
- [x] **v0.5.0:** Contract optimization (storage packing, SafeERC20) + SaaS SDK focus.
- [ ] **v0.6.0:** Rust Core PyO3 bindings & Base Mainnet live deployment.

## ⚡ Powered By

Built on **Base Mainnet** with **x402** protocol for gasless USDC micropayments.

<p align="center">
  <a href="https://base.org"><img src="https://img.shields.io/badge/Network-Base%20(8453)-0052ff?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTEyIDJMIDQgNnYxMmw4IDQgOC00VjZsLTgtNHptMCAydjIuODMgTDcuMTcgOS45NCA0IDcuODMgMTIgNHptNCA1LjgzTDIwIDkuOTRWNiAxNnYtMi4xN3ptMTIuMTcgNC4xN3Y0LjY2TDEyIDIwbC00LjgzLTIuMTd2NC42NkwxMiAyNHptLTQgMEwxMiAyLjE3djQuNjZsNC4xNyAyLjE3eiIgZmlsbD0iIzAwNTJGRiIvPjwvc3ZnPg==" alt="Base" /></a>
  <a href="https://x402.org"><img src="https://img.shields.io/badge/Payment%20Protocol-x402-4F46E5?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTEyIDJDMTYuNDIgMiAyMCA1LjU4IDIwIDEwYzAgMy4xOC0xLjcgNS45OC00LjI1IDcuNTlMMjAgMjBsLTMuNTktMy41OUMxNS40NyAxNi44OSAxMy4zOCAxNyAxMiAxN2MtNC40MiAwLTgtMy41OC04LThzMy41OC04IDgtOHptMCAyYy0zLjMxIDAtNiAyLjY5LTYgNnMyLjY5IDYgNiA2IDYtMi42OSA2LTZzLTIuNjktNi02LTZ6bS0xIDEydjJoMnYtMmgtMnptMC04djZoMnYtNmgtMnoiIGZpbGw9IiM0RjQ2RTUiLz48L3N2Zz4=" alt="x402" /></a>
  <a href="https://usdc.coinbase.com"><img src="https://img.shields.io/badge/Settlement-USDC%20Base-2775CA?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGNpcmNsZSBjeD0iMTIiIGN5PSIxMiIgcj0iMTAiIGZpbGw9IiMyNzc1Q0EiLz48dGV4dCB4PSIxMiIgeT0iMTYiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZvbnQtc2l6ZT0iMTIiIGZvbnQtd2VpZ2h0PSJib2xkIiBmaWxsPSIjZmZmIiBmb250LWZhbWlseT0ic2Fucy1zZXJpZiI+JDwvdGV4dD48L3N2Zz4=" alt="USDC" /></a>
</p>

<p align="center">
  <strong>Credits by <a href="https://x.com/gerryfishers">TomKet</a></strong>
</p>

## 📄 License
MIT
