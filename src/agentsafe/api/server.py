"""agentsafe Web Dashboard — Production API Server + Static Dashboard.

Serves:
1. REST API (/api/v1/...) — real-time agent safety data
2. Web UI (/) — dashboard.html with live data
"""

from flask import Flask, jsonify, send_file
from agentsafe import SafeAgent
import json
import os
from pathlib import Path

app = Flask(__name__, static_folder='.')
agent = SafeAgent()

# ── API Endpoints ─────────────────────────────────────────────────────

@app.route('/api/v1/status')
def api_status():
    return jsonify(agent.status())

@app.route('/api/v1/audit/<int:hours>')
def api_audit(hours):
    entries = agent.audit.entries(hours=hours)
    return jsonify({
        "count": len(entries),
        "verified": agent.audit.verify(),
        "merkle_root": agent.audit.merkle_root,
        "entries": entries[:100],
    })

@app.route('/api/v1/trust')
def api_trust():
    return jsonify(agent.trust.stats)

@app.route('/api/v1/budget')
def api_budget():
    return jsonify({
        "daily_limit": agent.budget.daily_limit,
        "spent_today": agent.budget.spent_today,
        "remaining": agent.budget.remaining,
        "transactions_today": agent.budget._state.get("count", 0),
    })

@app.route('/api/v1/killswitch', methods=['GET', 'POST'])
def api_killswitch():
    if agent.kill_switch.is_active:
        if request.method == 'POST' and request.get_json().get('action') == 'resume':
            agent.kill_switch.resume()
            return jsonify({"status": "resumed"})
        return jsonify({
            "active": True,
            "reason": agent.kill_switch.reason,
            "activated_at": agent.kill_switch.activated_at,
        })
    return jsonify({"active": False})

@app.route('/api/v1/pause', methods=['POST'])
def api_pause():
    data = request.get_json() or {}
    reason = data.get('reason', 'owner command')
    agent.kill_switch.activate(reason)
    return jsonify({"status": "paused", "reason": reason})

@app.route('/api/v1/spend', methods=['POST'])
def api_spend():
    """Record a spend or check before spending."""
    data = request.get_json()
    to = data.get('to', '')
    amount = data.get('amount', 0)
    action = data.get('action', '')
    
    result = agent.before_spend(to=to, amount=amount, action=action)
    if result.status == 'APPROVED':
        agent.record_spent(amount, to, action)
        return jsonify({
            "status": "approved",
            "remaining": agent.budget.remaining,
        })
    
    return jsonify({
        "status": result.status,
        "reason": result.reason,
        "risk_score": result.risk_score,
    })

# ── Web UI ────────────────────────────────────────────────────────────

@app.route('/')
def dashboard():
    return send_file(Path(__file__).parent / 'dashboard.html')


def start_server(host='0.0.0.0', port=8050):
    """Start the Flask dashboard server."""
    print(f"\n🌐 agentsafe Dashboard: http://localhost:{port}")
    print(f"   API:       http://localhost:{port}/api/v1/status")
    app.run(host=host, port=port, debug=False)


if __name__ == '__main__':
    start_server()
