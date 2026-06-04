//! Merkle Cross-Shard Reconciliation
//! EPISTEMIC TIER: T2
//!
//! Binary Merkle tree over shard terminal hashes. Each AEGIS shard maintains
//! its own hash chain; this module produces a single cross-shard root that any
//! verifier can check in O(log n) — without downloading all chains.
//!
//! Hash invariants:
//!   - Leaf hash: shard terminal hash (`[u8; 32]`) passed in as-is
//!   - Internal node: SHA-256(left_child || right_child), big-endian concatenation
//!   - Odd leaf count: last leaf is duplicated (standard Merkle padding)
//!   - Empty tree: returns CROSS_SHARD_GENESIS_HASH = [0u8; 32]
//!
//! Source: bls-threshold-aggregation skill (Merkle cross-shard component, T2).
//! BLS pairing operations are a separate concern requiring bls12_381 crate.

use sha2::{Sha256, Digest};

pub const CROSS_SHARD_GENESIS_HASH: [u8; 32] = [0u8; 32];

/// Proof that a leaf hash is included in a Merkle root.
/// Each element is (sibling_hash, is_left_sibling).
#[derive(Debug, Clone)]
pub struct MerkleProof {
    pub path: Vec<([u8; 32], bool)>,
}

/// Merkle tree over shard terminal hashes.
pub struct MerkleCrossShardTree {
    leaves: Vec<[u8; 32]>,
}

impl MerkleCrossShardTree {
    pub fn new(shard_terminal_hashes: Vec<[u8; 32]>) -> Self {
        Self { leaves: shard_terminal_hashes }
    }

    /// Compute and return the Merkle root hash.
    /// Returns CROSS_SHARD_GENESIS_HASH for an empty tree.
    pub fn root(&self) -> [u8; 32] {
        if self.leaves.is_empty() {
            return CROSS_SHARD_GENESIS_HASH;
        }
        let mut layer: Vec<[u8; 32]> = self.leaves.clone();
        while layer.len() > 1 {
            layer = Self::next_layer(&layer);
        }
        layer[0]
    }

    /// Generate an inclusion proof for leaf at `index`.
    /// Returns None if index is out of bounds.
    pub fn prove(&self, index: usize) -> Option<MerkleProof> {
        if index >= self.leaves.len() {
            return None;
        }
        let mut path = Vec::new();
        let mut layer: Vec<[u8; 32]> = self.leaves.clone();
        let mut idx = index;
        while layer.len() > 1 {
            let padded = Self::pad(&layer);
            let sibling_idx = if idx % 2 == 0 { idx + 1 } else { idx - 1 };
            let sibling = padded[sibling_idx.min(padded.len() - 1)];
            path.push((sibling, idx % 2 == 1));
            layer = Self::next_layer(&layer);
            idx /= 2;
        }
        Some(MerkleProof { path })
    }

    /// Verify that `leaf` is included at position `index` given a proof and root.
    /// O(log n) — walks the proof path without accessing any leaves.
    pub fn verify(root: &[u8; 32], leaf: &[u8; 32], proof: &MerkleProof) -> bool {
        let mut current = *leaf;
        for (sibling, is_left_sibling) in &proof.path {
            current = if *is_left_sibling {
                Self::hash_pair(sibling, &current)
            } else {
                Self::hash_pair(&current, sibling)
            };
        }
        &current == root
    }

    fn hash_pair(left: &[u8; 32], right: &[u8; 32]) -> [u8; 32] {
        let mut hasher = Sha256::new();
        hasher.update(left);
        hasher.update(right);
        hasher.finalize().into()
    }

    fn pad(layer: &[[u8; 32]]) -> Vec<[u8; 32]> {
        let mut padded = layer.to_vec();
        if padded.len() % 2 == 1 {
            padded.push(*padded.last().unwrap());
        }
        padded
    }

    fn next_layer(layer: &[[u8; 32]]) -> Vec<[u8; 32]> {
        let padded = Self::pad(layer);
        padded.chunks(2)
            .map(|pair| Self::hash_pair(&pair[0], &pair[1]))
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn h(byte: u8) -> [u8; 32] { let mut a = [0u8; 32]; a[0] = byte; a }

    #[test]
    fn empty_tree_returns_genesis() {
        let tree = MerkleCrossShardTree::new(vec![]);
        assert_eq!(tree.root(), CROSS_SHARD_GENESIS_HASH);
    }

    #[test]
    fn single_shard_root_equals_leaf() {
        let leaf = h(0xAB);
        let tree = MerkleCrossShardTree::new(vec![leaf]);
        assert_eq!(tree.root(), leaf);
    }

    #[test]
    fn two_shards_root_is_hash_of_pair() {
        let l0 = h(0x01);
        let l1 = h(0x02);
        let tree = MerkleCrossShardTree::new(vec![l0, l1]);
        let expected = {
            let mut hasher = sha2::Sha256::new();
            hasher.update(&l0);
            hasher.update(&l1);
            let out: [u8; 32] = hasher.finalize().into();
            out
        };
        assert_eq!(tree.root(), expected);
    }

    #[test]
    fn root_changes_when_any_leaf_changes() {
        let leaves = vec![h(1), h(2), h(3), h(4)];
        let root1 = MerkleCrossShardTree::new(leaves.clone()).root();
        let mut modified = leaves.clone();
        modified[2] = h(99);
        let root2 = MerkleCrossShardTree::new(modified).root();
        assert_ne!(root1, root2);
    }

    #[test]
    fn determinism_triple() {
        let leaves = vec![h(10), h(20), h(30), h(40), h(50)];
        let r1 = MerkleCrossShardTree::new(leaves.clone()).root();
        let r2 = MerkleCrossShardTree::new(leaves.clone()).root();
        let r3 = MerkleCrossShardTree::new(leaves.clone()).root();
        assert_eq!(r1, r2);
        assert_eq!(r2, r3);
    }

    #[test]
    fn odd_leaf_count_does_not_panic() {
        let tree = MerkleCrossShardTree::new(vec![h(1), h(2), h(3)]);
        let root = tree.root();
        assert_ne!(root, CROSS_SHARD_GENESIS_HASH);
    }

    #[test]
    fn prove_returns_none_for_out_of_bounds() {
        let tree = MerkleCrossShardTree::new(vec![h(1), h(2)]);
        assert!(tree.prove(2).is_none());
        assert!(tree.prove(100).is_none());
    }

    #[test]
    fn proof_verification_valid() {
        let leaves = vec![h(1), h(2), h(3), h(4)];
        let tree = MerkleCrossShardTree::new(leaves.clone());
        let root = tree.root();
        for i in 0..4 {
            let proof = tree.prove(i).unwrap();
            assert!(MerkleCrossShardTree::verify(&root, &leaves[i], &proof),
                "proof for leaf {i} should verify");
        }
    }

    #[test]
    fn tampered_leaf_fails_verification() {
        let leaves = vec![h(1), h(2), h(3), h(4)];
        let tree = MerkleCrossShardTree::new(leaves.clone());
        let root = tree.root();
        let proof = tree.prove(1).unwrap();
        let wrong_leaf = h(0xFF);
        assert!(!MerkleCrossShardTree::verify(&root, &wrong_leaf, &proof));
    }

    #[test]
    fn tampered_proof_fails_verification() {
        let leaves = vec![h(1), h(2), h(3), h(4)];
        let tree = MerkleCrossShardTree::new(leaves.clone());
        let root = tree.root();
        let mut proof = tree.prove(0).unwrap();
        proof.path[0].0 = h(0xDE); // corrupt first sibling
        assert!(!MerkleCrossShardTree::verify(&root, &leaves[0], &proof));
    }

    #[test]
    fn four_leaf_tree_has_two_level_proof() {
        let leaves = vec![h(1), h(2), h(3), h(4)];
        let tree = MerkleCrossShardTree::new(leaves);
        let proof = tree.prove(0).unwrap();
        assert_eq!(proof.path.len(), 2, "4 leaves → 2-level proof (O(log 4))");
    }

    #[test]
    fn genesis_hash_is_all_zeros() {
        assert_eq!(CROSS_SHARD_GENESIS_HASH, [0u8; 32]);
    }
}
