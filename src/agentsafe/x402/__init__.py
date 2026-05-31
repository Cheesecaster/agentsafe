"""x402 payment client for Base Network (agentsafe[x402])."""

try:
    from .client import X402Client, X402PaymentError
    from .eip3009 import prepare_transfer_with_authorization
    
    __all__ = ["X402Client", "X402PaymentError", "prepare_transfer_with_authorization"]
except ImportError as e:
    # Graceful fallback if dependencies (web3, eth_account) aren't installed
    X402Client = None
    X402PaymentError = None
    prepare_transfer_with_authorization = None
