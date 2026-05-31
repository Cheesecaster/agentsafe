"""Merkle tree — cryptographic integrity log."""

import hashlib


class MerkleTree:
    """A simple SHA-256 Merkle tree for integrity verification."""

    def __init__(self):
        self._leaves: list = []

    def append(self, data: str) -> None:
        """Append a leaf to the tree."""
        self._leaves.append(data)

    def get_root(self) -> str:
        """Compute the Merkle root hash."""
        return self._compute_root(self._leaves)

    @staticmethod
    def get_root_of(leaves: list) -> str:
        """Compute a Merkle root from an explicit list of leaves."""
        return MerkleTree._compute_root(leaves)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_root(items: list) -> str:
        if not items:
            return hashlib.sha256(b"").hexdigest()

        # Hash each leaf
        hashes = [hashlib.sha256(str(item).encode()).hexdigest() for item in items]

        # Build tree bottom-up
        while len(hashes) > 1:
            if len(hashes) % 2 != 0:
                hashes.append(hashes[-1])  # duplicate last if odd
            next_level = []
            for i in range(0, len(hashes), 2):
                combined = hashes[i] + hashes[i + 1]
                next_level.append(hashlib.sha256(combined.encode()).hexdigest())
            hashes = next_level

        return hashes[0]

    def __len__(self) -> int:
        return len(self._leaves)
