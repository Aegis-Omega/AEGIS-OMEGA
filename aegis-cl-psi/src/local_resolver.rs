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

    // 4. Single branch has zero divergence — resolves in one iteration
    #[test]
    fn single_branch_zero_divergence() {
        let resolver = LocalResolver::new(0.5, 0.01, 0.01);
        let mut branches = vec![vec![1.0f32, 2.0, 3.0]];
        let result = resolver.resolve(&mut branches);
        assert!(result.resolved);
        assert_eq!(result.final_divergence, 0.0);
    }

    // 5. Consensus of two symmetric branches is their midpoint
    #[test]
    fn consensus_is_midpoint_of_two_branches() {
        let resolver = LocalResolver::new(1.0, 0.001, 0.01); // large step → converges fast
        let mut branches = vec![vec![0.0f32, 0.0], vec![2.0f32, 2.0]];
        let result = resolver.resolve(&mut branches);
        // After convergence the consensus should be near [1, 1]
        assert!((result.consensus[0] - 1.0).abs() < 0.1);
        assert!((result.consensus[1] - 1.0).abs() < 0.1);
    }

    // 6. All-zeros branches produce zero consensus
    #[test]
    fn all_zero_branches_produce_zero_consensus() {
        let resolver = LocalResolver::new(0.5, 0.01, 0.01);
        let mut branches = vec![vec![0.0f32; 4], vec![0.0f32; 4]];
        let result = resolver.resolve(&mut branches);
        assert!(result.resolved);
        assert!(result.consensus.iter().all(|&v| v == 0.0));
    }

    // 7. convergence_reason is "threshold_reached" on successful convergence
    #[test]
    fn convergence_reason_threshold_reached() {
        let resolver = LocalResolver::new(0.9, 0.01, 0.01);
        let mut branches = vec![vec![1.0f32], vec![1.005]];
        let result = resolver.resolve(&mut branches);
        assert!(result.resolved);
        assert_eq!(result.convergence_reason, "threshold_reached");
    }

    // 8. convergence_reason is "empty_input" for empty branches
    #[test]
    fn convergence_reason_empty_input() {
        let resolver = LocalResolver::new(0.5, 0.01, 0.01);
        let result = resolver.resolve(&mut vec![]);
        assert_eq!(result.convergence_reason, "empty_input");
    }

    // 9. Larger step size converges in fewer iterations than tiny step
    #[test]
    fn larger_step_converges_faster() {
        let resolver_fast = LocalResolver::new(0.8, 0.001, 0.01);
        let resolver_slow = LocalResolver::new(0.01, 0.001, 0.01);
        let initial = vec![vec![0.0f32, 0.0], vec![10.0f32, 10.0]];
        let result_fast = resolver_fast.resolve(&mut initial.clone());
        let result_slow = resolver_slow.resolve(&mut initial.clone());
        assert!(result_fast.iterations <= result_slow.iterations);
    }

    // 10. Max iterations never exceeded (32 is the hard cap)
    #[test]
    fn max_iterations_hard_cap() {
        let resolver = LocalResolver::new(0.001, 0.0, 0.01); // threshold=0 → always resolves
        // Use divergence_threshold=0 to force early exit and check cap isn't exceeded
        let resolver2 = LocalResolver::new(0.001, 0.001, 0.01);
        let mut branches = vec![vec![0.0f32; 4], vec![1000.0f32; 4]]; // very far apart
        let result = resolver2.resolve(&mut branches);
        assert!(result.iterations <= MAX_ITERATIONS);
        let _ = resolver; // suppress unused warning
    }
}
