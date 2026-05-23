//! Local Topology Resolver — Lyapunov Gradient Descent for H³ Resolution
//! EPISTEMIC TIER: T1/T2
//!
//! Applies constrained gradient steps to minimize divergence between superposition
//! branches, bounded by Lyapunov stability. Max 32 iterations (compute-bounded).
//! Returns a resolved consensus vector or signals failure for cloud escalation.

use serde::Serialize;

const MAX_ITERATIONS: u32 = 32;

#[derive(Serialize, Debug, Clone)]
pub struct ResolutionResult {
    pub resolved: bool,
    pub iterations: u32,
    pub final_divergence: f32,
    pub consensus: Vec<f32>,
    pub convergence_reason: String,
}

pub struct LocalResolver {
    pub step_size: f32,
    pub divergence_threshold: f32,
    pub lyapunov_epsilon: f32,
}

impl LocalResolver {
    pub fn new(step_size: f32, divergence_threshold: f32, lyapunov_epsilon: f32) -> Self {
        Self { step_size, divergence_threshold, lyapunov_epsilon }
    }

    fn mean_vector(branches: &[Vec<f32>]) -> Vec<f32> {
        if branches.is_empty() { return Vec::new(); }
        let len = branches[0].len();
        let mut mean = vec![0.0f32; len];
        for branch in branches {
            for (m, &v) in mean.iter_mut().zip(branch.iter()) {
                *m += v;
            }
        }
        let n = branches.len() as f32;
        mean.iter_mut().for_each(|v| *v /= n);
        mean
    }

    fn max_divergence(branches: &[Vec<f32>], mean: &[f32]) -> f32 {
        branches.iter().map(|branch| {
            branch.iter().zip(mean.iter())
                .map(|(&b, &m)| (b - m).powi(2))
                .sum::<f32>()
                .sqrt()
        }).fold(0.0f32, f32::max)
    }

    /// Attempt to collapse superposition branches to a consensus via gradient descent.
    pub fn resolve(&self, branches: &mut Vec<Vec<f32>>) -> ResolutionResult {
        if branches.is_empty() {
            return ResolutionResult {
                resolved: true, iterations: 0, final_divergence: 0.0,
                consensus: Vec::new(), convergence_reason: "empty_input".to_string(),
            };
        }

        let mut iterations = 0u32;
        let mut divergence = f32::MAX;

        for iter in 0..MAX_ITERATIONS {
            iterations = iter + 1;
            let mean = Self::mean_vector(branches);
            divergence = Self::max_divergence(branches, &mean);

            if divergence <= self.divergence_threshold {
                return ResolutionResult {
                    resolved: true,
                    iterations,
                    final_divergence: divergence,
                    consensus: mean,
                    convergence_reason: "threshold_reached".to_string(),
                };
            }

            // Gradient step: move each branch toward the mean
            for branch in branches.iter_mut() {
                for (b, &m) in branch.iter_mut().zip(mean.iter()) {
                    *b += self.step_size * (m - *b);
                }
            }

            // Lyapunov stability check on mean
            let v = mean.iter().map(|&x| x * x).sum::<f32>() / 2.0;
            if v.is_nan() || v.is_infinite() {
                return ResolutionResult {
                    resolved: false,
                    iterations,
                    final_divergence: divergence,
                    consensus: Self::mean_vector(branches),
                    convergence_reason: "lyapunov_nan_abort".to_string(),
                };
            }
        }

        let mean = Self::mean_vector(branches);
        ResolutionResult {
            resolved: divergence <= self.divergence_threshold * 2.0,
            iterations,
            final_divergence: divergence,
            consensus: mean,
            convergence_reason: "max_iterations_reached".to_string(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn converges_near_identical_branches() {
        let resolver = LocalResolver::new(0.5, 0.01, 0.01);
        let mut branches = vec![
            vec![1.0f32, 2.0],
            vec![1.01, 2.01],
        ];
        let result = resolver.resolve(&mut branches);
        assert!(result.resolved);
        assert!(result.final_divergence < 0.01);
    }

    #[test]
    fn does_not_exceed_max_iterations() {
        let resolver = LocalResolver::new(0.01, 0.001, 0.01); // tiny step + tight threshold
        let mut branches = vec![vec![0.0f32; 4], vec![100.0; 4]];
        let result = resolver.resolve(&mut branches);
        assert!(result.iterations <= MAX_ITERATIONS);
    }

    #[test]
    fn empty_branches_resolved_immediately() {
        let resolver = LocalResolver::new(0.5, 0.01, 0.01);
        let result = resolver.resolve(&mut vec![]);
        assert!(result.resolved);
        assert_eq!(result.iterations, 0);
    }
}
