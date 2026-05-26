//! Gate 387 — Gossip Reachability Map (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks per-peer reachability status (Reachable / Unreachable) per epoch
//! in a hash-chained event log. Provides aggregate reachable/unreachable
//! peer counts across the entire event history.
//!
//! GossipReachabilityEvent (hash-chained):
//!   peer_id:        u64
//!   epoch:          u64
//!   reachable:      bool  — true=Reachable, false=Unreachable
//!   event_hash:     [u8;32]
//!   prev_hash:      [u8;32]
//!
//! event_hash = SHA-256(prev[32] ‖ peer_id_be8 ‖ epoch_be8 ‖ reachable_byte)
//!
//! GossipReachabilityLog: mark_reachable(peer_id, epoch),
//!   mark_unreachable(peer_id, epoch), is_reachable(peer_id),
//!   reachable_count(), unreachable_count(), event_count(), verify_chain().
//!
//! Current status per peer is tracked in a BTreeMap (deterministic iteration).

use std::collections::BTreeMap;
use sha2::{Sha256, Digest};

pub const GOSSIP_REACH_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── GossipReachabilityEvent ──────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipReachabilityEvent {
    pub peer_id:    u64,
    pub epoch:      u64,
    pub reachable:  bool,
    pub event_hash: [u8; 32],
    pub prev_hash:  [u8; 32],
}

fn compute_reach_hash(
    prev:      &[u8; 32],
    peer_id:   u64,
    epoch:     u64,
    reachable: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update([reachable as u8]);
    h.finalize().into()
}

// ─── GossipReachabilityLog ────────────────────────────────────────────────────

pub struct GossipReachabilityLog {
    events:  Vec<GossipReachabilityEvent>,
    // BTreeMap: peer_id → current reachable status
    status:  BTreeMap<u64, bool>,
}

impl GossipReachabilityLog {
    pub fn new() -> Self {
        Self {
            events: Vec::new(),
            status: BTreeMap::new(),
        }
    }

    pub fn event_count(&self)    -> usize { self.events.len() }
    pub fn is_empty(&self)       -> bool  { self.events.is_empty() }
    pub fn events(&self)         -> &[GossipReachabilityEvent] { &self.events }
    pub fn latest(&self)         -> Option<&GossipReachabilityEvent> { self.events.last() }

    /// Current reachability of a peer. Returns None if peer never seen.
    pub fn is_reachable(&self, peer_id: u64) -> Option<bool> {
        self.status.get(&peer_id).copied()
    }

    /// Count of peers currently marked Reachable.
    pub fn reachable_count(&self) -> usize {
        self.status.values().filter(|&&r| r).count()
    }

    /// Count of peers currently marked Unreachable.
    pub fn unreachable_count(&self) -> usize {
        self.status.values().filter(|&&r| !r).count()
    }

    pub fn mark_reachable(&mut self, peer_id: u64, epoch: u64) -> &GossipReachabilityEvent {
        self.record_event(peer_id, epoch, true)
    }

    pub fn mark_unreachable(&mut self, peer_id: u64, epoch: u64) -> &GossipReachabilityEvent {
        self.record_event(peer_id, epoch, false)
    }

    fn record_event(&mut self, peer_id: u64, epoch: u64, reachable: bool) -> &GossipReachabilityEvent {
        self.status.insert(peer_id, reachable);

        let prev = self.events.last()
            .map(|e| e.event_hash)
            .unwrap_or(GOSSIP_REACH_GENESIS_HASH);

        let event_hash = compute_reach_hash(&prev, peer_id, epoch, reachable);

        self.events.push(GossipReachabilityEvent {
            peer_id,
            epoch,
            reachable,
            event_hash,
            prev_hash: prev,
        });
        self.events.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_REACH_GENESIS_HASH;
        for (i, e) in self.events.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_reach_hash(&prev, e.peer_id, e.epoch, e.reachable);
            if e.event_hash != expected {
                return (false, Some(i));
            }
            prev = e.event_hash;
        }
        (true, None)
    }
}

impl Default for GossipReachabilityLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── mark_reachable / mark_unreachable ─────────────────────────────────────

    #[test]
    fn mark_reachable_stores_status() {
        let mut log = GossipReachabilityLog::new();
        log.mark_reachable(1, 10);
        assert_eq!(log.is_reachable(1), Some(true));
    }

    #[test]
    fn mark_unreachable_stores_status() {
        let mut log = GossipReachabilityLog::new();
        log.mark_unreachable(2, 10);
        assert_eq!(log.is_reachable(2), Some(false));
    }

    #[test]
    fn status_updates_on_second_event() {
        let mut log = GossipReachabilityLog::new();
        log.mark_reachable(1, 10);
        log.mark_unreachable(1, 11);
        assert_eq!(log.is_reachable(1), Some(false));
    }

    #[test]
    fn unknown_peer_returns_none() {
        let log = GossipReachabilityLog::new();
        assert_eq!(log.is_reachable(99), None);
    }

    // ── aggregate counts ──────────────────────────────────────────────────────

    #[test]
    fn reachable_count_correct() {
        let mut log = GossipReachabilityLog::new();
        log.mark_reachable(1, 1);
        log.mark_reachable(2, 1);
        log.mark_unreachable(3, 1);
        assert_eq!(log.reachable_count(), 2);
        assert_eq!(log.unreachable_count(), 1);
    }

    #[test]
    fn counts_update_when_status_changes() {
        let mut log = GossipReachabilityLog::new();
        log.mark_reachable(1, 1);
        assert_eq!(log.reachable_count(), 1);
        log.mark_unreachable(1, 2);
        assert_eq!(log.reachable_count(), 0);
        assert_eq!(log.unreachable_count(), 1);
    }

    #[test]
    fn empty_log_counts_zero() {
        let log = GossipReachabilityLog::new();
        assert_eq!(log.reachable_count(), 0);
        assert_eq!(log.unreachable_count(), 0);
    }

    // ── event fields ──────────────────────────────────────────────────────────

    #[test]
    fn reachable_event_is_true() {
        let mut log = GossipReachabilityLog::new();
        let e = log.mark_reachable(5, 7);
        assert_eq!(e.peer_id, 5);
        assert_eq!(e.epoch, 7);
        assert!(e.reachable);
    }

    #[test]
    fn unreachable_event_is_false() {
        let mut log = GossipReachabilityLog::new();
        let e = log.mark_unreachable(3, 4);
        assert!(!e.reachable);
    }

    #[test]
    fn event_hash_nonzero() {
        let mut log = GossipReachabilityLog::new();
        let e = log.mark_reachable(1, 1);
        assert_ne!(e.event_hash, [0u8; 32]);
    }

    #[test]
    fn first_event_prev_hash_is_genesis() {
        let mut log = GossipReachabilityLog::new();
        let e = log.mark_reachable(1, 1);
        assert_eq!(e.prev_hash, GOSSIP_REACH_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipReachabilityLog::new();
        log.mark_reachable(1, 1);
        let h0 = log.events()[0].event_hash;
        log.mark_unreachable(2, 2);
        assert_eq!(log.events()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipReachabilityLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipReachabilityLog::new();
        for i in 1u64..=5 {
            if i % 2 == 0 { log.mark_reachable(i, i); } else { log.mark_unreachable(i, i); }
        }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipReachabilityLog::new();
        log.mark_reachable(1, 1);
        log.mark_unreachable(2, 2);
        log.events[0].event_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn event_hash_deterministic() {
        let mut l1 = GossipReachabilityLog::new();
        let mut l2 = GossipReachabilityLog::new();
        let h1 = l1.mark_reachable(3, 7).event_hash;
        let h2 = l2.mark_reachable(3, 7).event_hash;
        assert_eq!(h1, h2);
    }
}
