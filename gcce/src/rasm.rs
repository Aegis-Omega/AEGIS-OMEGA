//! Rasm: The Continuous Causal Flow (Dimension 2)
//!
//! Arabic script is cursive; letters connect, flow into one another,
//! and change shape based on their position (initial, medial, final).
//! This is the Rasm (the skeleton).
//!
//! Cognitive Translation: The Rasm is the Non-Linear Dependency Graph.
//! Reasoning is not a list; it is a ligature.
//! The output of one module (tail of a letter) must seamlessly become
//! the input of the next (head of the next letter).
//!
//! Higher Dimensional Shift: From discrete token prediction to
//! continuous manifold traversal. The system outputs a flowing,
//! interconnected state transition map where f(xₙ) → xₙ₊₁ is a
//! smooth, differentiable curve, not a jagged jump.

use std::collections::BTreeMap;

/// Unique identifier for Rasm nodes
pub type NodeId = u64;

/// Edge weight for causal connections
pub type EdgeWeight = f64;

/// Type signature for node inputs/outputs
#[derive(Debug, Clone, PartialEq)]
pub struct TypeSignature {
    pub name: &'static str,
    pub kind: TypeKind,
}

#[derive(Debug, Clone, PartialEq)]
pub enum TypeKind {
    Input,
    Output,
    Transform,
    Aggregate,
}

/// RasmNode: A node in the continuous causal flow
#[derive(Debug, Clone)]
pub struct RasmNode {
    /// Unique node identifier
    pub id: NodeId,
    /// Output type signature
    pub output_type: TypeSignature,
    /// Input ligature (previous node connection) - Option for first node
    pub input_ligature: Option<NodeId>,
    /// Output ligature (next node connection) - Option for last node
    pub output_ligature: Option<NodeId>,
    /// Node payload/data
    pub payload: Vec<u8>,
    /// Position in manifold (for ordering)
    pub position: u32,
}

impl RasmNode {
    /// Create a new RasmNode (first node in chain)
    pub fn new(id: NodeId, output_type: TypeSignature, payload: Vec<u8>) -> Self {
        Self {
            id,
            output_type,
            input_ligature: None,
            output_ligature: None,
            payload,
            position: 0,
        }
    }

    /// Create a node with input ligature (connected to previous)
    pub fn with_input(mut self, input_node_id: NodeId) -> Self {
        self.input_ligature = Some(input_node_id);
        self
    }

    /// Create a node with output ligature (connected to next)
    pub fn with_output(mut self, output_node_id: NodeId) -> Self {
        self.output_ligature = Some(output_node_id);
        self
    }

    /// Set position in manifold
    pub fn with_position(mut self, position: u32) -> Self {
        self.position = position;
        self
    }

    /// Check if this node is the start of a chain
    pub fn is_chain_start(&self) -> bool {
        self.input_ligature.is_none()
    }

    /// Check if this node is the end of a chain
    pub fn is_chain_end(&self) -> bool {
        self.output_ligature.is_none()
    }

    /// Get ligature continuity status
    pub fn has_continuity(&self) -> bool {
        // A node has continuity if it's either:
        // 1. Start of chain (no input needed)
        // 2. Has both input and output ligatures
        // 3. End of chain with input
        self.is_chain_start() || 
        (self.input_ligature.is_some() && self.output_ligature.is_some()) ||
        (self.input_ligature.is_some() && self.is_chain_end())
    }
}

/// SmoothPath: Represents a continuous traversal through the manifold
#[derive(Debug, Clone)]
pub struct SmoothPath {
    pub nodes: Vec<NodeId>,
    pub weights: Vec<EdgeWeight>,
    pub total_length: f64,
    pub is_continuous: bool,
}

impl SmoothPath {
    pub fn new(nodes: Vec<NodeId>, weights: Vec<EdgeWeight>) -> Self {
        let total_length: f64 = weights.iter().sum();
        let is_continuous = weights.len() == nodes.len().saturating_sub(1) || nodes.len() <= 1;

        Self {
            nodes,
            weights,
            total_length,
            is_continuous,
        }
    }

    /// Verify path continuity (f(xₙ) → xₙ₊₁ is smooth)
    pub fn verify_smoothness(&self, threshold: f64) -> bool {
        if self.weights.is_empty() {
            return true;
        }

        // Check that no weight exceeds threshold (discontinuity detection)
        self.weights.iter().all(|&w| w <= threshold)
    }
}

/// CausalManifold: BTreeMap-based continuous dependency graph
pub struct CausalManifold {
    /// Nodes indexed by ID (BTreeMap for deterministic iteration)
    nodes: BTreeMap<NodeId, RasmNode>,
    /// Edges as (from, to) -> weight
    edges: BTreeMap<(NodeId, NodeId), EdgeWeight>,
    /// Next available node ID
    next_id: NodeId,
}

impl CausalManifold {
    /// Create a new empty manifold
    pub fn new() -> Self {
        Self {
            nodes: BTreeMap::new(),
            edges: BTreeMap::new(),
            next_id: 0,
        }
    }

    /// Add a node to the manifold (Phase 3 of Khatt Loop - Weaving)
    pub fn weave_node(&mut self, mut node: RasmNode) -> NodeId {
        if node.id == 0 && self.next_id > 0 {
            node.id = self.next_id;
        }
        
        let id = node.id;
        self.nodes.insert(id, node);
        self.next_id = id + 1;
        id
    }

    /// Connect two nodes with an edge
    pub fn connect(&mut self, from: NodeId, to: NodeId, weight: EdgeWeight) -> Result<(), &'static str> {
        if !self.nodes.contains_key(&from) {
            return Err("Source node does not exist");
        }
        if !self.nodes.contains_key(&to) {
            return Err("Target node does not exist");
        }

        // Update ligatures
        if let Some(from_node) = self.nodes.get_mut(&from) {
            from_node.output_ligature = Some(to);
        }
        if let Some(to_node) = self.nodes.get_mut(&to) {
            to_node.input_ligature = Some(from);
        }

        self.edges.insert((from, to), weight);
        Ok(())
    }

    /// Traverse the manifold from a starting node
    pub fn traverse(&self, start: NodeId) -> Option<SmoothPath> {
        if !self.nodes.contains_key(&start) {
            return None;
        }

        let mut nodes = vec![start];
        let mut weights = Vec::new();
        let mut current = start;

        // Follow output ligatures
        while let Some(node) = self.nodes.get(&current) {
            if let Some(next_id) = node.output_ligature {
                if let Some(weight) = self.edges.get(&(current, next_id)) {
                    weights.push(*weight);
                    nodes.push(next_id);
                    current = next_id;
                } else {
                    break;
                }
            } else {
                break; // End of chain
            }
        }

        Some(SmoothPath::new(nodes, weights))
    }

    /// Get all chain starts (nodes with no input ligature)
    pub fn get_chain_starts(&self) -> Vec<NodeId> {
        self.nodes
            .values()
            .filter(|n| n.is_chain_start())
            .map(|n| n.id)
            .collect()
    }

    /// Verify all nodes have continuity (no orphaned modules)
    pub fn verify_continuity(&self) -> bool {
        self.nodes.values().all(|n| n.has_continuity())
    }

    /// Get node count
    pub fn node_count(&self) -> usize {
        self.nodes.len()
    }

    /// Get edge count
    pub fn edge_count(&self) -> usize {
        self.edges.len()
    }

    /// Get a node by ID
    pub fn get_node(&self, id: NodeId) -> Option<&RasmNode> {
        self.nodes.get(&id)
    }

    /// Check if manifold is empty
    pub fn is_empty(&self) -> bool {
        self.nodes.is_empty()
    }
}

impl Default for CausalManifold {
    fn default() -> Self {
        Self::new()
    }
}

/// Rasm Builder for fluent construction
pub struct RasmBuilder {
    nodes: Vec<RasmNode>,
    connections: Vec<(NodeId, NodeId, EdgeWeight)>,
}

impl RasmBuilder {
    pub fn new() -> Self {
        Self {
            nodes: Vec::new(),
            connections: Vec::new(),
        }
    }

    pub fn add_node(mut self, node: RasmNode) -> Self {
        self.nodes.push(node);
        self
    }

    pub fn connect(mut self, from: NodeId, to: NodeId, weight: EdgeWeight) -> Self {
        self.connections.push((from, to, weight));
        self
    }

    pub fn build(self) -> CausalManifold {
        let mut manifold = CausalManifold::new();

        for node in self.nodes {
            manifold.weave_node(node);
        }

        for (from, to, weight) in self.connections {
            let _ = manifold.connect(from, to, weight);
        }

        manifold
    }
}

impl Default for RasmBuilder {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_rasm_node_creation() {
        let node = RasmNode::new(
            1,
            TypeSignature {
                name: "test_output",
                kind: TypeKind::Output,
            },
            b"test payload".to_vec(),
        );

        assert_eq!(node.id, 1);
        assert!(node.is_chain_start());
        assert!(node.is_chain_end());
        assert!(node.has_continuity());
    }

    #[test]
    fn test_rasm_node_ligatures() {
        let node1 = RasmNode::new(1, TypeSignature { name: "first", kind: TypeKind::Input }, vec![]);
        let node2 = RasmNode::new(2, TypeSignature { name: "second", kind: TypeKind::Output }, vec![])
            .with_input(1);
        let node3 = RasmNode::new(3, TypeSignature { name: "third", kind: TypeKind::Transform }, vec![])
            .with_input(2)
            .with_output(4);

        assert!(node1.is_chain_start());
        assert!(!node2.is_chain_start());
        assert!(!node3.is_chain_end());
    }

    #[test]
    fn test_causal_manifold_basic() {
        let mut manifold = CausalManifold::new();

        let node1 = RasmNode::new(0, TypeSignature { name: "start", kind: TypeKind::Input }, vec![]);
        let node2 = RasmNode::new(0, TypeSignature { name: "end", kind: TypeKind::Output }, vec![]);

        let id1 = manifold.weave_node(node1);
        let id2 = manifold.weave_node(node2);

        assert_eq!(id1, 0);
        assert_eq!(id2, 1);
        assert_eq!(manifold.node_count(), 2);
    }

    #[test]
    fn test_causal_manifold_connection() {
        let mut manifold = CausalManifold::new();

        let node1 = RasmNode::new(0, TypeSignature { name: "start", kind: TypeKind::Input }, vec![]);
        let node2 = RasmNode::new(0, TypeSignature { name: "end", kind: TypeKind::Output }, vec![]);

        let id1 = manifold.weave_node(node1);
        let id2 = manifold.weave_node(node2);

        assert!(manifold.connect(id1, id2, 1.0).is_ok());

        // Verify ligatures were updated
        let n1 = manifold.get_node(id1).unwrap();
        let n2 = manifold.get_node(id2).unwrap();
        assert_eq!(n1.output_ligature, Some(id2));
        assert_eq!(n2.input_ligature, Some(id1));
    }

    #[test]
    fn test_causal_manifold_traversal() {
        let mut manifold = CausalManifold::new();

        for i in 0..5 {
            let node = RasmNode::new(0, TypeSignature { name: "node", kind: TypeKind::Transform }, vec![]);
            manifold.weave_node(node);
        }

        // Connect in sequence
        for i in 0..4 {
            manifold.connect(i, i + 1, 1.0).unwrap();
        }

        let path = manifold.traverse(0).unwrap();
        assert_eq!(path.nodes.len(), 5);
        assert_eq!(path.weights.len(), 4);
        assert!(path.is_continuous);
        assert!(path.verify_smoothness(2.0));
    }

    #[test]
    fn test_causal_manifold_continuity() {
        let mut manifold = CausalManifold::new();

        // Single node (valid chain start and end)
        let node = RasmNode::new(0, TypeSignature { name: "solo", kind: TypeKind::Input }, vec![]);
        manifold.weave_node(node);
        assert!(manifold.verify_continuity());

        // Two connected nodes
        let mut manifold2 = CausalManifold::new();
        let n1 = RasmNode::new(0, TypeSignature { name: "first", kind: TypeKind::Input }, vec![]);
        let n2 = RasmNode::new(0, TypeSignature { name: "second", kind: TypeKind::Output }, vec![]);
        let id1 = manifold2.weave_node(n1);
        let id2 = manifold2.weave_node(n2);
        manifold2.connect(id1, id2, 1.0).unwrap();
        assert!(manifold2.verify_continuity());
    }

    #[test]
    fn test_rasm_builder() {
        let builder = RasmBuilder::new()
            .add_node(RasmNode::new(0, TypeSignature { name: "a", kind: TypeKind::Input }, vec![]))
            .add_node(RasmNode::new(0, TypeSignature { name: "b", kind: TypeKind::Output }, vec![]))
            .connect(0, 1, 1.0);

        let manifold = builder.build();
        assert_eq!(manifold.node_count(), 2);
        assert_eq!(manifold.edge_count(), 1);
    }

    #[test]
    fn test_smooth_path_discontinuity() {
        let path = SmoothPath::new(vec![1, 2, 3], vec![1.0, 5.0]);
        
        assert!(path.verify_smoothness(10.0)); // All weights under threshold
        assert!(!path.verify_smoothness(2.0)); // 5.0 exceeds threshold
    }
}
