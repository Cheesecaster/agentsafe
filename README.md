# agentsafe — Invisible Safety Layer for Autonomous AI Agents

## Base MCP Agent Wallet Philosophy

> **"Narasi base MCP harus punya walletnya jangan pernah hilang"**
> *(Every Base MCP agent MUST have its own wallet — it must never disappear.)*

This is the core philosophy behind agentsafe. When autonomous AI agents operate on Base, each one needs its own wallet with its own identity, budget constraints, and safety controls. Without safety infrastructure, an agent's wallet is either completely free (and exploitable) or completely locked (and useless).

agentsafe provides the safety kit that makes autonomous agent wallets viable. It sits between the agent and the internet/blockchain, enforcing budget caps, trust rules, anomaly detection, and kill switches before any funds leave the wallet.

**Credit:** This philosophy and project vision were pioneered by [@gerryfishers](https://x.com/gerryfishers) — the idea that every Base MCP agent deserves its own protected wallet, and that safety infrastructure should be invisible to the agent developer.

---

## Architecture

agentsafe is an "Invisible Safety Layer" for **existing AI agents**. Not a standalone platform — it's drop-in middleware.

```
[ Agent (LangChain, MCP, CrewAI) ]
        │
        ▼
[ agentsafe SDK ]  ──→  Budget, Trust, Anomaly, Kill Switch
        │
        ▼
[ x402 on Base ]  ──→  Gasless USDC payments (EIP-3009)
        │
        ▼
[ Solidity Contracts ]  ──→  SessionGuard, Escrow, Registry
```

## Installation

```bash
pip install agentsafe                  # Core SDK
pip install agentsafe[dev,mcp,api]    # Full stack
```

## Quick Start

```python
from agentsafe import SafeAgent

# Create agent with $20/day budget and allowlist
agent = SafeAgent(
    daily_budget="20.00",
    allowlist=["api.openai.com", "api.anthropic.com"],
)

# Before every spend
result = agent.before_spend(
    to="api.openai.com",
    amount=0.05,
    action="chat_completion"
)

if result.status == "APPROVED":
    print(f"Spend approved. Remaining: ${result.remaining_budget:.2f}")
    print(f"Session: {result.session_id}")
    print(f"Merkle: {result.merkle_root}")
```

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

## Components

| Component | Description |
|---|---|
| **BudgetGuard** | Daily caps (e.g. $20 USDC), auto-reset at midnight UTC |
| **TrustGuard** | Allowlist/blocklist with auto-promotion |
| **AnomalyGuard** | Flags spending deviations (>3x avg) |
| **KillSwitch** | Hard-stop by owner |
| **TimeLock** | Quiet hours restrictions |
| **MerkleTree** | SHA-256 audit tree, anchor to Base L2 |
| **AuditChain** | Append-only log with Merkle root |
| **SafetyProof** | HMAC-signed compliance proofs |
| **x402Client** | EIP-3009 gasless USDC on Base |

## Smart Contracts

Deployed on Base Mainnet:
- **SessionGuard** — Per-session budget management, storage-packed
- **EscrowSimple** — Agent escrow with seller claim after timeout
- **AgentRegistry** — DID identity, trust scores 0-100

## Development

```bash
make install       # Install with all extras
make test          # Run full test suite (32+ tests)
make test-e2e      # E2E tests only
make deploy        # Deploy contracts to Base
make mcp           # Start MCP server
make clean         # Clean artifacts
```

## Version

Current: v0.5.1
