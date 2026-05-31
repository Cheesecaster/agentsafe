"""x402 Protocol Client for Base Network.

This module bridges the gap between an agent's need to access a paid API
and the safety constraints enforced by `agentsafe`.

Workflow:
1. Agent calls `client.get(url)`.
2. If API returns 402:
   a. Parse requirement (amount, destination).
   b. Check `agentsafe` guards (Budget, Trust, etc.).
   c. If safe, prepare EIP-3009 signature (gasless USDC transfer).
   d. Retry request with `X-Payment` header.
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
REQUIRED_SCHEME = "pay-to"  # e.g., "pay-to:0x..."

class X402PaymentError(Exception):
    """Raised when a payment fails or is denied by agentsafe."""
    pass

class X402Client:
    """HTTP Client that natively supports x402 micropayments on Base."""

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
        # Format typically: '{"scheme": "pay-to", "network": 8453, "payload": {...}}'
        if not req_str:
            return None
        
        try:
            req_data = json.loads(req_str)
            
            # Check for exact scheme support
            # x402 standard uses 'network' and 'payload' (transferWithAuthorization details)
            if req_data.get("scheme") == "exact" and req_data.get("network") == 8453:
                return req_data.get("payload")
            
            # Fallback for older/different implementations
            # 'pay-to:0x...' format
            if req_str.startswith("pay-to"):
                # Parse amount from body or specific header
                return {"raw_header": req_str}

        except json.JSONDecodeError:
            # Try to parse the raw pay-to string
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
        """Make an x402-enabled HTTP request.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: The resource URL.
            amount_wei: If known, the amount to pay. If None, will detect from 402.
            merchant_address: If known, the destination wallet.
        """
        headers = kwargs.pop("headers", {})
        
        # Attempt 1: Normal request
        response = requests.request(method, url, headers=headers, **kwargs)

        if response.status_code == 402:
            if response.status_code != 402:
                return response

            return self._handle_402(method, url, headers, response, **kwargs)

        return response

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
        """Handle the 402 Payment Required challenge."""
        logger.info(f"402 received from {url}. Initiating payment...")

        requirement = self._get_payment_info_from_headers(response_402.headers)
        if not requirement:
            logger.error("No valid payment requirement found in 402 headers.")
            return response_402

        to_address = requirement.get("to")
        amount = requirement.get("value")
        
        # Fallback for older formats if necessary
        if not to_address and not amount:
            # Try to extract from raw string or body
            # For now, assume standard x402 v1 exact format
            raise X402PaymentError("Could not parse payment requirement")

        # 1. SAFETY CHECK (The core value of agentsafe)
        amount_usdc = amount / 1_000_000
        result = self.agent_safe.before_spend(
            to=to_address,
            amount=amount_usdc,
            action=f"x402 payment to {url}",
        )

        if result.status != "APPROVED":
            logger.warning(f"Payment DENIED by agentsafe: {result.reason}")
            raise X402PaymentError(f"agentsafe denied payment: {result.reason}")

        # 2. PREPARE SIGNATURE (EIP-3009 Gasless Transfer)
        # Note: In x402, the "facilitator" usually accepts the signed payload.
        # We sign it here.
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

        # 3. CONSTRUCT X-PAYMENT HEADER
        # x402 spec says header should contain the signed payload
        payload = {
            "scheme": "exact",
            "network": 8453,
            "signature": auth_data["signature"],
            "from": auth_data["from"],
            "to": auth_data["to"],
            "value": auth_data["value"],
            "validAfter": auth_data["validAfter"],
            "validBefore": auth_data["validBefore"],
            "nonce": auth_data["nonce"],
        }
        
        headers[X_PAYMENT_HEADER] = json.dumps(payload)

        # 4. RETRY REQUEST
        logger.info(f"Retrying {url} with payment header.")
        final_response = requests.request(method, url, headers=headers, **kwargs)

        if final_response.status_code == 200:
            self.agent_safe.record_spent(amount_usdc, to_address, action=f"x402: {url}")
        else:
            logger.error(f"Payment sent but request failed: {final_response.status_code}")

        return final_response
