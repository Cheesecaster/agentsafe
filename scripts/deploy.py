#!/usr/bin/env python3
"""
deploy.py — Deploy AgentSafe contracts to Base (Ethereum L2).

Usage:
    export PRIVATE_KEY=0x...
    export RPC_URL=https://mainnet.base.org
    python3 scripts/deploy.py

Generates artifacts/deployment-base.json with deployed addresses, ABIs, and tx hashes.

Dependencies:
    pip install eth-account web3 py-solc-x requests
"""

import json
import os
import shutil
import sys
import tarfile
import tempfile
import time
from pathlib import Path

import requests
from eth_account import Account
from solcx import compile_standard, install_solc, get_installed_solc_versions
from web3 import Web3

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = PROJECT_ROOT / "contracts"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
OZ_DIR = PROJECT_ROOT / "lib" / "openzeppelin-contracts"
ARTIFACTS_DIR.mkdir(exist_ok=True)

PRIVATE_KEY = os.environ.get("PRIVATE_KEY")
RPC_URL = os.environ.get("RPC_URL", "https://mainnet.base.org")

BASE_USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

# Solidity version to install (supports ^0.8.24)
SOLC_VERSION = "0.8.24"

# Full OZ release tarball (v5.0.0) — contains all transitive deps
OZ_RELEASE_URL = "https://github.com/OpenZeppelin/openzeppelin-contracts/archive/refs/tags/v5.0.0.tar.gz"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def log(msg: str):
    print(f"[deploy] {msg}")


def ensure_solc() -> None:
    """Install the required solc binary if missing."""
    installed = [str(v) for v in get_installed_solc_versions()]
    if SOLC_VERSION not in installed:
        log(f"Installing solc {SOLC_VERSION} ...")
        install_solc(SOLC_VERSION)
    log(f"solc {SOLC_VERSION} ready")


def ensure_oz_sources() -> Path:
    """Download the full OZ v5.0.0 release tarball and extract it."""
    reentrancy_file = OZ_DIR / "contracts" / "utils" / "ReentrancyGuard.sol"
    if reentrancy_file.exists():
        log(f"OpenZeppelin sources already at {OZ_DIR}")
        return OZ_DIR

    log(f"Downloading OpenZeppelin v5.0.0 ...")
    resp = requests.get(OZ_RELEASE_URL, timeout=60, stream=True)
    resp.raise_for_status()

    with tempfile.TemporaryDirectory() as tmpdir:
        tar_path = Path(tmpdir) / "oz.tar.gz"
        tar_path.write_bytes(resp.content)

        with tarfile.open(tar_path, "r:gz") as tf:
            tf.extractall(tmpdir, filter="data")

        # Extracted to openzeppelin-contracts-5.0.0/
        extracted = Path(tmpdir) / "openzeppelin-contracts-5.0.0"
        if OZ_DIR.exists():
            shutil.rmtree(OZ_DIR)
        shutil.move(str(extracted), str(OZ_DIR))

    log(f"OpenZeppelin sources extracted to {OZ_DIR}")
    return OZ_DIR


def compile_contracts(oz_dir: Path) -> dict:
    """Compile all project sources with OZ remapping."""
    sources = {}
    for sol_file in CONTRACTS_DIR.glob("*.sol"):
        sources[sol_file.name] = {"content": sol_file.read_text()}

    # Absolute remapping path
    oz_abs = str((oz_dir / "contracts").resolve())

    build_input = {
        "language": "Solidity",
        "sources": sources,
        "settings": {
            "optimizer": {"enabled": True, "runs": 200},
            "outputSelection": {
                "*": {
                    "*": ["abi", "evm.bytecode.object", "evm.deployedBytecode.object"],
                    "": ["ast"],
                }
            },
            "remappings": [f"@openzeppelin/contracts/={oz_abs}/"],
        },
    }

    log(f"Compiling {len(sources)} source files ...")
    compiled = compile_standard(
        build_input,
        solc_version=SOLC_VERSION,
        allow_paths=[str(CONTRACTS_DIR.resolve()), str(oz_dir.resolve())],
    )
    return compiled


def get_contract_artifact(compiled: dict, contract_name: str) -> dict:
    """Extract ABI + bytecode for a specific contract name."""
    for filename, data in compiled["contracts"].items():
        if contract_name in data:
            entry = data[contract_name]
            return {
                "abi": entry["abi"],
                "bytecode": entry["evm"]["bytecode"]["object"],
                "deployed_bytecode": entry["evm"]["deployedBytecode"]["object"],
            }
    raise ValueError(f"Contract {contract_name} not found in compiled output")


def deploy_contract(
    w3: Web3,
    account,
    contract_name: str,
    artifact: dict,
    constructor_args=None,
    value: int = 0,
) -> dict:
    """Deploy a contract and return deployment info."""
    abi = artifact["abi"]
    bytecode = artifact["bytecode"]

    contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    tx = contract.constructor(*(constructor_args or [])).build_transaction({
        "from": account.address,
        "value": value,
        "gas": 5_000_000,
        "chainId": w3.eth.chain_id,
        "nonce": w3.eth.get_transaction_count(account.address),
    })

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    log(f"  Deploying {contract_name} ... tx={tx_hash.hex()}")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    address = receipt.contractAddress
    log(f"  {contract_name} deployed at {address}")

    return {
        "name": contract_name,
        "address": address,
        "tx_hash": tx_hash.hex(),
        "block": receipt.blockNumber,
        "gas_used": receipt.gasUsed,
        "abi": abi,
        "bytecode": artifact["bytecode"],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if not PRIVATE_KEY:
        log("ERROR: PRIVATE_KEY environment variable not set")
        sys.exit(1)

    log(f"Target RPC: {RPC_URL}")

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        log("ERROR: Cannot connect to RPC")
        sys.exit(1)

    account = Account.from_key(PRIVATE_KEY)
    balance = w3.eth.get_balance(account.address)
    log(f"Deployer: {account.address} (balance: {balance/1e18:.4f} ETH)")

    # --- Setup ---
    ensure_solc()
    oz_dir = ensure_oz_sources()

    # --- Compile ---
    compiled = compile_contracts(oz_dir)

    # --- Deploy ---
    results = {
        "chain_id": w3.eth.chain_id,
        "rpc": RPC_URL,
        "deployer": account.address,
        "timestamp": int(time.time()),
        "contracts": {},
    }

    contracts_to_deploy = [
        ("AgentRegistry", None, 0),
        ("SessionGuard", None, 0),
        ("EscrowSimple", None, 0),
    ]

    for name, args, value in contracts_to_deploy:
        artifact = get_contract_artifact(compiled, name)
        info = deploy_contract(w3, account, name, artifact, args, value)
        results["contracts"][name] = {
            "address": info["address"],
            "tx_hash": info["tx_hash"],
            "block": info["block"],
            "gas_used": info["gas_used"],
        }

        # Save ABI to individual file
        abi_path = ARTIFACTS_DIR / f"{name}_abi.json"
        abi_path.write_text(json.dumps(artifact["abi"], indent=2))
        log(f"  ABI saved: {abi_path}")

    # Write full deployment manifest
    manifest_path = ARTIFACTS_DIR / "deployment-base.json"
    manifest = {
        "chain_id": results["chain_id"],
        "rpc": results["rpc"],
        "deployer": results["deployer"],
        "timestamp": results["timestamp"],
        "contracts": results["contracts"],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))

    log(f"\nDeployment manifest: {manifest_path}")
    log("=" * 50)
    for name, info in results["contracts"].items():
        log(f"  {name}: {info['address']}")
    log("=" * 50)
    log("Done!")

    return results


if __name__ == "__main__":
    main()
