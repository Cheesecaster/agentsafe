"""agentsafe — Production CLI + API v0.2

- agentsafe status   → dashboard with budget, trust, anomaly, kill switch
- agentsafe audit    → view hash-chain audit log
- agentsafe pause    → activate kill switch
- agentsafe resume   → deactivate kill switch
- agentsafe serve    → start web dashboard
"""

import os
from pathlib import Path

def main():
    import sys
    args = sys.argv[1:]
    
    if not args:
        print_help()
        return
    
    cmd = args[0]
    
    if cmd == "status":
        cmd_status()
    elif cmd == "audit":
        hours = int(args[1]) if len(args) > 1 else 24
        cmd_audit(hours)
    elif cmd == "pause":
        reason = " ".join(args[1:]) or "owner command"
        cmd_pause(reason)
    elif cmd == "resume":
        cmd_resume()
    elif cmd == "trust":
        cmd_trust(args[1:])
    elif cmd == "serve":
        cmd_serve()
    else:
        print(f"Unknown command: {cmd}")
        print_help()


def cmd_status():
    from agentsafe import SafeAgent
    agent = SafeAgent()
    status = agent.status()
    
    # Rich terminal output (fallback to plain text if rich not installed)
    try:
        _print_rich_status(status)
    except ImportError:
        _print_plain_status(status)


def cmd_audit(hours=24):
    from agentsafe import SafeAgent
    agent = SafeAgent()
    entries = agent.audit.entries(hours=hours)
    
    if not entries:
        print(f"No audit entries in the last {hours} hours.")
        return
    
    print(f"\n📋 Audit Log (last {hours}h) — {len(entries)} entries")
    print(f"{'Time':<22} {'Action':<20} {'To':<30} {'Amount':>8}")
    print("─" * 85)
    
    for e in entries:
        ts = e.get("ts", 0)
        from datetime import datetime
        t = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        action = e.get("action", "?")
        details = e.get("details", {})
        to = details.get("to", "")[:28]
        amount = details.get("amount", "")
        print(f"{t:<22} {action:<20} {to:<30} {amount:>8}")
    
    # Verify integrity
    ok = agent.audit.verify()
    print(f"\n{'✅ Chain valid' if ok else '❌ Chain tampered!'}")


def cmd_pause(reason):
    from agentsafe import SafeAgent
    agent = SafeAgent()
    agent.kill_switch.activate(reason)
    print(f"⛔ Kill switch activated: {reason}")


def cmd_resume():
    from agentsafe import SafeAgent
    agent = SafeAgent()
    agent.kill_switch.resume()
    print("✅ Kill switch deactivated. Agent resumed.")


def cmd_trust(args):
    from agentsafe import SafeAgent
    agent = SafeAgent()
    
    if not args or args[0] == "list":
        stats = agent.trust.stats
        print(f"\n🤝 Trust Registry")
        print(f"  Trusted: {stats['trusted']}")
        print(f"  Blocked: {stats['blocked']}")
        print(f"  Unknown: {stats['unknown_pending']}")
    elif args[0] == "block" and len(args) > 1:
        agent.trust.block(args[1])
        print(f"🚫 Blocked: {args[1]}")
    elif args[0] == "allow" and len(args) > 1:
        agent.trust.promote(args[1])
        print(f"✅ Trusted: {args[1]}")


def cmd_serve():
    """Start the web dashboard."""
    try:
        from agentsafe.api.server import start_server
        start_server()
    except ImportError:
        # Fallback: serve static HTML directly
        import http.server
        import webbrowser
        import threading
        
        dashboard_path = Path(__file__).parent.parent.parent / "docs" / "dashboard.html"
        if dashboard_path.exists():
            print(f"🌐 Opening dashboard...")
            webbrowser.open(f"file://{dashboard_path.absolute()}")
            print(f"   Dashboard: file://{dashboard_path.absolute()}")
        else:
            print("Dashboard HTML not found. Run 'pip install agentsafe[cli]' for full features.")


def _print_rich_status(status):
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    
    console = Console()
    
    # Header
    is_paused = status.get("kill_switch", False)
    badge = "⛔ PAUSED" if is_paused else "✅ ACTIVE"
    console.print(Panel(
        f"[bold blue]agentsafe[/bold blue] v0.2  |  {badge}\n"
        f"Budget: {status['remaining']} remaining  |  "
        f"Spent: {status['spent_today']}  |  "
        f"Audit entries: {status.get('audit_entries', 0)}"
    ))
    
    # Trust stats
    ts = status.get("trust_stats", {})
    console.print(f"Trust — Trusted: [green]{ts.get('trusted', 0)}[/green]  "
                  f"Blocked: [red]{ts.get('blocked', 0)}[/red]  "
                  f"Unknown: [yellow]{ts.get('unknown_pending', 0)}[/yellow]")


def _print_plain_status(status):
    is_paused = status.get("kill_switch", False)
    badge = "PAUSED" if is_paused else "ACTIVE"
    
    print(f"\n{'='*50}")
    print(f"  agentsafe v0.2  |  Status: {badge}")
    print(f"{'='*50}")
    print(f"  Daily Budget: {status['daily_budget']}")
    print(f"  Spent Today:  {status['spent_today']}")
    print(f"  Remaining:    {status['remaining']}")
    print(f"  Audit Entries: {status.get('audit_entries', 0)}")
    print()
    
    ts = status.get("trust_stats", {})
    print(f"  Trust Registry:")
    print(f"    ✅ Trusted:  {ts.get('trusted', 0)}")
    print(f"    🚫 Blocked:  {ts.get('blocked', 0)}")
    print(f"    ❓ Unknown:  {ts.get('unknown_pending', 0)}")
    print(f"{'='*50}\n")


def print_help():
    print("""agentsafe — The seatbelt for autonomous agents that spend money via x402

Usage:
  agentsafe status              Show agent safety dashboard
  agentsafe audit [hours]       View audit log (default: 24h)
  agentsafe pause [reason]      Activate kill switch
  agentsafe resume              Deactivate kill switch
  agentsafe trust list          Show trust registry stats
  agentsafe trust block <addr>  Block a counterparty
  agentsafe trust allow <addr>  Trust a counterparty
  agentsafe serve               Start web dashboard
""")


if __name__ == "__main__":
    main()
