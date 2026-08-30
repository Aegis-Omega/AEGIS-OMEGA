//! Obstruction-Aware Routing — Divergence Detection
//! EPISTEMIC TIER: T2 (code) — deterministic divergence classification
//!
//! EPISTEMIC NOTE: H¹/H²/H³ labels are engineering divergence severity classes.
//! The mathematical correspondence to group cohomology is T3 (research conjecture,
//! not empirically validated). This code detects divergence between model outputs.
//! No T0–T2 authority may be grounded in the mathematical correspondence.

use serde::Serialize;

#[derive(Serialize, Debug, Clone, PartialEq)]
pub enum ObstructionClass {
    /// H¹: Multiple non-equivalent outputs from the same input.
    EnhancementDivergence,
    /// H²: Local filter/stratum data is incompatible between models.
    LocalizationIncompatibility,
    /// H³: No canonical merge exists between divergent model outputs.
    NoGlobalComparison,
    /// No obstruction detected.
    None,
}

#[derive(Serialize, Debug, Clone)]
pub struct ObstructionReport {
    pub step: u64,
    pub obstruction_class: ObstructionClass,
    pub divergence_score: f32,
    pub model_count: usize,
    pub superposition_required: bool,
}

pub struct MCMObstructionMonitor {
    pub h1_threshold: f32,
    pub h2_threshold: f32,
    pub h3_threshold: f32,
    pub step: u64,
}

impl MCMObstructionMonitor {
    pub fn new(h1_threshold: f32, h2_threshold: f32, h3_threshold: f32) -> Self {
        Self { h1_threshold, h2_threshold, h3_threshold, step: 0 }
    }

    /// Compute mean pairwise L2 divergence between model output vectors.
    pub fn pairwise_divergence(outputs: &[Vec<f32>]) -> f32 {
        if outputs.len() < 2 { return 0.0; }
        let mut total = 0.0f32;
        let mut count = 0u32;
        for i in 0..outputs.len() {
            for j in (i + 1)..outputs.len() {
                let diff: f32 = outputs[i].iter().zip(outputs[j].iter())
                    .map(|(&a, &b)| (a - b).powi(2))
                    .sum::<f32>()
                    .sqrt();
                total += diff;
                count += 1;
            }
        }
        if count == 0 { 0.0 } else { total / count as f32 }
    }

    /// Assess obstruction class from multiple model outputs.
    pub fn assess(&mut self, model_outputs: &[Vec<f32>]) -> ObstructionReport {
        self.step += 1;
        let divergence_score = Self::pairwise_divergence(model_outputs);

        let obstruction_class = if divergence_score >= self.h3_threshold {
            ObstructionClass::NoGlobalComparison
        } else if divergence_score >= self.h2_threshold {
            ObstructionClass::LocalizationIncompatibility
        } else if divergence_score >= self.h1_threshold {
            ObstructionClass::EnhancementDivergence
        } else {
            ObstructionClass::None
        };

        let superposition_required = obstruction_class != ObstructionClass::None;

        ObstructionReport {
            step: self.step,
            obstruction_class,
            divergence_score,
            model_count: model_outputs.len(),
            superposition_required,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn identical_outputs_no_obstruction() {
        let mut mon = MCMObstructionMonitor::new(0.1, 0.5, 1.0);
        let outputs = vec![vec![1.0, 2.0], vec![1.0, 2.0]];
        let report = mon.assess(&outputs);
        assert_eq!(report.obstruction_class, ObstructionClass::None);
        assert!(!report.superposition_required);
    }

    #[test]
    fn large_divergence_is_h3() {
        let mut mon = MCMObstructionMonitor::new(0.1, 0.5, 1.0);
        let outputs = vec![vec![10.0, 0.0], vec![0.0, 10.0]];
        let report = mon.assess(&outputs);
        assert_eq!(report.obstruction_class, ObstructionClass::NoGlobalComparison);
        assert!(report.superposition_required);
    }

    #[test]
    fn single_model_zero_divergence() {
        let mut mon = MCMObstructionMonitor::new(0.1, 0.5, 1.0);
        let report = mon.assess(&[vec![1.0, 2.0]]);
        assert_eq!(report.divergence_score, 0.0);
        assert_eq!(report.obstruction_class, ObstructionClass::None);
    }

    // 4. Moderate divergence classified as H1 (EnhancementDivergence)
    #[test]
    fn moderate_divergence_is_h1() {
        let mut mon = MCMObstructionMonitor::new(0.1, 0.5, 1.0);
        // divergence ≈ 0.2 → in [h1=0.1, h2=0.5)
        let outputs = vec![vec![0.0f32], vec![0.2]];
        let report = mon.assess(&outputs);
        assert_eq!(report.obstruction_class, ObstructionClass::EnhancementDivergence);
        assert!(report.superposition_required);
    }

    // 5. Divergence in [h2, h3) classified as H2 (LocalizationIncompatibility)
    #[test]
    fn mid_divergence_is_h2() {
        let mut mon = MCMObstructionMonitor::new(0.1, 0.5, 1.0);
        // divergence ≈ 0.7 → in [h2=0.5, h3=1.0)
        let outputs = vec![vec![0.0f32], vec![0.7]];
        let report = mon.assess(&outputs);
        assert_eq!(report.obstruction_class, ObstructionClass::LocalizationIncompatibility);
    }

    // 6. Step counter increments on each assess call
    #[test]
    fn step_counter_increments() {
        let mut mon = MCMObstructionMonitor::new(0.1, 0.5, 1.0);
        assert_eq!(mon.step, 0);
        mon.assess(&[vec![1.0f32]]);
        assert_eq!(mon.step, 1);
        mon.assess(&[vec![1.0f32]]);
        assert_eq!(mon.step, 2);
    }

    // 7. pairwise_divergence on empty outputs returns 0
    #[test]
    fn pairwise_divergence_empty_returns_zero() {
        assert_eq!(MCMObstructionMonitor::pairwise_divergence(&[]), 0.0);
    }

    // 8. model_count in report matches input length
    #[test]
    fn model_count_matches_input() {
        let mut mon = MCMObstructionMonitor::new(0.1, 0.5, 1.0);
        let report = mon.assess(&[vec![1.0f32], vec![2.0], vec![3.0]]);
        assert_eq!(report.model_count, 3);
    }

    // 9. superposition_required is false when class is None
    #[test]
    fn superposition_not_required_for_none_class() {
        let mut mon = MCMObstructionMonitor::new(0.1, 0.5, 1.0);
        let report = mon.assess(&[vec![1.0f32], vec![1.0]]);
        assert_eq!(report.obstruction_class, ObstructionClass::None);
        assert!(!report.superposition_required);
    }

    // 10. Three-way pairwise divergence averages all pairs
    #[test]
    fn three_outputs_pairwise_average() {
        // outputs: [0], [1], [2] → pairs: d(0,1)=1, d(0,2)=2, d(1,2)=1 → avg=4/3
        let outputs = vec![vec![0.0f32], vec![1.0], vec![2.0]];
        let d = MCMObstructionMonitor::pairwise_divergence(&outputs);
        assert!((d - 4.0f32 / 3.0).abs() < 1e-5);
    }
}
