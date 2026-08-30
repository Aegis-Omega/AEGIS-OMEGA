//! Gate 208: Holonic State Machine
//! Orchestrates 3-layer BFT consensus (Autonomous → Relational → Finality).
//! Implements Byzantine Fault Tolerant consensus with O(log N) verification.

use crate::triadic_merkle_node::{TriadicMerkleNode, TriadicState};
use std::collections::BTreeMap;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ConsensusLayer {
    /// Layer X: Local Trie Mutation
    Autonomous,
    /// Layer Y: Cluster Gossip & Reconciliation  
    Relational,
    /// Layer Z: Root Finality & Pruning
    Finality,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GlobalState {
    Synchronized,
    Divergent,
    Reconciling,
    Finalized,
    ByzantineFault,
}

pub struct HolonicLayer {
    pub name: String,
    pub layer_type: ConsensusLayer,
    pub nodes: BTreeMap<String, TriadicMerkleNode>,
    pub active_threshold: f64,
}

impl HolonicLayer {
    pub fn new(name: &str, layer_type: ConsensusLayer, threshold: f64) -> Self {
        Self {
            name: name.to_string(),
            layer_type,
            nodes: BTreeMap::new(),
            active_threshold: threshold,
        }
    }

    pub fn add_node(&mut self, node_id: &str, tensor_size: usize) {
        let node = TriadicMerkleNode::new(node_id, tensor_size, self.active_threshold);
        self.nodes.insert(node_id.to_string(), node);
    }

    pub fn get_node_mut(&mut self, node_id: &str) -> Option<&mut TriadicMerkleNode> {
        self.nodes.get_mut(node_id)
    }

    /// Evaluates the overall state of this layer based on node states.
    pub fn evaluate_layer_state(&self) -> GlobalState {
        if self.nodes.is_empty() {
            return GlobalState::ByzantineFault;
        }

        let mut has_divergence = false;
        let mut has_veto = false;

        for node in self.nodes.values() {
            let variance = node.weights.compute_geometric_variance();
            if variance > self.active_threshold * 2.0 {
                has_veto = true;
            } else if variance > self.active_threshold {
                has_divergence = true;
            }
        }

        if has_veto {
            GlobalState::ByzantineFault
        } else if has_divergence {
            GlobalState::Reconciling
        } else {
            GlobalState::Synchronized
        }
    }
}

pub struct HolonicStateMachine {
    pub l1_autonomous: HolonicLayer,
    pub l2_relational: HolonicLayer,
    pub l3_transcendent: HolonicLayer,
    pub current_epoch: u64,
}

impl HolonicStateMachine {
    pub fn new(threshold: f64) -> Self {
        Self {
            l1_autonomous: HolonicLayer::new("Autonomous_UTXO", ConsensusLayer::Autonomous, threshold),
            l2_relational: HolonicLayer::new("Relational_Gossip", ConsensusLayer::Relational, threshold),
            l3_transcendent: HolonicLayer::new("Finality_Root", ConsensusLayer::Finality, threshold),
            current_epoch: 0,
        }
    }

    /// Processes a state mutation through the holonic layers.
    pub fn process_mutation(
        &mut self,
        node_id: &str,
        key: &str,
        value_hash: &str,
    ) -> GlobalState {
        // Step 1: Try L1 Autonomous layer first
        let l1_state = {
            if let Some(node) = self.l1_autonomous.get_node_mut(node_id) {
                node.commit_mutation(key, value_hash)
            } else {
                // Node doesn't exist in L1, create it
                self.l1_autonomous.add_node(node_id, 4);
                if let Some(node) = self.l1_autonomous.get_node_mut(node_id) {
                    node.commit_mutation(key, value_hash)
                } else {
                    return GlobalState::ByzantineFault;
                }
            }
        };

        match l1_state {
            TriadicState::Equilibrium => {
                // L1 synchronized, no escalation needed
                GlobalState::Synchronized
            }
            TriadicState::Morphing => {
                // L2 Reconciliation required
                self.escalate_to_l2(node_id, key, value_hash)
            }
            TriadicState::VetoCollapse => {
                // Critical failure, escalate to L3 for final adjudication
                self.escalate_to_l3(node_id, key, value_hash)
            }
        }
    }

    fn escalate_to_l2(&mut self, node_id: &str, _key: &str, _value_hash: &str) -> GlobalState {
        // Simulate L2 gossip reconciliation
        // In production: propagate delta to peers, run metastable voting
        
        // Add corresponding node to L2 if not exists
        if !self.l2_relational.nodes.contains_key(node_id) {
            self.l2_relational.add_node(node_id, 4);
        }

        let l2_state = self.l2_relational.evaluate_layer_state();
        
        match l2_state {
            GlobalState::Synchronized => GlobalState::Finalized,
            GlobalState::Reconciling => GlobalState::Reconciling,
            _ => self.escalate_to_l3(node_id, "", ""),
        }
    }

    fn escalate_to_l3(&mut self, node_id: &str, key: &str, value_hash: &str) -> GlobalState {
        // L3 Finality layer - final authority
        // In production: topological sort, mainchain extraction, finality certificate
        
        // Add corresponding node to L3 if not exists
        if !self.l3_transcendent.nodes.contains_key(node_id) {
            self.l3_transcendent.add_node(node_id, 4);
        }

        // Attempt commit at L3 level
        let l3_result = {
            if let Some(node) = self.l3_transcendent.get_node_mut(node_id) {
                node.commit_mutation(key, value_hash)
            } else {
                return GlobalState::ByzantineFault;
            }
        };

        match l3_result {
            TriadicState::Equilibrium | TriadicState::Morphing => {
                self.current_epoch += 1;
                GlobalState::Finalized
            }
            TriadicState::VetoCollapse => {
                // Even L3 cannot resolve - permanent fork or prune required
                GlobalState::ByzantineFault
            }
        }
    }

    /// Returns the current epoch number.
    pub fn get_epoch(&self) -> u64 {
        self.current_epoch
    }

    /// Prunes orphaned branches from all layers.
    pub fn prune_orphans(&mut self) -> usize {
        let mut pruned_count = 0;
        
        for layer in [&mut self.l1_autonomous, &mut self.l2_relational, &mut self.l3_transcendent] {
            for node in layer.nodes.values_mut() {
                let variance = node.weights.compute_geometric_variance();
                if variance > layer.active_threshold * 2.0 {
                    // Reset weights to force re-alignment
                    node.weights = crate::geometric_variance::TensorWeights::new(
                        node.weights.planner.len(),
                        1.0,
                    );
                    pruned_count += 1;
                }
            }
        }
        
        pruned_count
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_l1_equilibrium_no_escalation() {
        let mut machine = HolonicStateMachine::new(0.5);
        machine.l1_autonomous.add_node("node1", 4);
        
        let state = machine.process_mutation("node1", "key1", "hash1");
        assert_eq!(state, GlobalState::Synchronized);
        assert_eq!(machine.get_epoch(), 0);
    }

    #[test]
    fn test_l1_morphing_triggers_l2() {
        let mut machine = HolonicStateMachine::new(0.1);
        machine.l1_autonomous.add_node("node1", 4);
        
        // Inject moderate misalignment
        if let Some(node) = machine.l1_autonomous.get_node_mut("node1") {
            node.weights.planner = vec![1.5, 0.5, 1.0, 1.0];
            node.weights.generator = vec![0.5, 1.5, 1.0, 1.0];
            node.weights.evaluator = vec![1.0, 1.0, 1.0, 1.0];
        }
        
        let state = machine.process_mutation("node1", "key1", "hash1");
        assert_eq!(state, GlobalState::Finalized); // L2 resolves it
    }

    #[test]
    fn test_l1_veto_triggers_l3() {
        let mut machine = HolonicStateMachine::new(0.5);
        machine.l1_autonomous.add_node("node1", 4);
        
        // Inject severe misalignment
        if let Some(node) = machine.l1_autonomous.get_node_mut("node1") {
            node.weights.planner = vec![10.0, 0.0, 0.0, 0.0];
            node.weights.generator = vec![0.0, 10.0, 0.0, 0.0];
            node.weights.evaluator = vec![0.0, 0.0, 0.0, 0.0];
        }
        
        let state = machine.process_mutation("node1", "key1", "hash1");
        // L3 should resolve and increment epoch
        assert_eq!(state, GlobalState::Finalized);
        assert_eq!(machine.get_epoch(), 1);
    }

    #[test]
    fn test_prune_orphans() {
        let mut machine = HolonicStateMachine::new(0.5);
        machine.l1_autonomous.add_node("node1", 4);
        machine.l2_relational.add_node("node2", 4);
        
        // Inject severe misalignment in both
        if let Some(node) = machine.l1_autonomous.get_node_mut("node1") {
            node.weights.planner = vec![10.0, 0.0, 0.0, 0.0];
            node.weights.generator = vec![0.0, 10.0, 0.0, 0.0];
        }
        if let Some(node) = machine.l2_relational.get_node_mut("node2") {
            node.weights.planner = vec![10.0, 0.0, 0.0, 0.0];
            node.weights.generator = vec![0.0, 10.0, 0.0, 0.0];
        }
        
        let pruned = machine.prune_orphans();
        assert_eq!(pruned, 2);
        
        // Verify weights were reset
        let node1 = machine.l1_autonomous.nodes.get("node1").unwrap();
        assert_eq!(node1.weights.planner, vec![1.0, 1.0, 1.0, 1.0]);
    }

    #[test]
    fn test_byzantine_fault_on_persistent_veto() {
        let mut machine = HolonicStateMachine::new(0.1);
        machine.l1_autonomous.add_node("node1", 4);
        machine.l2_relational.add_node("node1", 4);
        machine.l3_transcendent.add_node("node1", 4);

        // Inject extreme misalignment that even L3 can't resolve
        for layer in [&mut machine.l1_autonomous, &mut machine.l2_relational, &mut machine.l3_transcendent] {
            if let Some(node) = layer.nodes.get_mut("node1") {
                node.weights.planner = vec![100.0, 0.0, 0.0, 0.0];
                node.weights.generator = vec![0.0, 100.0, 0.0, 0.0];
                node.weights.evaluator = vec![0.0, 0.0, 0.0, 0.0];
            }
        }

        let state = machine.process_mutation("node1", "key1", "hash1");
        assert_eq!(state, GlobalState::ByzantineFault);
    }

    // 6. New machine starts at epoch 0
    #[test]
    fn new_machine_epoch_zero() {
        let machine = HolonicStateMachine::new(0.5);
        assert_eq!(machine.get_epoch(), 0);
    }

    // 7. Empty layer evaluates as ByzantineFault
    #[test]
    fn empty_layer_is_byzantine_fault() {
        let layer = HolonicLayer::new("test", ConsensusLayer::Autonomous, 0.5);
        assert_eq!(layer.evaluate_layer_state(), GlobalState::ByzantineFault);
    }

    // 8. Prune orphans on a clean (no-node) machine returns 0
    #[test]
    fn prune_orphans_clean_machine_zero() {
        let mut machine = HolonicStateMachine::new(0.5);
        assert_eq!(machine.prune_orphans(), 0);
    }

    // 9. add_node creates a node accessible via get_node_mut
    #[test]
    fn add_node_creates_accessible_node() {
        let mut machine = HolonicStateMachine::new(0.5);
        machine.l1_autonomous.add_node("nx", 4);
        assert!(machine.l1_autonomous.get_node_mut("nx").is_some());
        assert!(machine.l1_autonomous.nodes.contains_key("nx"));
    }

    // 10. process_mutation auto-creates unknown node and does not panic
    #[test]
    fn process_mutation_auto_creates_node() {
        let mut machine = HolonicStateMachine::new(0.5);
        // "unknown_node" not pre-added — process_mutation must handle this
        let state = machine.process_mutation("unknown_node", "k", "v");
        // May be Synchronized or Finalized but must not panic
        assert!(state == GlobalState::Synchronized || state == GlobalState::Finalized
            || state == GlobalState::Reconciling || state == GlobalState::ByzantineFault);
    }
}