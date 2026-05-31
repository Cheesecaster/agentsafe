"""Example: agentsafe x402 Client in Action.

Simulates an agent trying to access a paid API (weather, data, LLM, etc.)
and paying for it safely via Base USDC.
"""

import os
import logging
from agentsafe import SafeAgent

logging.basicConfig(level=logging.INFO)

# Configuration
API_ENDPOINT = "https://api.example.com/premium-weather"
WALLET_PRIVATE_KEY = os.environ.get("AGENT_PRIVATE_KEY", "0x...")
RPC_URL = "https://mainnet.base.org"

# 1. Setup the Safety Agent
agent_safe = SafeAgent(
    daily_budget="5.00",  # Max $5/day
    currency="USDC",
    allowlist=["weather-api-official.com"],
)

# 2. Check if we have the x402 dependencies installed
from agentsafe import X402Client
if not X402Client:
    print("x402 extras not installed. Run: pip install 'agentsafe[x402]'")
    exit(0)

# 3. Initialize x402 Client
try:
    client = X402Client(
        agent_safe=agent_safe,
        wallet_private_key=WALLET_PRIVATE_KEY,
        web3_provider_url=RPC_URL,
    )
except Exception as e:
    print(f"Client init failed (likely bad RPC or Key): {e}")
    exit(0)

# 4. Access the API
print(f"Querying {API_ENDPOINT} with payment enforcement...")

try:
    # The client handles the 402 flow, guard checks, and signature automatically.
    response = client.get(API_ENDPOINT)
    
    if response.status_code == 200:
        print("✅ Success! Content received.")
        print(response.json())
    elif response.status_code == 402:
        print(f"❌ Payment failed. API response: {response.text}")
    else:
        print(f"⚠️ Unexpected status: {response.status_code}")

except Exception as e:
    print(f"🚨 Critical Error: {e}")
