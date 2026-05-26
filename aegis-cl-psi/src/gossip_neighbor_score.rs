//! Gate 400 — Gossip Neighbor Score Log (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Per-peer per-epoch composite neighbor score combining three signals:
//!   latency_score:     u32  — inverse latency bucket: 0=high, 50=medium, 100=low latency
//!   reliability_score: u32  — delivery reliability percent [0, 100]
//!   stability_score:   u32  — 100 if no churn event, 0 if churned this epoch
//! composite_score = (latency_score + reliability_score + stability_score) / 3
//!   (integer division, rounds down).
//!
//! NeighborTier: Elite (composite >= 85), Active (50..85), Weak (< 50).
//!
//! GossipNeighborScoreEntry (hash-chained):
//!   peer_id:           u64
//!   epoch_end:         u64
//!   latency_score:     u32
//!   reliability_score: u32
//!   stability_score:   u32
//!   composite_score:   u32
//!   neighbor_tier:     NeighborTier
//!   entry_hash:        [u8;32]
//!   prev_hash:         [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ peer_id_be8 ‖ epoch_end_be8 ‖ latency_score_be4
//!                       ‖ reliability_score_be4 ‖ stability_score_be4
//!                       ‖ composite_score_be4 ‖ tier_byte)
//!
//! GossipNeighborScoreLog: record(...), score_for(peer_id),
//!   elite_count(), weak_count(), verify_chain().

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const GOSSIP_NEIGHBOR_SCORE_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const NEIGHBOR_ELITE_FLOOR: u32 = 85;
pub const NEIGHBOR_WEAK_CEIL:   u32 = 50;

// ─── NeighborTier ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum NeighborTier {
    Elite  = 0, // composite >= 85
    Active = 1, // 50 <= composite < 85
    Weak   = 2, // composite < 50
}

impl NeighborTier {
    fn classify(score: u32) -> Self {
        if score >= NEIGHBOR_ELITE_FLOOR {
            NeighborTier::Elite
        } else if score >= NEIGHBOR_WEAK_CEIL {
            NeighborTier::Active
        } else {
            NeighborTier::Weak
        }
    }
}

// ─── GossipNeighborScoreEntry ─────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipNeighborScoreEntry {
    pub peer_id:           u64,
    pub epoch_end:         u64,
    pub latency_score:     u32,
    pub reliability_score: u32,
    pub stability_score:   u32,
    pub composite_score:   u32,
    pub neighbor_tier:     NeighborTier,
    pub entry_hash:        [u8; 32],
    pub prev_hash:         [u8; 32],
}

fn compute_neighbor_score_hash(
    prev:              &[u8; 32],
    peer_id:           u64,
    epoch_end:         u64,
    latency_score:     u32,
    reliability_score: u32,
    stability_score:   u32,
    composite_score:   u32,
    neighbor_tier:     NeighborTier,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(epoch_end.to_be_bytes());
    h.update(latency_score.to_be_bytes());
    h.update(reliability_score.to_be_bytes());
    h.update(stability_score.to_be_bytes());
    h.update(composite_score.to_be_bytes());
    h.update([neighbor_tier as u8]);
    h.finalize().into()
}

// ─── GossipNeighborScoreLog ───────────────────────────────────────────────────

pub struct GossipNeighborScoreLog {
    entries: Vec<GossipNeighborScoreEntry>,
    // most recent composite score per peer
    peer_composites: BTreeMap<u64, u32>,
}

impl GossipNeighborScoreLog {
    pub fn new() -> Self {
        Self {
            entries:         Vec::new(),
            peer_composites: BTreeMap::new(),
        }
    }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipNeighborScoreEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipNeighborScoreEntry> { self.entries.last() }

    /// Most recent composite score for a peer. Returns 0 if unseen.
    pub fn score_for(&self, peer_id: u64) -> u32 {
        *self.peer_composites.get(&peer_id).unwrap_or(&0)
    }

    /// Count of peers whose latest composite score is Elite (>= 85).
    pub fn elite_count(&self) -> usize {
        self.peer_composites.values()
            .filter(|&&s| s >= NEIGHBOR_ELITE_FLOOR)
            .count()
    }

    /// Count of peers whose latest composite score is Weak (< 50).
    pub fn weak_count(&self) -> usize {
        self.peer_composites.values()
            .filter(|&&s| s < NEIGHBOR_WEAK_CEIL)
            .count()
    }

    /// Record neighbor scores for one peer in one epoch.
    /// composite_score = (latency + reliability + stability) / 3.
    pub fn record(
        &mut self,
        peer_id:           u64,
        epoch_end:         u64,
        latency_score:     u32,
        reliability_score: u32,
        stability_score:   u32,
    ) -> &GossipNeighborScoreEntry {
        let composite_score = (latency_score
            .saturating_add(reliability_score)
            .saturating_add(stability_score)) / 3;
        let neighbor_tier = NeighborTier::classify(composite_score);

        self.peer_composites.insert(peer_id, composite_score);

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_NEIGHBOR_SCORE_GENESIS_HASH);

        let entry_hash = compute_neighbor_score_hash(
            &prev, peer_id, epoch_end,
            latency_score, reliability_score, stability_score,
            composite_score, neighbor_tier,
        );

        self.entries.push(GossipNeighborScoreEntry {
            peer_id,
            epoch_end,
            latency_score,
            reliability_score,
            stability_score,
            composite_score,
            neighbor_tier,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_NEIGHBOR_SCORE_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_neighbor_score_hash(
                &prev, e.peer_id, e.epoch_end,
                e.latency_score, e.reliability_score, e.stability_score,
                e.composite_score, e.neighbor_tier,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipNeighborScoreLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipNeighborScoreLog::new();
        let e = log.record(1, 1, 90, 80, 100);
        assert_eq!(e.peer_id, 1);
        assert_eq!(e.latency_score, 90);
        assert_eq!(e.reliability_score, 80);
        assert_eq!(e.stability_score, 100);
        // composite = (90+80+100)/3 = 90
        assert_eq!(e.composite_score, 90);
    }

    #[test]
    fn composite_rounds_down() {
        let mut log = GossipNeighborScoreLog::new();
        // (70+80+90)/3 = 240/3 = 80
        let e = log.record(1, 1, 70, 80, 90);
        assert_eq!(e.composite_score, 80);
        // (70+70+71)/3 = 211/3 = 70
        let e2 = log.record(2, 1, 70, 70, 71);
        assert_eq!(e2.composite_score, 70);
    }

    // ── neighbor_tier ─────────────────────────────────────────────────────────

    #[test]
    fn elite_tier_at_floor() {
        let mut log = GossipNeighborScoreLog::new();
        // composite = (85+85+85)/3 = 85 → Elite
        let e = log.record(1, 1, 85, 85, 85);
        assert_eq!(e.composite_score, 85);
        assert_eq!(e.neighbor_tier, NeighborTier::Elite);
    }

    #[test]
    fn active_tier() {
        let mut log = GossipNeighborScoreLog::new();
        // composite = (50+60+70)/3 = 60 → Active
        let e = log.record(1, 1, 50, 60, 70);
        assert_eq!(e.neighbor_tier, NeighborTier::Active);
    }

    #[test]
    fn weak_tier_below_ceil() {
        let mut log = GossipNeighborScoreLog::new();
        // composite = (30+30+30)/3 = 30 → Weak
        let e = log.record(1, 1, 30, 30, 30);
        assert_eq!(e.neighbor_tier, NeighborTier::Weak);
    }

    #[test]
    fn churned_peer_gets_stability_zero() {
        let mut log = GossipNeighborScoreLog::new();
        // stability=0 (churned), latency=100, reliability=100 → composite=(100+100+0)/3=66 → Active
        let e = log.record(1, 1, 100, 100, 0);
        assert_eq!(e.composite_score, 66);
        assert_eq!(e.neighbor_tier, NeighborTier::Active);
    }

    // ── score_for / counts ────────────────────────────────────────────────────

    #[test]
    fn score_for_unseen_is_zero() {
        let log = GossipNeighborScoreLog::new();
        assert_eq!(log.score_for(99), 0);
    }

    #[test]
    fn scores_independent_per_peer() {
        let mut log = GossipNeighborScoreLog::new();
        log.record(1, 1, 90, 90, 90); // composite=90
        log.record(2, 1, 30, 30, 30); // composite=30
        assert_eq!(log.score_for(1), 90);
        assert_eq!(log.score_for(2), 30);
    }

    #[test]
    fn elite_and_weak_counts() {
        let mut log = GossipNeighborScoreLog::new();
        log.record(1, 1, 90, 90, 90); // 90 → Elite
        log.record(2, 1, 30, 30, 30); // 30 → Weak
        log.record(3, 1, 60, 60, 60); // 60 → Active
        assert_eq!(log.elite_count(), 1);
        assert_eq!(log.weak_count(), 1);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipNeighborScoreLog::new();
        let e = log.record(1, 1, 80, 80, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipNeighborScoreLog::new();
        let e = log.record(1, 1, 80, 80, 100);
        assert_eq!(e.prev_hash, GOSSIP_NEIGHBOR_SCORE_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipNeighborScoreLog::new();
        log.record(1, 1, 80, 80, 100);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 2, 60, 70, 100);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipNeighborScoreLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipNeighborScoreLog::new();
        for i in 1u64..=5 {
            log.record(i, i, i as u32 * 10, 80, 100);
        }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipNeighborScoreLog::new();
        log.record(1, 1, 80, 80, 100);
        log.record(2, 2, 60, 70, 100);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipNeighborScoreLog::new();
        let mut l2 = GossipNeighborScoreLog::new();
        let h1 = l1.record(5, 3, 70, 80, 100).entry_hash;
        let h2 = l2.record(5, 3, 70, 80, 100).entry_hash;
        assert_eq!(h1, h2);
    }
}
