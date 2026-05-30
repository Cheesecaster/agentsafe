"""agentsafe CLI — status, audit, and kill switch control."""

import sys
from pathlib import Path


def main():
    usage = """agentsafe — The seatbelt for autonomous agents that spend money via x402.

Usage:
    agentsafe status        Show all agent safety status
    agentsafe audit [hours] Show audit log (default: 24h)
    agentsafe pause [msg]   Activate kill switch
    agentsafe resume        Deactivate kill switch
    agentsafe trust list    Show trust registry
    agentsafe trust block <addr>  Block a counterparty
    agentsafe trust allow <addr>  Trust a counterparty
"""
    args = sys.argv[1:]
    if not args:
        print(usage)
        return

    command = args[0]
    print(f"agentsafe {command}: coming in v0.2")
    print("For now, use the Python API: from agentsafe import SafeAgent")
