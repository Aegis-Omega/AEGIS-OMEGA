//! Gate 284 — Gossip Bandwidth Tracker: per-peer byte budget enforcement (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks outbound gossip bytes per peer per epoch against a byte budget.
//! Enforces limits to prevent any single peer from consuming the full bandwidth.
//!
//! BandwidthDecision: Allow / Throttle / Deny
//!   Allow    — bytes_used + requested ≤ budget
//!   Throttle — bytes_used + requested > budget, but bytes_used ≤ budget (partial)
//!   Deny     — bytes_used already ≥ budget (budget fully consumed)
//!
//! PeerBandwidthRecord:
//!   peer_id        — u32
//!   epoch          — u64
//!   bytes_allowed  — u64
//!   bytes_throttled — u64
//!   bytes_denied   — u64
//!   budget_bytes   — u64
//!   utilization_pct — u8 (bytes_allowed * 100 / budget_bytes; capped at 100)
//!   record_hash    — SHA-256(prev ‖ peer_be4 ‖ epoch_be8 ‖ allowed_be8 ‖ throttled_be8 ‖ denied_be8)
//!   prev_hash      — [u8; 32]
//!
//! PeerBandwidthLog: append-only per-epoch records per peer.
//!   record_epoch(), total_bytes_sent(), avg_utilization_pct(), over_budget_epochs(), verify_chain().
//!
//! BandwidthRegistry: BTreeMap<peer_id, (PeerBandwidthLog, current_epoch_usage)>.
//!   request_bytes(peer, epoch, count) → BandwidthDecision.
//!   seal_epoch(epoch) → seals all open epochs and records them in logs.

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const DEFAULT_BUDGET_BYTES: u64 = 1_000_000; // 1 MB per peer per epoch

// ─── Decision ─────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BandwidthDecision {
    Allow,
    Throttle,
    Deny,
}

impl BandwidthDecision {
    pub fn is_allowed(self) -> bool { matches!(self, Self::Allow) }
    pub fn is_rejected(self) -> bool { matches!(self, Self::Deny) }
}

// ─── Peer bandwidth record ────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct PeerBandwidthRecord {
    pub peer_id:          u32,
    pub epoch:            u64,
    pub bytes_allowed:    u64,
    pub bytes_throttled:  u64,
    pub bytes_denied:     u64,
    pub budget_bytes:     u64,
    pub utilization_pct:  u8,
    pub record_hash:      [u8; 32],
    pub prev_hash:        [u8; 32],
}

pub const BANDWIDTH_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_bw_hash(
    peer_id:         u32,
    epoch:           u64,
    bytes_allowed:   u64,
    bytes_throttled: u64,
    bytes_denied:    u64,
    prev:            &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update(bytes_allowed.to_be_bytes());
    h.update(bytes_throttled.to_be_bytes());
    h.update(bytes_denied.to_be_bytes());
    h.finalize().into()
}

pub fn build_bandwidth_record(
    peer_id:         u32,
    epoch:           u64,
    bytes_allowed:   u64,
    bytes_throttled: u64,
    bytes_denied:    u64,
    budget_bytes:    u64,
    prev_hash:       &[u8; 32],
) -> PeerBandwidthRecord {
    let utilization_pct = if budget_bytes == 0 {
        if bytes_allowed > 0 { 100 } else { 0 }
    } else {
        ((bytes_allowed * 100) / budget_bytes).min(100) as u8
    };
    let record_hash = compute_bw_hash(
        peer_id, epoch, bytes_allowed, bytes_throttled, bytes_denied, prev_hash,
    );
    PeerBandwidthRecord {
        peer_id, epoch, bytes_allowed, bytes_throttled, bytes_denied,
        budget_bytes, utilization_pct, record_hash, prev_hash: *prev_hash,
    }
}

// ─── Peer bandwidth log ────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct PeerBandwidthLog {
    peer_id: u32,
    records: Vec<PeerBandwidthRecord>,
}

#[derive(Debug)]
pub enum BandwidthError {
    StaleEpoch,
}

impl PeerBandwidthLog {
    pub fn new(peer_id: u32) -> Self { Self { peer_id, records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[PeerBandwidthRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(BANDWIDTH_GENESIS_HASH)
    }

    pub fn record_epoch(
        &mut self,
        epoch:           u64,
        bytes_allowed:   u64,
        bytes_throttled: u64,
        bytes_denied:    u64,
        budget_bytes:    u64,
    ) -> Result<&PeerBandwidthRecord, BandwidthError> {
        if let Some(last) = self.records.last() {
            if epoch <= last.epoch {
                return Err(BandwidthError::StaleEpoch);
            }
        }
        let prev = self.last_hash();
        let r = build_bandwidth_record(
            self.peer_id, epoch, bytes_allowed, bytes_throttled, bytes_denied, budget_bytes, &prev,
        );
        self.records.push(r);
        Ok(self.records.last().unwrap())
    }

    pub fn total_bytes_sent(&self) -> u64 {
        self.records.iter().map(|r| r.bytes_allowed).sum()
    }

    pub fn avg_utilization_pct(&self) -> u8 {
        if self.records.is_empty() { return 0; }
        let sum: u64 = self.records.iter().map(|r| r.utilization_pct as u64).sum();
        (sum / self.records.len() as u64) as u8
    }

    /// Epochs where bytes_allowed >= budget_bytes (fully consumed budget).
    pub fn over_budget_epochs(&self) -> usize {
        self.records.iter().filter(|r| r.bytes_allowed >= r.budget_bytes).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = BANDWIDTH_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_bw_hash(
                r.peer_id, r.epoch, r.bytes_allowed, r.bytes_throttled, r.bytes_denied, &r.prev_hash,
            );
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

// ─── Bandwidth registry ────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
struct PeerState {
    log:             PeerBandwidthLog,
    current_epoch:   u64,
    bytes_allowed:   u64,
    bytes_throttled: u64,
    bytes_denied:    u64,
}

#[derive(Debug, Clone)]
pub struct BandwidthRegistry {
    budget_bytes: u64,
    peers:        BTreeMap<u32, PeerState>,
}

impl BandwidthRegistry {
    pub fn new(budget_bytes: u64) -> Self {
        Self { budget_bytes, peers: BTreeMap::new() }
    }

    pub fn with_default_budget() -> Self { Self::new(DEFAULT_BUDGET_BYTES) }

    pub fn peer_count(&self) -> usize { self.peers.len() }

    /// Classify a byte request for peer at this epoch.
    /// Automatically initialises a new epoch context if epoch changes.
    pub fn request_bytes(
        &mut self,
        peer_id: u32,
        epoch:   u64,
        bytes:   u64,
    ) -> BandwidthDecision {
        let budget = self.budget_bytes;
        let state = self.peers.entry(peer_id).or_insert_with(|| PeerState {
            log:             PeerBandwidthLog::new(peer_id),
            current_epoch:   epoch,
            bytes_allowed:   0,
            bytes_throttled: 0,
            bytes_denied:    0,
        });

        // If epoch advanced, reset usage counters
        if epoch > state.current_epoch {
            state.current_epoch   = epoch;
            state.bytes_allowed   = 0;
            state.bytes_throttled = 0;
            state.bytes_denied    = 0;
        }

        let used = state.bytes_allowed;
        let decision = if used >= budget {
            BandwidthDecision::Deny
        } else if used.saturating_add(bytes) > budget {
            BandwidthDecision::Throttle
        } else {
            BandwidthDecision::Allow
        };

        match decision {
            BandwidthDecision::Allow    => state.bytes_allowed   = state.bytes_allowed.saturating_add(bytes),
            BandwidthDecision::Throttle => state.bytes_throttled = state.bytes_throttled.saturating_add(bytes),
            BandwidthDecision::Deny     => state.bytes_denied    = state.bytes_denied.saturating_add(bytes),
        }
        decision
    }

    /// Seal all open epoch contexts, recording them in logs.
    pub fn seal_epoch(&mut self, epoch: u64) -> Result<(), BandwidthError> {
        let budget = self.budget_bytes;
        for state in self.peers.values_mut() {
            if state.current_epoch == epoch {
                state.log.record_epoch(
                    epoch,
                    state.bytes_allowed,
                    state.bytes_throttled,
                    state.bytes_denied,
                    budget,
                ).map_err(|_| BandwidthError::StaleEpoch)?;
            }
        }
        Ok(())
    }

    pub fn get_log(&self, peer_id: u32) -> Option<&PeerBandwidthLog> {
        self.peers.get(&peer_id).map(|s| &s.log)
    }

    pub fn current_usage(&self, peer_id: u32) -> Option<u64> {
        self.peers.get(&peer_id).map(|s| s.bytes_allowed)
    }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── BandwidthDecision ─────────────────────────────────────────────────────

    #[test]
    fn allow_is_allowed() {
        assert!(BandwidthDecision::Allow.is_allowed());
        assert!(!BandwidthDecision::Deny.is_allowed());
        assert!(!BandwidthDecision::Throttle.is_allowed());
    }

    // ── build_bandwidth_record ────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let r = build_bandwidth_record(1, 1, 500, 0, 0, 1000, &BANDWIDTH_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_bandwidth_record(1, 1, 500, 0, 0, 1000, &BANDWIDTH_GENESIS_HASH);
        let r2 = build_bandwidth_record(1, 1, 500, 0, 0, 1000, &BANDWIDTH_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    #[test]
    fn utilization_pct_computed() {
        let r = build_bandwidth_record(1, 1, 500, 0, 0, 1000, &BANDWIDTH_GENESIS_HASH);
        assert_eq!(r.utilization_pct, 50);
    }

    #[test]
    fn utilization_pct_capped() {
        let r = build_bandwidth_record(1, 1, 2000, 0, 0, 1000, &BANDWIDTH_GENESIS_HASH);
        assert_eq!(r.utilization_pct, 100);
    }

    // ── PeerBandwidthLog ──────────────────────────────────────────────────────

    #[test]
    fn new_log_empty() {
        let l = PeerBandwidthLog::new(1);
        assert!(l.is_empty());
        assert_eq!(l.total_bytes_sent(), 0);
        assert_eq!(l.avg_utilization_pct(), 0);
    }

    #[test]
    fn record_epoch_tracks() {
        let mut l = PeerBandwidthLog::new(1);
        l.record_epoch(1, 400, 100, 50, 1000).unwrap();
        l.record_epoch(2, 600, 0, 0, 1000).unwrap();
        assert_eq!(l.total_bytes_sent(), 1000);
        assert_eq!(l.avg_utilization_pct(), 50); // (40+60)/2
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut l = PeerBandwidthLog::new(1);
        l.record_epoch(5, 100, 0, 0, 1000).unwrap();
        assert!(matches!(l.record_epoch(4, 100, 0, 0, 1000), Err(BandwidthError::StaleEpoch)));
    }

    #[test]
    fn over_budget_epochs() {
        let mut l = PeerBandwidthLog::new(1);
        l.record_epoch(1, 1000, 0, 0, 1000).unwrap(); // exactly at budget
        l.record_epoch(2, 500, 0, 0, 1000).unwrap();  // under budget
        assert_eq!(l.over_budget_epochs(), 1);
    }

    #[test]
    fn verify_chain_valid() {
        let mut l = PeerBandwidthLog::new(1);
        for e in 1..=5u64 {
            l.record_epoch(e, e * 100, 0, 0, 1000).unwrap();
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    #[test]
    fn chain_links() {
        let mut l = PeerBandwidthLog::new(1);
        l.record_epoch(1, 100, 0, 0, 1000).unwrap();
        l.record_epoch(2, 200, 0, 0, 1000).unwrap();
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    // ── BandwidthRegistry ─────────────────────────────────────────────────────

    #[test]
    fn allow_within_budget() {
        let mut reg = BandwidthRegistry::new(1000);
        let d = reg.request_bytes(1, 1, 500);
        assert_eq!(d, BandwidthDecision::Allow);
        assert_eq!(reg.current_usage(1), Some(500));
    }

    #[test]
    fn throttle_when_overflow() {
        let mut reg = BandwidthRegistry::new(1000);
        reg.request_bytes(1, 1, 800);
        // 800 used, 300 more would overflow → Throttle
        let d = reg.request_bytes(1, 1, 300);
        assert_eq!(d, BandwidthDecision::Throttle);
    }

    #[test]
    fn deny_when_budget_exhausted() {
        let mut reg = BandwidthRegistry::new(1000);
        reg.request_bytes(1, 1, 1000);
        let d = reg.request_bytes(1, 1, 100);
        assert_eq!(d, BandwidthDecision::Deny);
    }

    #[test]
    fn epoch_reset_clears_usage() {
        let mut reg = BandwidthRegistry::new(1000);
        reg.request_bytes(1, 1, 900);
        // New epoch: budget reset
        let d = reg.request_bytes(1, 2, 900);
        assert_eq!(d, BandwidthDecision::Allow);
        assert_eq!(reg.current_usage(1), Some(900));
    }

    #[test]
    fn seal_epoch_records_in_log() {
        let mut reg = BandwidthRegistry::new(1000);
        reg.request_bytes(1, 1, 600);
        reg.seal_epoch(1).unwrap();
        let log = reg.get_log(1).unwrap();
        assert_eq!(log.len(), 1);
        assert_eq!(log.records()[0].bytes_allowed, 600);
    }

    #[test]
    fn multiple_peers_independent() {
        let mut reg = BandwidthRegistry::new(1000);
        reg.request_bytes(1, 1, 900);
        reg.request_bytes(2, 1, 900);
        assert_eq!(reg.peer_count(), 2);
        // peer 2 independent: 900 < 1000 → Allow
        assert_eq!(reg.current_usage(2), Some(900));
    }
}
