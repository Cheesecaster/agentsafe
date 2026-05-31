# agentsafe

**Autonomous Agent Safety Kit for x402 Payments & Base Mainnet**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Rust](https://img.shields.io/badge/Rust-1.70+-orange.svg)](https://www.rust-lang.org/)
[![Solidity](https://img.shields.io/badge/Solidity-0.8.20-363636.svg)](https://soliditylang.org/)
[![Base Mainnet](https://img.shields.io/badge/Network-Base%20Mainnet-0052ff.svg)](https://base.org/)
**v0.4.0 — Merkle Audits & Formal Proofs**

---

`agentsafe` is a drop-in safety layer for autonomous AI agents performing **x402 micropayments**.
It provides **budget caps, trust verification, anomaly detection, and cryptographic audit trails** without requiring enterprise bloatware.

Built for the **Base Agent Economy**.

## 🚀 The Philosophy: Every Base MCP Agent Needs Its Own Wallet
Base is pushing a future where **every AI Agent has its own on-chain identity and wallet**.
This is powerful, but dangerous without safety rails:
- 🐇 **True Autonomy**: Agents should pay for their own compute/data via x402 without asking permission for every $0.05.
- 🛑 **The "Runaway" Risk**: An agent with a wallet and no limits is a liability. One loop error = drained funds. One prompt injection = stolen assets.
- 🕳️ **The Gap**: Giving an agent a wallet is easy. Giving it **financial discipline** is hard.

**`agentsafe` bridges this gap.** 
It provides the **safety kit** that makes independent Agent Wallets viable for production. We ensure agents stay within budget, behave normally, and can be stopped instantly—so developers can trust their MCP agents to transact autonomously on Base.

## 🛡️ Architecture

We blend **Python flexibility** with **Rust performance** and **Solidity enforcement**.

### 1. 🧠 Python Guard Core (`src/agentsafe/guard/`)
Deterministic safety policy engine running <1ms checks:
- `BudgetGuard`: Enforces daily/total spend limits (e.g., $20/day).
- `TrustRegistry`: Whitelists verified x402 endpoints.
- `AnomalyGuard`: Detects spending velocity spikes (3σ deviation).
- `TimeLock`: Prevents burst spending; enforces cool-downs between transactions.
- `BehaviorHash`: Verifies agent "intent stability" before release.
- `KillSwitch`: Immediate session revocation by the owner.

### 2. 🌳 Merkle Audit Chain (v0.4.0)
Enterprise-grade verification (inspired by Layer 6 Financial protocols):
- Every agent action is logged in a **Merkle Tree**.
- The **Merkle Root** is available on-chain, making logs tamper-proof.
- Changing a single log entry invalidates the root hash: **Immediate fraud detection**.

### 3. 🛡️ Formal Safety Proofs (v0.4.0)
Before an x402 payment is released, agentsafe generates a **Signed Safety Proof**:
```json
{
  "agent_id": "agent_0x123",
  "intent_hash": "0xabc...",
  "checks": {
    "budget_ok": true,
    "trust_verified": true,
    "anomaly_score": 0.02
  },
  "merkle_root": "0x789...",
  "signature": "0xdead..."
}
```
This proof is attached to the x402 transaction, satisfying high-compliance environments.

### 4. 🤝 Smart Contracts (`contracts/`)
On-chain enforcement on Base Mainnet:
- `SessionGuard.sol`: Non-custodial session management with adjustable daily limits.
- `EscrowSimple.sol`: USDC escrow for trusted x402 transactions.
- `AgentRegistry.sol`: DID-style identity for verified agents.

### 5. ⚡ Rust Core (`crates/agentsafe-core/`)
Zero-cost abstractions for high-frequency loops. Guards ported to Rust for <100ns latency and zero allocation.

### 6. 🌐 Web Dashboard
- Connect Base wallet (MetaMask/WalletConnect).
- Live monitor of agent sessions, spend, and health.
- **Live Kill Switch** and limit adjustment directly from UI.

### Base MCP Integration

Connect `agentsafe` to any MCP-compatible agent (Claude Desktop, Base Agents, Cursor):

```bash
# Install MCP server
pip install agentsafe[mcp]

# Run as MCP server (stdio mode)
agentsafe-mcp

# Or use npx for Claude Desktop
npx mcp install agentsafe
```

Agents connecting via MCP automatically get access to 4 safety tools:
| Tool | Description |
|------|-------------|
| `create_session` | Set budget limits, whitelist, cooldowns |
| `check_budget` | Validate spend before execution |
| `kill_session` | Emergency revocation (Kill Switch) |
| `audit_log` | View Merkle Audit Root & history |

## 💻 Usage

### Installation
```bash
pip install agentsafe
# or from source
git clone https://github.com/Cheesecaster/agentsafe.git
cd agentsafe && pip install -e .
```

### Python Example
```python
from agentsafe.safe_agent import SafeAgent
from agentsafe.guard import BudgetGuard, TrustRegistry, AnomalyGuard

# 1. Initialize Guards
budget = BudgetGuard(daily_limit_usdc=20.0)  # $20/day cap
trust = TrustRegistry(whitelist=["api.openai.com"])
anomaly = AnomalyGuard()

# 2. Create Safe Agent
agent = SafeAgent(
    name="trader-bot",
    guards=[budget, trust, anomaly],
    wallet="0xYourBaseWallet"
)

# 3. Run with Safety
status = agent.check_safety(
    target="api.openai.com",
    amount_usdc=5.00
)

if status.allowed:
    print(f"✅ Approved. Remaining Daily: ${status.remaining}")
else:
    print(f"🚫 Denied: {status.reason}")
```

### Deploy to Base Mainnet
We provide a deployment script to initialize `SessionGuard` on Base:
```bash
python scripts/deploy.py --network mainnet --rpc-url $BASE_RPC --pk $PRIV_KEY
```

## 🧪 Development
```bash
pip install -e ".[dev]"
pytest tests/
```

## 🗺️ Roadmap
- [x] **v0.1.0:** Python Guard Core.
- [x] **v0.2.0:** Web Dashboard & API.
- [x] **v0.3.0:** x402 Client & Base Contracts.
- [x] **v0.4.0:** Merkle Audit & Formal Proofs.
- [ ] **v0.5.0:** Rust Core PyO3 bindings & ZK-Proof generation.

## 🤝 Contributing
PRs welcome. Focus on deterministic safety logic and Base Mainnet integration.

## 📄 License
MIT
