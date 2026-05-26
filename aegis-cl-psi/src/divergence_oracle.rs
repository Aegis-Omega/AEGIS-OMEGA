//! Gate 238: Divergence Oracle — Deterministic constitutional divergence analysis (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Compares two SwarmHealthReports (before/after) and produces a DivergenceOracle
//! record describing the constitutional delta. Designed for audit surfaces and
//! rollback decision logic.
//!
//! DivergenceClass (ordered):
//!   Stable    — no verdict change, all invariants maintained
//!   Nominal   — minor metric drift (entropy↓ or coherent_count↓) but verdict unchanged
//!   Elevated  — verdict worsened to Warn (quorum held but partial incoherence)
//!   Critical  — verdict worsened to Fail (authority suspended or quorum lost)
//!   Terminal  — D4 drift detected (constitutional invalidity)
//!
//! oracle_hash = SHA-256(prev_hash ‖ class_byte ‖ epoch_be8 ‖ verdict_before ‖ verdict_after)

use sha2::{Sha256, Digest};
use crate::swarm_health::{SwarmHealthReport, HealthVerdict, HealthFailReason};

// ─── Divergence class ─────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum DivergenceClass {
    Stable   = 0,
    Nominal  = 1,
    Elevated = 2,
    Critical = 3,
    Terminal = 4,
}

impl DivergenceClass {
    pub fn as_u8(self) -> u8 { self as u8 }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Stable   => "Stable",
            Self::Nominal  => "Nominal",
            Self::Elevated => "Elevated",
            Self::Critical => "Critical",
            Self::Terminal => "Terminal",
        }
    }

    /// True iff the system can still make adaptive decisions (divergence < Critical).
    pub fn adaptive_permitted(self) -> bool { self < DivergenceClass::Critical }

    /// True iff rollback should be considered (divergence >= Elevated).
    pub fn rollback_recommended(self) -> bool { self >= DivergenceClass::Elevated }
}

// ─── Oracle record ────────────────────────────────────────────────────────

pub const ORACLE_GENESIS_HASH: [u8; 32] = [0u8; 32];

#[derive(Debug, Clone, PartialEq)]
pub struct DivergenceOracle {
    pub epoch:             u64,
    pub divergence_class:  DivergenceClass,
    pub verdict_before:    HealthVerdict,
    pub verdict_after:     HealthVerdict,
    pub entropy_delta:     i64,  // entropy_after - entropy_before (signed)
    pub coherent_delta:    i64,  // coherent_node_count delta (signed)
    pub primary_reason:    HealthFailReason,
    pub adaptive_permitted: bool,
    pub rollback_recommended: bool,
    /// SHA-256(prev_hash ‖ class_byte ‖ epoch_be8 ‖ verdict_before_byte ‖ verdict_after_byte)
    pub oracle_hash:       [u8; 32],
    pub prev_oracle_hash:  [u8; 32],
}

// ─── Oracle function ──────────────────────────────────────────────────────

/// Produce a DivergenceOracle from two health snapshots.
///
/// `before` and `after` are consecutive SwarmHealthReport records.
/// `prev_oracle_hash` is the hash of the previous oracle record (ORACLE_GENESIS_HASH if first).
pub fn compute_oracle(
    before: &SwarmHealthReport,
    after: &SwarmHealthReport,
    prev_oracle_hash: &[u8; 32],
) -> DivergenceOracle {
    let verdict_before = before.verdict;
    let verdict_after  = after.verdict;

    let entropy_delta  = after.entropy_balance as i64 - before.entropy_balance as i64;
    let coherent_delta = after.coherent_node_count as i64 - before.coherent_node_count as i64;

    // Classify divergence
    let divergence_class = if after.drift_class_int >= 4 {
        DivergenceClass::Terminal
    } else if verdict_after == HealthVerdict::Fail
           && before.verdict != HealthVerdict::Fail {
        DivergenceClass::Critical
    } else if verdict_after == HealthVerdict::Warn
           && verdict_before == HealthVerdict::Pass {
        DivergenceClass::Elevated
    } else if verdict_after == verdict_before
           && (entropy_delta < 0 || coherent_delta < 0) {
        DivergenceClass::Nominal
    } else {
        DivergenceClass::Stable
    };

    let oracle_hash = compute_oracle_hash(
        prev_oracle_hash,
        divergence_class,
        after.epoch,
        verdict_before,
        verdict_after,
    );

    DivergenceOracle {
        epoch: after.epoch,
        divergence_class,
        verdict_before,
        verdict_after,
        entropy_delta,
        coherent_delta,
        primary_reason: after.primary_fail_reason,
        adaptive_permitted: divergence_class.adaptive_permitted(),
        rollback_recommended: divergence_class.rollback_recommended(),
        oracle_hash,
        prev_oracle_hash: *prev_oracle_hash,
    }
}

// ─── Oracle history ───────────────────────────────────────────────────────

#[derive(Debug)]
pub struct OracleError(pub &'static str);

#[derive(Debug, Clone)]
pub struct OracleHistory {
    oracles: Vec<DivergenceOracle>,
}

impl OracleHistory {
    pub fn new() -> Self { Self { oracles: Vec::new() } }

    pub fn len(&self) -> usize { self.oracles.len() }
    pub fn is_empty(&self) -> bool { self.oracles.is_empty() }
    pub fn oracles(&self) -> &[DivergenceOracle] { &self.oracles }

    pub fn last_hash(&self) -> [u8; 32] {
        self.oracles.last().map(|o| o.oracle_hash).unwrap_or(ORACLE_GENESIS_HASH)
    }

    /// Current (most recent) divergence class (Stable if no oracles yet).
    pub fn current_class(&self) -> DivergenceClass {
        self.oracles.last().map(|o| o.divergence_class).unwrap_or(DivergenceClass::Stable)
    }

    /// Worst divergence class observed across all oracles.
    pub fn worst_class(&self) -> Option<DivergenceClass> {
        self.oracles.iter().map(|o| o.divergence_class).max()
    }

    /// Append an oracle for a before/after pair.
    pub fn record(
        &mut self,
        before: &SwarmHealthReport,
        after: &SwarmHealthReport,
    ) -> Result<&DivergenceOracle, OracleError> {
        if let Some(last) = self.oracles.last() {
            if after.epoch <= last.epoch {
                return Err(OracleError("epoch must be strictly greater than last oracle epoch"));
            }
        }
        let prev_hash = self.last_hash();
        let oracle = compute_oracle(before, after, &prev_hash);
        self.oracles.push(oracle);
        Ok(self.oracles.last().unwrap())
    }

    /// Verify full hash chain integrity.
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = ORACLE_GENESIS_HASH;
        for (i, oracle) in self.oracles.iter().enumerate() {
            if oracle.prev_oracle_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_oracle_hash(
                &prev,
                oracle.divergence_class,
                oracle.epoch,
                oracle.verdict_before,
                oracle.verdict_after,
            );
            if expected != oracle.oracle_hash {
                return (false, Some(i));
            }
            prev = oracle.oracle_hash;
        }
        (true, None)
    }
}

impl Default for OracleHistory {
    fn default() -> Self { Self::new() }
}

fn compute_oracle_hash(
    prev: &[u8; 32],
    class: DivergenceClass,
    epoch: u64,
    verdict_before: HealthVerdict,
    verdict_after: HealthVerdict,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update([class.as_u8()]);
    h.update(epoch.to_be_bytes());
    h.update([verdict_before.as_u8(), verdict_after.as_u8()]);
    h.finalize().into()
}

// ─── Tests ────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::swarm_health::{HealthSnapshot, HealthHistory};

    fn make_health(epoch: u64, verdict: HealthVerdict, drift: u8, entropy: u64, coherent: usize) -> SwarmHealthReport {
        // Build via HealthHistory to get proper hash chaining
        let snap = HealthSnapshot {
            epoch,
            node_count: 5,
            coherent_node_count: coherent,
            continuously_coherent_count: coherent,
            quorum_reached: verdict != HealthVerdict::Fail || drift < 2,
            continuous_quorum: verdict == HealthVerdict::Pass,
            mutation_authority_active: verdict != HealthVerdict::Fail || drift < 2,
            entropy_balance: entropy,
            drift_class_int: drift,
            is_continuously_coherent: verdict != HealthVerdict::Fail,
        };
        crate::swarm_health::assess_health(&snap, &crate::swarm_health::HEALTH_GENESIS_HASH)
    }

    fn pass_rep(epoch: u64) -> SwarmHealthReport {
        make_health(epoch, HealthVerdict::Pass, 0, 1000, 5)
    }

    fn warn_rep(epoch: u64) -> SwarmHealthReport {
        make_health(epoch, HealthVerdict::Warn, 0, 800, 4)
    }

    fn fail_rep(epoch: u64) -> SwarmHealthReport {
        make_health(epoch, HealthVerdict::Fail, 2, 500, 2)
    }

    fn terminal_rep(epoch: u64) -> SwarmHealthReport {
        make_health(epoch, HealthVerdict::Fail, 4, 200, 1)
    }

    // ── DivergenceClass ───────────────────────────────────────────────────

    #[test]
    fn class_ordering() {
        assert!(DivergenceClass::Stable < DivergenceClass::Nominal);
        assert!(DivergenceClass::Nominal < DivergenceClass::Elevated);
        assert!(DivergenceClass::Elevated < DivergenceClass::Critical);
        assert!(DivergenceClass::Critical < DivergenceClass::Terminal);
    }

    #[test]
    fn adaptive_permitted_below_critical() {
        assert!(DivergenceClass::Stable.adaptive_permitted());
        assert!(DivergenceClass::Nominal.adaptive_permitted());
        assert!(DivergenceClass::Elevated.adaptive_permitted());
        assert!(!DivergenceClass::Critical.adaptive_permitted());
        assert!(!DivergenceClass::Terminal.adaptive_permitted());
    }

    #[test]
    fn rollback_recommended_at_elevated() {
        assert!(!DivergenceClass::Stable.rollback_recommended());
        assert!(!DivergenceClass::Nominal.rollback_recommended());
        assert!(DivergenceClass::Elevated.rollback_recommended());
        assert!(DivergenceClass::Critical.rollback_recommended());
        assert!(DivergenceClass::Terminal.rollback_recommended());
    }

    #[test]
    fn class_as_str() {
        assert_eq!(DivergenceClass::Stable.as_str(), "Stable");
        assert_eq!(DivergenceClass::Terminal.as_str(), "Terminal");
    }

    // ── compute_oracle ────────────────────────────────────────────────────

    #[test]
    fn pass_to_pass_no_metric_change_is_stable() {
        let before = pass_rep(1);
        let mut after = pass_rep(2);
        after.entropy_balance = before.entropy_balance; // same entropy
        after.coherent_node_count = before.coherent_node_count;
        let oracle = compute_oracle(&before, &after, &ORACLE_GENESIS_HASH);
        assert_eq!(oracle.divergence_class, DivergenceClass::Stable);
    }

    #[test]
    fn pass_to_pass_with_entropy_drop_is_nominal() {
        let before = pass_rep(1);
        let after = make_health(2, HealthVerdict::Pass, 0, 900, 5); // entropy dropped 100
        let oracle = compute_oracle(&before, &after, &ORACLE_GENESIS_HASH);
        assert_eq!(oracle.divergence_class, DivergenceClass::Nominal);
        assert!(oracle.entropy_delta < 0);
    }

    #[test]
    fn pass_to_warn_is_elevated() {
        let before = pass_rep(1);
        let after = warn_rep(2);
        let oracle = compute_oracle(&before, &after, &ORACLE_GENESIS_HASH);
        assert_eq!(oracle.divergence_class, DivergenceClass::Elevated);
        assert!(oracle.rollback_recommended);
        assert!(oracle.adaptive_permitted);
    }

    #[test]
    fn pass_to_fail_is_critical() {
        let before = pass_rep(1);
        let after = fail_rep(2);
        let oracle = compute_oracle(&before, &after, &ORACLE_GENESIS_HASH);
        assert_eq!(oracle.divergence_class, DivergenceClass::Critical);
        assert!(!oracle.adaptive_permitted);
        assert!(oracle.rollback_recommended);
    }

    #[test]
    fn d4_drift_is_terminal() {
        let before = pass_rep(1);
        let after = terminal_rep(2);
        let oracle = compute_oracle(&before, &after, &ORACLE_GENESIS_HASH);
        assert_eq!(oracle.divergence_class, DivergenceClass::Terminal);
        assert!(!oracle.adaptive_permitted);
    }

    #[test]
    fn oracle_hash_nonzero() {
        let before = pass_rep(1);
        let after = warn_rep(2);
        let oracle = compute_oracle(&before, &after, &ORACLE_GENESIS_HASH);
        assert_ne!(oracle.oracle_hash, [0u8; 32]);
    }

    #[test]
    fn oracle_hash_deterministic() {
        let before = pass_rep(1);
        let after = fail_rep(2);
        let o1 = compute_oracle(&before, &after, &ORACLE_GENESIS_HASH);
        let o2 = compute_oracle(&before, &after, &ORACLE_GENESIS_HASH);
        let o3 = compute_oracle(&before, &after, &ORACLE_GENESIS_HASH);
        assert_eq!(o1.oracle_hash, o2.oracle_hash);
        assert_eq!(o2.oracle_hash, o3.oracle_hash);
    }

    #[test]
    fn different_epochs_different_hash() {
        let b1 = pass_rep(1);
        let a1 = fail_rep(2);
        let b2 = pass_rep(2);
        let a2 = fail_rep(3);
        let o1 = compute_oracle(&b1, &a1, &ORACLE_GENESIS_HASH);
        let o2 = compute_oracle(&b2, &a2, &ORACLE_GENESIS_HASH);
        assert_ne!(o1.oracle_hash, o2.oracle_hash);
    }

    #[test]
    fn verdict_fields_preserved() {
        let before = pass_rep(1);
        let after = fail_rep(2);
        let oracle = compute_oracle(&before, &after, &ORACLE_GENESIS_HASH);
        assert_eq!(oracle.verdict_before, HealthVerdict::Pass);
        assert_eq!(oracle.verdict_after, HealthVerdict::Fail);
    }

    // ── OracleHistory ─────────────────────────────────────────────────────

    #[test]
    fn new_history_stable_default() {
        let h = OracleHistory::new();
        assert_eq!(h.current_class(), DivergenceClass::Stable);
        assert!(h.worst_class().is_none());
    }

    #[test]
    fn record_grows_history() {
        let mut h = OracleHistory::new();
        h.record(&pass_rep(1), &warn_rep(2)).unwrap();
        h.record(&warn_rep(2), &fail_rep(3)).unwrap();
        assert_eq!(h.len(), 2);
    }

    #[test]
    fn hash_chain_links() {
        let mut h = OracleHistory::new();
        h.record(&pass_rep(1), &warn_rep(2)).unwrap();
        h.record(&warn_rep(2), &fail_rep(3)).unwrap();
        assert_eq!(h.oracles()[1].prev_oracle_hash, h.oracles()[0].oracle_hash);
    }

    #[test]
    fn duplicate_epoch_is_err() {
        let mut h = OracleHistory::new();
        h.record(&pass_rep(1), &warn_rep(2)).unwrap();
        assert!(h.record(&pass_rep(2), &warn_rep(2)).is_err());
    }

    #[test]
    fn verify_chain_clean() {
        let mut h = OracleHistory::new();
        let reps: Vec<SwarmHealthReport> = vec![
            pass_rep(1), warn_rep(2), fail_rep(3), warn_rep(4), pass_rep(5),
        ];
        for i in 0..reps.len() - 1 {
            h.record(&reps[i], &reps[i + 1]).unwrap();
        }
        let (valid, broken) = h.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    #[test]
    fn worst_class_tracks_maximum() {
        let mut h = OracleHistory::new();
        h.record(&pass_rep(1), &warn_rep(2)).unwrap();
        h.record(&warn_rep(2), &fail_rep(3)).unwrap();
        assert_eq!(h.worst_class(), Some(DivergenceClass::Critical));
    }
}
