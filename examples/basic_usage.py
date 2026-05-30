"""agentsafe — Example: Safe autonomous agent spending via x402."""

from agentsafe import SafeAgent
import os

# 1. Create a safe agent with a daily budget
agent = SafeAgent(
    daily_budget="0.50",          # $0.50 USDC/day max
    currency="USDC",
    allowlist=["arch-tools.api", "blockrun.ai"],
    quiet_hours=(1, 6),           # Stricter 1 AM - 6 AM UTC
    quiet_hours_max="0.10",       # Max $0.10/tx during quiet hours
    anomaly_multiplier=3.0,       # Flag if 3x from avg
)

# 2. Agent wants to lease a memory module
result = agent.before_spend(
    to="react-expert-agent.io",
    amount=0.05,
    action="lease react-module-v1",
)

if result.status == "APPROVED":
    print(f"✅ Approved! Remaining budget: {result.remaining_budget}")
    # ... actually make the payment ...
    agent.record_spent(0.05, "react-expert-agent.io")

elif result.status == "ESCALATE":
    print(f"⚠️ Escalated: {result.reason}")
    # Notify owner (Telegram, webhook, etc.)
    # owner_bot.send(f"Agent wants to spend $0.05 on {result.reason}")

elif result.status == "DENIED":
    print(f"❌ Denied: {result.reason}")
    # Fall back to free mode
    # use_local_heuristic_module()

# 3. Check agent status
print(agent.status())
