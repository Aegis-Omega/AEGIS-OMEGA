//! Gate 273 — Fanout Controller: adaptive gossip fanout based on mesh health (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Computes the optimal gossip fanout for the current epoch based on:
//!   - current quorum level (QuorumLevel)
//!   - mesh health ratio (0–100)
//!   - target reach percentage (0–100)
//!   - mesh size (total_nodes)
//!
//! FanoutPolicy:
//!   Conservative — fanout=2 (minimal load, used when mesh is healthy and small)
//!   Standard     — fanout=3 (default operating mode)
//!   Aggressive   — fanout=5 (used when quorum is at threshold or mesh is degraded)
//!   Maximum      — fanout=8 (emergency: quorum lost or health below 50%)
//!
//! FanoutDecision:
//!   epoch         — u64
//!   policy        — FanoutPolicy
//!   fanout        — u8
//!   rationale     — &'static str
//!   decision_hash — SHA-256(prev ‖ epoch_be8 ‖ policy_byte ‖ fanout)
//!   prev_hash     — [u8; 32]
//!
//! FanoutLog: hash-chained FanoutDecisions; average_fanout(), max_fanout(),
//!   aggressive_epoch_count(), verify_chain().

use sha2::{Sha256, Digest};
use crate::quorum_guard::QuorumLevel;

// ─── Fanout policy ────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum FanoutPolicy {
    Conservative = 0,
    Standard     = 1,
    Aggressive   = 2,
    Maximum      = 3,
}

impl FanoutPolicy {
    pub fn fanout_value(self) -> u8 {
        match self {
            Self::Conservative => 2,
            Self::Standard     => 3,
            Self::Aggressive   => 5,
            Self::Maximum      => 8,
        }
    }

    pub fn rationale(self) -> &'static str {
        match self {
            Self::Conservative => "mesh healthy, small network — conservative fanout sufficient",
            Self::Standard     => "normal operating mode — standard fanout",
            Self::Aggressive   => "quorum at threshold or health degraded — aggressive fanout",
            Self::Maximum      => "quorum lost or health critical — maximum fanout for recovery",
        }
    }
}

/// Select fanout policy from quorum level and health ratio.
/// health_ratio: 0–100 (percentage of healthy nodes).
pub fn select_policy(quorum_level: QuorumLevel, health_ratio: u8, total_nodes: usize) -> FanoutPolicy {
    match quorum_level {
        QuorumLevel::NoNodes => FanoutPolicy::Maximum,
        QuorumLevel::BelowQuorum => FanoutPolicy::Maximum,
        QuorumLevel::AtThreshold => FanoutPolicy::Aggressive,
        QuorumLevel::Healthy => {
            if health_ratio < 50 {
                FanoutPolicy::Maximum
            } else if health_ratio < 70 {
                FanoutPolicy::Aggressive
            } else if total_nodes <= 8 {
                FanoutPolicy::Conservative
            } else {
                FanoutPolicy::Standard
            }
        }
    }
}

// ─── Fanout decision ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct FanoutDecision {
    pub epoch:         u64,
    pub policy:        FanoutPolicy,
    pub fanout:        u8,
    pub rationale:     &'static str,
    pub decision_hash: [u8; 32],
    pub prev_hash:     [u8; 32],
}

pub const FANOUT_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_decision_hash(
    epoch:   u64,
    policy:  FanoutPolicy,
    fanout:  u8,
    prev:    &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update([policy as u8, fanout]);
    h.finalize().into()
}

pub fn build_decision(
    epoch:        u64,
    quorum_level: QuorumLevel,
    health_ratio: u8,
    total_nodes:  usize,
    prev_hash:    &[u8; 32],
) -> FanoutDecision {
    let policy   = select_policy(quorum_level, health_ratio, total_nodes);
    let fanout   = policy.fanout_value();
    let rationale = policy.rationale();
    let decision_hash = compute_decision_hash(epoch, policy, fanout, prev_hash);
    FanoutDecision {
        epoch, policy, fanout, rationale, decision_hash, prev_hash: *prev_hash,
    }
}

impl FanoutDecision {
    pub fn is_elevated(&self) -> bool {
        self.policy >= FanoutPolicy::Aggressive
    }
}

// ─── Fanout log ───────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct FanoutLog {
    decisions: Vec<FanoutDecision>,
}

#[derive(Debug)]
pub enum FanoutLogError {
    StaleEpoch,
}

impl FanoutLog {
    pub fn new() -> Self { Self { decisions: Vec::new() } }

    pub fn len(&self)      -> usize { self.decisions.len() }
    pub fn is_empty(&self) -> bool  { self.decisions.is_empty() }
    pub fn decisions(&self) -> &[FanoutDecision] { &self.decisions }
    pub fn latest(&self)   -> Option<&FanoutDecision> { self.decisions.last() }

    pub fn last_hash(&self) -> [u8; 32] {
        self.decisions.last().map(|d| d.decision_hash).unwrap_or(FANOUT_GENESIS_HASH)
    }

    pub fn record(
        &mut self,
        epoch:        u64,
        quorum_level: QuorumLevel,
        health_ratio: u8,
        total_nodes:  usize,
    ) -> Result<&FanoutDecision, FanoutLogError> {
        if let Some(last) = self.decisions.last() {
            if epoch <= last.epoch {
                return Err(FanoutLogError::StaleEpoch);
            }
        }
        let prev_hash = self.last_hash();
        let d = build_decision(epoch, quorum_level, health_ratio, total_nodes, &prev_hash);
        self.decisions.push(d);
        Ok(self.decisions.last().unwrap())
    }

    /// Average fanout across all recorded decisions (integer, truncated).
    pub fn average_fanout(&self) -> u8 {
        if self.decisions.is_empty() { return 0; }
        let sum: usize = self.decisions.iter().map(|d| d.fanout as usize).sum();
        (sum / self.decisions.len()) as u8
    }

    pub fn max_fanout(&self) -> u8 {
        self.decisions.iter().map(|d| d.fanout).max().unwrap_or(0)
    }

    pub fn aggressive_epoch_count(&self) -> usize {
        self.decisions.iter().filter(|d| d.is_elevated()).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = FANOUT_GENESIS_HASH;
        for (i, d) in self.decisions.iter().enumerate() {
            if d.prev_hash != expected_prev {
                return (false, Some(i));
            }
            let recomputed = compute_decision_hash(d.epoch, d.policy, d.fanout, &d.prev_hash);
            if recomputed != d.decision_hash {
                return (false, Some(i));
            }
            expected_prev = d.decision_hash;
        }
        (true, None)
    }
}

impl Default for FanoutLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── select_policy ─────────────────────────────────────────────────────────

    #[test]
    fn no_nodes_gives_maximum() {
        assert_eq!(select_policy(QuorumLevel::NoNodes, 0, 0), FanoutPolicy::Maximum);
    }

    #[test]
    fn below_quorum_gives_maximum() {
        assert_eq!(select_policy(QuorumLevel::BelowQuorum, 80, 20), FanoutPolicy::Maximum);
    }

    #[test]
    fn at_threshold_gives_aggressive() {
        assert_eq!(select_policy(QuorumLevel::AtThreshold, 75, 20), FanoutPolicy::Aggressive);
    }

    #[test]
    fn healthy_low_health_ratio_gives_maximum() {
        assert_eq!(select_policy(QuorumLevel::Healthy, 40, 20), FanoutPolicy::Maximum);
    }

    #[test]
    fn healthy_moderate_health_ratio_gives_aggressive() {
        assert_eq!(select_policy(QuorumLevel::Healthy, 60, 20), FanoutPolicy::Aggressive);
    }

    #[test]
    fn healthy_good_health_small_network_gives_conservative() {
        assert_eq!(select_policy(QuorumLevel::Healthy, 90, 6), FanoutPolicy::Conservative);
    }

    #[test]
    fn healthy_good_health_large_network_gives_standard() {
        assert_eq!(select_policy(QuorumLevel::Healthy, 90, 20), FanoutPolicy::Standard);
    }

    // ── FanoutPolicy ──────────────────────────────────────────────────────────

    #[test]
    fn fanout_values_correct() {
        assert_eq!(FanoutPolicy::Conservative.fanout_value(), 2);
        assert_eq!(FanoutPolicy::Standard.fanout_value(),     3);
        assert_eq!(FanoutPolicy::Aggressive.fanout_value(),   5);
        assert_eq!(FanoutPolicy::Maximum.fanout_value(),      8);
    }

    #[test]
    fn is_elevated() {
        let d1 = build_decision(1, QuorumLevel::Healthy, 90, 20, &FANOUT_GENESIS_HASH);
        assert!(!d1.is_elevated()); // Standard

        let d2 = build_decision(2, QuorumLevel::AtThreshold, 80, 20, &FANOUT_GENESIS_HASH);
        assert!(d2.is_elevated()); // Aggressive

        let d3 = build_decision(3, QuorumLevel::BelowQuorum, 50, 20, &FANOUT_GENESIS_HASH);
        assert!(d3.is_elevated()); // Maximum
    }

    // ── build_decision ────────────────────────────────────────────────────────

    #[test]
    fn decision_hash_nonzero() {
        let d = build_decision(1, QuorumLevel::Healthy, 90, 20, &FANOUT_GENESIS_HASH);
        assert_ne!(d.decision_hash, [0u8; 32]);
    }

    #[test]
    fn decision_hash_deterministic() {
        let d1 = build_decision(1, QuorumLevel::Healthy, 90, 20, &FANOUT_GENESIS_HASH);
        let d2 = build_decision(1, QuorumLevel::Healthy, 90, 20, &FANOUT_GENESIS_HASH);
        assert_eq!(d1.decision_hash, d2.decision_hash);
    }

    #[test]
    fn different_policy_different_hash() {
        let d1 = build_decision(1, QuorumLevel::Healthy, 90, 6, &FANOUT_GENESIS_HASH);   // Conservative
        let d2 = build_decision(1, QuorumLevel::Healthy, 90, 20, &FANOUT_GENESIS_HASH);  // Standard
        assert_ne!(d1.decision_hash, d2.decision_hash);
    }

    // ── FanoutLog ─────────────────────────────────────────────────────────────

    #[test]
    fn new_log_empty() {
        let l = FanoutLog::new();
        assert!(l.is_empty());
        assert_eq!(l.average_fanout(), 0);
        assert_eq!(l.max_fanout(), 0);
        assert_eq!(l.aggressive_epoch_count(), 0);
    }

    #[test]
    fn record_appends() {
        let mut l = FanoutLog::new();
        l.record(1, QuorumLevel::Healthy, 90, 20).unwrap();
        l.record(2, QuorumLevel::Healthy, 90, 20).unwrap();
        assert_eq!(l.len(), 2);
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut l = FanoutLog::new();
        l.record(5, QuorumLevel::Healthy, 90, 20).unwrap();
        assert!(matches!(l.record(5, QuorumLevel::Healthy, 90, 20), Err(FanoutLogError::StaleEpoch)));
        assert!(matches!(l.record(4, QuorumLevel::Healthy, 90, 20), Err(FanoutLogError::StaleEpoch)));
    }

    #[test]
    fn max_fanout_tracks() {
        let mut l = FanoutLog::new();
        l.record(1, QuorumLevel::Healthy, 90, 20).unwrap();     // Standard → 3
        l.record(2, QuorumLevel::BelowQuorum, 40, 20).unwrap(); // Maximum → 8
        assert_eq!(l.max_fanout(), 8);
    }

    #[test]
    fn aggressive_epoch_count_counts_elevated() {
        let mut l = FanoutLog::new();
        l.record(1, QuorumLevel::Healthy, 90, 20).unwrap();    // Standard — not elevated
        l.record(2, QuorumLevel::AtThreshold, 80, 20).unwrap(); // Aggressive — elevated
        l.record(3, QuorumLevel::BelowQuorum, 50, 20).unwrap(); // Maximum — elevated
        assert_eq!(l.aggressive_epoch_count(), 2);
    }

    #[test]
    fn verify_chain_valid() {
        let mut l = FanoutLog::new();
        for i in 1..=5u64 {
            let ql = if i % 2 == 0 { QuorumLevel::Healthy } else { QuorumLevel::AtThreshold };
            l.record(i, ql, 75, 20).unwrap();
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }
}
