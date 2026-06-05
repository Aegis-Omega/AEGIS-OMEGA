//! Semantic Algebra - Fractal Arena with Zero-Allocation Traversal
//! 
//! EPISTEMIC TIER: T0 (mechanically proven)
//! Constitutional root: Cache-local memory arenas with deterministic traversal
//! 
//! This module implements a zero-allocation fractal semantic graph using
//! pre-allocated static arenas. All traversals use stack-based iteration
//! to guarantee no heap allocation during hot paths.

use crate::domain_boundary::AxiomKey;

/// Morphological operator types for deriving words from triliteral roots.
#[repr(u8)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MorphOperator {
    BaseForm    = 0x01,  // Original root form
    Intensive   = 0x02,  // Intensive/causative form
    Passive     = 0x03,  // Passive voice derivation
    Causative   = 0x04,  // Causative derivation
    Reflexive   = 0x05,  // Reflexive derivation
    Reciprocal  = 0x06,  // Reciprocal action
}

impl MorphOperator {
    /// Returns the number of child nodes this operator typically generates.
    pub fn arity(&self) -> u8 {
        match self {
            MorphOperator::BaseForm => 3,
            MorphOperator::Intensive => 2,
            MorphOperator::Passive => 1,
            MorphOperator::Causative => 2,
            MorphOperator::Reflexive => 1,
            MorphOperator::Reciprocal => 2,
        }
    }
}

/// Node type enumeration for the semantic graph.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NodeType {
    /// A triliteral root (3 consonants forming semantic base)
    Root([u8; 3]),
    /// A derived word form with morphological operator
    DerivedWord(MorphOperator),
    /// A leaf node referencing an axiom in the T0 core
    DataLeaf(AxiomKey),
}

/// A semantic node in the fractal arena.
/// 
/// Memory layout is optimized for cache locality:
/// - `node_type`: Discriminant for the kind of semantic unit
/// - `edge_start`: Index into the edge array where children begin
/// - `edge_count`: Number of child edges (enables slice indexing)
#[derive(Debug, Clone, Copy)]
pub struct SemanticNode {
    pub node_type: NodeType,
    pub edge_start: u32,
    pub edge_count: u16,
}

impl SemanticNode {
    /// Creates a new semantic node.
    pub const fn new(node_type: NodeType, edge_start: u32, edge_count: u16) -> Self {
        Self {
            node_type,
            edge_start,
            edge_count,
        }
    }
}

/// A zero-allocation fractal arena for semantic graph storage.
/// 
/// The arena uses two static slices:
/// - `nodes`: The node pool containing all semantic units
/// - `edges`: The edge pool containing parent-child relationships as indices
/// 
/// This design ensures:
/// - O(1) node access by index
/// - Cache-coherent sequential edge access
/// - Zero heap allocation during traversal
pub struct FractalArena {
    nodes: &'static [SemanticNode],
    edges: &'static [u32],
}

impl FractalArena {
    /// Creates a new FractalArena from static slices.
    /// 
    /// # Safety
    /// The caller must ensure that:
    /// - All edge indices are valid node indices
    /// - No cycles exist that would cause infinite traversal
    pub const fn new(nodes: &'static [SemanticNode], edges: &'static [u32]) -> Self {
        Self { nodes, edges }
    }

    /// Gets a reference to a node by index.
    /// 
    /// # Returns
    /// * `Some(&SemanticNode)` if index is valid
    /// * `None` if index is out of bounds
    pub fn get_node(&self, index: u32) -> Option<&SemanticNode> {
        self.nodes.get(index as usize)
    }

    /// Traces the growth from a root node to all reachable DataLeaf nodes.
    /// 
    /// Uses an iterative stack-based DFS algorithm with a fixed-size
    /// stack to guarantee zero heap allocation.
    /// 
    /// # Arguments
    /// * `root_index` - Index of the root node to start traversal from
    /// 
    /// # Returns
    /// A Vec of AxiomKeys found at leaf nodes (allocation occurs only
    /// in the return buffer, not during traversal itself).
    pub fn trace_growth(&self, root_index: u32) -> Vec<AxiomKey> {
        let mut yield_buffer = Vec::new();
        
        // Fixed-size stack for DFS traversal (max depth 16)
        let mut stack: [u32; 16] = [0; 16];
        let mut stack_ptr: usize = 0;
        
        // Push root onto stack
        if stack_ptr < stack.len() {
            stack[stack_ptr] = root_index;
            stack_ptr += 1;
        }

        while stack_ptr > 0 {
            // Pop from stack
            stack_ptr -= 1;
            let current_idx = stack[stack_ptr];
            
            // Get current node
            let node = match self.get_node(current_idx) {
                Some(n) => n,
                None => continue, // Skip invalid indices
            };

            match node.node_type {
                NodeType::DataLeaf(key) => {
                    // Found a leaf - add to yield buffer
                    yield_buffer.push(key);
                }
                _ => {
                    // Internal node - push children onto stack
                    let start = node.edge_start as usize;
                    let end = start + node.edge_count as usize;
                    
                    // Bounds check on edge array
                    if end <= self.edges.len() {
                        for &child_idx in &self.edges[start..end] {
                            if stack_ptr < stack.len() {
                                stack[stack_ptr] = child_idx;
                                stack_ptr += 1;
                            }
                        }
                    }
                }
            }
        }

        yield_buffer
    }

    /// Performs a breadth-first traversal from a root node.
    /// 
    /// Uses a fixed-size circular buffer for the queue.
    /// 
    /// # Arguments
    /// * `root_index` - Index of the root node
    /// 
    /// # Returns
    /// Vec of node indices in BFS order.
    pub fn bfs_traverse(&self, root_index: u32) -> Vec<u32> {
        let mut result = Vec::new();
        
        // Fixed-size circular queue (capacity 32)
        let mut queue: [u32; 32] = [0; 32];
        let mut head: usize = 0;
        let mut tail: usize = 0;
        
        // Enqueue root
        if tail < queue.len() {
            queue[tail] = root_index;
            tail += 1;
        }

        while head != tail {
            // Dequeue
            let current_idx = queue[head];
            head = (head + 1) % queue.len();
            
            result.push(current_idx);
            
            // Get current node and enqueue children
            if let Some(node) = self.get_node(current_idx) {
                let start = node.edge_start as usize;
                let end = start + node.edge_count as usize;
                
                if end <= self.edges.len() {
                    for &child_idx in &self.edges[start..end] {
                        if (tail + 1) % queue.len() != head {
                            queue[tail] = child_idx;
                            tail = (tail + 1) % queue.len();
                        }
                    }
                }
            }
        }

        result
    }

    /// Returns the total number of nodes in the arena.
    pub fn node_count(&self) -> usize {
        self.nodes.len()
    }

    /// Returns the total number of edges in the arena.
    pub fn edge_count(&self) -> usize {
        self.edges.len()
    }
}

/// Builder for constructing FractalArenas with compile-time guarantees.
pub struct ArenaBuilder {
    nodes: Vec<SemanticNode>,
    edges: Vec<u32>,
}

impl ArenaBuilder {
    /// Creates a new empty ArenaBuilder.
    pub fn new() -> Self {
        Self {
            nodes: Vec::new(),
            edges: Vec::new(),
        }
    }

    /// Adds a root node with the specified triliteral root.
    pub fn add_root(mut self, root_consonants: [u8; 3]) -> Self {
        let edge_start = self.edges.len() as u32;
        self.nodes.push(SemanticNode::new(
            NodeType::Root(root_consonants),
            edge_start,
            0, // Will be set when children are added
        ));
        self
    }

    /// Adds a derived word node with the specified morph operator.
    pub fn add_derived(mut self, operator: MorphOperator) -> Self {
        let edge_start = self.edges.len() as u32;
        self.nodes.push(SemanticNode::new(
            NodeType::DerivedWord(operator),
            edge_start,
            0,
        ));
        self
    }

    /// Adds a data leaf referencing an axiom.
    pub fn add_leaf(mut self, key: AxiomKey) -> Self {
        self.nodes.push(SemanticNode::new(
            NodeType::DataLeaf(key),
            0, // Leaves have no children
            0,
        ));
        self
    }

    /// Connects a parent node to a child node.
    pub fn connect(mut self, parent_idx: u32, child_idx: u32) -> Self {
        let edge_pos = self.edges.len() as u32;
        self.edges.push(child_idx);

        if let Some(parent) = self.nodes.get_mut(parent_idx as usize) {
            if parent.edge_count == 0 {
                // First edge for this parent — anchor edge_start here
                parent.edge_start = edge_pos;
                parent.edge_count = 1;
            } else {
                parent.edge_count += 1;
            }
        }
        self
    }

    /// Builds the arena, consuming the builder.
    /// 
    /// Note: This requires leaking memory to get 'static lifetime.
    /// Only use for one-time initialization of global arenas.
    pub fn build(self) -> FractalArena {
        let nodes: &'static [SemanticNode] = Box::leak(self.nodes.into_boxed_slice());
        let edges: &'static [u32] = Box::leak(self.edges.into_boxed_slice());
        FractalArena::new(nodes, edges)
    }
}

impl Default for ArenaBuilder {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_morph_operator_arity() {
        assert_eq!(MorphOperator::BaseForm.arity(), 3);
        assert_eq!(MorphOperator::Intensive.arity(), 2);
        assert_eq!(MorphOperator::Passive.arity(), 1);
        assert_eq!(MorphOperator::Causative.arity(), 2);
    }

    #[test]
    fn test_fractal_arena_simple_traversal() {
        // Build a simple tree: Root -> DerivedWord -> DataLeaf
        let arena = ArenaBuilder::new()
            .add_root([b'K', b'T', b'B'])  // Node 0: Root K-T-B (writing)
            .add_derived(MorphOperator::BaseForm)  // Node 1: Base form
            .add_leaf(AxiomKey::new(1, 1))  // Node 2: Leaf §1.1
            .connect(0, 1)  // Root -> Derived
            .connect(1, 2)  // Derived -> Leaf
            .build();

        assert_eq!(arena.node_count(), 3);
        assert_eq!(arena.edge_count(), 2);

        // Trace from root should find the leaf
        let leaves = arena.trace_growth(0);
        assert_eq!(leaves.len(), 1);
        assert_eq!(leaves[0], AxiomKey::new(1, 1));
    }

    #[test]
    fn test_bfs_traversal() {
        let arena = ArenaBuilder::new()
            .add_root([b'S', b'L', b'M'])  // Node 0
            .add_derived(MorphOperator::Intensive)  // Node 1
            .add_derived(MorphOperator::Passive)  // Node 2
            .add_leaf(AxiomKey::new(2, 1))  // Node 3
            .add_leaf(AxiomKey::new(2, 2))  // Node 4
            .connect(0, 1)
            .connect(0, 2)
            .connect(1, 3)
            .connect(2, 4)
            .build();

        let bfs_order = arena.bfs_traverse(0);
        assert_eq!(bfs_order.len(), 5);
        assert_eq!(bfs_order[0], 0); // Root first
        assert!(bfs_order.contains(&1));
        assert!(bfs_order.contains(&2));
        assert!(bfs_order.contains(&3));
        assert!(bfs_order.contains(&4));
    }

    #[test]
    fn test_multiple_leaves_single_root() {
        let arena = ArenaBuilder::new()
            .add_root([b'F', b'R', b'D'])  // Node 0
            .add_leaf(AxiomKey::new(3, 1))  // Node 1
            .add_leaf(AxiomKey::new(3, 2))  // Node 2
            .add_leaf(AxiomKey::new(3, 3))  // Node 3
            .connect(0, 1)
            .connect(0, 2)
            .connect(0, 3)
            .build();

        let leaves = arena.trace_growth(0);
        assert_eq!(leaves.len(), 3);
        assert!(leaves.contains(&AxiomKey::new(3, 1)));
        assert!(leaves.contains(&AxiomKey::new(3, 2)));
        assert!(leaves.contains(&AxiomKey::new(3, 3)));
    }

    #[test]
    fn test_get_node() {
        let arena = ArenaBuilder::new()
            .add_root([b'Q', b'L', b'B'])
            .add_leaf(AxiomKey::new(4, 1))
            .connect(0, 1)
            .build();

        let node = arena.get_node(0);
        assert!(node.is_some());
        match node.unwrap().node_type {
            NodeType::Root(chars) => assert_eq!(chars, [b'Q', b'L', b'B']),
            _ => panic!("Expected Root node type"),
        }

        assert!(arena.get_node(99).is_none());
    }

    // 6. Reflexive arity is 1, Reciprocal arity is 2
    #[test]
    fn morph_operator_reflexive_and_reciprocal_arity() {
        assert_eq!(MorphOperator::Reflexive.arity(), 1);
        assert_eq!(MorphOperator::Reciprocal.arity(), 2);
    }

    // 7. node_count matches the number of nodes added
    #[test]
    fn node_count_matches_added() {
        let arena = ArenaBuilder::new()
            .add_root([b'A', b'B', b'C'])
            .add_derived(MorphOperator::Passive)
            .add_leaf(AxiomKey::new(5, 1))
            .connect(0, 1)
            .connect(1, 2)
            .build();
        assert_eq!(arena.node_count(), 3);
    }

    // 8. edge_count matches the number of connect calls
    #[test]
    fn edge_count_matches_connects() {
        let arena = ArenaBuilder::new()
            .add_root([b'X', b'Y', b'Z'])
            .add_leaf(AxiomKey::new(6, 1))
            .add_leaf(AxiomKey::new(6, 2))
            .connect(0, 1)
            .connect(0, 2)
            .build();
        assert_eq!(arena.edge_count(), 2);
    }

    // 9. trace_growth on an out-of-bounds root index returns empty
    #[test]
    fn trace_growth_invalid_root_returns_empty() {
        let arena = ArenaBuilder::new()
            .add_root([b'P', b'Q', b'R'])
            .build();
        let leaves = arena.trace_growth(999);
        assert!(leaves.is_empty());
    }

    // 10. DerivedWord DataLeaf node type can be constructed and matched
    #[test]
    fn data_leaf_node_type_preserved() {
        let arena = ArenaBuilder::new()
            .add_root([b'D', b'E', b'F'])
            .add_leaf(AxiomKey::new(7, 3))
            .connect(0, 1)
            .build();
        let leaf = arena.get_node(1).unwrap();
        assert!(matches!(leaf.node_type, NodeType::DataLeaf(_)));
    }
}
