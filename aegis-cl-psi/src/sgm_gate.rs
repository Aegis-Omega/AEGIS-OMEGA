//! SGM-Ψ Gate — Sparse Gating Mechanism
//! EPISTEMIC TIER: T2
//!
//! Routes activations based on attention entropy threshold.
//! Outputs a sparse routing mask for LUT-KAN pathway selection.
//! Dense fallback when entropy ≤ threshold (all paths active).

use serde::Serialize;

#[derive(Clone, Serialize)]
pub struct RoutingMask {
    pub active_indices: Vec<usize>,
    pub entropy: f32,
    pub threshold_exceeded: bool,
}

pub struct SGMGate {
    pub threshold: f32,
    pub epsilon: f32,
}

impl SGMGate {
    pub fn new(threshold: f32) -> Self {
        Self { threshold, epsilon: 1e-9 }
    }

    /// Shannon entropy over normalized activation distribution.
    pub fn compute_entropy(&self, probs: &[f32]) -> f32 {
        let sum: f32 = probs.iter().sum();
        if sum <= self.epsilon { return 0.0; }
        let norm = probs.iter().map(|&p| p / sum).collect::<Vec<_>>();
        -norm.iter()
            .map(|&p| if p > self.epsilon { p * p.ln() } else { 0.0 })
            .sum::<f32>()
    }

    /// Sparse routing mask: indices where activation > mean + 0.5*std.
    /// Dense fallback (all indices) when entropy ≤ threshold.
    pub fn route(&self, activations: &[f32]) -> RoutingMask {
        let entropy = self.compute_entropy(activations);
        let threshold_exceeded = entropy > self.threshold;

        let mean = activations.iter().sum::<f32>() / activations.len().max(1) as f32;
        let var = activations.iter().map(|&x| (x - mean).powi(2)).sum::<f32>()
            / activations.len().max(1) as f32;
        let std = var.sqrt();
        let cutoff = mean + 0.5 * std;

        let active_indices = if threshold_exceeded {
            activations.iter()
                .enumerate()
                .filter(|&(_, &v)| v > cutoff)
                .map(|(i, _)| i)
                .collect()
        } else {
            (0..activations.len()).collect()
        };

        RoutingMask { active_indices, entropy, threshold_exceeded }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn uniform_distribution_low_entropy() {
        let gate = SGMGate::new(1.5);
        let uniform = vec![0.25f32; 4];
        let mask = gate.route(&uniform);
        // uniform → low entropy → dense fallback
        assert_eq!(mask.active_indices.len(), 4);
        assert!(!mask.threshold_exceeded);
    }

    #[test]
    fn peaked_distribution_high_entropy_sparse() {
        let gate = SGMGate::new(0.1);
        let peaked = vec![0.9f32, 0.05, 0.03, 0.02];
        let mask = gate.route(&peaked);
        assert!(mask.threshold_exceeded);
        // Only the dominant activation should pass cutoff
        assert!(mask.active_indices.len() < peaked.len());
    }

    #[test]
    fn entropy_zero_on_empty() {
        let gate = SGMGate::new(1.0);
        assert_eq!(gate.compute_entropy(&[]), 0.0);
    }
}
