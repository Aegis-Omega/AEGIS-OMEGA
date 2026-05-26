//! Gate 220: Compile-Time Acyclic DAG Lattice + Lawvere Metric + Homotopy Witness
//! EPISTEMIC TIER: T1 (rank enforcement) / T2 (Lawvere weights) / T3 (HoTT claim)
//!
//! Gemini architectural insight (T1): "Stripping symbolic metadata and translating runtime
//! checks into type-level evidence changes the system from a runtime interpreter into a
//! mathematically sound state machine."
//!
//! ─── What this implements ────────────────────────────────────────────────────────
//!
//! 1. COMPILE-TIME ACYCLIC LATTICE (T1)
//!    VerifiedEdge<From, To>::new() asserts From::RANK < To::RANK via inline const block.
//!    The assertion is evaluated when the generic function is instantiated — if
//!    From::RANK >= To::RANK, the program fails to compile. Cycles are unwritable.
//!    (Note: Gemini used `where (): CompileTimeAssert<{RANK<RANK}>` which requires
//!     nightly `generic_const_exprs`. This implementation uses the stable inline-const
//!     assertion pattern available on Rust 1.79+.)
//!
//! 2. LAWVERE METRIC LAYER (T2)
//!    Enriches the DAG category over ([0,∞], ≥, 0, +).
//!    d(A,B): divergence weight. Triangle inequality: d(A,C) ≤ d(A,B) + d(B,C).
//!    Holds by additive composition in PathMetricExt.
//!    DIVERGENCE_WEIGHT = 0.0025 is a T2 hypothesis; category structure is T1.
//!
//! 3. HOMOTOPY WITNESS (T2 code / T3 claim)
//!    HomotopyWitness<P1, P2> proves at compile time that P1 and P2 share start/end nodes.
//!    Structural endpoint equality — necessary but not sufficient for full HoTT equivalence.
//!    The 2-cell mathematical claim requires dependent types unavailable in stable Rust: T3.
//!
//! ─── Constitutional invariants ────────────────────────────────────────────────────
//! - No HashMap (pure type-level structures)
//! - Assertions are const-evaluated — zero runtime overhead per instantiation
//! - Lawvere weights are compile-time constants (IEEE 754 deterministic)
//! - No f64 in threshold comparison (weights are constants, not comparands)
//!
//! AdaptivePower(T) ≤ ReplayVerifiability(T) — the ring composition law is a DAG.
//! Copyright (C) 2025 Tarik Skalić — All rights reserved. AGPL-3.0-or-later

use std::marker::PhantomData;

// ─── Node trait ───────────────────────────────────────────────────────────

/// A node in the compile-time DAG. RANK determines its position in the strict
/// partial order. Edges must flow strictly upward: RANK(From) < RANK(To).
pub trait Node: Send + Sync + 'static {
    const RANK: usize;
    type State: Clone + Send + Sync + PartialEq;
}

// ─── Statically verified directed edge ────────────────────────────────────

/// A directed edge From→To. Construction panics at compile time if RANK(From) >= RANK(To).
///
/// Cycle impossibility proof:
///   A→B requires RANK(A) < RANK(B).
///   B→A requires RANK(B) < RANK(A).
///   Both cannot be true simultaneously — the compiler rejects one of the new() calls.
pub struct VerifiedEdge<From: Node, To: Node> {
    _from: PhantomData<From>,
    _to: PhantomData<To>,
}

impl<From: Node, To: Node> VerifiedEdge<From, To> {
    /// Construct the edge. Evaluated at compile time via inline const assertion.
    /// If RANK(From) >= RANK(To), compilation fails with a clear message.
    pub fn new() -> Self {
        // Inline const block: evaluated when this generic is instantiated.
        // With concrete From/To types, the compiler evaluates RANK comparisons
        // and panics (= compile error) if the ordering is violated.
        const { assert!(From::RANK < To::RANK, "VerifiedEdge: cycle detected — From::RANK must be strictly less than To::RANK") };
        Self { _from: PhantomData, _to: PhantomData }
    }
}

impl<From: Node, To: Node> Default for VerifiedEdge<From, To> {
    fn default() -> Self { Self::new() }
}

// ─── Path invariants ──────────────────────────────────────────────────────

/// Type-level proof that a reachable path exists from StartNode to EndNode.
pub trait PathInvariants {
    type StartNode: Node;
    type EndNode: Node;
}

/// Single-hop path: one VerifiedEdge From→To.
pub struct BaseStep<From: Node, To: Node> {
    pub edge: VerifiedEdge<From, To>,
}

impl<From: Node, To: Node> PathInvariants for BaseStep<From, To> {
    type StartNode = From;
    type EndNode = To;
}

/// Multi-hop path: prepend From→Inter to an existing path starting at Inter.
/// Type-level transitivity: if From < Inter and Inter ≤ End, then From < End.
pub struct ConsStep<From: Node, Inter: Node, Next: PathInvariants<StartNode = Inter>> {
    pub edge: VerifiedEdge<From, Inter>,
    pub next: Next,
}

impl<From: Node, Inter: Node, Next: PathInvariants<StartNode = Inter>> PathInvariants
    for ConsStep<From, Inter, Next>
{
    type StartNode = From;
    type EndNode = Next::EndNode;
}

// ─── Lawvere metric layer ─────────────────────────────────────────────────

/// Divergence weight for a single edge.
/// Enriches the DAG over ([0,∞], ≥, 0, +). Triangle inequality holds by addition.
pub trait LawvereMetric {
    const DIVERGENCE_WEIGHT: f64;
}

impl<From: Node, To: Node> LawvereMetric for VerifiedEdge<From, To> {
    // T2 hypothesis: base divergence per edge is 0.0025.
    // A rank-proportional weight (e.g., 1.0 / rank_gap) is a valid T2 extension.
    const DIVERGENCE_WEIGHT: f64 = 0.0025;
}

/// Accumulates divergence risk across a path. The total is the Lawvere composition.
pub trait PathMetricExt {
    fn total_divergence_risk() -> f64;
}

impl<From: Node, To: Node> PathMetricExt for BaseStep<From, To> {
    fn total_divergence_risk() -> f64 {
        <VerifiedEdge<From, To> as LawvereMetric>::DIVERGENCE_WEIGHT
    }
}

impl<From: Node, Inter: Node, Next> PathMetricExt for ConsStep<From, Inter, Next>
where
    Next: PathInvariants<StartNode = Inter> + PathMetricExt,
{
    fn total_divergence_risk() -> f64 {
        <VerifiedEdge<From, Inter> as LawvereMetric>::DIVERGENCE_WEIGHT
            + Next::total_divergence_risk()
    }
}

// ─── Homotopy witness ─────────────────────────────────────────────────────

/// Structural proof that P1 and P2 share the same start and end nodes.
///
/// EPISTEMIC NOTE: This is endpoint equality, not full HoTT 2-cell equivalence.
/// Full homotopy (identical state transformation effects) requires dependent types
/// unavailable in stable Rust. The mathematical claim of 2-cell propositional equality
/// is T3 — research conjecture. The struct itself is T2 engineering.
pub struct HomotopyWitness<P1, P2>
where
    P1: PathInvariants,
    P2: PathInvariants<StartNode = P1::StartNode, EndNode = P1::EndNode>,
{
    _p1: PhantomData<P1>,
    _p2: PhantomData<P2>,
}

impl<P1, P2> HomotopyWitness<P1, P2>
where
    P1: PathInvariants,
    P2: PathInvariants<StartNode = P1::StartNode, EndNode = P1::EndNode>,
{
    /// Declare structural endpoint equivalence. const fn — zero runtime cost.
    pub const fn declare() -> Self {
        Self { _p1: PhantomData, _p2: PhantomData }
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(Clone, PartialEq, Debug)] struct StateA(Vec<u8>);
    #[derive(Clone, PartialEq, Debug)] struct StateB(u64);
    #[derive(Clone, PartialEq, Debug)] struct StateC(bool);
    #[derive(Clone, PartialEq, Debug)] struct StateD(u32);

    struct NodeA;
    impl Node for NodeA { const RANK: usize = 1; type State = StateA; }

    struct NodeB;
    impl Node for NodeB { const RANK: usize = 2; type State = StateB; }

    struct NodeC;
    impl Node for NodeC { const RANK: usize = 3; type State = StateC; }

    struct NodeD;
    impl Node for NodeD { const RANK: usize = 10; type State = StateD; }

    #[test]
    fn verified_edge_adjacent_ranks() {
        let _e = VerifiedEdge::<NodeA, NodeB>::new();
    }

    #[test]
    fn verified_edge_large_rank_gap() {
        let _e = VerifiedEdge::<NodeA, NodeD>::new(); // rank 1 → 10
    }

    #[test]
    fn base_step_path_invariants() {
        let _path: BaseStep<NodeA, NodeB> = BaseStep { edge: VerifiedEdge::new() };
    }

    #[test]
    fn cons_step_two_hops() {
        let _path = ConsStep {
            edge: VerifiedEdge::<NodeA, NodeB>::new(),
            next: BaseStep { edge: VerifiedEdge::<NodeB, NodeC>::new() },
        };
        // StartNode=NodeA, EndNode=NodeC — transitivity enforced in the type
    }

    #[test]
    fn cons_step_three_hops() {
        let _path = ConsStep {
            edge: VerifiedEdge::<NodeA, NodeB>::new(),
            next: ConsStep {
                edge: VerifiedEdge::<NodeB, NodeC>::new(),
                next: BaseStep { edge: VerifiedEdge::<NodeC, NodeD>::new() },
            },
        };
    }

    #[test]
    fn base_step_divergence_is_single_weight() {
        let risk = <BaseStep<NodeA, NodeB> as PathMetricExt>::total_divergence_risk();
        assert!((risk - 0.0025).abs() < 1e-12);
    }

    #[test]
    fn cons_step_divergence_accumulates() {
        let risk = <ConsStep<NodeA, NodeB, BaseStep<NodeB, NodeC>> as PathMetricExt>::total_divergence_risk();
        assert!((risk - 0.005).abs() < 1e-12); // 2 × 0.0025
    }

    #[test]
    fn three_hop_divergence_accumulates() {
        type P = ConsStep<NodeA, NodeB, ConsStep<NodeB, NodeC, BaseStep<NodeC, NodeD>>>;
        let risk = <P as PathMetricExt>::total_divergence_risk();
        assert!((risk - 0.0075).abs() < 1e-12); // 3 × 0.0025
    }

    #[test]
    fn triangle_inequality_holds() {
        let d_ab = <BaseStep<NodeA, NodeB> as PathMetricExt>::total_divergence_risk();
        let d_bc = <BaseStep<NodeB, NodeC> as PathMetricExt>::total_divergence_risk();
        let d_ac = <ConsStep<NodeA, NodeB, BaseStep<NodeB, NodeC>> as PathMetricExt>::total_divergence_risk();
        // d(A,C) ≤ d(A,B) + d(B,C) — equality holds since metric is purely additive
        assert!(d_ac <= d_ab + d_bc + 1e-12);
    }

    #[test]
    fn lawvere_weight_is_valid_probability() {
        let w = <VerifiedEdge<NodeA, NodeB> as LawvereMetric>::DIVERGENCE_WEIGHT;
        assert!(w > 0.0);
        assert!(w < 1.0);
    }

    #[test]
    fn divergence_below_phi_threshold() {
        // 1/φ ≈ 0.6180 — two-hop path well below the constitutional threshold
        let risk = <ConsStep<NodeA, NodeB, BaseStep<NodeB, NodeC>> as PathMetricExt>::total_divergence_risk();
        assert!(risk < 0.6180, "divergence must remain below φ-quorum-threshold");
    }

    #[test]
    fn homotopy_witness_reflexive() {
        type P = BaseStep<NodeA, NodeB>;
        let _w = HomotopyWitness::<P, P>::declare();
    }

    #[test]
    fn homotopy_witness_same_endpoints_different_paths() {
        // Both paths: NodeA → NodeB → NodeC (same structural shape here)
        type P1 = ConsStep<NodeA, NodeB, BaseStep<NodeB, NodeC>>;
        type P2 = ConsStep<NodeA, NodeB, BaseStep<NodeB, NodeC>>;
        let _w = HomotopyWitness::<P1, P2>::declare();
    }

    #[test]
    fn rank_ordering_strictly_increasing() {
        assert!(NodeA::RANK < NodeB::RANK);
        assert!(NodeB::RANK < NodeC::RANK);
        assert!(NodeC::RANK < NodeD::RANK);
    }

    #[test]
    fn default_edge_constructs() {
        let _e: VerifiedEdge<NodeA, NodeB> = Default::default();
    }
}
