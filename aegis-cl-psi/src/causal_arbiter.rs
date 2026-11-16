//! Gate 206: Causal Confidence Arbiter
//! Secular Implementation of Uncertainty Preservation and Horizon Recognition.
//! Prevents hallucination by mathematically bounding causal confidence and enforcing execution halts.

use std::collections::{BTreeMap, BTreeSet};

/// Represents the verifiable state of a causal node.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum EpistemicState {
    /// Mechanically proven, cryptographically sealed.
    Verified = 0,
    /// Strong causal support, but incomplete verification.
    Inferred = 1,
    /// Probabilistic estimate, high uncertainty.
    Speculative = 2,
    /// Beyond computational or verifiable horizon.
    Unverifiable = 3,
}

/// A node in the causal dependency graph.
#[derive(Debug, Clone)]
pub struct CausalNode {
    pub id: u64,
    pub state: EpistemicState,
    /// Confidence score from 0.0 (pure noise) to 1.0 (absolute certainty).
    pub confidence: f64, 
    pub dependencies: Vec<u64>,
}

/// The Arbiter evaluates the structural integrity of a causal chain.
pub struct CausalConfidenceArbiter {
    nodes: BTreeMap<u64, CausalNode>,
    /// The minimum confidence threshold required to proceed with execution.
    execution_threshold: f64, 
}

impl CausalConfidenceArbiter {
    pub fn new(execution_threshold: f64) -> Self {
        Self {
            nodes: BTreeMap::new(),
            execution_threshold: if execution_threshold.is_finite() {
                execution_threshold.clamp(0.0, 1.0)
            } else {
                f64::NAN
            },
        }
    }

    pub fn register_node(&mut self, node: CausalNode) {
        self.nodes.insert(node.id, node);
    }

    /// Evaluates a causal chain. If any dependency is Unverifiable or falls below 
    /// the confidence threshold, the chain is halted to prevent hallucination.
    pub fn evaluate_chain(&self, root_id: u64) -> Result<EpistemicState, EpistemicViolation> {
        if !self.execution_threshold.is_finite() {
            return Err(EpistemicViolation::InvalidThreshold);
        }
        let mut visited = BTreeMap::new();
        let mut active = BTreeSet::new();
        self.traverse(root_id, &mut visited, &mut active)
    }

    fn traverse(
        &self,
        current_id: u64,
        visited: &mut BTreeMap<u64, EpistemicState>,
        active: &mut BTreeSet<u64>,
    ) -> Result<EpistemicState, EpistemicViolation> {
        if let Some(&state) = visited.get(&current_id) {
            return Ok(state);
        }

        // Visited nodes are complete; active nodes mark dependency cycles.
        if !active.insert(current_id) {
            return Err(EpistemicViolation::DependencyCycle(current_id));
        }
        let node = self.nodes.get(&current_id).ok_or(EpistemicViolation::MissingDependency(current_id))?;
        if !node.confidence.is_finite() || !(0.0..=1.0).contains(&node.confidence) {
            return Err(EpistemicViolation::InvalidConfidence(current_id));
        }

        // THE ABSOLUTE HORIZON: If we hit Unverifiable, we must halt and preserve uncertainty.
        if node.state == EpistemicState::Unverifiable {
            return Err(EpistemicViolation::HorizonExceeded(current_id));
        }

        let mut min_confidence = node.confidence;
        let mut weakest_state = node.state;

        for &dep_id in &node.dependencies {
            let dep_state = self.traverse(dep_id, visited, active)?;
            
            // Identify the weakest epistemic link in the causal chain
            if dep_state > weakest_state {
                weakest_state = dep_state;
            }
            
            // Compound confidence (multiplicative decay across dependencies)
            let dep_node = self.nodes.get(&dep_id).unwrap();
            min_confidence *= dep_node.confidence;
        }

        // Enforce the Feasibility as Constraint directive
        if min_confidence < self.execution_threshold {
            return Err(EpistemicViolation::ConfidenceDecay {
                node_id: current_id,
                score: min_confidence,
                threshold: self.execution_threshold,
            });
        }

        active.remove(&current_id);
        visited.insert(current_id, weakest_state);
        Ok(weakest_state)
    }
}

/// Errors generated when the system detects structural entropy or unverified assumptions.
#[derive(Debug, PartialEq)]
pub enum EpistemicViolation {
    /// A NaN or infinite threshold cannot authorize execution.
    InvalidThreshold,
    /// The node has a nonfinite or out-of-range confidence.
    InvalidConfidence(u64),
    /// The graph references a node already active in this DFS path.
    DependencyCycle(u64),
    /// A required causal dependency is missing from the graph.
    MissingDependency(u64),
    /// The system has reached the boundary of verifiable logic.
    HorizonExceeded(u64),
    /// The compounded uncertainty of the chain exceeds the operational threshold.
    ConfidenceDecay {
        node_id: u64,
        score: f64,
        threshold: f64,
    },
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_verified_chain_passes() {
        let mut arbiter = CausalConfidenceArbiter::new(0.8);
        arbiter.register_node(CausalNode { id: 1, state: EpistemicState::Verified, confidence: 0.95, dependencies: vec![2] });
        arbiter.register_node(CausalNode { id: 2, state: EpistemicState::Verified, confidence: 0.95, dependencies: vec![] });

        assert_eq!(arbiter.evaluate_chain(1).unwrap(), EpistemicState::Verified);
    }

    #[test]
    fn test_horizon_exceeded_halts_execution() {
        let mut arbiter = CausalConfidenceArbiter::new(0.5);
        arbiter.register_node(CausalNode { id: 1, state: EpistemicState::Inferred, confidence: 0.9, dependencies: vec![2] });
        arbiter.register_node(CausalNode { id: 2, state: EpistemicState::Unverifiable, confidence: 0.0, dependencies: vec![] });

        assert_eq!(arbiter.evaluate_chain(1).unwrap_err(), EpistemicViolation::HorizonExceeded(2));
    }

    #[test]
    fn test_confidence_decay_halts_execution() {
        let mut arbiter = CausalConfidenceArbiter::new(0.8);
        // 0.9 * 0.85 = 0.765, which is below the 0.8 threshold
        arbiter.register_node(CausalNode { id: 1, state: EpistemicState::Verified, confidence: 0.9, dependencies: vec![2] });
        arbiter.register_node(CausalNode { id: 2, state: EpistemicState::Inferred, confidence: 0.85, dependencies: vec![] });

        match arbiter.evaluate_chain(1) {
            Err(EpistemicViolation::ConfidenceDecay { score, .. }) => {
                assert!((score - 0.765).abs() < 1e-9);
            }
            _ => panic!("Expected ConfidenceDecay"),
        }
    }

    // 4. Single node with no dependencies passes
    #[test]
    fn single_node_no_deps_passes() {
        let mut arbiter = CausalConfidenceArbiter::new(0.5);
        arbiter.register_node(CausalNode { id: 42, state: EpistemicState::Verified, confidence: 0.99, dependencies: vec![] });
        assert_eq!(arbiter.evaluate_chain(42).unwrap(), EpistemicState::Verified);
    }

    // 5. Missing dependency returns MissingDependency error
    #[test]
    fn missing_dependency_returns_error() {
        let mut arbiter = CausalConfidenceArbiter::new(0.5);
        arbiter.register_node(CausalNode { id: 1, state: EpistemicState::Verified, confidence: 0.9, dependencies: vec![99] });
        assert_eq!(arbiter.evaluate_chain(1).unwrap_err(), EpistemicViolation::MissingDependency(99));
    }

    // 6. Speculative state propagates through the chain
    #[test]
    fn speculative_state_propagates() {
        let mut arbiter = CausalConfidenceArbiter::new(0.0);
        arbiter.register_node(CausalNode { id: 1, state: EpistemicState::Verified, confidence: 1.0, dependencies: vec![2] });
        arbiter.register_node(CausalNode { id: 2, state: EpistemicState::Speculative, confidence: 1.0, dependencies: vec![] });
        assert_eq!(arbiter.evaluate_chain(1).unwrap(), EpistemicState::Speculative);
    }

    // 7. Zero threshold means any confidence passes
    #[test]
    fn threshold_zero_always_passes() {
        let mut arbiter = CausalConfidenceArbiter::new(0.0);
        arbiter.register_node(CausalNode { id: 1, state: EpistemicState::Inferred, confidence: 0.0001, dependencies: vec![] });
        assert!(arbiter.evaluate_chain(1).is_ok());
    }

    // 8. Deep chain of 5 verified nodes all pass
    #[test]
    fn deep_verified_chain_passes() {
        let mut arbiter = CausalConfidenceArbiter::new(0.5);
        for i in 1u64..=5 {
            let deps = if i < 5 { vec![i + 1] } else { vec![] };
            arbiter.register_node(CausalNode { id: i, state: EpistemicState::Verified, confidence: 0.99, dependencies: deps });
        }
        assert_eq!(arbiter.evaluate_chain(1).unwrap(), EpistemicState::Verified);
    }

    // 9. Confidence exactly at threshold is NOT a decay error (strict <)
    #[test]
    fn confidence_at_threshold_passes() {
        let mut arbiter = CausalConfidenceArbiter::new(0.9);
        // Single node, confidence == threshold: 0.9 < 0.9 is false → passes
        arbiter.register_node(CausalNode { id: 1, state: EpistemicState::Verified, confidence: 0.9, dependencies: vec![] });
        assert!(arbiter.evaluate_chain(1).is_ok());
    }

    // 10. Inferred state propagates to root
    #[test]
    fn inferred_state_propagates() {
        let mut arbiter = CausalConfidenceArbiter::new(0.0);
        arbiter.register_node(CausalNode { id: 1, state: EpistemicState::Verified, confidence: 1.0, dependencies: vec![2] });
        arbiter.register_node(CausalNode { id: 2, state: EpistemicState::Inferred, confidence: 1.0, dependencies: vec![] });
        assert_eq!(arbiter.evaluate_chain(1).unwrap(), EpistemicState::Inferred);
    }

    // 11. A NaN or otherwise invalid confidence cannot evade the threshold.
    #[test]
    fn invalid_confidence_fails_closed() {
        for confidence in [f64::NAN, f64::INFINITY, f64::NEG_INFINITY, -0.01, 1.01] {
            let mut arbiter = CausalConfidenceArbiter::new(0.5);
            arbiter.register_node(CausalNode {
                id: 7, state: EpistemicState::Verified, confidence, dependencies: vec![],
            });
            assert_eq!(arbiter.evaluate_chain(7).unwrap_err(), EpistemicViolation::InvalidConfidence(7));
        }
    }

    // 12. Threshold NaN and infinity are not accepted as permissions.
    #[test]
    fn invalid_threshold_fails_closed() {
        for threshold in [f64::NAN, f64::INFINITY, f64::NEG_INFINITY] {
            let mut arbiter = CausalConfidenceArbiter::new(threshold);
            arbiter.register_node(CausalNode {
                id: 1, state: EpistemicState::Verified, confidence: 1.0, dependencies: vec![],
            });
            assert_eq!(arbiter.evaluate_chain(1).unwrap_err(), EpistemicViolation::InvalidThreshold);
        }
    }

    // 13. Self-loops and two-node cycles are errors, not unbounded recursion.
    #[test]
    fn dependency_cycles_fail_closed() {
        let mut self_loop = CausalConfidenceArbiter::new(0.5);
        self_loop.register_node(CausalNode {
            id: 1, state: EpistemicState::Verified, confidence: 1.0, dependencies: vec![1],
        });
        assert_eq!(self_loop.evaluate_chain(1).unwrap_err(), EpistemicViolation::DependencyCycle(1));

        let mut two_node = CausalConfidenceArbiter::new(0.5);
        two_node.register_node(CausalNode {
            id: 1, state: EpistemicState::Verified, confidence: 1.0, dependencies: vec![2],
        });
        two_node.register_node(CausalNode {
            id: 2, state: EpistemicState::Verified, confidence: 1.0, dependencies: vec![1],
        });
        assert_eq!(two_node.evaluate_chain(1).unwrap_err(), EpistemicViolation::DependencyCycle(1));
    }

    // 14. Reused DAG dependencies are not cycles.
    #[test]
    fn shared_dependency_dag_still_passes() {
        let mut arbiter = CausalConfidenceArbiter::new(1.0);
        arbiter.register_node(CausalNode {
            id: 1, state: EpistemicState::Verified, confidence: 1.0, dependencies: vec![2, 3],
        });
        for id in [2, 3] {
            arbiter.register_node(CausalNode {
                id, state: EpistemicState::Verified, confidence: 1.0, dependencies: vec![4],
            });
        }
        arbiter.register_node(CausalNode {
            id: 4, state: EpistemicState::Verified, confidence: 1.0, dependencies: vec![],
        });
        assert_eq!(arbiter.evaluate_chain(1).unwrap(), EpistemicState::Verified);
    }
}