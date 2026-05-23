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
}
