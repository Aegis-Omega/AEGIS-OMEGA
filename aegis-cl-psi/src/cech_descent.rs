//! Čech Descent Tracker — Cosimplicial Coherence up to Level 3
//!
//! EPISTEMIC TIER: T2 (code) / T3 (theoretical claim)
//! Code: deterministic O(N) array operations. Compiles on any Rust target.
//! Claim: the assertion that this constitutes Čech descent in the algebraic
//! topology sense is T3 (research conjecture, not empirically validated).
//! No T0–T2 authority may be grounded in the mathematical correspondence.
//!
//! What this does: tracks coherence defects between model layers at
//! 0-simplex (single model), 1-simplex (pairwise), 2-simplex (triple), and
//! 3-simplex (quadruple) levels. k3_invariant is the mean absolute 3-simplex
//! defect used as a routing threshold.

use serde::Serialize;

#[derive(Serialize, Debug, Clone)]
pub struct CechDescentState {
    /// Level 0: individual model output vectors.
    pub level0_models: Vec<Vec<f32>>,
    /// Level 1: pairwise difference vectors (1-simplices).
    pub level1: Vec<Vec<f32>>,
    /// Level 2: triple-wise coherence defects (2-simplices).
    pub level2: Vec<f32>,
    /// Level 3: quadruple-wise coherence defects (3-simplices).
    pub level3: Vec<f32>,
    /// Routing threshold proxy: mean |level3| defect.
    pub k3_invariant: f32,
}

impl CechDescentState {
    pub fn new() -> Self {
        Self {
            level0_models: Vec::new(),
            level1: Vec::new(),
            level2: Vec::new(),
            level3: Vec::new(),
            k3_invariant: 0.0,
        }
    }

    /// Build descent state from model output vectors.
    pub fn build(models: Vec<Vec<f32>>) -> Self {
        let n = models.len();
        if n == 0 {
            return Self::new();
        }

        // Level 1: pairwise differences
        let mut level1 = Vec::new();
        for i in 0..n {
            for j in (i + 1)..n {
                let diff: Vec<f32> = models[i].iter().zip(models[j].iter())
                    .map(|(&a, &b)| a - b)
                    .collect();
                level1.push(diff);
            }
        }

        // Level 2: triple coherence — |a-b| + |b-c| - |a-c| defect
        let mut level2 = Vec::new();
        for i in 0..n {
            for j in (i + 1)..n {
                for k in (j + 1)..n {
                    let defect: f32 = models[i].iter()
                        .zip(models[j].iter())
                        .zip(models[k].iter())
                        .map(|((&a, &b), &c)| ((a - b).abs() + (b - c).abs() - (a - c).abs()).abs())
                        .sum::<f32>()
                        / models[i].len().max(1) as f32;
                    level2.push(defect);
                }
            }
        }

        // Level 3: quadruple coherence defect
        let mut level3 = Vec::new();
        for i in 0..n {
            for j in (i + 1)..n {
                for k in (j + 1)..n {
                    for l in (k + 1)..n {
                        let defect: f32 = models[i].iter()
                            .zip(models[j].iter())
                            .zip(models[k].iter())
                            .zip(models[l].iter())
                            .map(|(((&a, &b), &c), &d)| {
                                let ab = (a - b).abs();
                                let cd = (c - d).abs();
                                (ab - cd).abs()
                            })
                            .sum::<f32>()
                            / models[i].len().max(1) as f32;
                        level3.push(defect);
                    }
                }
            }
        }

        let k3_invariant = if level3.is_empty() { 0.0 } else {
            level3.iter().sum::<f32>() / level3.len() as f32
        };

        Self { level0_models: models, level1, level2, level3, k3_invariant }
    }
}

impl Default for CechDescentState {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn identical_models_zero_k3() {
        let models = vec![vec![1.0f32, 2.0, 3.0, 4.0]; 4];
        let state = CechDescentState::build(models);
        assert_eq!(state.k3_invariant, 0.0);
    }

    #[test]
    fn two_models_no_level3() {
        let models = vec![vec![1.0f32], vec![2.0]];
        let state = CechDescentState::build(models);
        assert!(state.level3.is_empty());
        assert_eq!(state.level1.len(), 1);
    }

    #[test]
    fn four_models_has_level3() {
        let models = vec![
            vec![1.0f32], vec![2.0], vec![3.0], vec![4.0],
        ];
        let state = CechDescentState::build(models);
        assert_eq!(state.level3.len(), 1);
    }

    #[test]
    fn empty_input_returns_default() {
        let state = CechDescentState::build(vec![]);
        assert_eq!(state.k3_invariant, 0.0);
        assert!(state.level0_models.is_empty());
    }

    // 5. Three models: level2 non-empty, level3 empty (need 4 for quads)
    #[test]
    fn three_models_has_level2_no_level3() {
        let models = vec![vec![1.0f32], vec![2.0], vec![3.0]];
        let state = CechDescentState::build(models);
        assert!(!state.level2.is_empty());
        assert!(state.level3.is_empty());
    }

    // 6. Two models: level1 has 1 entry, level2 empty
    #[test]
    fn two_models_level1_one_entry_level2_empty() {
        let models = vec![vec![1.0f32, 2.0], vec![3.0, 4.0]];
        let state = CechDescentState::build(models);
        assert_eq!(state.level1.len(), 1);
        assert!(state.level2.is_empty());
    }

    // 7. level0_models is preserved verbatim
    #[test]
    fn level0_models_preserved() {
        let input = vec![vec![1.0f32, 2.0], vec![3.0, 4.0]];
        let state = CechDescentState::build(input.clone());
        assert_eq!(state.level0_models, input);
    }

    // 8. k3_invariant is always non-negative
    #[test]
    fn k3_invariant_nonneg() {
        let models = vec![vec![5.0f32, -3.0], vec![-2.0, 7.0], vec![1.0, 1.0], vec![0.0, 0.0]];
        let state = CechDescentState::build(models);
        assert!(state.k3_invariant >= 0.0);
    }

    // 9. Default matches new()
    #[test]
    fn default_is_empty_state() {
        let d = CechDescentState::default();
        assert!(d.level0_models.is_empty());
        assert_eq!(d.k3_invariant, 0.0);
        assert!(d.level3.is_empty());
    }

    // 10. Single model: all levels empty
    #[test]
    fn single_model_all_levels_empty() {
        let state = CechDescentState::build(vec![vec![1.0f32, 2.0]]);
        assert!(state.level1.is_empty());
        assert!(state.level2.is_empty());
        assert!(state.level3.is_empty());
        assert_eq!(state.k3_invariant, 0.0);
    }
}
