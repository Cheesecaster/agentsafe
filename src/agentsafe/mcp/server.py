"""
agentsafe MCP Server — Model Context Protocol wrapper.
Exposes agentsafe safety tools to any MCP-compatible agent (Claude, Base Agents, etc.)
"""
import json
import tempfile
from pathlib import Path
from contextlib import contextmanager
from typing import Optional

from mcp.server import Server
from mcp.types import Tool, TextContent, CallToolResult

# Import agentsafe core
from agentsafe.safe_agent import SafeAgent

# ── Session State ──────────────────────────────────────────
_tmpdir: Optional[str] = None
_active_session: Optional[SafeAgent] = None


def _ensure_tmpdir():
    global _tmpdir
    if _tmpdir is None:
        _tmpdir = tempfile.mkdtemp(prefix="agentsafe_mcp_")
    return _tmpdir


def _get_session() -> SafeAgent:
    """Get or create session. If no session, create a default."""
    global _active_session, _tmpdir
    if _active_session is None:
        _tmpdir = tempfile.mkdtemp(prefix="agentsafe_mcp_")
        _active_session = SafeAgent(
            daily_budget="20.00",
            allowlist=[],
            storage_path=_tmpdir,
        )
    return _active_session


def _create_session(args: dict) -> SafeAgent:
    global _active_session, _tmpdir
    _tmpdir = tempfile.mkdtemp(prefix="agentsafe_mcp_")
    _active_session = SafeAgent(
        daily_budget=str(float(args.get("daily_limit_usd", 20.0))),
        allowlist=args.get("whitelist", []),
        quiet_hours=(args.get("quiet_start", 0), args.get("quiet_end", 0)),
        storage_path=_tmpdir,
    )
    return _active_session


# ── MCP Server Definition ──────────────────────────────────
app = Server("agentsafe")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="create_session",
            description="Create a new safety session for an agent with limits and whitelist.",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_name": {"type": "string"},
                    "daily_limit_usd": {"type": "number", "description": "e.g. 20"},
                    "whitelist": {"type": "array", "items": {"type": "string"}, "description": "Allowed domains"},
                },
                "required": ["daily_limit_usd"],
            },
        ),
        Tool(
            name="check_budget",
            description="Check if an agent has enough budget for a transaction.",
            inputSchema={
                "type": "object",
                "properties": {
                    "amount_usd": {"type": "number", "description": "Amount to spend in USD"},
                    "target": {"type": "string", "description": "Target domain or API"},
                },
                "required": ["amount_usd"],
            },
        ),
        Tool(
            name="kill_session",
            description="Immediately revoke agent access (Kill Switch).",
            inputSchema={
                "type": "object",
                "properties": {"reason": {"type": "string", "description": "Reason for kill"}},
                "required": [],
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
        session = _create_session(arguments)
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"✅ Session created\nBudget: ${arguments.get('daily_limit_usd', 20.0)}/day\nWhitelist: {arguments.get('whitelist', [])}"
            )]
        )

    if name == "check_budget":
        session = _get_session()
        target = arguments.get("target", "unknown")
        amount = arguments["amount_usd"]
        result = session.before_spend(to=target, amount=amount)
        status_text = "✅ ALLOWED" if result.status == "APPROVED" else f"🚫 {result.status}"
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"{status_text}: {result.reason}\nRemaining: ${session.budget.remaining:.2f}/day"
            )]
        )

    if name == "kill_session":
        session = _get_session()
        session.kill_switch.activate(arguments.get("reason", "manual"))
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"🛑 Kill switch triggered. Reason: {arguments.get('reason', 'manual')}"
            )]
        )

    if name == "audit_log":
        session = _get_session()
        audit = session.audit
        root = audit.merkle_root
        logs = audit.get_recent_logs(10)
        log_lines = "\n".join(f"- {e['action']}: {e.get('details', {})}" for e in logs)
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"🌳 Merkle Root: {root or 'Empty'}\n\nRecent Logs:\n{log_lines or '(no entries)'}"
            )]
        )

    return CallToolResult(
        content=[TextContent(type="text", text=f"❌ Unknown tool: {name}")]
    )
