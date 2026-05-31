"""AuditChain — tamper-evident hash-chain audit log with Merkle Anchoring.

Adapted from Brain.fi architecture (Layer 6: Audit/Merkle Anchoring).
"""

import hashlib
import json
import time
from pathlib import Path

from .merkle import MerkleTree


class AuditChain:
    """Append-only, hash-chained audit log with Merkle Anchoring.

    Every entry includes the hash of the previous entry, making it
    tamper-evident. Rewriting any entry invalidates all subsequent hashes.
    
    Additionally, the log can be aggregated into a Merkle Tree to produce
    a 'Merkle Root'—a single cryptographic fingerprint of the entire log.
    This root is what would be anchored on-chain (Base L2) in Brain.fi style.
    """

    def __init__(self, storage_path: str = "audit.jsonl"):
        self._path = Path(storage_path)
        self._last_hash = self._load_last_hash()

    @property
    def merkle_root(self) -> str:
        """Compute the Merkle Root of the current audit log.
        
        This is the 'fingerprint' of all actions taken by the agent.
        """
        entries = self._read_all()
        if not entries:
            return ""
        # Create leaf data string (hash + ts + action + session_id for agent attribution)
        leaves = []
        for e in entries:
            session_id = e.get("details", {}).get("session_id", "")
            leaves.append(f"{e['hash']}-{e['ts']}-{e['action']}-{session_id}")
        return MerkleTree.get_root_hash(leaves)

    def log(self, action: str, details: dict) -> str:
        """Append an audit entry. Returns the entry hash."""
        entry = {
            "ts": time.time(),
            "action": action,
            "details": details,
            "prev_hash": self._last_hash,
        }
        entry_str = json.dumps(entry, sort_keys=True)
        entry["hash"] = hashlib.sha256(entry_str.encode()).hexdigest()
        self._last_hash = entry["hash"]

        with open(self._path, "a") as f:
            f.write(json.dumps(entry) + "\n")

        return entry["hash"]

    def verify(self) -> bool:
        """Verify the integrity of the entire audit chain."""
        if not self._path.exists():
            return True

        entries = self._read_all()
        if not entries:
            return True

        prev_hash = entries[0].get("prev_hash", "")
        for entry in entries:
            # Recompute hash without the "hash" field
            check_entry = {
                "ts": entry["ts"],
                "action": entry["action"],
                "details": entry["details"],
                "prev_hash": prev_hash,
            }
            expected_hash = hashlib.sha256(
                json.dumps(check_entry, sort_keys=True).encode()
            ).hexdigest()

            if entry.get("hash") != expected_hash:
                return False

            prev_hash = entry["hash"]
        return True

    def entries(self, hours: float = 24) -> list[dict]:
        """Return entries from the last N hours."""
        cutoff = time.time() - (hours * 3600)
        result = []
        for entry in self._read_all():
            if entry.get("ts", 0) >= cutoff:
                result.append(entry)
        return result

    def export(self, path: str) -> int:
        """Export audit log to a new file. Returns entry count."""
        entries = self._read_all()
        count = 0
        with open(path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
                count += 1
        return count

    @property
    def count(self) -> int:
        if not self._path.exists():
            return 0
        with open(self._path) as f:
            return sum(1 for _ in f)

    def get_recent_logs(self, n: int = 10) -> list[dict]:
        """Return the last N log entries."""
        all_entries = self._read_all()
        return all_entries[-n:] if all_entries else []

    def _read_all(self) -> list[dict]:
        if not self._path.exists():
            return []
        entries = []
        with open(self._path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return entries

    def _load_last_hash(self) -> str:
        """Load the last hash from the chain (for continuation)."""
        entries = self._read_all()
        if entries:
            return entries[-1].get("hash", "")
        return ""
