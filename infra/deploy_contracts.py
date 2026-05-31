#!/usr/bin/env python3
"""
agentsafe_deploy.py — Production deployment script for Base Mainnet.
Compiles Solidity contracts, deploys them, and generates deployment artifacts.

Usage:
    cp .env.example .env  # Edit with your private key
    python scripts/deploy.py --network base  # Deploy to Base Mainnet
    python scripts/deploy.py --network local # Deploy to local Anvil for testing
"""
import os
import sys
import json
from pathlib import Path

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
from dotenv import load_dotenv

# ── Configuration ──────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent
CONTRACTS_DIR = ROOT_DIR / "contracts"
ARTIFACTS_DIR = ROOT_DIR / "artifacts"

load_dotenv(ROOT_DIR / ".env")

BASE_RPC = os.getenv("BASE_RPC_URL", "https://mainnet.base.org")
BASE_CHAIN_ID = int(os.getenv("BASE_CHAIN_ID", "8453"))
PRIVATE_KEY = os.getenv("DEPLOYER_PRIVATE_KEY", "")
USDC_ADDRESS = os.getenv(
    "USDC_ADDRESS", "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
)
SOLC_VERSION = os.getenv("SOLIDITY_VERSION", "0.8.24")

# OpenZeppelin remote paths (we fetch them via CDN)
OZ_BASE_URL = "https://raw.githubusercontent.com/OpenZeppelin/openzeppelin-contracts/v5.0.0/contracts"
OZ_IMPORTS = {
    "@openzeppelin/contracts/access/Ownable.sol": f"{OZ_BASE_URL}/access/Ownable.sol",
    "@openzeppelin/contracts/token/ERC20/IERC20.sol": f"{OZ_BASE_URL}/token/ERC20/IERC20.sol",
    "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol": f"{OZ_BASE_URL}/token/ERC20/utils/SafeERC20.sol",
    "@openzeppelin/contracts/utils/ReentrancyGuard.sol": f"{OZ_BASE_URL}/utils/ReentrancyGuard.sol",
}


# ── Solidity Compilation ──────────────────────────────────
def setup_solc(version: str):
    """Install and configure Solidity compiler."""
    import solcx

    try:
        installed = solcx.get_installed_solc_versions()
        if version not in installed:
            print(f"🔨 Installing solc {version}...")
            solcx.install_solc(version)
        solcx.set_solc_version(version)
    except solcx.exceptions.SolcError as e:
        print(f"❌ solcx error: {e}")
        print("💡 Try: pip install py-solc-x>=2.0 and ensure network access")
        sys.exit(1)
    return solcx


def resolve_imports(source_code: str) -> dict:
    """Resolve OpenZeppelin imports by fetching from CDN."""
    import requests as req

    imports = {}
    for pragma_path, url in OZ_IMPORTS.items():
        if pragma_path in source_code:
            resp = req.get(url, timeout=30)
            resp.raise_for_status()
            imports[pragma_path] = {"content": resp.text}
    return imports


def compile_contract(name: str, solcx_mod) -> dict:
    """Compile a single Solidity file and return bytecode + ABI."""
    source_path = CONTRACTS_DIR / f"{name}.sol"
    if not source_path.exists():
        print(f"⚠️  Contract not found: {source_path}")
        return {}

    source_code = source_path.read_text()
    imports = resolve_imports(source_code)

    # Add source as the main file
    all_sources = {f"{name}.sol": {"content": source_code}}
    all_sources.update(imports)

    print(f"🔨 Compiling {name}.sol...")
    compiled = solcx_mod.compile_standard(
        {
            "language": "Solidity",
            "sources": all_sources,
            "settings": {
                "outputSelection": {"*": {"*": ["abi", "evm.bytecode.object"]}},
                "optimizer": {"enabled": True, "runs": 200},
            },
        },
        import_remappings=[
            f"@openzeppelin/contracts={OZ_BASE_URL}",
            f"@openzeppelin/contracts/access={OZ_BASE_URL}/access",
            f"@openzeppelin/contracts/token={OZ_BASE_URL}/token",
            f"@openzeppelin/contracts/token/ERC20={OZ_BASE_URL}/token/ERC20",
            f"@openzeppelin/contracts/token/ERC20/utils={OZ_BASE_URL}/token/ERC20/utils",
            f"@openzeppelin/contracts/utils={OZ_BASE_URL}/utils",
        ],
    )

    # Extract ABI and bytecode
    for file_key, contracts in compiled["contracts"].items():
        for contract_name, data in contracts.items():
            bytecode = data["evm"]["bytecode"]["object"]
            abi = data["abi"]
            return {"abi": abi, "bytecode": bytecode}

    return {}


# ── Deployment ────────────────────────────────────────────
def deploy_contract(w3: Web3, account: Account, name: str, compiled: dict, constructor_args: list = None) -> str:
    """Deploy a contract and return its address."""
    if not compiled or not compiled.get("bytecode"):
        print(f"⚠️  No bytecode for {name}")
        return ""

    if constructor_args is None:
        constructor_args = []

    contract = w3.eth.contract(abi=compiled["abi"], bytecode=compiled["bytecode"])

    nonce = w3.eth.get_transaction_count(account.address)
    gas_price = w3.eth.gas_price

    tx = contract.constructor(*constructor_args).build_transaction({
        "from": account.address,
        "nonce": nonce,
        "gas": 2_000_000,
        "gasPrice": gas_price,
        "chainId": BASE_CHAIN_ID,
    })

    signed = w3.eth.account.sign_transaction(tx, account.key)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    tx_hex = tx_hash.hex()

    print(f"🚀 Deploying {name}... Tx: {tx_hex}")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

    if receipt.status != 1:
        print(f"❌ Deployment failed! Revert. Tx: {tx_hex}")
        return ""

    addr = receipt.contractAddress
    gas_used = receipt.gasUsed
    print(f"✅ {name} deployed at: {addr} (Gas: {gas_used:,})")
    return addr


def main():
    network = "base"
    if len(sys.argv) > 1:
        network = sys.argv[1]

    print("═" * 60)
    print(f"  agentsafe v0.5.0 — Deploy to {network.upper()}")
    print("═" * 60)

    # Setup solc
    solcx_mod = setup_solc(SOLC_VERSION)

    # Connect to network
    w3 = Web3(Web3.HTTPProvider(BASE_RPC))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    if not w3.is_connected():
        print(f"❌ Failed to connect to {BASE_RPC}")
        sys.exit(1)

    block = w3.eth.block_number
    print(f"🌐 Connected to {network}: block #{block:,}")

    # Account setup
    if not PRIVATE_KEY:
        print("❌ DEPLOYER_PRIVATE_KEY not set in .env")
        sys.exit(1)

    account = Account.from_key(PRIVATE_KEY)
    balance = w3.eth.get_balance(account.address)
    balance_eth = w3.from_wei(balance, "ether")
    print(f"💰 Deployer: {account.address}")
    print(f"💵 Balance: {balance_eth:.4f} ETH")

    if balance < w3.to_wei(0.001, "ether"):
        print("⚠️  Low ETH balance. Need at least 0.001 ETH for gas.")

    # Compile & deploy
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    deployments = {}

    # 1. Deploy SessionGuard
    compiled_sg = compile_contract("SessionGuard", solcx_mod)
    if compiled_sg:
        sg_addr = deploy_contract(w3, account, "SessionGuard", compiled_sg, [USDC_ADDRESS])
        if sg_addr:
            deployments["SessionGuard"] = {
                "address": sg_addr,
                "abi": compiled_sg["abi"],
            }

    # 2. Deploy EscrowSimple
    compiled_es = compile_contract("EscrowSimple", solcx_mod)
    if compiled_es:
        es_addr = deploy_contract(w3, account, "EscrowSimple", compiled_es, [USDC_ADDRESS])
        if es_addr:
            deployments["EscrowSimple"] = {
                "address": es_addr,
                "abi": compiled_es["abi"],
            }

    # 3. Deploy AgentRegistry
    compiled_ar = compile_contract("AgentRegistry", solcx_mod)
    if compiled_ar:
        ar_addr = deploy_contract(w3, account, "AgentRegistry", compiled_ar)
        if ar_addr:
            deployments["AgentRegistry"] = {
                "address": ar_addr,
                "abi": compiled_ar["abi"],
            }

    if not deployments:
        print("❌ No contracts deployed successfully.")
        sys.exit(1)

    # Save artifacts (ABIs only, addresses)
    deployment_json = {
        "network": network,
        "chainId": BASE_CHAIN_ID,
        "deployer": account.address,
        "timestamp": w3.eth.block_number,
        "contracts": {},
    }

    for name, data in deployments.items():
        deployment_json["contracts"][name] = {
            "address": data["address"],
            "abi": data["abi"],
        }

    artifact_file = ARTIFACTS_DIR / f"deployment-{network}.json"
    artifact_file.write_text(json.dumps(deployment_json, indent=2))

    # Also save ABI-only files for frontend usage
    for name, data in deployments.items():
        abi_file = ARTIFACTS_DIR / f"{name}.json"
        abi_file.write_text(json.dumps(data["abi"], indent=2))

    print("\n" + "═" * 60)
    print("  🎉 DEPLOYMENT COMPLETE")
    print("═" * 60)
    for name, data in deployments.items():
        print(f"  {name}: {data['address']}")
    print(f"\n  Artifacts saved to: {artifact_file}")
    print(f"  Update .env with: SESSION_GUARD={deployments['SessionGuard']['address']}")


if __name__ == "__main__":
    main()
