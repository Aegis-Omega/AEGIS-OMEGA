//! Gate 241 — Adaptive Threshold Engine: dynamic constitutional alert thresholds (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Prevents alert fatigue by tracking a rolling baseline for entropy balance and
//! coherent_node_count. Thresholds tighten when the system is healthy (reducing
//! tolerance for drops) and relax when sustained degraded (preventing false alarms
//! from already-degraded state).
//!
//! ThresholdProfile — computed from N most-recent HealthSnapshots:
//!   entropy_threshold   = max(ADAPTIVE_EVENT_COST, baseline_entropy * HIGH_WATER_FACTOR)
//!   coherence_threshold = max(1, baseline_coherence_fraction * node_count)
//!   HIGH_WATER_FACTOR   = 618_034 / 1_000_000  (1/φ integer approximation)
//!
//! EvaluationResult:
//!   EntropyAlert   — entropy_balance below adaptive threshold
//!   CoherenceAlert — coherent_node_count below adaptive threshold
//!   BothAlert      — both below threshold
//!   Clear          — all metrics above adaptive thresholds
//!
//! threshold_hash = SHA-256(prev_hash ‖ result_byte ‖ epoch_be8 ‖ entropy_threshold_be8)

use sha2::{Sha256, Digest};
use crate::swarm_health::HealthSnapshot;
use crate::entropy_budget::ADAPTIVE_EVENT_COST;

// ─── Constants ───────────────────────────────────────────────────────────────

/// Integer 1/φ: 618034 / 1_000_000 — applied as numerator/denominator pair.
pub const PHI_NUMERATOR:   u64 = 618_034;
pub const PHI_DENOMINATOR: u64 = 1_000_000;

pub const DEFAULT_WINDOW: usize = 10;

// ─── Threshold profile ───────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ThresholdProfile {
    /// Adaptive entropy lower-bound: max(ADAPTIVE_EVENT_COST, baseline * φ)
    pub entropy_threshold:   u64,
    /// Adaptive coherence lower-bound (node count): max(1, baseline_fraction * node_count)
    pub coherence_threshold: usize,
    /// Number of snapshots used to compute this profile.
    pub sample_count:        usize,
}

impl ThresholdProfile {
    /// Compute from a window of snapshots. Returns default minimums on empty window.
    pub fn compute(window: &[HealthSnapshot]) -> Self {
        if window.is_empty() {
            return Self {
                entropy_threshold:   ADAPTIVE_EVENT_COST,
                coherence_threshold: 1,
                sample_count:        0,
            };
        }

        // Baseline entropy = integer average across window
        let total_entropy: u64 = window.iter().map(|s| s.entropy_balance).sum();
        let baseline_entropy = total_entropy / window.len() as u64;

        // entropy_threshold = max(ADAPTIVE_EVENT_COST, baseline * PHI_NUM / PHI_DEN)
        let phi_entropy = baseline_entropy * PHI_NUMERATOR / PHI_DENOMINATOR;
        let entropy_threshold = phi_entropy.max(ADAPTIVE_EVENT_COST);

        // Baseline coherence fraction as integer: sum(coherent) / sum(node_count)
        let total_coherent: usize = window.iter().map(|s| s.coherent_node_count).sum();
        let total_nodes:    usize = window.iter().map(|s| s.node_count).sum();
        let latest_nodes = window.last().map(|s| s.node_count).unwrap_or(1);

        let coherence_threshold = if total_nodes == 0 {
            1
        } else {
            // coherence_fraction_numerator / total_nodes applied to latest_nodes
            // = (total_coherent * PHI_NUM / PHI_DEN * latest_nodes) / total_nodes
            // Use integer arithmetic, avoid overflow via ordering of operations
            let frac_num = total_coherent * PHI_NUMERATOR as usize;
            let frac_den = total_nodes * PHI_DENOMINATOR as usize;
            let threshold = (frac_num / frac_den).max(1);
            // scale to latest node count
            threshold.min(latest_nodes).max(1)
        };

        Self {
            entropy_threshold,
            coherence_threshold,
            sample_count: window.len(),
        }
    }
}

// ─── Evaluation result ───────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EvaluationResult {
    Clear         = 0,
    EntropyAlert  = 1,
    CoherenceAlert= 2,
    BothAlert     = 3,
}

impl EvaluationResult {
    pub fn as_u8(self) -> u8 { self as u8 }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Clear          => "clear",
            Self::EntropyAlert   => "entropy_alert",
            Self::CoherenceAlert => "coherence_alert",
            Self::BothAlert      => "both_alert",
        }
    }

    pub fn is_clear(self) -> bool { self == EvaluationResult::Clear }
    pub fn has_entropy_alert(self) -> bool {
        matches!(self, Self::EntropyAlert | Self::BothAlert)
    }
    pub fn has_coherence_alert(self) -> bool {
        matches!(self, Self::CoherenceAlert | Self::BothAlert)
    }
}

// ─── Threshold evaluation ────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct ThresholdEvaluation {
    pub epoch:              u64,
    pub profile:            ThresholdProfile,
    pub result:             EvaluationResult,
    pub entropy_balance:    u64,
    pub coherent_count:     usize,
    pub evaluation_hash:    [u8; 32],
    pub prev_hash:          [u8; 32],
}

pub const THRESHOLD_GENESIS_HASH: [u8; 32] = [0u8; 32];

/// Evaluate a snapshot against an adaptive threshold profile.
pub fn evaluate_snapshot(
    snap:      &HealthSnapshot,
    profile:   &ThresholdProfile,
    prev_hash: &[u8; 32],
) -> ThresholdEvaluation {
    let entropy_below   = snap.entropy_balance   < profile.entropy_threshold;
    let coherence_below = snap.coherent_node_count < profile.coherence_threshold;

    let result = match (entropy_below, coherence_below) {
        (false, false) => EvaluationResult::Clear,
        (true,  false) => EvaluationResult::EntropyAlert,
        (false, true)  => EvaluationResult::CoherenceAlert,
        (true,  true)  => EvaluationResult::BothAlert,
    };

    let evaluation_hash = compute_eval_hash(
        prev_hash, result, snap.epoch, profile.entropy_threshold,
    );

    ThresholdEvaluation {
        epoch:           snap.epoch,
        profile:         profile.clone(),
        result,
        entropy_balance: snap.entropy_balance,
        coherent_count:  snap.coherent_node_count,
        evaluation_hash,
        prev_hash:       *prev_hash,
    }
}

fn compute_eval_hash(
    prev:              &[u8; 32],
    result:            EvaluationResult,
    epoch:             u64,
    entropy_threshold: u64,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update([result.as_u8()]);
    h.update(epoch.to_be_bytes());
    h.update(entropy_threshold.to_be_bytes());
    h.finalize().into()
}

// ─── Evaluation history ──────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct EvaluationHistory {
    evaluations: Vec<ThresholdEvaluation>,
    window_size: usize,
}

#[derive(Debug)]
pub struct ThresholdError(pub &'static str);

impl EvaluationHistory {
    pub fn new(window_size: usize) -> Self {
        Self { evaluations: Vec::new(), window_size }
    }

    pub fn new_default() -> Self { Self::new(DEFAULT_WINDOW) }

    pub fn len(&self) -> usize { self.evaluations.len() }
    pub fn is_empty(&self) -> bool { self.evaluations.is_empty() }
    pub fn evaluations(&self) -> &[ThresholdEvaluation] { &self.evaluations }

    pub fn last_hash(&self) -> [u8; 32] {
        self.evaluations.last().map(|e| e.evaluation_hash).unwrap_or(THRESHOLD_GENESIS_HASH)
    }

    pub fn alert_count(&self) -> usize {
        self.evaluations.iter().filter(|e| !e.result.is_clear()).count()
    }

    /// Record a new snapshot, computing adaptive profile from the rolling window.
    /// Epoch must be strictly increasing.
    pub fn record(
        &mut self,
        snap:    &HealthSnapshot,
        history: &[HealthSnapshot],
    ) -> Result<&ThresholdEvaluation, ThresholdError> {
        if let Some(last) = self.evaluations.last() {
            if snap.epoch <= last.epoch {
                return Err(ThresholdError("epoch must be strictly greater"));
            }
        }
        let window_start = history.len().saturating_sub(self.window_size);
        let window = &history[window_start..];
        let profile = ThresholdProfile::compute(window);
        let prev_hash = self.last_hash();
        let eval = evaluate_snapshot(snap, &profile, &prev_hash);
        self.evaluations.push(eval);
        Ok(self.evaluations.last().unwrap())
    }

    /// Verify hash chain integrity.
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = THRESHOLD_GENESIS_HASH;
        for (i, eval) in self.evaluations.iter().enumerate() {
            if eval.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_eval_hash(
                &prev, eval.result, eval.epoch, eval.profile.entropy_threshold,
            );
            if expected != eval.evaluation_hash {
                return (false, Some(i));
            }
            prev = eval.evaluation_hash;
        }
        (true, None)
    }
}

impl Default for EvaluationHistory {
    fn default() -> Self { Self::new_default() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn snap(epoch: u64, entropy: u64, coherent: usize, total: usize) -> HealthSnapshot {
        HealthSnapshot {
            epoch,
            node_count: total,
            coherent_node_count: coherent,
            continuously_coherent_count: coherent,
            quorum_reached: coherent * PHI_DENOMINATOR as usize >= total * PHI_NUMERATOR as usize,
            continuous_quorum: true,
            mutation_authority_active: true,
            entropy_balance: entropy,
            drift_class_int: 0,
            is_continuously_coherent: true,
        }
    }

    // ── ThresholdProfile ──────────────────────────────────────────────────────

    #[test]
    fn empty_window_gives_minimums() {
        let p = ThresholdProfile::compute(&[]);
        assert_eq!(p.entropy_threshold, ADAPTIVE_EVENT_COST);
        assert_eq!(p.coherence_threshold, 1);
        assert_eq!(p.sample_count, 0);
    }

    #[test]
    fn entropy_threshold_at_least_adaptive_event_cost() {
        // Very low baseline — threshold must be clamped to ADAPTIVE_EVENT_COST
        let window = vec![snap(1, 1, 5, 5), snap(2, 1, 5, 5)];
        let p = ThresholdProfile::compute(&window);
        assert!(p.entropy_threshold >= ADAPTIVE_EVENT_COST);
    }

    #[test]
    fn entropy_threshold_scales_with_baseline() {
        // baseline = 1000 → threshold ≈ 618
        let window: Vec<_> = (1..=5).map(|i| snap(i, 1000, 5, 5)).collect();
        let p = ThresholdProfile::compute(&window);
        // 1000 * 618_034 / 1_000_000 = 618
        assert_eq!(p.entropy_threshold, 618);
    }

    #[test]
    fn coherence_threshold_clamped_to_node_count() {
        // All nodes always coherent → threshold ≤ node_count
        let window: Vec<_> = (1..=5).map(|i| snap(i, 1000, 5, 5)).collect();
        let p = ThresholdProfile::compute(&window);
        assert!(p.coherence_threshold <= 5);
        assert!(p.coherence_threshold >= 1);
    }

    #[test]
    fn sample_count_matches_window() {
        let window: Vec<_> = (1..=7).map(|i| snap(i, 500, 5, 5)).collect();
        let p = ThresholdProfile::compute(&window);
        assert_eq!(p.sample_count, 7);
    }

    // ── EvaluationResult ──────────────────────────────────────────────────────

    #[test]
    fn clear_is_clear() {
        assert!(EvaluationResult::Clear.is_clear());
        assert!(!EvaluationResult::Clear.has_entropy_alert());
        assert!(!EvaluationResult::Clear.has_coherence_alert());
    }

    #[test]
    fn entropy_alert_flags() {
        assert!(EvaluationResult::EntropyAlert.has_entropy_alert());
        assert!(!EvaluationResult::EntropyAlert.has_coherence_alert());
    }

    #[test]
    fn coherence_alert_flags() {
        assert!(EvaluationResult::CoherenceAlert.has_coherence_alert());
        assert!(!EvaluationResult::CoherenceAlert.has_entropy_alert());
    }

    #[test]
    fn both_alert_flags_both() {
        assert!(EvaluationResult::BothAlert.has_entropy_alert());
        assert!(EvaluationResult::BothAlert.has_coherence_alert());
    }

    #[test]
    fn result_as_u8() {
        assert_eq!(EvaluationResult::Clear.as_u8(), 0);
        assert_eq!(EvaluationResult::EntropyAlert.as_u8(), 1);
        assert_eq!(EvaluationResult::CoherenceAlert.as_u8(), 2);
        assert_eq!(EvaluationResult::BothAlert.as_u8(), 3);
    }

    // ── evaluate_snapshot ─────────────────────────────────────────────────────

    #[test]
    fn above_threshold_gives_clear() {
        let profile = ThresholdProfile { entropy_threshold: 100, coherence_threshold: 3, sample_count: 5 };
        let s = snap(1, 500, 5, 5);
        let eval = evaluate_snapshot(&s, &profile, &THRESHOLD_GENESIS_HASH);
        assert_eq!(eval.result, EvaluationResult::Clear);
    }

    #[test]
    fn below_entropy_gives_entropy_alert() {
        let profile = ThresholdProfile { entropy_threshold: 500, coherence_threshold: 1, sample_count: 5 };
        let s = snap(1, 100, 5, 5);
        let eval = evaluate_snapshot(&s, &profile, &THRESHOLD_GENESIS_HASH);
        assert_eq!(eval.result, EvaluationResult::EntropyAlert);
    }

    #[test]
    fn below_coherence_gives_coherence_alert() {
        let profile = ThresholdProfile { entropy_threshold: 10, coherence_threshold: 4, sample_count: 5 };
        let s = snap(1, 1000, 2, 5);
        let eval = evaluate_snapshot(&s, &profile, &THRESHOLD_GENESIS_HASH);
        assert_eq!(eval.result, EvaluationResult::CoherenceAlert);
    }

    #[test]
    fn both_below_gives_both_alert() {
        let profile = ThresholdProfile { entropy_threshold: 500, coherence_threshold: 4, sample_count: 5 };
        let s = snap(1, 100, 2, 5);
        let eval = evaluate_snapshot(&s, &profile, &THRESHOLD_GENESIS_HASH);
        assert_eq!(eval.result, EvaluationResult::BothAlert);
    }

    #[test]
    fn evaluation_hash_nonzero() {
        let profile = ThresholdProfile { entropy_threshold: 100, coherence_threshold: 1, sample_count: 1 };
        let eval = evaluate_snapshot(&snap(1, 500, 5, 5), &profile, &THRESHOLD_GENESIS_HASH);
        assert_ne!(eval.evaluation_hash, [0u8; 32]);
    }

    #[test]
    fn evaluation_hash_deterministic() {
        let profile = ThresholdProfile { entropy_threshold: 618, coherence_threshold: 3, sample_count: 5 };
        let s = snap(7, 700, 4, 5);
        let e1 = evaluate_snapshot(&s, &profile, &THRESHOLD_GENESIS_HASH);
        let e2 = evaluate_snapshot(&s, &profile, &THRESHOLD_GENESIS_HASH);
        let e3 = evaluate_snapshot(&s, &profile, &THRESHOLD_GENESIS_HASH);
        assert_eq!(e1.evaluation_hash, e2.evaluation_hash);
        assert_eq!(e2.evaluation_hash, e3.evaluation_hash);
    }

    // ── EvaluationHistory ─────────────────────────────────────────────────────

    #[test]
    fn new_history_empty() {
        let h = EvaluationHistory::new_default();
        assert!(h.is_empty());
        assert_eq!(h.alert_count(), 0);
    }

    #[test]
    fn duplicate_epoch_is_err() {
        let mut h = EvaluationHistory::new_default();
        let history: Vec<HealthSnapshot> = (1..=5).map(|i| snap(i, 1000, 5, 5)).collect();
        h.record(&snap(5, 800, 5, 5), &history).unwrap();
        assert!(h.record(&snap(5, 800, 5, 5), &history).is_err());
    }

    #[test]
    fn alert_count_tracks() {
        let mut h = EvaluationHistory::new_default();
        // History with high entropy baseline → threshold ≈ 618
        let history: Vec<HealthSnapshot> = (1..=5).map(|i| snap(i, 1000, 5, 5)).collect();
        // Snap with entropy well above threshold
        h.record(&snap(6, 900, 5, 5), &history).unwrap();
        // Snap with entropy below threshold (< 618)
        h.record(&snap(7, 100, 5, 5), &history).unwrap();
        assert_eq!(h.alert_count(), 1);
    }

    #[test]
    fn verify_chain_clean() {
        let mut h = EvaluationHistory::new_default();
        let history: Vec<HealthSnapshot> = (1..=5).map(|i| snap(i, 1000, 5, 5)).collect();
        for epoch in 6u64..=10 {
            h.record(&snap(epoch, 1000, 5, 5), &history).unwrap();
        }
        let (valid, broken) = h.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }
}
