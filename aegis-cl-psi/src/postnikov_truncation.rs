//! Postnikov τ≤k Truncation
//!
//! EPISTEMIC TIER: T2 (code) / T3 (theoretical claim)
//! Code: deterministic zeroing of components above index k.
//! Claim: correspondence to Postnikov truncation in homotopy theory is T3.
//!
//! What this does: given a multi-level coherence state, zeroes out
//! components above truncation level k, producing a "simpler" representation
//! used as input to gerbe splitting.

use serde::Serialize;

#[derive(Serialize, Debug, Clone, PartialEq)]
pub enum TruncationLevel {
    Tau0,   // Keep only π₀ (connected components)
    Tau1,   // Keep up to π₁
    Tau2,   // Keep up to π₂
    TauInf, // No truncation
}

#[derive(Serialize, Debug, Clone)]
pub struct TruncationResult {
    pub level: TruncationLevel,
    pub retained_components: Vec<f32>,
    pub zeroed_count: usize,
}

pub struct PostnikovTruncation;

impl PostnikovTruncation {
    /// Apply τ≤k truncation to a coherence state vector.
    /// k is the maximum index to retain; components above k are zeroed.
    pub fn truncate(state: &[f32], level: TruncationLevel) -> TruncationResult {
        let k = match level {
            TruncationLevel::Tau0 => 1,
            TruncationLevel::Tau1 => 2,
            TruncationLevel::Tau2 => 4,
            TruncationLevel::TauInf => state.len(),
        };

        let mut retained = state.to_vec();
        let mut zeroed_count = 0;
        for component in retained.iter_mut().skip(k) {
            if *component != 0.0 {
                zeroed_count += 1;
                *component = 0.0;
            }
        }

        TruncationResult { level, retained_components: retained, zeroed_count }
    }

    /// π₀ extraction: return the mean of the first component (global section proxy).
    pub fn pi0_extract(state: &[f32]) -> f32 {
        if state.is_empty() { return 0.0; }
        state[0]
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tau0_keeps_only_first() {
        let state = vec![1.0f32, 2.0, 3.0, 4.0, 5.0];
        let result = PostnikovTruncation::truncate(&state, TruncationLevel::Tau0);
        assert_eq!(result.retained_components[0], 1.0);
        assert!(result.retained_components[1..].iter().all(|&v| v == 0.0));
        assert_eq!(result.zeroed_count, 4);
    }

    #[test]
    fn tau_inf_keeps_all() {
        let state = vec![1.0f32, 2.0, 3.0];
        let result = PostnikovTruncation::truncate(&state, TruncationLevel::TauInf);
        assert_eq!(result.zeroed_count, 0);
        assert_eq!(result.retained_components, state);
    }

    #[test]
    fn pi0_returns_first_component() {
        assert_eq!(PostnikovTruncation::pi0_extract(&[5.0, 3.0, 1.0]), 5.0);
        assert_eq!(PostnikovTruncation::pi0_extract(&[]), 0.0);
    }
}
