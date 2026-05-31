"""EIP-3009: TransferWithAuthorization implementation for Base USDC.

This module handles the creation and signing of gasless USDC transfers
required for x402 payments on Base Network.

Reference: https://eips.ethereum.org/EIPS/eip-3009
"""

from eth_account import Account
from web3 import Web3
from web3.middleware import SignAndSendRawMiddlewareBuilder
from typing import Dict, Any
import time

from eth_abi import encode

# USDC on Base Mainnet Address
USDC_BASE_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

# Minimal ABI for USDC transferWithAuthorization
USDC_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "from", "type": "address"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "value", "type": "uint256"},
            {"internalType": "uint256", "name": "validAfter", "type": "uint256"},
            {"internalType": "uint256", "name": "validBefore", "type": "uint256"},
            {"internalType": "bytes32", "name": "nonce", "type": "bytes32"},
        ],
        "name": "transferWithAuthorization",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "DOMAIN_SEPARATOR",
        "outputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "owner", "type": "address"}],
        "name": "nonces",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# EIP-712 Domain for USDC on Base
# Note: This must be verified against the actual DOMAIN_SEPARATOR on-chain
USDC_DOMAIN_DATA = {
    "name": "USD Coin",
    "version": "2",
    "chainId": 8453,  # Base Mainnet
}

EIP3009_TYPE_HASH = Web3.keccak(
    text="TransferWithAuthorization(address from,address to,uint256 value,uint256 validAfter,uint256 validBefore,bytes32 nonce)"
).hex()


def prepare_transfer_with_authorization(
    web3: Web3,
    from_address: str,
    to_address: str,
    amount_wei: int,
    private_key: str,
    valid_seconds: int = 300,
) -> Dict[str, Any]:
    """Prepare and sign an EIP-3009 transfer.

    Args:
        web3: Web3 instance connected to Base.
        from_address: The agent's wallet address (owner).
        to_address: The API/Merchant receiving the payment.
        amount_wei: Amount of USDC (in 6 decimals units, e.g., 1,000,000 = $1.00).
        private_key: Private key of the `from_address`.
        valid_seconds: How long this authorization is valid for.

    Returns:
        Dictionary containing the signed authorization payload.
    """
    # Get Contract for nonce checking
    usdc_contract = web3.eth.contract(address=USDC_BASE_ADDRESS, abi=USDC_ABI)
    
    # Fetch nonce
    nonce = usdc_contract.functions.nonces(from_address).call()
    
    # Fetch DOMAIN_SEPARATOR dynamically from chain
    domain_separator_raw = usdc_contract.functions.DOMAIN_SEPARATOR().call()
    
    # Time bounds
    now = int(time.time())
    valid_after = now - 10  # 10 seconds buffer
    valid_before = now + valid_seconds

    # Convert bytes nonce to hex string (without 0x) if needed
    nonce_bytes = Web3.to_bytes(hexstr=Web3.to_hex(nonce)[2:].zfill(64))
    
    # EIP-712 Typehash
    typehash = EIP3009_TYPE_HASH

    # Encode struct hash
    struct_hash = Web3.keccak(
        hexstr=typehash[2:]
        + Web3.to_bytes(hexstr=Web3.to_checksum_address(from_address)[2:]).hex()
        + Web3.to_bytes(hexstr=Web3.to_checksum_address(to_address)[2:]).hex()
        + Web3.to_bytes(amount_wei).hex().zfill(64)
        + Web3.to_bytes(valid_after).hex().zfill(64)
        + Web3.to_bytes(valid_before).hex().zfill(64)
        + Web3.to_bytes(nonce_bytes).hex()
    )

    # EIP-712 Domain Separator
    domain_typehash = Web3.keccak(text="EIP712Domain(string name,string version,uint256 chainId,bytes32 salt)")
    # Note: We are skipping salt here, assuming standard domain. 
    # If the contract uses a salt in domain, this needs adjustment.
    # Base USDC standard domain separator is usually known or fetched.
    
    # In a real production env, we use `account.sign_typed_data`.
    # However, Web3.py support for full EIP-712 typing varies.
    # We will construct the raw hash to sign.
    
    # Domain Hash (Standard for Base USDC)
    # We fetch it from on-chain to be safe, so we don't hardcode wrong values.
    domain_hash = domain_separator_raw 

    # The payload hash to sign
    payload_hash = Web3.keccak(hexstr="1901" + domain_hash[2:] + struct_hash.hex()[2:])

    # Sign
    account = Account.from_key(private_key)
    signed_msg = account.signHash(payload_hash)

    return {
        "from": from_address,
        "to": to_address,
        "value": amount_wei,
        "validAfter": valid_after,
        "validBefore": valid_before,
        "nonce": nonce,
        "signature": signed_msg.signature.hex(),
    }
