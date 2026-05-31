"""x402 Protocol Client for Base Network with Agent Identity Tracking.

Flow:
1. Agent calls client.get(url)
2. If API returns 402:
   a. Parse requirement (amount, destination)
   b. Check agentsafe guards (Budget, Trust, etc.)
   c. If safe → inject X-Agent-Session + X-Payment headers
   d. Retry request with payment + identity
"""

import base64
import json
import logging
import requests
import time

from typing import Optional, Dict, Any
from web3 import Web3

from agentsafe.safe_agent import SafeAgent
from agentsafe.x402.eip3009 import (
    prepare_transfer_with_authorization,
    USDC_BASE_ADDRESS,
)

logger = logging.getLogger(__name__)

# x402 v1 constants
X_PAYMENT_HEADER = "X-Payment"
X_PAYMENT_REQUIREMENT_HEADER = "X-Payment-Requirement"
X_AGENT_SESSION_HEADER = "X-Agent-Session"  # Agent identity header


class X402PaymentError(Exception):
    """Raised when a payment fails or is denied by agentsafe."""
    pass


class X402Client:
    """HTTP Client that natively supports x402 micropayments on Base
    with agent identity attribution via X-Agent-Session headers."""

    def __init__(
        self,
        agent_safe: SafeAgent,
        wallet_private_key: str,
        web3_provider_url: str = "https://mainnet.base.org",
    ):
        self.agent_safe = agent_safe
        self.wallet_private_key = wallet_private_key
        self.wallet_address = Web3().eth.account.from_key(wallet_private_key).address
        self.web3 = Web3(Web3.HTTPProvider(web3_provider_url))

    def _get_payment_info_from_headers(self, headers) -> Optional[dict]:
        """Extract payment requirement from 402 response headers."""
        req_str = headers.get(X_PAYMENT_REQUIREMENT_HEADER)
        if not req_str:
            return None

        try:
            req_data = json.loads(req_str)
            if req_data.get("scheme") == "exact" and req_data.get("network") == 8453:
                return req_data.get("payload")
            if req_str.startswith("pay-to"):
                return {"raw_header": req_str}
        except json.JSONDecodeError:
            pass

        return None

    def request(
        self,
        method: str,
        url: str,
        amount_wei: Optional[int] = None,
        merchant_address: Optional[str] = None,
        **kwargs
    ) -> requests.Response:
        """Make an x402-enabled HTTP request."""
        headers = kwargs.pop("headers", {})

        response = requests.request(method, url, headers=headers, **kwargs)

        if response.status_code == 402:
            return self._handle_402(method, url, headers, response, **kwargs)

        return response

    def handle_402(self, response_402, url, amount_usdc):
        """Public convenience method for testing."""
        return self._handle_402("GET", url, {}, response_402)

    def get(self, url, **kwargs) -> requests.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs) -> requests.Response:
        return self.request("POST", url, **kwargs)

    def _handle_402(
        self,
        method: str,
        url: str,
        headers: dict,
        response_402: requests.Response,
        **kwargs
    ) -> requests.Response:
        """Handle HTTP 402 with safety check + agent identity + payment."""
        logger.info(f"402 received from {url}. Initiating payment...")

        requirement = self._get_payment_info_from_headers(response_402.headers)
        if not requirement:
            logger.error("No valid payment requirement found in 402 headers.")
            return response_402

        to_address = requirement.get("to")
        amount = requirement.get("value")

        if not to_address and not amount:
            raise X402PaymentError("Could not parse payment requirement")

        # 1. SAFETY CHECK + generate X-Agent-Session header
        amount_usdc = amount / 1_000_000
        result = self.agent_safe.before_spend(
            to=to_address,
            amount=amount_usdc,
            action=f"x402 payment to {url}",
        )

        if result.status != "APPROVED":
            logger.warning(f"Payment DENIED by agentsafe: {result.reason}")
            raise X402PaymentError(f"agentsafe denied payment: {result.reason}")

        # 2. Inject X-Agent-Session header (merchant can identify WHO paid)
        if result.agent_header:
            headers[X_AGENT_SESSION_HEADER] = result.agent_header
            logger.info(f"Agent session: {result.session_id} (header: {result.agent_header[:40]}...)")

        # 3. PREPARE SIGNATURE (EIP-3009 Gasless Transfer)
        try:
            auth_data = prepare_transfer_with_authorization(
                web3=self.web3,
                from_address=self.wallet_address,
                to_address=to_address,
                amount_wei=amount,
                private_key=self.wallet_private_key,
                valid_seconds=300,
            )
        except Exception as e:
            logger.error(f"Signature failed: {e}")
            raise X402PaymentError(f"Signature failed: {e}")

        # 4. CONSTRUCT X-PAYMENT HEADER with session_id embedded
        payload = {
            "scheme": "exact",
            "network": 8453,
            "sessionId": result.session_id,         # 👈 embedded in payment
            "signature": auth_data["signature"],
            "from": auth_data["from"],
            "to": auth_data["to"],
            "value": auth_data["value"],
            "validAfter": auth_data["validAfter"],
            "validBefore": auth_data["validBefore"],
            "nonce": auth_data["nonce"],
        }

        headers[X_PAYMENT_HEADER] = json.dumps(payload)

        # 5. RETRY REQUEST
        logger.info(f"Retrying {url} with payment + agent identity headers.")
        final_response = requests.request(method, url, headers=headers, **kwargs)

        if final_response.status_code == 200:
            self.agent_safe.record_spent(amount_usdc, to_address, action=f"x402: {url}")
        else:
            logger.error(f"Payment sent but request failed: {final_response.status_code}")

        return final_response
