"""AuditChain — tamper-evident hash-chain audit log."""

import hashlib
import json
import time
from pathlib import Path


class AuditChain:
    """Append-only, hash-chained audit log.

    Every entry includes the hash of the previous entry, making it
    tamper-evident. Rewriting any entry invalidates all subsequent hashes.

    Storage: JSONL (one JSON object per line) — easy to stream and verify.
    """

    def __init__(self, storage_path: str = "audit.jsonl"):
        self._path = Path(storage_path)
        self._last_hash = self._load_last_hash()

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
