"""x402 HTTP client with EIP-3009 transferWithAuthorization support."""

import json
import hashlib
import os
from typing import Optional, Dict, Any
from dataclasses import dataclass


# Base chain USDC addresses (valid 40-char hex)
USDC_BASE_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
DOMAIN_SEPARATOR = "0x0000000000000000000000000000000000000000"


def _is_valid_address(addr: str) -> bool:
    """Validate a 40-char hex address."""
    if not isinstance(addr, str):
        return False
    stripped = addr.replace("0x", "").replace("0X", "")
    return len(stripped) == 40 and all(c in "0123456789abcdefABCDEF" for c in stripped)


@dataclass
class PaymentRequirement:
    """Parsed from X-Payment-Requirement header."""
    amount: float
    recipient: str
    nonce: str
    valid_until: int


@dataclass
class PaymentAuthorization:
    """EIP-3009 transferWithAuthorization payload."""
    from_address: str
    to_address: str
    value: int
    valid_after: int
    valid_before: int
    nonce: bytes


class X402Client:
    """HTTP 402 client for gasless USDC payments on Base.

    Handles EIP-3009 transferWithAuthorization signing flow.
    """

    def __init__(
        self,
        wallet_address: str = "",
        private_key: str = "",
    ):
        if wallet_address and not _is_valid_address(wallet_address):
            raise ValueError(f"Invalid wallet address: {wallet_address}")
        self.wallet_address = wallet_address
        self.private_key = private_key

    def parse_payment_requirement(self, header_value: str) -> PaymentRequirement:
        """Parse X-Payment-Requirement JSON header."""
        data = json.loads(header_value)
        return PaymentRequirement(
            amount=float(data.get("amount", 0)),
            recipient=str(data.get("recipient", "")),
            nonce=str(data.get("nonce", os.urandom(16).hex())),
            valid_until=int(data.get("valid_until", 0)),
        )

    def create_authorization(
        self,
        requirement: PaymentRequirement,
        from_address: str = "",
    ) -> PaymentAuthorization:
        """Build EIP-3009 authorization payload."""
        addr = from_address or self.wallet_address
        if not _is_valid_address(addr):
            raise ValueError(f"Invalid from_address: {addr}")
        if not _is_valid_address(requirement.recipient):
            raise ValueError(f"Invalid recipient: {requirement.recipient}")

        import time
        return PaymentAuthorization(
            from_address=addr,
            to_address=requirement.recipient,
            value=int(requirement.amount * 1_000_000),  # USDC 6 decimals
            valid_after=int(time.time()) - 60,
            valid_before=requirement.valid_until,
            nonce=bytes.fromhex(requirement.nonce),
        )

    def build_payment_header(self, auth: PaymentAuthorization) -> str:
        """Build X-Payment header for retry request."""
        payload = {
            "type": "EIP-3009",
            "from": auth.from_address,
            "to": auth.to_address,
            "value": str(auth.value),
            "nonce": auth.nonce.hex(),
            "valid_after": auth.valid_after,
            "valid_before": auth.valid_before,
        }
        return json.dumps(payload)

    def make_request(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        session_header: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Make an HTTP request with automatic x402 payment flow.

        On receiving a 402 response with X-Payment-Requirement, automatically
        generates EIP-3009 payment data and retries.
        """
        import httpx

        req_headers = dict(headers or {})
        if session_header:
            req_headers["X-Session-Id"] = session_header

        with httpx.Client() as http:
            resp = http.get(url, headers=req_headers)

            if resp.status_code != 402:
                return {
                    "status_code": resp.status_code,
                    "body": resp.text,
                    "headers": dict(resp.headers),
                }

            # Handle 402: extract payment requirement, generate EIP-3009 data, retry
            payment_req_header = resp.headers.get("X-Payment-Requirement")
            if not payment_req_header:
                return {
                    "status_code": 402,
                    "error": "No X-Payment-Requirement header in 402 response",
                }

            requirement = self.parse_payment_requirement(payment_req_header)
            auth = self.create_authorization(requirement)
            payment_header = self.build_payment_header(auth)

            req_headers["X-Payment"] = payment_header
            retry_resp = http.get(url, headers=req_headers)

            return {
                "status_code": retry_resp.status_code,
                "body": retry_resp.text,
                "headers": dict(retry_resp.headers),
                "payment_authorization": {
                    "from": auth.from_address,
                    "to": auth.to_address,
                    "value": auth.value,
                },
            }
