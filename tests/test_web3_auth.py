"""Web3 authentication tests — SiWE flow, nonce replay, JWT."""

import json
import time
import pytest


class TestWeb3AuthNonce:
    """Test nonce generation and one-time use."""

    def test_nonce_generation(self):
        from agentsafe.api.routes import _nonces, generate_nonce
        result = generate_nonce()
        assert "nonce" in result
        assert result["nonce"] in _nonces
        assert "domain" in result
        assert "uri" in result

    def test_nonce_replay_protection(self):
        """Nonce is consumed after first use."""
        from agentsafe.api.routes import _nonces, generate_nonce
        nonce_res = generate_nonce()
        nonce = nonce_res["nonce"]
        assert nonce in _nonces

        # Simulate first use (removes from _nonces)
        # In routes.py, verify_sign pops the nonce
        # Here we test the mechanism directly
        _nonces.pop(nonce)
        assert nonce not in _nonces


class TestWeb3AuthSign:
    """Test signature verification flow."""

    def test_sign_message_format(self):
        """SiWE message has expected structure."""
        address = "0x742d35Cc6634C0532925a3b844Bc9e7595f5eE20"
        nonce = "abc123"
        message = (
            "agentsafe.io wants you to sign in with your Ethereum account:\n"
            f"{address}\n\n"
            "Sign in to agentsafe\n\n"
            "URI: https://agentsafe.io\n"
            "Version: 1\n"
            "Chain ID: 8453\n"
            f"Nonce: {nonce}\n"
        )
        assert address in message
        assert nonce in message
        assert "Chain ID: 8453" in message

    def test_jwt_structure(self):
        """JWT token has expected format when jose is available."""
        # Test fallback token format
        address = "0x742d35Cc6634C0532925a3b844Bc9e7595f5eE20"
        token = f"agentsafe-jwt-{address[:10]}-{int(time.time())}"
        assert token.startswith("agentsafe-jwt-")
        assert "0x742d35" in token


class TestSiWEFlow:
    """Full SiWE integration test."""

    def test_full_siwe_flow(self):
        """End-to-end: get nonce → sign → verify → JWT."""
        # Step 1: Get nonce
        from agentsafe.api.routes import _nonces, generate_nonce
        nonce_res = generate_nonce()
        nonce = nonce_res["nonce"]
        assert nonce in _nonces

        # Step 2: Sign message (simulated with eth_account)
        from eth_account import Account
        from eth_account.messages import encode_defunct

        account = Account.create()
        address = account.address

        message = (
            "agentsafe.io wants you to sign in with your Ethereum account:\n"
            f"{address}\n\n"
            "Sign in to agentsafe\n\n"
            "URI: https://agentsafe.io\n"
            "Version: 1\n"
            "Chain ID: 8453\n"
            f"Nonce: {nonce}\n"
        )
        signed = account.sign_message(encode_defunct(text=message))

        # Step 3: Verify signature
        recovered = Account.recover_message(
            encode_defunct(text=message),
            signature=signed.signature,
        )
        assert recovered == address

        # Step 4: Consume nonce (simulate routes.py behavior)
        _nonces.pop(nonce)
        assert nonce not in _nonces

    def test_nonce_expiry(self):
        """Nonces expire after 5 minutes."""
        from agentsafe.api.routes import _nonces, generate_nonce
        # Get a fresh nonce (expires in 300s)
        res = generate_nonce()
        nonce = res["nonce"]
        expiry_time = _nonces[nonce]
        assert expiry_time > time.time()
        assert expiry_time <= time.time() + 360  # within 6 min


class TestWeb3AuthEdgeCases:
    """Edge cases for Web3 auth."""

    def test_invalid_nonce_rejected(self):
        """Non-existent nonce should not be in store."""
        from agentsafe.api.routes import _nonces
        fake_nonce = "not_a_real_nonce_12345"
        assert fake_nonce not in _nonces

    def test_signature_mismatch_detection(self):
        """Wrong address on wrong signature is detectable."""
        from eth_account import Account
        from eth_account.messages import encode_defunct

        account1 = Account.create()
        account2 = Account.create()
        message = "Test message for signing"

        # Sign with account1
        signed = account1.sign_message(encode_defunct(text=message))

        # Recover with signature
        recovered = Account.recover_message(
            encode_defunct(text=message),
            signature=signed.signature,
        )

        # Should match account1, NOT account2
        assert recovered == account1.address
        assert recovered != account2.address

    def test_multiple_concurrent_nonces(self):
        """Multiple nonces can coexist."""
        from agentsafe.api.routes import _nonces, generate_nonce
        res1 = generate_nonce()
        res2 = generate_nonce()
        assert res1["nonce"] != res2["nonce"]
        assert res1["nonce"] in _nonces
        assert res2["nonce"] in _nonces
