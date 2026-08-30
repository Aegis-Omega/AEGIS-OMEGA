//! Gate 208: Triadic Merkle-Patricia Node
//! Implements 3-layer distributed semantic state management with geometric variance gating.
//! Gates state mutations behind geometric variance checks.

use std::collections::BTreeMap;
use sha2::{Sha256, Digest};
use crate::geometric_variance::TensorWeights;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TriadicState {
    /// Geometric alignment verified; safe to commit.
    Equilibrium,
    /// Divergence detected; gossip reconciliation required.
    Morphing,
    /// Auditor intervention; state mutation rejected.
    VetoCollapse,
}

pub struct TriadicMerkleNode {
    pub node_id: String,
    pub children: BTreeMap<String, String>, // Path -> Child Hash
    pub weights: TensorWeights,
    pub auditor_threshold: f64,
}

impl TriadicMerkleNode {
    pub fn new(id: &str, size: usize, threshold: f64) -> Self {
        Self {
            node_id: id.to_string(),
            children: BTreeMap::new(),
            weights: TensorWeights::new(size, 1.0),
            auditor_threshold: threshold,
        }
    }

    /// Attempts to mutate the node state. The Auditor vetoes if geometric variance is too high.
    pub fn commit_mutation(&mut self, key: &str, value_hash: &str) -> TriadicState {
        let variance = self.weights.compute_geometric_variance();

        if variance > self.auditor_threshold * 2.0 {
            // VetoCollapse: The latent subspaces are critically misaligned.
            return TriadicState::VetoCollapse;
        }
        
        if variance > self.auditor_threshold {
            // Morphing: State is drifting; commit locally but flag for mesh reconciliation.
            self.children.insert(key.to_string(), value_hash.to_string());
            return TriadicState::Morphing;
        }

        // Equilibrium: Subspaces are geometrically aligned. Commit securely.
        self.children.insert(key.to_string(), value_hash.to_string());
        TriadicState::Equilibrium
    }

    /// Computes the cryptographic seal of the current node state.
    pub fn compute_seal(&self) -> [u8; 32] {
        let mut hasher = Sha256::new();
        hasher.update(self.node_id.as_bytes());
        
        // Sort keys to ensure deterministic hashing
        let mut keys: Vec<&String> = self.children.keys().collect();
        keys.sort();
        
        for k in keys {
            hasher.update(k.as_bytes());
            hasher.update(self.children[k].as_bytes());
        }
        
        hasher.finalize().into()
    }

    /// Returns the number of children (branching factor).
    pub fn branch_count(&self) -> usize {
        self.children.len()
    }

    /// Retrieves a child hash by key.
    pub fn get_child(&self, key: &str) -> Option<&String> {
        self.children.get(key)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_auditor_veto() {
        let mut node = TriadicMerkleNode::new("root", 2, 0.5);
        // Inject severe misalignment
        node.weights.planner = vec![10.0, 0.0];
        node.weights.generator = vec![0.0, 10.0];
        
        let state = node.commit_mutation("key1", "hash1");
        assert_eq!(state, TriadicState::VetoCollapse);
        assert!(node.children.is_empty(), "Mutation must be rejected by Auditor.");
    }

    #[test]
    fn test_equilibrium_commit() {
        let mut node = TriadicMerkleNode::new("root", 2, 0.5);
        // Perfect alignment - variance = 0
        
        let state = node.commit_mutation("key1", "hash1");
        assert_eq!(state, TriadicState::Equilibrium);
        assert_eq!(node.branch_count(), 1);
        assert_eq!(node.get_child("key1"), Some(&"hash1".to_string()));
    }

    #[test]
    fn test_morphing_state() {
        // variance = 0.5; threshold must satisfy: threshold < 0.5 < 2*threshold → use 0.3
        let mut node = TriadicMerkleNode::new("root", 2, 0.3);
        node.weights.planner = vec![1.5, 0.5];
        node.weights.generator = vec![0.5, 1.5];
        node.weights.evaluator = vec![1.0, 1.0];
        
        let state = node.commit_mutation("key1", "hash1");
        assert_eq!(state, TriadicState::Morphing);
        assert_eq!(node.branch_count(), 1);
    }

    #[test]
    fn test_deterministic_seal() {
        let mut node1 = TriadicMerkleNode::new("root", 2, 0.5);
        let mut node2 = TriadicMerkleNode::new("root", 2, 0.5);
        
        // Insert in different order
        node1.commit_mutation("b", "hash_b");
        node1.commit_mutation("a", "hash_a");
        
        node2.commit_mutation("a", "hash_a");
        node2.commit_mutation("b", "hash_b");
        
        let seal1 = node1.compute_seal();
        let seal2 = node2.compute_seal();
        
        assert_eq!(seal1, seal2, "Seals must be identical regardless of insertion order");
    }

    #[test]
    fn test_scalar_flaw_integration() {
        let mut node = TriadicMerkleNode::new("root", 2, 0.1);
        // This is the scalar flaw case: sums equal but orthogonal
        node.weights.planner = vec![1.0, 0.0];
        node.weights.generator = vec![0.0, 1.0];
        node.weights.evaluator = vec![0.5, 0.5];

        // Scalar variance would be 0, but geometric variance catches it
        let geometric_var = node.weights.compute_geometric_variance();
        assert!(geometric_var > 0.1, "Must detect orthogonal misalignment");

        // Should trigger Morphing or VetoCollapse depending on threshold
        let state = node.commit_mutation("key1", "hash1");
        assert_ne!(state, TriadicState::Equilibrium, "Should not be equilibrium with orthogonal vectors");
    }

    // 6. compute_seal changes after a mutation is committed
    #[test]
    fn seal_changes_after_mutation() {
        let mut node = TriadicMerkleNode::new("root", 2, 0.5);
        let seal_before = node.compute_seal();
        node.commit_mutation("k", "v");
        let seal_after = node.compute_seal();
        assert_ne!(seal_before, seal_after);
    }

    // 7. Two fresh nodes with same ID have identical seals
    #[test]
    fn fresh_nodes_same_id_equal_seal() {
        let n1 = TriadicMerkleNode::new("node_x", 4, 0.5);
        let n2 = TriadicMerkleNode::new("node_x", 4, 0.5);
        assert_eq!(n1.compute_seal(), n2.compute_seal());
    }

    // 8. branch_count increments with each successful commit
    #[test]
    fn branch_count_increments_on_commit() {
        let mut node = TriadicMerkleNode::new("root", 2, 0.5);
        assert_eq!(node.branch_count(), 0);
        node.commit_mutation("a", "hash_a");
        assert_eq!(node.branch_count(), 1);
        node.commit_mutation("b", "hash_b");
        assert_eq!(node.branch_count(), 2);
    }

    // 9. get_child returns the stored hash after commit
    #[test]
    fn get_child_returns_committed_hash() {
        let mut node = TriadicMerkleNode::new("root", 2, 0.5);
        node.commit_mutation("mykey", "myvalue_hash");
        assert_eq!(node.get_child("mykey"), Some(&"myvalue_hash".to_string()));
        assert!(node.get_child("nonexistent").is_none());
    }

    // 10. Different node IDs produce different seals (even with same children)
    #[test]
    fn different_node_ids_different_seals() {
        let mut n1 = TriadicMerkleNode::new("alpha", 2, 0.5);
        let mut n2 = TriadicMerkleNode::new("beta", 2, 0.5);
        n1.commit_mutation("k", "v");
        n2.commit_mutation("k", "v");
        assert_ne!(n1.compute_seal(), n2.compute_seal());
    }
}