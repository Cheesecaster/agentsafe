"""
agentsafe MCP Server — Model Context Protocol wrapper.
Exposes agentsafe safety tools to any MCP-compatible agent (Claude, Base Agents, etc.)
"""
from pathlib import Path
import json
from typing import Optional

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.types import (
    Tool,
    TextContent,
    CallToolRequest,
    CallToolResult,
    ListToolsResult,
)

# Import agentsafe core logic
from agentsafe.safe_agent import SafeAgent
from agentsafe.guard import (
    BudgetGuard,
    TrustRegistry,
    AnomalyGuard,
    TimeLock,
    KillSwitch,
)
from agentsafe.guard.audit_chain import AuditChain
from agentsafe.guard.behavior import BehaviorHash


# ── Session State ──────────────────────────────────────────
_active_session: Optional[SafeAgent] = None
_guards_config: dict = {}
_state_file = Path("agentsafe_session.json")


def _load_session():
    global _active_session, _guards_config
    if _state_file.exists():
        state = json.loads(_state_file.read_text())
        budget = BudgetGuard(daily_limit_usd=state["budget_limit"])
        trust = TrustRegistry(whitelist=state.get("whitelist", []))
        anomaly = AnomalyGuard()
        timelock = TimeLock(cooldown_seconds=state.get("cooldown", 60))
        killswitch = KillSwitch()
        audit = AuditChain()
        _guards_config = {
            "budget": budget,
            "trust": trust,
            "anomaly": anomaly,
            "timelock": timelock,
            "killswitch": killswitch,
            "audit": audit,
        }
        _active_session = SafeAgent(
            name=state["agent_name"],
            guards=[budget, trust, anomaly, timelock, killswitch],
            wallet=state["agent_wallet"],
            audit_chain=audit,
        )
        return True
    return False


def _save_session():
    if _active_session:
        state = {
            "agent_name": _active_session.agent_name,
            "agent_wallet": _active_session.agent_wallet,
            "budget_limit": _guards_config["budget"].daily_limit_usd,
            "whitelist": _guards_config["trust"].whitelist,
            "cooldown": _guards_config["timelock"].cooldown_seconds,
        }
        _state_file.write_text(json.dumps(state, indent=2))


# ── MCP Server Definition ──────────────────────────────────
app = Server("agentsafe")

# Tool: check_budget
@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="check_budget",
            description="Check if an agent has enough budget for a transaction.",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_name": {"type": "string", "description": "Agent identifier"},
                    "amount_usd": {"type": "number", "description": "Amount to spend in USD"},
                },
                "required": ["agent_name", "amount_usd"],
            },
        ),
        Tool(
            name="create_session",
            description="Create a new safety session for an agent with limits and whitelist.",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_name": {"type": "string"},
                    "agent_wallet": {"type": "string"},
                    "daily_limit_usd": {"type": "number", "description": "e.g. 20"},
                    "whitelist": {"type": "array", "items": {"type": "string"}, "description": "Allowed domains"},
                    "cooldown_seconds": {"type": "integer", "description": "Min seconds between txs"},
                },
                "required": ["agent_name", "agent_wallet", "daily_limit_usd"],
            },
        ),
        Tool(
            name="kill_session",
            description="Immediately revoke agent access (Kill Switch).",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_name": {"type": "string"},
                },
                "required": ["agent_name"],
            },
        ),
        Tool(
            name="audit_log",
            description="Return the latest Merkle Audit Root and last 10 log entries.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> CallToolResult:
    if name == "create_session":
        budget = BudgetGuard(daily_limit_usd=arguments["daily_limit_usd"])
        trust = TrustRegistry(whitelist=arguments.get("whitelist", []))
        anomaly = AnomalyGuard()
        timelock = TimeLock(cooldown_seconds=arguments.get("cooldown_seconds", 60))
        killswitch = KillSwitch()
        audit = AuditChain()

        _active_session = SafeAgent(
            name=arguments["agent_name"],
            guards=[budget, trust, anomaly, timelock, killswitch],
            wallet=arguments["agent_wallet"],
            audit_chain=audit,
        )
        _guards_config = {
            "budget": budget,
            "trust": trust,
            "anomaly": anomaly,
            "timelock": timelock,
            "killswitch": killswitch,
            "audit": audit,
        }
        _save_session()

        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"✅ Session created: {arguments['agent_name']}\nBudget: ${arguments['daily_limit_usd']}/day\nWhitelist: {arguments.get('whitelist', [])}"
            )]
        )

    if name == "check_budget":
        if not _load_session():
            return CallToolResult(
                content=[TextContent(type="text", text="❌ No active session. Call create_session first.")]
            )
        status = _active_session.check_safety(
            target=arguments.get("target", "unknown"),
            amount_usd=arguments["amount_usd"],
        )
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"{'✅ ALLOWED' if status.allowed else '🚫 DENIED'}: {status.reason}\nRemaining: ${status.remaining}/day"
            )]
        )

    if name == "kill_session":
        if not _load_session():
            return CallToolResult(
                content=[TextContent(type="text", text="❌ No active session")]
            )
        _guards_config["killswitch"].trigger()
        _save_session()
        return CallToolResult(
            content=[TextContent(type="text", text=f"🛑 Kill switch triggered. Session revoked for {arguments['agent_name']}")]
        )

    if name == "audit_log":
        if not _load_session():
            return CallToolResult(
                content=[TextContent(type="text", text="❌ No active session")]
            )
        audit = _guards_config["audit"]
        root = audit.get_merkle_root()
        logs = audit.get_recent_logs(10)
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"🌳 Merkle Root: {root or 'Empty'}\n\nLast Logs:\n" + "\n".join(str(l) for l in logs)
            )]
        )

    return CallToolResult(
        content=[TextContent(type="text", text=f"❌ Unknown tool: {name}")]
    )
