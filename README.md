# agentsafe

**The Invisible Safety Layer for Autonomous AI Agents.**

[![PyPI version](https://img.shields.io/pypi/v/agentsafe.svg)](https://pypi.org/project/agentsafe/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Base Mainnet](https://img.shields.io/badge/Network-Base%20(8453)-0052ff.svg)](https://base.org/)
**v0.5.0 — SaaS Middleware SDK**

---

`agentsafe` is a drop-in **safety middleware** for AI agents that pay for resources via **x402 micropayments**.
Instead of building complex blockchain logic, simply connect your agent to Agentsafe. We handle the budget enforcement, trust verification, and audit trails in real-time.

**Stop worrying about runaway agents. Start building.**

## 🚀 Why Agentsafe?
AI Agents need wallets to pay for APIs (via x402), but that's dangerous:
- 📉 **Runaway Spend**: An agent loops 1,000 times → wallet drained in seconds.
- 🐛 **Prompt Injection**: A malicious site tricks the agent into draining funds.
- 👀 **No Visibility**: You don't know what your agent bought until the bill hits.

**Agentsafe** acts as the **guardrail**. It intercepts every payment request, checks your policies, and only approves safe transactions.

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

## 🛡️ What We Handle (The "Invisible" Layer)

When your agent calls `agent.get()`, Agentsafe Cloud performs:

1. **🔒 Budget Guard**: Checks daily limit (e.g. $20/day). Rejects excess instantly.
2. **🛡️ Trust Check**: Validates domains against your whitelist. Blocks phishing URLs.
3. **🧠 Anomaly Detection**: Spends spikes (e.g., $0.05 -> $50.00) trigger an auto-block.
4. **🛑 Kill Switch**: Kill your agent's spending power from the Dashboard in 1 click.
5. **📝 Merkle Audit**: Every approved/denied action is logged on-chain verifiably.

## 🧩 Integrations

We support multiple ways to integrate:

| Platform | Integration Method | Docs |
|---|---|---|
| **Python (LangChain, CrewAI)** | `pip install agentsafe` | [Python SDK](examples/basic_usage.py) |
| **Claude Desktop / Cursor** | MCP Server Config | `mcpServers` JSON snippet |
| **API / Webhooks** | REST API (JWT Auth) | Coming Soon |

## 🏗️ Architecture (Under the Hood)

Your agent talks to our **SDK**, which communicates with **Agentsafe Cloud**.
Agentsafe Cloud then settles payments on **Base Mainnet** via **x402 contracts**.

```text
[ Agent Code ]
      │
      ▼ (Intercept Request)
[ agentsafe SDK ] ◄───── 1. Check Local Cache
      │                      2. If needed, call API
      ▼
[ Agentsafe Cloud ] ◄─── Safety Logic + Relayer (Base Chain)
      │                      • BudgetCheck
      │                      • TrustRegistry
      │                      • KillSwitch Status
      ▼
[ External API (x402) ] ◄─ Settlement via USDC on Base
```

## 🧪 Development
```bash
git clone https://github.com/Cheesecaster/agentsafe.git
cd agentsafe
pip install -e ".[dev]"
pytest  # Run 27 E2E & Unit Tests
```

## 📄 License
MIT
