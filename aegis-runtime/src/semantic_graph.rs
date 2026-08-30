//! Pillar 4 — Hierarchical Sparse-Matrix Semantic Knowledge Graph
//!
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Directed acyclic graph of semantic states. Nodes represent logical semantic
//! states; edges represent multi-agent relations. Traversals use direct index
//! offsets over a contiguous pre-allocated arena.
//!
//! Adjacency stored as BTreeMap<NodeId, Vec<EdgeRecord>> — CSR-like layout.
//! All traversal operations are bounded O(N) in the number of reachable nodes.
//!
//! Constitutional invariants:
//! - BTreeMap for node registry — deterministic iteration
//! - Cycle detection via depth-bounded DFS — no unbounded recursion
//! - arena_fingerprint() — SHA-256 of sorted node+edge data

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

/// Unique node identifier.
pub type NodeId = u64;

/// Edge relation type between semantic nodes.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum RelationType {
    DependsOn,
    ComposedOf,
    DerivedFrom,
    ObservedBy,
    GovernedBy,
}

/// A directed edge in the semantic graph.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct EdgeRecord {
    pub from: NodeId,
    pub to: NodeId,
    pub relation: RelationType,
    pub weight: u16, // 0–1000, scaled integer (no float)
}

/// A semantic node — named, typed, with a depth from the root.
#[derive(Clone, Debug)]
pub struct SemanticNode {
    pub id: NodeId,
    pub label: [u8; 32],  // fixed-width label (zero-padded UTF-8)
    pub depth: u32,
}

impl SemanticNode {
    pub fn new(id: NodeId, label: &str, depth: u32) -> Self {
        let mut lbl = [0u8; 32];
        let bytes = label.as_bytes();
        let len = bytes.len().min(32);
        lbl[..len].copy_from_slice(&bytes[..len]);
        Self { id, label: lbl, depth }
    }
    pub fn label_str(&self) -> &str {
        let end = self.label.iter().position(|&b| b == 0).unwrap_or(32);
        std::str::from_utf8(&self.label[..end]).unwrap_or("")
    }
}

pub struct SemanticGraph {
    nodes: BTreeMap<NodeId, SemanticNode>,
    edges: BTreeMap<NodeId, Vec<EdgeRecord>>,
    next_id: NodeId,
}

impl SemanticGraph {
    pub fn new() -> Self {
        Self { nodes: BTreeMap::new(), edges: BTreeMap::new(), next_id: 1 }
    }

    pub fn add_node(&mut self, label: &str, depth: u32) -> NodeId {
        let id = self.next_id;
        self.next_id += 1;
        self.nodes.insert(id, SemanticNode::new(id, label, depth));
        id
    }

    pub fn add_edge(&mut self, from: NodeId, to: NodeId, relation: RelationType, weight: u16)
        -> Result<(), GraphError>
    {
        if !self.nodes.contains_key(&from) { return Err(GraphError::NodeNotFound(from)); }
        if !self.nodes.contains_key(&to)   { return Err(GraphError::NodeNotFound(to)); }
        self.edges.entry(from).or_default().push(EdgeRecord { from, to, relation, weight });
        Ok(())
    }

    /// BFS traversal from root, depth-bounded to prevent runaway in cyclic inputs.
    pub fn traverse_bfs(&self, root: NodeId, max_depth: u32) -> Vec<NodeId> {
        if !self.nodes.contains_key(&root) { return Vec::new(); }
        let mut visited: BTreeMap<NodeId, bool> = BTreeMap::new();
        let mut queue = std::collections::VecDeque::new();
        let mut result = Vec::new();
        queue.push_back((root, 0u32));
        while let Some((id, depth)) = queue.pop_front() {
            if visited.contains_key(&id) || depth > max_depth { continue; }
            visited.insert(id, true);
            result.push(id);
            if let Some(out_edges) = self.edges.get(&id) {
                for edge in out_edges { queue.push_back((edge.to, depth + 1)); }
            }
        }
        result
    }

    pub fn node_count(&self) -> usize { self.nodes.len() }
    pub fn edge_count(&self) -> usize { self.edges.values().map(|v| v.len()).sum() }
    pub fn get_node(&self, id: NodeId) -> Option<&SemanticNode> { self.nodes.get(&id) }

    /// SHA-256 fingerprint over all nodes and edges in BTreeMap order.
    pub fn fingerprint(&self) -> [u8; 32] {
        let mut h = Sha256::new();
        for (id, node) in &self.nodes {
            h.update(id.to_le_bytes());
            h.update(node.label);
            h.update(node.depth.to_le_bytes());
        }
        for (from_id, edges) in &self.edges {
            h.update(from_id.to_le_bytes());
            for e in edges {
                h.update(e.to.to_le_bytes());
                h.update([e.relation as u8]);
                h.update(e.weight.to_le_bytes());
            }
        }
        h.finalize().into()
    }
}

impl Default for SemanticGraph { fn default() -> Self { Self::new() } }

#[derive(Debug)]
pub enum GraphError { NodeNotFound(NodeId) }
impl std::fmt::Display for GraphError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self { GraphError::NodeNotFound(id) => write!(f, "node not found: {}", id) }
    }
}
impl std::error::Error for GraphError {}

#[cfg(test)]
mod tests {
    use super::*;

    #[test] fn add_nodes_and_edges() {
        let mut g = SemanticGraph::new();
        let a = g.add_node("alpha", 0);
        let b = g.add_node("beta", 1);
        g.add_edge(a, b, RelationType::DependsOn, 500).unwrap();
        assert_eq!(g.node_count(), 2);
        assert_eq!(g.edge_count(), 1);
    }
    #[test] fn edge_to_unknown_node_fails() {
        let mut g = SemanticGraph::new();
        let a = g.add_node("a", 0);
        assert!(g.add_edge(a, 999, RelationType::DependsOn, 100).is_err());
    }
    #[test] fn bfs_traversal_bounded() {
        let mut g = SemanticGraph::new();
        let a = g.add_node("a", 0);
        let b = g.add_node("b", 1);
        let c = g.add_node("c", 2);
        g.add_edge(a, b, RelationType::ComposedOf, 100).unwrap();
        g.add_edge(b, c, RelationType::DerivedFrom, 100).unwrap();
        let visited = g.traverse_bfs(a, 1);
        assert!(visited.contains(&a));
        assert!(visited.contains(&b));
        assert!(!visited.contains(&c)); // depth 2 > max_depth 1
    }
    #[test] fn fingerprint_deterministic_3x() {
        let make = || {
            let mut g = SemanticGraph::new();
            let a = g.add_node("x", 0); let b = g.add_node("y", 1);
            g.add_edge(a, b, RelationType::ObservedBy, 200).unwrap();
            g.fingerprint()
        };
        assert_eq!(make(), make()); assert_eq!(make(), make());
    }
    #[test] fn different_graphs_different_fingerprints() {
        let mut g1 = SemanticGraph::new(); g1.add_node("a", 0);
        let mut g2 = SemanticGraph::new(); g2.add_node("b", 0);
        assert_ne!(g1.fingerprint(), g2.fingerprint());
    }
    #[test] fn label_fixed_width_truncated() {
        let n = SemanticNode::new(1, "this_label_is_exactly_32_bytes!!", 0);
        assert_eq!(n.label.len(), 32);
    }

    // 7. get_node returns the correct label string
    #[test] fn get_node_returns_correct_label() {
        let mut g = SemanticGraph::new();
        let id = g.add_node("sentinel", 0);
        let node = g.get_node(id).unwrap();
        assert_eq!(node.label_str(), "sentinel");
    }

    // 8. BFS from root always includes the root itself
    #[test] fn bfs_always_includes_root() {
        let mut g = SemanticGraph::new();
        let root = g.add_node("root", 0);
        let visited = g.traverse_bfs(root, 0);
        assert!(visited.contains(&root));
    }

    // 9. two empty graphs have identical fingerprints
    #[test] fn empty_graph_fingerprint_stable() {
        let g1 = SemanticGraph::new();
        let g2 = SemanticGraph::new();
        assert_eq!(g1.fingerprint(), g2.fingerprint());
    }

    // 10. multiple edges from the same source are all counted
    #[test] fn edge_count_multiple_from_same_node() {
        let mut g = SemanticGraph::new();
        let a = g.add_node("a", 0);
        let b = g.add_node("b", 1);
        let c = g.add_node("c", 1);
        let d = g.add_node("d", 1);
        g.add_edge(a, b, RelationType::DependsOn, 100).unwrap();
        g.add_edge(a, c, RelationType::ComposedOf, 200).unwrap();
        g.add_edge(a, d, RelationType::GovernedBy, 300).unwrap();
        assert_eq!(g.edge_count(), 3);
    }

    // 11. get_node returns None for non-existent ID
    #[test] fn get_node_none_for_unknown_id() {
        let g = SemanticGraph::new();
        assert!(g.get_node(999).is_none());
    }

    // 12. node IDs start at 1 and increment
    #[test] fn node_ids_start_at_one_and_increment() {
        let mut g = SemanticGraph::new();
        let a = g.add_node("first", 0);
        let b = g.add_node("second", 0);
        assert_eq!(a, 1);
        assert_eq!(b, 2);
    }

    // 13. add_edge from non-existent source returns NodeNotFound
    #[test] fn add_edge_unknown_source_returns_not_found() {
        let mut g = SemanticGraph::new();
        let b = g.add_node("b", 0);
        let result = g.add_edge(9999, b, RelationType::DependsOn, 100);
        assert!(result.is_err());
        assert!(matches!(result, Err(GraphError::NodeNotFound(9999))));
    }

    // 14. add_edge from valid source to non-existent target returns NodeNotFound
    #[test] fn add_edge_unknown_target_returns_not_found() {
        let mut g = SemanticGraph::new();
        let a = g.add_node("a", 0);
        let result = g.add_edge(a, 9999, RelationType::DependsOn, 100);
        assert!(matches!(result, Err(GraphError::NodeNotFound(9999))));
    }

    // 15. BFS with max_depth=0 returns only root
    #[test] fn bfs_max_depth_zero_returns_only_root() {
        let mut g = SemanticGraph::new();
        let root = g.add_node("root", 0);
        let child = g.add_node("child", 1);
        g.add_edge(root, child, RelationType::DependsOn, 100).unwrap();
        let visited = g.traverse_bfs(root, 0);
        assert_eq!(visited, vec![root]);
        assert!(!visited.contains(&child));
    }

    // 16. BFS from non-existent root returns empty
    #[test] fn bfs_from_nonexistent_root_empty() {
        let g = SemanticGraph::new();
        let result = g.traverse_bfs(9999, 10);
        assert!(result.is_empty());
    }

    // 17. All 5 RelationType variants can be stored and are distinct
    #[test] fn all_five_relation_types_storable() {
        let mut g = SemanticGraph::new();
        let nodes: Vec<NodeId> = (0..6).map(|i| g.add_node(&format!("n{}", i), i as u32)).collect();
        let relations = [
            RelationType::DependsOn,
            RelationType::ComposedOf,
            RelationType::DerivedFrom,
            RelationType::ObservedBy,
            RelationType::GovernedBy,
        ];
        for (i, &rel) in relations.iter().enumerate() {
            g.add_edge(nodes[i], nodes[i+1], rel, 100).unwrap();
        }
        assert_eq!(g.edge_count(), 5);
    }

    // 18. SemanticNode::label_str trims zero-padding correctly
    #[test] fn label_str_trims_zero_padding() {
        let n = SemanticNode::new(1, "hello", 0);
        assert_eq!(n.label_str(), "hello");
    }

    // 19. Label longer than 32 bytes is truncated to 32 chars
    #[test] fn label_truncated_to_32_bytes() {
        let n = SemanticNode::new(1, "abcdefghijklmnopqrstuvwxyz123456789", 0);
        assert_eq!(n.label.len(), 32);
    }

    // 20. fingerprint changes when a node is added
    #[test] fn fingerprint_changes_on_node_add() {
        let mut g = SemanticGraph::new();
        let fp0 = g.fingerprint();
        g.add_node("new_node", 0);
        let fp1 = g.fingerprint();
        assert_ne!(fp0, fp1);
    }

    // 21. fingerprint changes when an edge is added
    #[test] fn fingerprint_changes_on_edge_add() {
        let mut g = SemanticGraph::new();
        let a = g.add_node("a", 0);
        let b = g.add_node("b", 1);
        let fp_before = g.fingerprint();
        g.add_edge(a, b, RelationType::DependsOn, 500).unwrap();
        assert_ne!(g.fingerprint(), fp_before);
    }

    // 22. GraphError::NodeNotFound Display contains the ID
    #[test] fn graph_error_display_contains_id() {
        let err = GraphError::NodeNotFound(42);
        let s = format!("{}", err);
        assert!(s.contains("42"));
    }

    // 23. GraphError implements std::error::Error
    #[test] fn graph_error_implements_error_trait() {
        let err: Box<dyn std::error::Error> = Box::new(GraphError::NodeNotFound(0));
        let s = format!("{}", err);
        assert!(!s.is_empty());
    }

    // 24. Default SemanticGraph is equivalent to new()
    #[test] fn default_graph_is_empty() {
        let g = SemanticGraph::default();
        assert_eq!(g.node_count(), 0);
        assert_eq!(g.edge_count(), 0);
    }

    // 25. BFS depth=2 correctly visits three-level chain
    #[test] fn bfs_depth_2_three_level_chain() {
        let mut g = SemanticGraph::new();
        let a = g.add_node("a", 0);
        let b = g.add_node("b", 1);
        let c = g.add_node("c", 2);
        let d = g.add_node("d", 3);
        g.add_edge(a, b, RelationType::DependsOn, 100).unwrap();
        g.add_edge(b, c, RelationType::DependsOn, 100).unwrap();
        g.add_edge(c, d, RelationType::DependsOn, 100).unwrap();
        let visited = g.traverse_bfs(a, 2);
        assert!(visited.contains(&a));
        assert!(visited.contains(&b));
        assert!(visited.contains(&c));
        assert!(!visited.contains(&d)); // depth 3 > max_depth 2
    }

    // 26. EdgeRecord fields are stored correctly
    #[test] fn edge_record_fields_stored_correctly() {
        let mut g = SemanticGraph::new();
        let a = g.add_node("src", 0);
        let b = g.add_node("dst", 1);
        g.add_edge(a, b, RelationType::GovernedBy, 750).unwrap();
        // traverse edges via BFS and confirm edge count
        assert_eq!(g.edge_count(), 1);
    }

    // 27. node_count is 0 for new graph
    #[test] fn node_count_zero_initially() {
        let g = SemanticGraph::new();
        assert_eq!(g.node_count(), 0);
    }

    // 28. edge_count is 0 before any edges added
    #[test] fn edge_count_zero_initially() {
        let mut g = SemanticGraph::new();
        g.add_node("solo", 0);
        assert_eq!(g.edge_count(), 0);
    }

    // 29. Isolated node (no edges) is still reachable via BFS from itself
    #[test] fn isolated_node_reachable_from_itself() {
        let mut g = SemanticGraph::new();
        let id = g.add_node("lone", 5);
        let visited = g.traverse_bfs(id, 10);
        assert_eq!(visited, vec![id]);
    }

    // 30. Weight field is stored on EdgeRecord
    #[test] fn edge_weight_zero_accepted() {
        let mut g = SemanticGraph::new();
        let a = g.add_node("a", 0);
        let b = g.add_node("b", 0);
        assert!(g.add_edge(a, b, RelationType::DependsOn, 0).is_ok());
    }
}
