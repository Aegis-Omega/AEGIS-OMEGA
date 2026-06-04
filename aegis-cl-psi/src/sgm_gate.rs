//! SGM-Ψ Gate — Sparse Gating Mechanism
//! EPISTEMIC TIER: T2
//!
//! Routes activations based on attention entropy threshold.
//! Outputs a sparse routing mask for LUT-KAN pathway selection.
//! Dense fallback when entropy ≤ threshold (all paths active).
//!
//! `hoeffding_lcb` and `SgmGateAcceptanceEstimator` implement Hoeffding LCB
//! confidence bounds for gate acceptance-rate estimation (From Intent to Execution,
//! SGM Hoeffding LCB bounds, T2). Statistical bounds only — no hash inputs, f64 permitted.

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

/// Hoeffding lower confidence bound for a Bernoulli acceptance rate.
///
/// LCB = max(0, p̂ − √(ln(1/δ) / 2n))  where δ = 1 − confidence.
/// Returns 0.0 when trials == 0 (no evidence → worst-case bound).
pub fn hoeffding_lcb(successes: u64, trials: u64, confidence: f64) -> f64 {
    if trials == 0 { return 0.0; }
    let p_hat = successes as f64 / trials as f64;
    let delta = 1.0 - confidence;
    let margin = ((1.0_f64 / delta).ln() / (2.0 * trials as f64)).sqrt();
    (p_hat - margin).max(0.0)
}

/// Tracks observed gate pass/fail counts and tests whether the Hoeffding LCB
/// on acceptance rate statistically exceeds `min_rate` at `confidence` level.
pub struct SgmGateAcceptanceEstimator {
    pub min_rate: f64,
    pub confidence: f64,
    successes: u64,
    trials: u64,
}

impl SgmGateAcceptanceEstimator {
    pub fn new(min_rate: f64, confidence: f64) -> Self {
        Self { min_rate, confidence, successes: 0, trials: 0 }
    }

    pub fn record(&mut self, passed: bool) {
        self.trials += 1;
        if passed { self.successes += 1; }
    }

    /// True when the Hoeffding LCB on acceptance rate exceeds `min_rate`.
    pub fn is_acceptable(&self) -> bool {
        hoeffding_lcb(self.successes, self.trials, self.confidence) > self.min_rate
    }

    pub fn trials(&self) -> u64 { self.trials }
    pub fn successes(&self) -> u64 { self.successes }
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

    // ── Hoeffding LCB viability ring ──────────────────────────────────────────

    // 1. Zero trials → worst-case bound 0.0
    #[test]
    fn hoeffding_lcb_zero_trials_returns_zero() {
        assert_eq!(hoeffding_lcb(0, 0, 0.95), 0.0);
    }

    // 2. All successes, large n → LCB close to 1.0 (within Hoeffding margin)
    #[test]
    fn hoeffding_lcb_all_successes_large_n() {
        let lcb = hoeffding_lcb(10_000, 10_000, 0.95);
        assert!(lcb > 0.98, "LCB={lcb}");
        assert!(lcb <= 1.0);
    }

    // 3. No successes, large n → LCB clamped to 0.0
    #[test]
    fn hoeffding_lcb_no_successes_is_zero() {
        let lcb = hoeffding_lcb(0, 10_000, 0.95);
        assert_eq!(lcb, 0.0);
    }

    // 4. LCB is always ≤ empirical rate p̂
    #[test]
    fn hoeffding_lcb_at_most_empirical_rate() {
        let p_hat = 700.0 / 1000.0;
        let lcb = hoeffding_lcb(700, 1000, 0.95);
        assert!(lcb <= p_hat, "LCB={lcb} must be ≤ p̂={p_hat}");
    }

    // 5. Higher confidence → wider margin → lower or equal LCB
    #[test]
    fn hoeffding_lcb_decreases_with_confidence() {
        let lcb_90 = hoeffding_lcb(800, 1000, 0.90);
        let lcb_99 = hoeffding_lcb(800, 1000, 0.99);
        assert!(lcb_99 <= lcb_90, "more confidence → wider margin → lcb_99={lcb_99} ≤ lcb_90={lcb_90}");
    }

    // 6. More trials → LCB tightens toward p̂
    #[test]
    fn hoeffding_lcb_tightens_with_more_trials() {
        // 80% pass rate at different sample sizes
        let lcb_small = hoeffding_lcb(80, 100, 0.95);
        let lcb_large = hoeffding_lcb(8000, 10_000, 0.95);
        assert!(lcb_large > lcb_small, "larger n → tighter LCB: {lcb_large} > {lcb_small}");
    }

    // 7. Estimator: records update counts correctly
    #[test]
    fn estimator_record_updates_counts() {
        let mut est = SgmGateAcceptanceEstimator::new(0.5, 0.95);
        est.record(true);
        est.record(false);
        est.record(true);
        assert_eq!(est.trials(), 3);
        assert_eq!(est.successes(), 2);
    }

    // 8. Estimator: zero trials → is_acceptable returns false
    #[test]
    fn estimator_rejects_with_no_data() {
        let est = SgmGateAcceptanceEstimator::new(0.5, 0.95);
        assert!(!est.is_acceptable());
    }

    // 9. Estimator: low pass rate → LCB below min_rate → not acceptable
    #[test]
    fn estimator_rejects_low_pass_rate() {
        let mut est = SgmGateAcceptanceEstimator::new(0.8, 0.95);
        for _ in 0..200 { est.record(true); }
        for _ in 0..800 { est.record(false); }
        assert!(!est.is_acceptable(), "20% rate must not pass 0.8 threshold");
    }

    // 10. Estimator: high pass rate → LCB above min_rate → acceptable
    #[test]
    fn estimator_accepts_after_enough_passes() {
        let mut est = SgmGateAcceptanceEstimator::new(0.5, 0.95);
        for _ in 0..9_900 { est.record(true); }
        for _ in 0..100 { est.record(false); }
        assert!(est.is_acceptable(), "99% pass rate with 10_000 trials must exceed 0.5 threshold");
    }

    // 11. Determinism ×3: same inputs yield identical LCB
    #[test]
    fn hoeffding_lcb_determinism_triple() {
        let r1 = hoeffding_lcb(314, 500, 0.95);
        let r2 = hoeffding_lcb(314, 500, 0.95);
        let r3 = hoeffding_lcb(314, 500, 0.95);
        assert_eq!(r1, r2);
        assert_eq!(r2, r3);
    }
}
