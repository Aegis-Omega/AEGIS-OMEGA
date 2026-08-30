//! Gate 297 — Gossip Epoch Boundary Detector: network-wide epoch transition coordination (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Detects when the gossip network is crossing an epoch boundary by tracking
//! the highest epoch seen from each peer. When a quorum (>= BOUNDARY_QUORUM_PCT%)
//! of seen peers have advanced beyond the current epoch, a BoundaryEvent is emitted.
//!
//! Constants:
//!   BOUNDARY_QUORUM_PCT: u8 = 67  (percent of peers that must have advanced)
//!
//! BoundaryPhase:
//!   Stable      — no epoch transition in progress
//!   Transitioning — quorum advancing, boundary imminent
//!   Committed   — all tracked peers have advanced; epoch is finalized
//!
//! BoundaryEvent:
//!   old_epoch    — u64
//!   new_epoch    — u64
//!   phase        — BoundaryPhase
//!   peers_advanced  — u32
//!   peers_total     — u32
//!   event_hash   — SHA-256(prev ‖ old_be8 ‖ new_be8 ‖ adv_be4 ‖ tot_be4 ‖ phase_byte)
//!   prev_hash    — [u8; 32]
//!
//! BoundaryLog: hash-chained BoundaryEvents.
//!   record(), transition_count(), committed_count(), verify_chain().
//!
//! EpochBoundaryDetector:
//!   report_peer_epoch(peer_id, epoch) — update peer's highest seen epoch
//!   evaluate(current_epoch) → BoundaryPhase — assess transition state
//!   trigger_boundary(old_epoch, new_epoch) → records BoundaryEvent
//!   get_phase(), peers_total(), peers_advanced(epoch)

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const BOUNDARY_QUORUM_PCT: u8 = 67;

// ─── Boundary phase ───────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BoundaryPhase {
    Stable        = 0,
    Transitioning = 1,
    Committed     = 2,
}

impl BoundaryPhase {
    pub fn phase_byte(self) -> u8 { self as u8 }
}

// ─── Boundary event ───────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct BoundaryEvent {
    pub old_epoch:      u64,
    pub new_epoch:      u64,
    pub phase:          BoundaryPhase,
    pub peers_advanced: u32,
    pub peers_total:    u32,
    pub event_hash:     [u8; 32],
    pub prev_hash:      [u8; 32],
}

pub const BOUNDARY_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_boundary_hash(
    old_epoch:      u64,
    new_epoch:      u64,
    phase:          BoundaryPhase,
    peers_advanced: u32,
    peers_total:    u32,
    prev:           &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(old_epoch.to_be_bytes());
    h.update(new_epoch.to_be_bytes());
    h.update(peers_advanced.to_be_bytes());
    h.update(peers_total.to_be_bytes());
    h.update([phase.phase_byte()]);
    h.finalize().into()
}

pub fn build_boundary_event(
    old_epoch:      u64,
    new_epoch:      u64,
    phase:          BoundaryPhase,
    peers_advanced: u32,
    peers_total:    u32,
    prev_hash:      &[u8; 32],
) -> BoundaryEvent {
    let event_hash = compute_boundary_hash(old_epoch, new_epoch, phase, peers_advanced, peers_total, prev_hash);
    BoundaryEvent { old_epoch, new_epoch, phase, peers_advanced, peers_total, event_hash, prev_hash: *prev_hash }
}

// ─── Boundary log ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct BoundaryLog {
    events: Vec<BoundaryEvent>,
}

#[derive(Debug)]
pub enum BoundaryError {
    EpochNotAdvancing,
}

impl BoundaryLog {
    pub fn new() -> Self { Self { events: Vec::new() } }

    pub fn len(&self)      -> usize { self.events.len() }
    pub fn is_empty(&self) -> bool  { self.events.is_empty() }
    pub fn events(&self)   -> &[BoundaryEvent] { &self.events }

    pub fn last_hash(&self) -> [u8; 32] {
        self.events.last().map(|e| e.event_hash).unwrap_or(BOUNDARY_GENESIS_HASH)
    }

    pub fn record(
        &mut self,
        old_epoch:      u64,
        new_epoch:      u64,
        phase:          BoundaryPhase,
        peers_advanced: u32,
        peers_total:    u32,
    ) -> Result<&BoundaryEvent, BoundaryError> {
        if new_epoch <= old_epoch { return Err(BoundaryError::EpochNotAdvancing); }
        let prev = self.last_hash();
        let e = build_boundary_event(old_epoch, new_epoch, phase, peers_advanced, peers_total, &prev);
        self.events.push(e);
        Ok(self.events.last().unwrap())
    }

    pub fn transition_count(&self) -> usize {
        self.events.iter().filter(|e| e.phase == BoundaryPhase::Transitioning).count()
    }

    pub fn committed_count(&self) -> usize {
        self.events.iter().filter(|e| e.phase == BoundaryPhase::Committed).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = BOUNDARY_GENESIS_HASH;
        for (i, e) in self.events.iter().enumerate() {
            if e.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_boundary_hash(
                e.old_epoch, e.new_epoch, e.phase, e.peers_advanced, e.peers_total, &e.prev_hash,
            );
            if recomputed != e.event_hash { return (false, Some(i)); }
            expected_prev = e.event_hash;
        }
        (true, None)
    }
}

impl Default for BoundaryLog {
    fn default() -> Self { Self::new() }
}

// ─── Epoch boundary detector ──────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct EpochBoundaryDetector {
    peer_epochs: BTreeMap<u32, u64>,
    pub log:     BoundaryLog,
}

impl EpochBoundaryDetector {
    pub fn new() -> Self { Self { peer_epochs: BTreeMap::new(), log: BoundaryLog::new() } }

    /// Record the highest epoch seen from a peer.
    pub fn report_peer_epoch(&mut self, peer_id: u32, epoch: u64) {
        let e = self.peer_epochs.entry(peer_id).or_insert(0);
        if epoch > *e { *e = epoch; }
    }

    pub fn peers_total(&self) -> u32 { self.peer_epochs.len() as u32 }

    /// Count peers whose highest seen epoch is > current_epoch.
    pub fn peers_advanced(&self, current_epoch: u64) -> u32 {
        self.peer_epochs.values().filter(|&&e| e > current_epoch).count() as u32
    }

    /// Evaluate boundary phase for the given current_epoch.
    pub fn evaluate(&self, current_epoch: u64) -> BoundaryPhase {
        let total    = self.peers_total();
        if total == 0 { return BoundaryPhase::Stable; }
        let advanced = self.peers_advanced(current_epoch);
        if advanced == total {
            BoundaryPhase::Committed
        } else if advanced * 100 >= total * BOUNDARY_QUORUM_PCT as u32 {
            BoundaryPhase::Transitioning
        } else {
            BoundaryPhase::Stable
        }
    }

    /// Record a boundary event for the transition old_epoch → new_epoch.
    pub fn trigger_boundary(
        &mut self,
        old_epoch: u64,
        new_epoch: u64,
    ) -> Result<BoundaryPhase, BoundaryError> {
        let phase    = self.evaluate(old_epoch);
        let advanced = self.peers_advanced(old_epoch);
        let total    = self.peers_total();
        self.log.record(old_epoch, new_epoch, phase, advanced, total)?;
        Ok(phase)
    }
}

impl Default for EpochBoundaryDetector {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── BoundaryPhase ─────────────────────────────────────────────────────────

    #[test]
    fn phase_bytes() {
        assert_eq!(BoundaryPhase::Stable.phase_byte(),        0);
        assert_eq!(BoundaryPhase::Transitioning.phase_byte(), 1);
        assert_eq!(BoundaryPhase::Committed.phase_byte(),     2);
    }

    // ── build_boundary_event ──────────────────────────────────────────────────

    #[test]
    fn event_hash_nonzero() {
        let e = build_boundary_event(1, 2, BoundaryPhase::Committed, 3, 3, &BOUNDARY_GENESIS_HASH);
        assert_ne!(e.event_hash, [0u8; 32]);
    }

    #[test]
    fn event_hash_deterministic() {
        let e1 = build_boundary_event(1, 2, BoundaryPhase::Committed, 3, 3, &BOUNDARY_GENESIS_HASH);
        let e2 = build_boundary_event(1, 2, BoundaryPhase::Committed, 3, 3, &BOUNDARY_GENESIS_HASH);
        assert_eq!(e1.event_hash, e2.event_hash);
    }

    // ── BoundaryLog ───────────────────────────────────────────────────────────

    #[test]
    fn new_log_empty() {
        let l = BoundaryLog::new();
        assert!(l.is_empty());
        assert_eq!(l.transition_count(), 0);
        assert_eq!(l.committed_count(), 0);
    }

    #[test]
    fn log_counts_phases() {
        let mut l = BoundaryLog::new();
        l.record(1, 2, BoundaryPhase::Transitioning, 2, 3).unwrap();
        l.record(2, 3, BoundaryPhase::Committed, 3, 3).unwrap();
        assert_eq!(l.transition_count(), 1);
        assert_eq!(l.committed_count(), 1);
    }

    #[test]
    fn epoch_not_advancing_rejected() {
        let mut l = BoundaryLog::new();
        assert!(matches!(l.record(5, 5, BoundaryPhase::Stable, 0, 3), Err(BoundaryError::EpochNotAdvancing)));
        assert!(matches!(l.record(5, 4, BoundaryPhase::Stable, 0, 3), Err(BoundaryError::EpochNotAdvancing)));
    }

    #[test]
    fn chain_links() {
        let mut l = BoundaryLog::new();
        l.record(1, 2, BoundaryPhase::Committed, 3, 3).unwrap();
        l.record(2, 3, BoundaryPhase::Committed, 3, 3).unwrap();
        assert_eq!(l.events()[1].prev_hash, l.events()[0].event_hash);
    }

    #[test]
    fn verify_chain_valid() {
        let mut l = BoundaryLog::new();
        for e in 1..=5u64 {
            l.record(e, e+1, BoundaryPhase::Committed, 3, 3).unwrap();
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    // ── EpochBoundaryDetector ─────────────────────────────────────────────────

    #[test]
    fn no_peers_is_stable() {
        let d = EpochBoundaryDetector::new();
        assert_eq!(d.evaluate(1), BoundaryPhase::Stable);
    }

    #[test]
    fn all_peers_advanced_is_committed() {
        let mut d = EpochBoundaryDetector::new();
        d.report_peer_epoch(1, 2);
        d.report_peer_epoch(2, 2);
        d.report_peer_epoch(3, 2);
        assert_eq!(d.evaluate(1), BoundaryPhase::Committed);
    }

    #[test]
    fn quorum_advanced_is_transitioning() {
        let mut d = EpochBoundaryDetector::new();
        // 3 of 4 peers advanced = 75% >= 67% → Transitioning (not Committed since peer 4 is behind)
        d.report_peer_epoch(1, 2);
        d.report_peer_epoch(2, 2);
        d.report_peer_epoch(3, 2);
        d.report_peer_epoch(4, 1); // still on old epoch
        assert_eq!(d.evaluate(1), BoundaryPhase::Transitioning);
    }

    #[test]
    fn below_quorum_is_stable() {
        let mut d = EpochBoundaryDetector::new();
        // 1/3 = 33% < 67% → Stable
        d.report_peer_epoch(1, 2);
        d.report_peer_epoch(2, 1);
        d.report_peer_epoch(3, 1);
        assert_eq!(d.evaluate(1), BoundaryPhase::Stable);
    }

    #[test]
    fn peers_advanced_counts_correctly() {
        let mut d = EpochBoundaryDetector::new();
        d.report_peer_epoch(1, 5);
        d.report_peer_epoch(2, 3);
        d.report_peer_epoch(3, 3);
        assert_eq!(d.peers_advanced(3), 1); // only peer 1 advanced beyond epoch 3
    }

    #[test]
    fn report_only_updates_if_higher() {
        let mut d = EpochBoundaryDetector::new();
        d.report_peer_epoch(1, 5);
        d.report_peer_epoch(1, 3); // lower → no change
        assert_eq!(d.peers_advanced(4), 1); // peer 1 still at epoch 5
    }

    #[test]
    fn trigger_boundary_records_event() {
        let mut d = EpochBoundaryDetector::new();
        d.report_peer_epoch(1, 2);
        d.report_peer_epoch(2, 2);
        d.report_peer_epoch(3, 2);
        let phase = d.trigger_boundary(1, 2).unwrap();
        assert_eq!(phase, BoundaryPhase::Committed);
        assert_eq!(d.log.len(), 1);
    }
}
