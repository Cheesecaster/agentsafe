"""Merkle Tree implementation for Audit Anchoring.

Adapts Brain.fi's Layer 6 architecture (Merkle Anchoring) for agentsafe.
Transforms the linear audit log into a verifiable Merkle Tree.
"""

import hashlib

class MerkleNode:
    def __init__(self, left=None, right=None, hash_val=None):
        self.left = left
        self.right = right
        self.hash = hash_val

class MerkleTree:
    """Builds a Merkle Tree from a list of hashes (audit entries).
    
    Can be used as static methods or as an instance-based appendable tree.
    """

    def __init__(self):
        self._leaves: list[str] = []

    def append(self, data: str):
        """Add a leaf entry to the tree."""
        self._leaves.append(data)

    def get_root(self) -> str | None:
        """Returns the current Root Hash."""
        if not self._leaves:
            return None
        return MerkleTree.get_root_hash(self._leaves)

    @staticmethod
    def _hash(data: str) -> str:
        return hashlib.sha256(data.encode('utf-8')).hexdigest()

    @staticmethod
    def build(leaf_data: list[str]):
        """Builds the tree and returns the list of nodes (bottom-up)."""
        if not leaf_data:
            return None
        
        # Create leaf nodes
        nodes = []
        for data in leaf_data:
            nodes.append(MerkleNode(hash_val=MerkleTree._hash(data)))

        # Build up
        while len(nodes) > 1:
            next_level = []
            for i in range(0, len(nodes), 2):
                left = nodes[i]
                right = nodes[i+1] if (i+1) < len(nodes) else nodes[i] # Duplicate last if odd
                combined_hash = MerkleTree._hash(left.hash + right.hash)
                next_level.append(MerkleNode(left=left, right=right, hash_val=combined_hash))
            nodes = next_level
            
        return nodes[0] if nodes else None

    @staticmethod
    def get_root_hash(leaf_data: list[str]) -> str:
        """Returns the Root Hash of the tree."""
        root = MerkleTree.build(leaf_data)
        return root.hash if root else ""

    @staticmethod
    def verify_proof(root_hash: str, leaf_data: str, proof_hashes: list[tuple[str, str]]) -> bool:
        """Verifies if leaf_data belongs to root_hash using the proof path."""
        current_hash = MerkleTree._hash(leaf_data)
        for direction, sibling_hash in proof_hashes:
            if direction == 'left':
                current_hash = MerkleTree._hash(sibling_hash + current_hash)
            else:
                current_hash = MerkleTree._hash(current_hash + sibling_hash)
        
        return current_hash == root_hash
