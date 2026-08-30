//! Gate 382 — Gossip Peer Score Tracker (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Maintains a per-peer delivery reliability score as a hash-chained event log.
//! Each score event records whether a peer successfully delivered a gossip frame
//! (hit) or failed (miss). The running score is an integer percentage:
//!
//!   score_pct = floor(hits * 100 / max(total, 1))
//!
//! GossipPeerScoreEvent (hash-chained):
//!   peer_id:      u64
//!   epoch:        u64
//!   is_hit:       bool (1=delivered, 0=missed)
//!   hits:         u64  — cumulative hits for this peer
//!   total:        u64  — cumulative attempts for this peer
//!   score_pct:    u32  — floor(hits * 100 / max(total, 1))
//!   event_hash:   [u8;32]
//!   prev_hash:    [u8;32]
//!
//! event_hash = SHA-256(prev[32] ‖ peer_id_be8 ‖ epoch_be8 ‖ is_hit_byte
//!                        ‖ hits_be8 ‖ total_be8 ‖ score_pct_be4)
//!
//! GossipPeerScoreLog: record_hit(peer_id, epoch), record_miss(peer_id, epoch),
//!   score_for(peer_id), latest(), event_count(), verify_chain().

use std::collections::BTreeMap;
use sha2::{Sha256, Digest};

pub const GOSSIP_SCORE_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── GossipPeerScoreEvent ─────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPeerScoreEvent {
    pub peer_id:    u64,
    pub epoch:      u64,
    pub is_hit:     bool,
    pub hits:       u64,
    pub total:      u64,
    pub score_pct:  u32,
    pub event_hash: [u8; 32],
    pub prev_hash:  [u8; 32],
}

fn compute_score_hash(
    prev:      &[u8; 32],
    peer_id:   u64,
    epoch:     u64,
    is_hit:    bool,
    hits:      u64,
    total:     u64,
    score_pct: u32,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update([is_hit as u8]);
    h.update(hits.to_be_bytes());
    h.update(total.to_be_bytes());
    h.update(score_pct.to_be_bytes());
    h.finalize().into()
}

// ─── GossipPeerScoreLog ───────────────────────────────────────────────────────

pub struct GossipPeerScoreLog {
    events:  Vec<GossipPeerScoreEvent>,
    // BTreeMap for deterministic iteration; key = peer_id
    totals:  BTreeMap<u64, (u64, u64)>, // (hits, total)
}

impl GossipPeerScoreLog {
    pub fn new() -> Self {
        Self {
            events: Vec::new(),
            totals: BTreeMap::new(),
        }
    }

    pub fn event_count(&self) -> usize { self.events.len() }
    pub fn is_empty(&self)    -> bool  { self.events.is_empty() }
    pub fn events(&self)      -> &[GossipPeerScoreEvent] { &self.events }
    pub fn latest(&self)      -> Option<&GossipPeerScoreEvent> { self.events.last() }

    /// Current score_pct for a given peer. Returns 0 if peer unknown.
    pub fn score_for(&self, peer_id: u64) -> u32 {
        match self.totals.get(&peer_id) {
            None => 0,
            Some(&(hits, total)) => {
                if total == 0 { 0 } else { (hits * 100 / total) as u32 }
            }
        }
    }

    /// Record a successful delivery (hit) for a peer.
    pub fn record_hit(&mut self, peer_id: u64, epoch: u64) -> &GossipPeerScoreEvent {
        self.record_event(peer_id, epoch, true)
    }

    /// Record a missed delivery (miss) for a peer.
    pub fn record_miss(&mut self, peer_id: u64, epoch: u64) -> &GossipPeerScoreEvent {
        self.record_event(peer_id, epoch, false)
    }

    fn record_event(&mut self, peer_id: u64, epoch: u64, is_hit: bool) -> &GossipPeerScoreEvent {
        let (hits, total) = self.totals.entry(peer_id).or_insert((0, 0));
        if is_hit { *hits += 1; }
        *total += 1;
        let (hits, total) = (*hits, *total);
        let score_pct = (hits * 100 / total) as u32;

        let prev = self.events.last()
            .map(|e| e.event_hash)
            .unwrap_or(GOSSIP_SCORE_GENESIS_HASH);

        let event_hash = compute_score_hash(
            &prev, peer_id, epoch, is_hit, hits, total, score_pct,
        );

        self.events.push(GossipPeerScoreEvent {
            peer_id,
            epoch,
            is_hit,
            hits,
            total,
            score_pct,
            event_hash,
            prev_hash: prev,
        });
        self.events.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_SCORE_GENESIS_HASH;
        for (i, e) in self.events.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_score_hash(
                &prev,
                e.peer_id,
                e.epoch,
                e.is_hit,
                e.hits,
                e.total,
                e.score_pct,
            );
            if e.event_hash != expected {
                return (false, Some(i));
            }
            prev = e.event_hash;
        }
        (true, None)
    }
}

impl Default for GossipPeerScoreLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── score computation ─────────────────────────────────────────────────────

    #[test]
    fn first_hit_score_100() {
        let mut log = GossipPeerScoreLog::new();
        let e = log.record_hit(1, 10);
        assert_eq!(e.score_pct, 100);
        assert_eq!(e.hits, 1);
        assert_eq!(e.total, 1);
    }

    #[test]
    fn first_miss_score_0() {
        let mut log = GossipPeerScoreLog::new();
        let e = log.record_miss(1, 10);
        assert_eq!(e.score_pct, 0);
        assert_eq!(e.hits, 0);
        assert_eq!(e.total, 1);
    }

    #[test]
    fn score_floor_division() {
        let mut log = GossipPeerScoreLog::new();
        // 2 hits then 1 miss → 2/3 * 100 = 66 (floor)
        log.record_hit(1, 1);
        log.record_hit(1, 2);
        let e = log.record_miss(1, 3);
        assert_eq!(e.score_pct, 66);
    }

    #[test]
    fn score_for_unknown_peer_is_0() {
        let log = GossipPeerScoreLog::new();
        assert_eq!(log.score_for(99), 0);
    }

    #[test]
    fn score_for_known_peer() {
        let mut log = GossipPeerScoreLog::new();
        log.record_hit(5, 1);
        log.record_hit(5, 2);
        log.record_miss(5, 3);
        log.record_miss(5, 4);
        // 2/4 = 50
        assert_eq!(log.score_for(5), 50);
    }

    // ── multiple peers tracked independently ──────────────────────────────────

    #[test]
    fn two_peers_tracked_independently() {
        let mut log = GossipPeerScoreLog::new();
        log.record_hit(1, 1);
        log.record_miss(2, 1);
        assert_eq!(log.score_for(1), 100);
        assert_eq!(log.score_for(2), 0);
    }

    #[test]
    fn peer_cumulative_accumulates() {
        let mut log = GossipPeerScoreLog::new();
        for _ in 0..10 { log.record_hit(1, 1); }
        let e = log.record_miss(1, 2);
        assert_eq!(e.hits, 10);
        assert_eq!(e.total, 11);
        // floor(10/11 * 100) = floor(90.9) = 90
        assert_eq!(e.score_pct, 90);
    }

    // ── event fields ──────────────────────────────────────────────────────────

    #[test]
    fn record_hit_fields() {
        let mut log = GossipPeerScoreLog::new();
        let e = log.record_hit(7, 42);
        assert_eq!(e.peer_id, 7);
        assert_eq!(e.epoch, 42);
        assert!(e.is_hit);
    }

    #[test]
    fn record_miss_is_not_hit() {
        let mut log = GossipPeerScoreLog::new();
        let e = log.record_miss(3, 5);
        assert!(!e.is_hit);
    }

    #[test]
    fn event_hash_nonzero() {
        let mut log = GossipPeerScoreLog::new();
        let e = log.record_hit(1, 1);
        assert_ne!(e.event_hash, [0u8; 32]);
    }

    #[test]
    fn first_event_prev_hash_is_genesis() {
        let mut log = GossipPeerScoreLog::new();
        let e = log.record_hit(1, 1);
        assert_eq!(e.prev_hash, GOSSIP_SCORE_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipPeerScoreLog::new();
        log.record_hit(1, 1);
        let h0 = log.events()[0].event_hash;
        log.record_miss(1, 2);
        assert_eq!(log.events()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipPeerScoreLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipPeerScoreLog::new();
        for i in 1u64..=5 { log.record_hit(i % 2 + 1, i); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipPeerScoreLog::new();
        log.record_hit(1, 1);
        log.record_miss(1, 2);
        log.events[0].event_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn event_hash_deterministic() {
        let mut l1 = GossipPeerScoreLog::new();
        let mut l2 = GossipPeerScoreLog::new();
        let h1 = l1.record_hit(3, 7).event_hash;
        let h2 = l2.record_hit(3, 7).event_hash;
        assert_eq!(h1, h2);
    }
}
