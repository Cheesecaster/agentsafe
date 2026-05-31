use sha2::{Digest, Sha256};

/// A simple Merkle Tree implementation for audit logging.
pub struct MerkleTree {
    pub leaves: Vec<String>,
    pub root: Option<String>,
}

impl MerkleTree {
    pub fn new() -> Self {
        Self {
            leaves: Vec::new(),
            root: None,
        }
    }

    /// Add a new log entry to the tree.
    pub fn append(&mut self, entry: &str) {
        self.leaves.push(entry.to_string());
        self.recalculate_root();
    }

    /// Recalculate the root hash based on all leaves.
    /// Uses a naive linear approach for simplicity & speed in audit context.
    fn recalculate_root(&mut self) {
        if self.leaves.is_empty() {
            self.root = None;
            return;
        }

        let mut current_hashes: Vec<Vec<u8>> = self
            .leaves
            .iter()
            .map(|s| {
                let mut hasher = Sha256::new();
                hasher.update(s.as_bytes());
                hasher.finalize().to_vec()
            })
            .collect();

        if current_hashes.len() == 1 {
            self.root = Some(hex::encode(&current_hashes[0]));
            return;
        }

        // Build the tree upwards
        while current_hashes.len() > 1 {
            let mut next_level: Vec<Vec<u8>> = Vec::new();
            for chunk in current_hashes.chunks(2) {
                match chunk {
                    [left, right] => {
                        let mut hasher = Sha256::new();
                        hasher.update(left);
                        hasher.update(right);
                        next_level.push(hasher.finalize().to_vec());
                    }
                    [only] => next_level.push(only.clone()),
                    _ => {}
                }
            }
            current_hashes = next_level;
        }

        if let Some(final_hash) = current_hashes.first() {
            self.root = Some(hex::encode(final_hash));
        }
    }

    /// Return the current Merkle Root.
    pub fn get_root(&self) -> Option<String> {
        self.root.clone()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tree_growth() {
        let mut tree = MerkleTree::new();
        assert_eq!(tree.get_root(), None);

        tree.append("log_1");
        let root1 = tree.get_root().unwrap();
        assert!(!root1.is_empty());

        tree.append("log_2");
        let root2 = tree.get_root().unwrap();
        assert_ne!(root1, root2);
    }
}
