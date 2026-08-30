//! Gate 206: Causal Confidence Arbiter
//! Secular Implementation of Uncertainty Preservation and Horizon Recognition.
//! Prevents hallucination by mathematically bounding causal confidence and enforcing execution halts.

use std::collections::BTreeMap;

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
            execution_threshold: execution_threshold.clamp(0.0, 1.0),
        }
    }

    pub fn register_node(&mut self, node: CausalNode) {
        self.nodes.insert(node.id, node);
    }

    /// Evaluates a causal chain. If any dependency is Unverifiable or falls below 
    /// the confidence threshold, the chain is halted to prevent hallucination.
    pub fn evaluate_chain(&self, root_id: u64) -> Result<EpistemicState, EpistemicViolation> {
        let mut visited = BTreeMap::new();
        self.traverse(root_id, &mut visited)
    }

    fn traverse(
        &self,
        current_id: u64,
        visited: &mut BTreeMap<u64, EpistemicState>,
    ) -> Result<EpistemicState, EpistemicViolation> {
        if let Some(&state) = visited.get(&current_id) {
            return Ok(state);
        }

        let node = self.nodes.get(&current_id).ok_or(EpistemicViolation::MissingDependency(current_id))?;

        // THE ABSOLUTE HORIZON: If we hit Unverifiable, we must halt and preserve uncertainty.
        if node.state == EpistemicState::Unverifiable {
            return Err(EpistemicViolation::HorizonExceeded(current_id));
        }

        let mut min_confidence = node.confidence;
        let mut weakest_state = node.state;

        for &dep_id in &node.dependencies {
            let dep_state = self.traverse(dep_id, visited)?;
            
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

        visited.insert(current_id, weakest_state);
        Ok(weakest_state)
    }
}

/// Errors generated when the system detects structural entropy or unverified assumptions.
#[derive(Debug, PartialEq)]
pub enum EpistemicViolation {
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
}