# agentsafe SDK Example (SaaS API Key Style)
# Install: pip install agentsafe

from agentsafe import AgentsafeClient

# 1. Initialize with API Key (from dashboard)
agentsafe = AgentsafeClient(
    api_key="sk-agentsafe-xxxx-xxxx-xxxx", 
    agent_id="my-research-bot"
)

# 2. Wrap your API calls (Mimic x402 flow)
response = agentsafe.request(
    method="GET",
    url="https://api.openai.com/v1/chat/completions",
    # Safety checks happen automatically behind the scenes:
    # - Is budget okay?
    # - Is URL whitelisted?
    # - Is Kill Switch active?
)

if response.status_code == 200:
    print("Success!")
else:
    print(f"Blocked by agentsafe: {response.reason}")
