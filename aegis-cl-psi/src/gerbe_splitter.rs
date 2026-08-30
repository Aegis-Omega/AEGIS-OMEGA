//! Gerbe Splitter — Constitutional Symmetry Breaking via CCIL Projection
//!
//! EPISTEMIC TIER: T2 (code) / T3 (theoretical claim)
//! Code: deterministic π₀ extraction via weighted projection.
//! Claim: correspondence to gerbe splitting in higher gauge theory is T3.
//!
//! What this does: given multiple superposition branches, applies
//! CCIL constitutional weights to select a single resolved output
//! (deterministic π₀ extraction). No randomness. Auditable.

use serde::Serialize;

#[derive(Serialize, Debug, Clone)]
pub struct GerbeSplitResult {
    pub resolved_vector: Vec<f32>,
    pub selected_branch_idx: usize,
    pub constitutional_score: f32,
    pub split_method: String,
}

pub struct GerbeSplitter {
    /// CCIL constitutional weights — higher weight = preferred branch.
    pub ccil_weights: Vec<f32>,
}

impl GerbeSplitter {
    pub fn new(ccil_weights: Vec<f32>) -> Self {
        Self { ccil_weights }
    }

    /// Uniform weights fallback constructor.
    pub fn uniform(branch_count: usize) -> Self {
        let w = if branch_count == 0 { Vec::new() }
                else { vec![1.0 / branch_count as f32; branch_count] };
        Self { ccil_weights: w }
    }

    /// Split: select the branch with the highest constitutional score.
    /// Score = dot(ccil_weights, lyapunov_margins) per branch.
    pub fn split(
        &self,
        branches: &[Vec<f32>],
        lyapunov_margins: &[f32],
    ) -> Option<GerbeSplitResult> {
        if branches.is_empty() { return None; }

        let n = branches.len();
        let weights: Vec<f32> = if self.ccil_weights.len() >= n {
            self.ccil_weights[..n].to_vec()
        } else {
            vec![1.0 / n as f32; n]
        };

        let scores: Vec<f32> = branches.iter().enumerate().map(|(i, _)| {
            let w = weights.get(i).copied().unwrap_or(0.0);
            let margin = lyapunov_margins.get(i).copied().unwrap_or(0.0);
            w * margin
        }).collect();

        let selected = scores.iter().enumerate()
            .max_by(|(_, a), (_, b)| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal))
            .map(|(i, _)| i)
            .unwrap_or(0);

        Some(GerbeSplitResult {
            resolved_vector: branches[selected].clone(),
            selected_branch_idx: selected,
            constitutional_score: scores[selected],
            split_method: "ccil_weighted_lyapunov".to_string(),
        })
    }

    /// Weighted mean collapse (when no single branch dominates).
    pub fn weighted_mean(&self, branches: &[Vec<f32>]) -> Vec<f32> {
        if branches.is_empty() { return Vec::new(); }
        let n = branches.len();
        let dim = branches[0].len();
        let weights: Vec<f32> = if self.ccil_weights.len() >= n {
            let s: f32 = self.ccil_weights[..n].iter().sum();
            if s > 0.0 { self.ccil_weights[..n].iter().map(|&w| w / s).collect() }
            else { vec![1.0 / n as f32; n] }
        } else {
            vec![1.0 / n as f32; n]
        };

        let mut result = vec![0.0f32; dim];
        for (branch, &w) in branches.iter().zip(weights.iter()) {
            for (r, &v) in result.iter_mut().zip(branch.iter()) {
                *r += w * v;
            }
        }
        result
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn selects_branch_with_highest_score() {
        let splitter = GerbeSplitter::new(vec![0.3, 0.7]);
        let branches = vec![vec![1.0f32], vec![2.0]];
        let margins = vec![1.0, 1.0];
        let result = splitter.split(&branches, &margins).unwrap();
        // weights [0.3, 0.7] * margins [1, 1] → scores [0.3, 0.7] → branch 1 wins
        assert_eq!(result.selected_branch_idx, 1);
        assert_eq!(result.resolved_vector, vec![2.0]);
    }

    #[test]
    fn empty_branches_returns_none() {
        let splitter = GerbeSplitter::uniform(0);
        assert!(splitter.split(&[], &[]).is_none());
    }

    #[test]
    fn weighted_mean_uniform() {
        let splitter = GerbeSplitter::uniform(2);
        let branches = vec![vec![0.0f32, 4.0], vec![2.0, 0.0]];
        let mean = splitter.weighted_mean(&branches);
        assert_eq!(mean, vec![1.0, 2.0]);
    }

    // 4. uniform(3) has 3 equal weights summing to ~1
    #[test]
    fn uniform_weights_are_equal() {
        let splitter = GerbeSplitter::uniform(3);
        assert_eq!(splitter.ccil_weights.len(), 3);
        let expected = 1.0f32 / 3.0;
        for &w in &splitter.ccil_weights {
            assert!((w - expected).abs() < 1e-6);
        }
    }

    // 5. single branch always returns index 0
    #[test]
    fn single_branch_selects_index_0() {
        let splitter = GerbeSplitter::new(vec![1.0]);
        let result = splitter.split(&[vec![7.0f32, 8.0]], &[1.0]).unwrap();
        assert_eq!(result.selected_branch_idx, 0);
        assert_eq!(result.resolved_vector, vec![7.0, 8.0]);
    }

    // 6. split_method is always "ccil_weighted_lyapunov"
    #[test]
    fn split_method_field_value() {
        let splitter = GerbeSplitter::uniform(2);
        let result = splitter.split(&[vec![1.0f32], vec![2.0]], &[1.0, 1.0]).unwrap();
        assert_eq!(result.split_method, "ccil_weighted_lyapunov");
    }

    // 7. constitutional_score = weight * margin for winning branch
    #[test]
    fn constitutional_score_correct() {
        let splitter = GerbeSplitter::new(vec![0.4, 0.6]);
        let result = splitter.split(&[vec![1.0f32], vec![2.0]], &[2.0, 3.0]).unwrap();
        // scores: [0.4*2=0.8, 0.6*3=1.8] → branch 1 wins, score=1.8
        assert_eq!(result.selected_branch_idx, 1);
        assert!((result.constitutional_score - 1.8f32).abs() < 1e-5);
    }

    // 8. weighted_mean on empty branches returns empty vec
    #[test]
    fn weighted_mean_empty_branches() {
        let splitter = GerbeSplitter::uniform(0);
        let mean = splitter.weighted_mean(&[]);
        assert!(mean.is_empty());
    }

    // 9. weighted_mean three equal-weight branches
    #[test]
    fn weighted_mean_three_branches() {
        let splitter = GerbeSplitter::uniform(3);
        let branches = vec![vec![0.0f32], vec![3.0], vec![6.0]];
        let mean = splitter.weighted_mean(&branches);
        assert!((mean[0] - 3.0f32).abs() < 1e-5);
    }

    // 10. zero margin means zero score (branch with nonzero margin wins)
    #[test]
    fn zero_margin_loses_to_nonzero() {
        let splitter = GerbeSplitter::new(vec![0.5, 0.5]);
        let result = splitter.split(&[vec![1.0f32], vec![2.0]], &[0.0, 1.0]).unwrap();
        assert_eq!(result.selected_branch_idx, 1);
    }
}
