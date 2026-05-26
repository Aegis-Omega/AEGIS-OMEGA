//! Gate 264 — Mesh Census: periodic peer mesh population snapshot (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Takes a periodic census of the gossip mesh, counting nodes by state and
//! capability. Produces a CensusRecord for each epoch; records are hash-chained.
//!
//! CensusRecord:
//!   epoch                — u64
//!   total_nodes          — usize
//!   active_count         — usize (Active + Recovery states)
//!   degraded_count       — usize (Degraded state)
//!   halted_count         — usize (Halted state)
//!   gossip_capable_count — usize (peers with GOSSIP cap in registry)
//!   consensus_capable_count — usize (peers with CONSENSUS cap)
//!   health_ratio_pct     — u8  (active_count * 100 / total_nodes, or 0 if empty)
//!   census_hash          — SHA-256(prev ‖ epoch ‖ total ‖ active ‖ degraded ‖ halted)
//!
//! CensusLog: hash-chained CensusRecords; census_count(), min_health_pct(), trend().

use sha2::{Sha256, Digest};
use crate::node_state_machine::{NodeHistory, NodeState};
use crate::peer_manifest::{PeerRegistry, cap};

// ─── Census record ────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct CensusRecord {
    pub epoch:                   u64,
    pub total_nodes:             usize,
    pub active_count:            usize,
    pub degraded_count:          usize,
    pub halted_count:            usize,
    pub gossip_capable_count:    usize,
    pub consensus_capable_count: usize,
    pub health_ratio_pct:        u8,
    pub census_hash:             [u8; 32],
    pub prev_hash:               [u8; 32],
}

impl CensusRecord {
    /// True if active_count / total >= 1/φ (integer arithmetic).
    pub fn mesh_healthy(&self) -> bool {
        if self.total_nodes == 0 { return false; }
        self.active_count * 1_000_000 >= self.total_nodes * 618_034
    }
}

pub const CENSUS_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_census_hash(
    epoch:          u64,
    total:          usize,
    active:         usize,
    degraded:       usize,
    halted:         usize,
    prev:           &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update((total   as u64).to_be_bytes());
    h.update((active  as u64).to_be_bytes());
    h.update((degraded as u64).to_be_bytes());
    h.update((halted  as u64).to_be_bytes());
    h.finalize().into()
}

// ─── Take census ─────────────────────────────────────────────────────────────

/// Build a CensusRecord from node histories + peer registry at the given epoch.
pub fn take_census(
    epoch:     u64,
    histories: &[&NodeHistory],
    registry:  &PeerRegistry,
    prev_hash: &[u8; 32],
) -> CensusRecord {
    let total_nodes    = histories.len();
    let active_count   = histories.iter()
        .filter(|h| h.current_state().is_operational()).count();
    let degraded_count = histories.iter()
        .filter(|h| h.current_state() == NodeState::Degraded).count();
    let halted_count   = histories.iter()
        .filter(|h| h.current_state() == NodeState::Halted).count();

    let gossip_capable_count    = registry.peers_with_cap(cap::GOSSIP).len();
    let consensus_capable_count = registry.peers_with_cap(cap::CONSENSUS).len();

    let health_ratio_pct = if total_nodes == 0 {
        0u8
    } else {
        ((active_count * 100) / total_nodes).min(100) as u8
    };

    let census_hash = compute_census_hash(
        epoch, total_nodes, active_count, degraded_count, halted_count, prev_hash);

    CensusRecord {
        epoch,
        total_nodes,
        active_count,
        degraded_count,
        halted_count,
        gossip_capable_count,
        consensus_capable_count,
        health_ratio_pct,
        census_hash,
        prev_hash: *prev_hash,
    }
}

// ─── Census trend ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CensusTrend {
    Improving  = 0,
    Stable     = 1,
    Declining  = 2,
    Insufficient = 3, // fewer than 2 records
}

impl CensusTrend {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Improving     => "improving",
            Self::Stable        => "stable",
            Self::Declining     => "declining",
            Self::Insufficient  => "insufficient data",
        }
    }
}

// ─── Census log ───────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct CensusLog {
    records: Vec<CensusRecord>,
}

#[derive(Debug)]
pub enum CensusError {
    StaleEpoch,
}

impl CensusError {
    pub fn as_str(&self) -> &'static str { "stale epoch" }
}

impl CensusLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self) -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool { self.records.is_empty() }
    pub fn records(&self) -> &[CensusRecord] { &self.records }
    pub fn latest(&self) -> Option<&CensusRecord> { self.records.last() }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.census_hash).unwrap_or(CENSUS_GENESIS_HASH)
    }

    pub fn record(
        &mut self,
        epoch:     u64,
        histories: &[&NodeHistory],
        registry:  &PeerRegistry,
    ) -> Result<&CensusRecord, CensusError> {
        if let Some(last) = self.records.last() {
            if epoch <= last.epoch {
                return Err(CensusError::StaleEpoch);
            }
        }
        let prev_hash = self.last_hash();
        let rec = take_census(epoch, histories, registry, &prev_hash);
        self.records.push(rec);
        Ok(self.records.last().unwrap())
    }

    /// Minimum health_ratio_pct across all records (or 0 if empty).
    pub fn min_health_pct(&self) -> u8 {
        self.records.iter().map(|r| r.health_ratio_pct).min().unwrap_or(0)
    }

    /// Trend: compare last two health_ratio_pct values.
    pub fn trend(&self) -> CensusTrend {
        if self.records.len() < 2 {
            return CensusTrend::Insufficient;
        }
        let prev = self.records[self.records.len() - 2].health_ratio_pct;
        let last = self.records[self.records.len() - 1].health_ratio_pct;
        if last > prev { CensusTrend::Improving }
        else if last < prev { CensusTrend::Declining }
        else { CensusTrend::Stable }
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = CENSUS_GENESIS_HASH;
        for (i, rec) in self.records.iter().enumerate() {
            if rec.prev_hash != expected_prev {
                return (false, Some(i));
            }
            let recomputed = compute_census_hash(
                rec.epoch, rec.total_nodes, rec.active_count,
                rec.degraded_count, rec.halted_count, &rec.prev_hash);
            if recomputed != rec.census_hash {
                return (false, Some(i));
            }
            expected_prev = rec.census_hash;
        }
        (true, None)
    }
}

impl Default for CensusLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::node_state_machine::NodeHistory;
    use crate::peer_manifest::{build_manifest, cap, PeerRegistry};
    use crate::phase_transition::ConstitutionalPhase;

    fn active_history(id: u32) -> NodeHistory {
        let mut h = NodeHistory::new(id);
        h.transition(NodeState::Active, 1, "boot").unwrap();
        h
    }

    fn degraded_history(id: u32) -> NodeHistory {
        let mut h = NodeHistory::new(id);
        h.transition(NodeState::Active, 1, "boot").unwrap();
        h.transition(NodeState::Degraded, 2, "fault").unwrap();
        h
    }

    fn halted_history(id: u32) -> NodeHistory {
        let mut h = NodeHistory::new(id);
        h.transition(NodeState::Active, 1, "boot").unwrap();
        h.transition(NodeState::Halted, 2, "halt").unwrap();
        h
    }

    fn full_registry(n: u32) -> PeerRegistry {
        let mut r = PeerRegistry::new();
        for i in 0..n {
            r.register(build_manifest(i, 1, cap::ALL, ConstitutionalPhase::Nominal)).unwrap();
        }
        r
    }

    // ── take_census ──────────────────────────────────────────────────────────

    #[test]
    fn empty_mesh_census() {
        let r = PeerRegistry::new();
        let c = take_census(1, &[], &r, &CENSUS_GENESIS_HASH);
        assert_eq!(c.total_nodes, 0);
        assert_eq!(c.health_ratio_pct, 0);
        assert!(!c.mesh_healthy());
    }

    #[test]
    fn all_active_100pct() {
        let a = active_history(1);
        let b = active_history(2);
        let r = full_registry(2);
        let c = take_census(5, &[&a, &b], &r, &CENSUS_GENESIS_HASH);
        assert_eq!(c.total_nodes, 2);
        assert_eq!(c.active_count, 2);
        assert_eq!(c.degraded_count, 0);
        assert_eq!(c.halted_count, 0);
        assert_eq!(c.health_ratio_pct, 100);
        assert!(c.mesh_healthy());
    }

    #[test]
    fn mixed_state_counts() {
        let a  = active_history(1);
        let d  = degraded_history(2);
        let h  = halted_history(3);
        let r  = full_registry(3);
        let c = take_census(5, &[&a, &d, &h], &r, &CENSUS_GENESIS_HASH);
        assert_eq!(c.active_count,   1);
        assert_eq!(c.degraded_count, 1);
        assert_eq!(c.halted_count,   1);
        assert_eq!(c.health_ratio_pct, 33); // 1/3 → 33%
    }

    #[test]
    fn mesh_healthy_at_phi_threshold() {
        // 5 active out of 8 → 62.5% > 61.8% → healthy
        let histories: Vec<NodeHistory> = (0..8).map(|i| {
            if i < 5 { active_history(i) } else { degraded_history(i) }
        }).collect();
        let refs: Vec<&NodeHistory> = histories.iter().collect();
        let r = full_registry(8);
        let c = take_census(1, &refs, &r, &CENSUS_GENESIS_HASH);
        assert!(c.mesh_healthy());
    }

    #[test]
    fn census_hash_nonzero() {
        let a = active_history(1);
        let r = full_registry(1);
        let c = take_census(1, &[&a], &r, &CENSUS_GENESIS_HASH);
        assert_ne!(c.census_hash, [0u8; 32]);
    }

    #[test]
    fn census_hash_deterministic() {
        let a = active_history(1);
        let r = full_registry(1);
        let c1 = take_census(1, &[&a], &r, &CENSUS_GENESIS_HASH);
        let c2 = take_census(1, &[&a], &r, &CENSUS_GENESIS_HASH);
        assert_eq!(c1.census_hash, c2.census_hash);
    }

    #[test]
    fn capability_counts_from_registry() {
        let r = full_registry(4);
        let a = active_history(0);
        let c = take_census(1, &[&a], &r, &CENSUS_GENESIS_HASH);
        assert_eq!(c.gossip_capable_count, 4);
        assert_eq!(c.consensus_capable_count, 4);
    }

    // ── CensusLog ────────────────────────────────────────────────────────────

    #[test]
    fn new_log_empty() {
        let l = CensusLog::new();
        assert!(l.is_empty());
        assert_eq!(l.last_hash(), CENSUS_GENESIS_HASH);
        assert_eq!(l.trend(), CensusTrend::Insufficient);
        assert_eq!(l.min_health_pct(), 0);
    }

    #[test]
    fn record_appends() {
        let mut l = CensusLog::new();
        let a = active_history(1);
        let r = full_registry(1);
        l.record(1, &[&a], &r).unwrap();
        l.record(2, &[&a], &r).unwrap();
        assert_eq!(l.len(), 2);
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut l = CensusLog::new();
        let a = active_history(1);
        let r = full_registry(1);
        l.record(5, &[&a], &r).unwrap();
        assert!(matches!(l.record(5, &[&a], &r), Err(CensusError::StaleEpoch)));
        assert!(matches!(l.record(4, &[&a], &r), Err(CensusError::StaleEpoch)));
    }

    #[test]
    fn trend_improving() {
        let mut l = CensusLog::new();
        let d = degraded_history(1);
        let a = active_history(2);
        let r = full_registry(2);
        l.record(1, &[&d, &d], &r).unwrap(); // 0% healthy
        l.record(2, &[&a, &a], &r).unwrap(); // 100% healthy
        assert_eq!(l.trend(), CensusTrend::Improving);
    }

    #[test]
    fn trend_declining() {
        let mut l = CensusLog::new();
        let a = active_history(1);
        let d = degraded_history(2);
        let r = full_registry(2);
        l.record(1, &[&a, &a], &r).unwrap(); // 100%
        l.record(2, &[&a, &d], &r).unwrap(); // 50%
        assert_eq!(l.trend(), CensusTrend::Declining);
    }

    #[test]
    fn trend_stable() {
        let mut l = CensusLog::new();
        let a = active_history(1);
        let r = full_registry(1);
        l.record(1, &[&a], &r).unwrap();
        l.record(2, &[&a], &r).unwrap();
        assert_eq!(l.trend(), CensusTrend::Stable);
    }

    #[test]
    fn verify_chain_valid() {
        let mut l = CensusLog::new();
        let a = active_history(1);
        let r = full_registry(1);
        for e in 1..=4u64 {
            l.record(e, &[&a], &r).unwrap();
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    #[test]
    fn census_trend_as_str() {
        assert_eq!(CensusTrend::Improving.as_str(),    "improving");
        assert_eq!(CensusTrend::Declining.as_str(),    "declining");
        assert_eq!(CensusTrend::Stable.as_str(),       "stable");
        assert_eq!(CensusTrend::Insufficient.as_str(), "insufficient data");
    }
}
