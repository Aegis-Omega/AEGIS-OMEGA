//! Gate 237: Swarm Health Monitor — Unified constitutional health across the swarm (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Aggregates GovernancePipeline + SwarmAutonode outputs into a single
//! SwarmHealthReport per epoch. Provides a T0 health verdict (pass/fail) and
//! a reason code for any constitutional breach.
//!
//! Health invariants (all must hold for HealthVerdict::Pass):
//!   1. GovernancePipeline: mutation_authority_active && !drift_class D4
//!   2. SwarmAutonode: quorum_reached at 1/φ threshold
//!   3. Entropy budget: balance >= ADAPTIVE_EVENT_COST
//!   4. Continuously coherent: no breach epoch in pipeline or swarm
//!
//! SwarmHealthReport is hash-linked (SHA-256) for audit-trail integration.
//! health_hash = SHA-256(prev_hash ‖ verdict_byte ‖ epoch_be8 ‖ coherent_node_count_be4)

use sha2::{Sha256, Digest};

// ─── Health verdict ───────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum HealthVerdict {
    Pass = 0,
    Warn = 1, // quorum reached but some nodes incoherent
    Fail = 2, // quorum not reached or authority suspended
}

impl HealthVerdict {
    pub fn as_u8(self) -> u8 { self as u8 }
    pub fn is_pass(self) -> bool { self == HealthVerdict::Pass }
    pub fn is_operational(self) -> bool { self != HealthVerdict::Fail }
}

// ─── Failure reason ───────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum HealthFailReason {
    None,
    MutationAuthoritySuspended, // drift >= D2
    QuorumNotReached,           // < 1/φ of nodes coherent
    EntropyExhausted,           // balance < ADAPTIVE_EVENT_COST
    ContinuityBreach,           // is_continuously_coherent = false
    D4DriftDetected,            // drift class D4
}

impl HealthFailReason {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::None                      => "none",
            Self::MutationAuthoritySuspended => "mutation_authority_suspended",
            Self::QuorumNotReached          => "quorum_not_reached",
            Self::EntropyExhausted          => "entropy_exhausted",
            Self::ContinuityBreach          => "continuity_breach",
            Self::D4DriftDetected           => "d4_drift_detected",
        }
    }
}

// ─── Health snapshot ──────────────────────────────────────────────────────

/// Input snapshot for one health check cycle.
#[derive(Debug, Clone)]
pub struct HealthSnapshot {
    pub epoch:                     u64,
    pub node_count:                usize,
    pub coherent_node_count:       usize,
    pub continuously_coherent_count: usize,
    pub quorum_reached:            bool,
    pub continuous_quorum:         bool,
    pub mutation_authority_active: bool,
    pub entropy_balance:           u64,
    pub drift_class_int:           u8,   // 0=D0 .. 4=D4
    pub is_continuously_coherent:  bool, // pipeline-level flag
}

// ─── Health report ────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct SwarmHealthReport {
    pub epoch:                     u64,
    pub verdict:                   HealthVerdict,
    pub primary_fail_reason:       HealthFailReason,
    pub node_count:                usize,
    pub coherent_node_count:       usize,
    pub quorum_reached:            bool,
    pub continuous_quorum:         bool,
    pub mutation_authority_active: bool,
    pub entropy_balance:           u64,
    pub drift_class_int:           u8,
    /// SHA-256(prev_hash ‖ verdict_byte ‖ epoch_be8 ‖ coherent_count_be4)
    pub health_hash:               [u8; 32],
    pub prev_health_hash:          [u8; 32],
}

pub const HEALTH_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── Assess function ──────────────────────────────────────────────────────

/// Assess a SwarmHealthReport from a HealthSnapshot and previous hash.
pub fn assess_health(snap: &HealthSnapshot, prev_hash: &[u8; 32]) -> SwarmHealthReport {
    // Determine verdict and primary fail reason in priority order
    let (verdict, reason) = if snap.drift_class_int >= 4 {
        (HealthVerdict::Fail, HealthFailReason::D4DriftDetected)
    } else if !snap.mutation_authority_active {
        (HealthVerdict::Fail, HealthFailReason::MutationAuthoritySuspended)
    } else if !snap.quorum_reached {
        (HealthVerdict::Fail, HealthFailReason::QuorumNotReached)
    } else if snap.entropy_balance < crate::entropy_budget::ADAPTIVE_EVENT_COST {
        (HealthVerdict::Fail, HealthFailReason::EntropyExhausted)
    } else if !snap.is_continuously_coherent {
        (HealthVerdict::Fail, HealthFailReason::ContinuityBreach)
    } else if snap.coherent_node_count < snap.node_count {
        (HealthVerdict::Warn, HealthFailReason::None)
    } else {
        (HealthVerdict::Pass, HealthFailReason::None)
    };

    let health_hash = compute_health_hash(prev_hash, verdict, snap.epoch, snap.coherent_node_count);

    SwarmHealthReport {
        epoch: snap.epoch,
        verdict,
        primary_fail_reason: reason,
        node_count: snap.node_count,
        coherent_node_count: snap.coherent_node_count,
        quorum_reached: snap.quorum_reached,
        continuous_quorum: snap.continuous_quorum,
        mutation_authority_active: snap.mutation_authority_active,
        entropy_balance: snap.entropy_balance,
        drift_class_int: snap.drift_class_int,
        health_hash,
        prev_health_hash: *prev_hash,
    }
}

// ─── Health history ───────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct HealthHistory {
    reports: Vec<SwarmHealthReport>,
}

#[derive(Debug)]
pub struct HealthError(pub &'static str);

impl HealthHistory {
    pub fn new() -> Self { Self { reports: Vec::new() } }

    pub fn len(&self) -> usize { self.reports.len() }
    pub fn is_empty(&self) -> bool { self.reports.is_empty() }
    pub fn reports(&self) -> &[SwarmHealthReport] { &self.reports }

    pub fn last_hash(&self) -> [u8; 32] {
        self.reports.last().map(|r| r.health_hash).unwrap_or(HEALTH_GENESIS_HASH)
    }

    /// Current verdict (Pass if no reports yet — optimistic initial assumption).
    pub fn current_verdict(&self) -> HealthVerdict {
        self.reports.last().map(|r| r.verdict).unwrap_or(HealthVerdict::Pass)
    }

    /// Count of Fail verdicts across all epochs.
    pub fn fail_count(&self) -> usize {
        self.reports.iter().filter(|r| r.verdict == HealthVerdict::Fail).count()
    }

    /// Append a health snapshot.
    /// Returns Err if epoch not strictly greater than last epoch.
    pub fn record(&mut self, snap: &HealthSnapshot) -> Result<&SwarmHealthReport, HealthError> {
        if let Some(last) = self.reports.last() {
            if snap.epoch <= last.epoch {
                return Err(HealthError("epoch must be strictly greater than last epoch"));
            }
        }
        let prev_hash = self.last_hash();
        let report = assess_health(snap, &prev_hash);
        self.reports.push(report);
        Ok(self.reports.last().unwrap())
    }

    /// Verify full hash chain integrity. Returns (is_valid, first_broken_index).
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = HEALTH_GENESIS_HASH;
        for (i, rep) in self.reports.iter().enumerate() {
            if rep.prev_health_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_health_hash(&prev, rep.verdict, rep.epoch, rep.coherent_node_count);
            if expected != rep.health_hash {
                return (false, Some(i));
            }
            prev = rep.health_hash;
        }
        (true, None)
    }
}

impl Default for HealthHistory {
    fn default() -> Self { Self::new() }
}

fn compute_health_hash(
    prev: &[u8; 32],
    verdict: HealthVerdict,
    epoch: u64,
    coherent_count: usize,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update([verdict.as_u8()]);
    h.update(epoch.to_be_bytes());
    h.update((coherent_count as u32).to_be_bytes());
    h.finalize().into()
}

// ─── Tests ────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn good_snap(epoch: u64) -> HealthSnapshot {
        HealthSnapshot {
            epoch,
            node_count: 5,
            coherent_node_count: 5,
            continuously_coherent_count: 5,
            quorum_reached: true,
            continuous_quorum: true,
            mutation_authority_active: true,
            entropy_balance: 1000,
            drift_class_int: 0,
            is_continuously_coherent: true,
        }
    }

    fn bad_snap(epoch: u64, drift: u8) -> HealthSnapshot {
        HealthSnapshot {
            epoch,
            node_count: 5,
            coherent_node_count: 2,
            continuously_coherent_count: 2,
            quorum_reached: false,
            continuous_quorum: false,
            mutation_authority_active: drift < 2,
            entropy_balance: 1000,
            drift_class_int: drift,
            is_continuously_coherent: drift == 0,
        }
    }

    // ── HealthVerdict ─────────────────────────────────────────────────────

    #[test]
    fn pass_is_operational() {
        assert!(HealthVerdict::Pass.is_operational());
        assert!(HealthVerdict::Pass.is_pass());
    }

    #[test]
    fn warn_is_operational_not_pass() {
        assert!(HealthVerdict::Warn.is_operational());
        assert!(!HealthVerdict::Warn.is_pass());
    }

    #[test]
    fn fail_is_not_operational() {
        assert!(!HealthVerdict::Fail.is_operational());
        assert!(!HealthVerdict::Fail.is_pass());
    }

    #[test]
    fn verdict_as_u8() {
        assert_eq!(HealthVerdict::Pass.as_u8(), 0);
        assert_eq!(HealthVerdict::Warn.as_u8(), 1);
        assert_eq!(HealthVerdict::Fail.as_u8(), 2);
    }

    // ── assess_health ─────────────────────────────────────────────────────

    #[test]
    fn good_snap_gives_pass() {
        let rep = assess_health(&good_snap(1), &HEALTH_GENESIS_HASH);
        assert_eq!(rep.verdict, HealthVerdict::Pass);
        assert_eq!(rep.primary_fail_reason, HealthFailReason::None);
    }

    #[test]
    fn d4_drift_gives_fail_d4() {
        let mut s = good_snap(1);
        s.drift_class_int = 4;
        s.mutation_authority_active = false;
        let rep = assess_health(&s, &HEALTH_GENESIS_HASH);
        assert_eq!(rep.verdict, HealthVerdict::Fail);
        assert_eq!(rep.primary_fail_reason, HealthFailReason::D4DriftDetected);
    }

    #[test]
    fn suspended_authority_gives_fail() {
        let mut s = good_snap(1);
        s.mutation_authority_active = false;
        s.drift_class_int = 2;
        let rep = assess_health(&s, &HEALTH_GENESIS_HASH);
        assert_eq!(rep.verdict, HealthVerdict::Fail);
        assert_eq!(rep.primary_fail_reason, HealthFailReason::MutationAuthoritySuspended);
    }

    #[test]
    fn quorum_not_reached_gives_fail() {
        let mut s = good_snap(1);
        s.quorum_reached = false;
        let rep = assess_health(&s, &HEALTH_GENESIS_HASH);
        assert_eq!(rep.verdict, HealthVerdict::Fail);
        assert_eq!(rep.primary_fail_reason, HealthFailReason::QuorumNotReached);
    }

    #[test]
    fn entropy_exhausted_gives_fail() {
        let mut s = good_snap(1);
        s.entropy_balance = 5; // < ADAPTIVE_EVENT_COST = 10
        let rep = assess_health(&s, &HEALTH_GENESIS_HASH);
        assert_eq!(rep.verdict, HealthVerdict::Fail);
        assert_eq!(rep.primary_fail_reason, HealthFailReason::EntropyExhausted);
    }

    #[test]
    fn continuity_breach_gives_fail() {
        let mut s = good_snap(1);
        s.is_continuously_coherent = false;
        let rep = assess_health(&s, &HEALTH_GENESIS_HASH);
        assert_eq!(rep.verdict, HealthVerdict::Fail);
        assert_eq!(rep.primary_fail_reason, HealthFailReason::ContinuityBreach);
    }

    #[test]
    fn partial_coherence_gives_warn() {
        let mut s = good_snap(1);
        s.coherent_node_count = 4; // 4/5 coherent — quorum still reached
        s.continuously_coherent_count = 4;
        let rep = assess_health(&s, &HEALTH_GENESIS_HASH);
        assert_eq!(rep.verdict, HealthVerdict::Warn);
        assert_eq!(rep.primary_fail_reason, HealthFailReason::None);
    }

    #[test]
    fn health_hash_nonzero() {
        let rep = assess_health(&good_snap(1), &HEALTH_GENESIS_HASH);
        assert_ne!(rep.health_hash, [0u8; 32]);
    }

    #[test]
    fn health_hash_deterministic() {
        let snap = good_snap(42);
        let r1 = assess_health(&snap, &HEALTH_GENESIS_HASH);
        let r2 = assess_health(&snap, &HEALTH_GENESIS_HASH);
        let r3 = assess_health(&snap, &HEALTH_GENESIS_HASH);
        assert_eq!(r1.health_hash, r2.health_hash);
        assert_eq!(r2.health_hash, r3.health_hash);
    }

    #[test]
    fn different_epoch_different_hash() {
        let r1 = assess_health(&good_snap(1), &HEALTH_GENESIS_HASH);
        let r2 = assess_health(&good_snap(2), &HEALTH_GENESIS_HASH);
        assert_ne!(r1.health_hash, r2.health_hash);
    }

    // ── HealthHistory ─────────────────────────────────────────────────────

    #[test]
    fn new_history_empty() {
        let h = HealthHistory::new();
        assert!(h.is_empty());
        assert_eq!(h.len(), 0);
        assert_eq!(h.current_verdict(), HealthVerdict::Pass);
    }

    #[test]
    fn record_grows_history() {
        let mut h = HealthHistory::new();
        h.record(&good_snap(1)).unwrap();
        h.record(&good_snap(2)).unwrap();
        assert_eq!(h.len(), 2);
    }

    #[test]
    fn duplicate_epoch_is_err() {
        let mut h = HealthHistory::new();
        h.record(&good_snap(5)).unwrap();
        assert!(h.record(&good_snap(5)).is_err());
    }

    #[test]
    fn fail_count_tracks_correctly() {
        let mut h = HealthHistory::new();
        h.record(&good_snap(1)).unwrap();
        h.record(&bad_snap(2, 4)).unwrap();
        h.record(&good_snap(3)).unwrap();
        h.record(&bad_snap(4, 4)).unwrap();
        assert_eq!(h.fail_count(), 2);
    }

    #[test]
    fn hash_chain_links_correctly() {
        let mut h = HealthHistory::new();
        h.record(&good_snap(1)).unwrap();
        h.record(&good_snap(2)).unwrap();
        assert_eq!(h.reports()[1].prev_health_hash, h.reports()[0].health_hash);
    }

    #[test]
    fn verify_chain_clean() {
        let mut h = HealthHistory::new();
        for i in 1u64..=5 { h.record(&good_snap(i)).unwrap(); }
        let (valid, broken) = h.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    #[test]
    fn fail_reason_as_str() {
        assert_eq!(HealthFailReason::None.as_str(), "none");
        assert_eq!(HealthFailReason::D4DriftDetected.as_str(), "d4_drift_detected");
        assert_eq!(HealthFailReason::QuorumNotReached.as_str(), "quorum_not_reached");
    }
}
