"""JSON file DB with file locking for thread-safe read/write."""

import json
import os
import fcntl
from typing import Any, Dict, Optional


class JSONDB:
    """Simple JSON file-based database with POSIX file locking.

    Uses fcntl.flock for read/write locking to prevent concurrent corruption.
    """

    def __init__(self, path: str = "agentsafe.db.json"):
        self._path = path
        self._data: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self._path):
            self._data = {}
            return
        try:
            with open(self._path, "r") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    self._data = json.load(f)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except (json.JSONDecodeError, IOError):
            self._data = {}

    def _save(self) -> None:
        try:
            with open(self._path, "w") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    json.dump(self._data, f, indent=2)
                    f.flush()
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except IOError:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        self._load()
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._save()

    def delete(self, key: str) -> bool:
        if key in self._data:
            del self._data[key]
            self._save()
            return True
        return False
