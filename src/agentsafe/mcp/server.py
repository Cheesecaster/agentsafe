"""MCP server — exposes 4 safety tools for Base Agent compatibility.

Tools:
- create_session(daily_limit_usd, whitelist): Creates SafeAgent instance
- check_budget(amount_usd, target): Checks if spend is allowed
- kill_session(reason): Triggers kill switch
- audit_log(): Returns merkle_root + recent logs
"""

import asyncio
import json
import tempfile
from typing import Any, Dict, List, Optional

from agentsafe.safe_agent import SafeAgent

try:
    from mcp.server.fastmcp import FastMCP
    _HAS_MCP = True
except ImportError:
    _HAS_MCP = False

# In-memory session registry
_sessions: Dict[str, SafeAgent] = {}

if _HAS_MCP:
    app = FastMCP("agentsafe")

    @app.tool()
    def create_session(
        daily_limit_usd: float = 20.0,
        whitelist: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a new safety session with budget and allowlist."""
        tmpdir = tempfile.mkdtemp(prefix="agentsafe_mcp_")
        agent = SafeAgent(
            daily_budget=str(daily_limit_usd),
            allowlist=whitelist or [],
            storage_path=tmpdir,
            quiet_hours=(26, 27),  # disabled for MCP
        )
        session_id = agent.session_id
        _sessions[session_id] = agent
        return {
            "session_id": session_id,
            "daily_limit": daily_limit_usd,
            "allowlist": whitelist or [],
            "status": "active",
        }

    @app.tool()
    def check_budget(
        amount_usd: float,
        target: str = "",
        session_id: str = "",
    ) -> Dict[str, Any]:
        """Check if a spend is allowed. Returns ALLOWED/DENIED/ESCALATE."""
        if not _sessions:
            return {"error": "No active session. Call create_session first."}

        # Use last session if none specified
        sid = session_id or list(_sessions.keys())[-1]
        agent = _sessions.get(sid)
        if not agent:
            return {"error": f"Session not found: {sid}"}

        result = agent.before_spend(to=target, amount=amount_usd, action="mcp_check")
        return {
            "status": result.status,
            "remaining_budget": result.remaining_budget,
            "session_id": result.session_id,
            "merkle_root": result.merkle_root,
            "reason": result.reason,
        }

    @app.tool()
    def kill_session(
        reason: str = "Manual kill via MCP",
        session_id: str = "",
    ) -> Dict[str, Any]:
        """Activate kill switch for a session."""
        if not _sessions:
            return {"error": "No active session."}

        sid = session_id or list(_sessions.keys())[-1]
        agent = _sessions.get(sid)
        if not agent:
            return {"error": f"Session not found: {sid}"}

        agent.kill(reason)
        return {
            "status": "killed",
            "session_id": sid,
            "reason": reason,
        }

    @app.tool()
    def audit_log(session_id: str = "") -> Dict[str, Any]:
        """Return merkle_root and recent audit log entries."""
        if not _sessions:
            return {"error": "No active session."}

        sid = session_id or list(_sessions.keys())[-1]
        agent = _sessions.get(sid)
        if not agent:
            return {"error": f"Session not found: {sid}"}

        recent = agent.audit.get_recent_logs(10)
        return {
            "merkle_root": agent.audit.merkle_root,
            "entry_count": agent.audit.entry_count,
            "recent_logs": recent,
        }


def main():
    """Entrypoint for agentsafe-mcp CLI."""
    if not _HAS_MCP:
        print("Error: mcp package not installed. Run: pip install agentsafe[mcp]")
        return
    app.run()


if __name__ == "__main__":
    main()
