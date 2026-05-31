"""
Agentsafe SaaS Client — The 1-line integration for developers.
Replaces local SafeAgent setup with a cloud-managed API Key approach.
"""
import os
import time
import json
import requests
from typing import Optional, Dict, Any

class X402Response:
    """Wrapper for API responses."""
    def __init__(self, status_code, reason="", data=None):
        self.status_code = status_code
        self.reason = reason
        self.data = data
    
    @property
    def ok(self):
        return 200 <= self.status_code < 300

    def json(self):
        return self.data

class AgentsafeClient:
    """
    The SaaS entry point.
    
    Usage:
        client = AgentsafeClient(api_key="sk-age-...")
        res = client.get("https://api.example.com", max_spend=0.05)
    """

    def __init__(self, api_key: str, base_url: str = None):
        self.api_key = api_key
        self.base_url = base_url or os.environ.get("AGENTSAFE_API_URL", "https://api.agentsafe.com")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        })

    def request(self, method: str, url: str, max_spend_usd: Optional[float] = 0.05, **kwargs) -> X402Response:
        """
        Make a safety-checked HTTP request.
        If the endpoint requires x402 payment, Agentsafe Cloud handles the signature.
        """
        # 1. Ask Agentsafe Cloud for permission (Safety Check)
        check_payload = {
            "url": url,
            "amount": max_spend_usd,
            "method": method
        }
        
        try:
            check_res = self.session.post(f"{self.base_url}/v1/check", json=check_payload)
            check_res.raise_for_status()
            
            permit = check_res.json()
            if not permit.get("allowed"):
                return X402Response(
                    status_code=403, 
                    reason=f"Safety Denied: {permit.get('reason', 'Policy violation')}"
                )
            
            # 2. Execute request with the signed permit (x402 Payment Header)
            headers = kwargs.get("headers", {})
            headers["X-Payment"] = permit.get("payment_header") # Signed EIP-3009 payload
            kwargs["headers"] = headers

            actual_res = self.session.request(method, url, **kwargs)
            
            if actual_res.status_code == 200:
                return X402Response(status_code=200, data=actual_res.json())
            else:
                # Merchant rejected the payment
                return X402Response(status_code=actual_res.status_code, reason="Merchant rejected payment")

        except requests.exceptions.RequestException as e:
            return X402Response(status_code=500, reason=f"Connection to Agentsafe failed: {str(e)}")

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)
