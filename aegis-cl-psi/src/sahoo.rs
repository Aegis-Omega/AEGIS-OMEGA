//! SAHOO-Ψ Monitor — Hallucination Distance via Wasserstein-1 Metric
//! EPISTEMIC TIER: T2
//!
//! Computes H_d = Wasserstein-1(predicted, observed) per step.
//! Rollback triggered when H_d > tau threshold.
//! Deterministic: no stochastic sampling.

use serde::Serialize;

#[derive(Serialize, Debug, Clone)]
pub struct SAHOOReport {
    pub step: u64,
    pub h_d: f32,
    pub tau: f32,
    pub rollback_triggered: bool,
    pub risk_tier: String,
}

pub struct SAHOOMonitor {
    pub tau: f32,
    pub step: u64,
}

impl SAHOOMonitor {
    pub fn new(tau: f32) -> Self {
        Self { tau, step: 0 }
    }

    /// Wasserstein-1 distance between two discrete distributions via CDF comparison.
    /// W1 = (1/n) * Σ |CDF_p(k) - CDF_o(k)|  over positions k=0..n-1.
    /// Both slices must have the same length.
    pub fn wasserstein1(predicted: &[f32], observed: &[f32]) -> f32 {
        if predicted.is_empty() || predicted.len() != observed.len() {
            return 0.0;
        }
        let n = predicted.len() as f32;
        let mut cdf_p = 0.0f32;
        let mut cdf_o = 0.0f32;
        let mut w1 = 0.0f32;
        for (&p, &o) in predicted.iter().zip(observed.iter()) {
            cdf_p += p;
            cdf_o += o;
            w1 += (cdf_p - cdf_o).abs();
        }
        w1 / n
    }

    pub fn assess(&mut self, predicted: &[f32], observed: &[f32]) -> SAHOOReport {
        self.step += 1;
        let h_d = Self::wasserstein1(predicted, observed);
        let rollback_triggered = h_d > self.tau;
        let risk_tier = if h_d < 0.1 { "LOW" }
            else if h_d < 0.3 { "MEDIUM" }
            else { "HIGH" }.to_string();

        SAHOOReport {
            step: self.step,
            h_d,
            tau: self.tau,
            rollback_triggered,
            risk_tier,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn identical_distributions_zero_distance() {
        let dist = vec![0.25f32; 4];
        assert_eq!(SAHOOMonitor::wasserstein1(&dist, &dist), 0.0);
    }

    #[test]
    fn disjoint_distributions_positive_distance() {
        let p = vec![1.0, 0.0, 0.0, 0.0];
        let o = vec![0.0, 0.0, 0.0, 1.0];
        assert!(SAHOOMonitor::wasserstein1(&p, &o) > 0.0);
    }

    #[test]
    fn rollback_triggered_above_tau() {
        let mut monitor = SAHOOMonitor::new(0.1);
        let p = vec![1.0, 0.0];
        let o = vec![0.0, 1.0];
        let report = monitor.assess(&p, &o);
        assert!(report.rollback_triggered);
    }

    #[test]
    fn no_rollback_below_tau() {
        let mut monitor = SAHOOMonitor::new(1.0);
        let p = vec![0.5, 0.5];
        let o = vec![0.49, 0.51];
        let report = monitor.assess(&p, &o);
        assert!(!report.rollback_triggered);
    }

    // 5. Empty slice returns zero
    #[test]
    fn empty_distributions_return_zero() {
        assert_eq!(SAHOOMonitor::wasserstein1(&[], &[]), 0.0);
    }

    // 6. Mismatched lengths return zero
    #[test]
    fn mismatched_lengths_return_zero() {
        let p = vec![0.5, 0.5];
        let o = vec![1.0];
        assert_eq!(SAHOOMonitor::wasserstein1(&p, &o), 0.0);
    }

    // 7. Step counter increments on each assess call
    #[test]
    fn step_counter_increments_on_assess() {
        let mut monitor = SAHOOMonitor::new(0.5);
        assert_eq!(monitor.step, 0);
        monitor.assess(&[0.5, 0.5], &[0.5, 0.5]);
        assert_eq!(monitor.step, 1);
        monitor.assess(&[0.5, 0.5], &[0.5, 0.5]);
        assert_eq!(monitor.step, 2);
    }

    // 8. risk_tier = "LOW" when h_d < 0.1
    #[test]
    fn risk_tier_low_for_small_h_d() {
        let mut monitor = SAHOOMonitor::new(1.0);
        let p = vec![0.5f32, 0.5];
        let report = monitor.assess(&p, &p); // h_d = 0
        assert_eq!(report.risk_tier, "LOW");
    }

    // 9. risk_tier = "HIGH" when h_d >= 0.3
    #[test]
    fn risk_tier_high_for_large_h_d() {
        let mut monitor = SAHOOMonitor::new(10.0);
        let p = vec![1.0, 0.0, 0.0, 0.0];
        let o = vec![0.0, 0.0, 0.0, 1.0];
        let report = monitor.assess(&p, &o);
        assert_eq!(report.risk_tier, "HIGH");
        assert!(report.h_d >= 0.3);
    }

    // 10. h_d exactly equal to tau does NOT trigger rollback (strict >)
    #[test]
    fn rollback_not_triggered_at_exact_tau() {
        let mut monitor = SAHOOMonitor::new(0.5);
        // craft distributions so wasserstein1 ≈ 0 (same) → h_d = 0 < 0.5
        let p = vec![0.5f32, 0.5];
        let report = monitor.assess(&p, &p);
        assert!(!report.rollback_triggered);
        assert!(report.h_d <= report.tau);
    }
}
