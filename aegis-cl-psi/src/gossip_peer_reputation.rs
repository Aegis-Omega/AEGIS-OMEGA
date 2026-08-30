//! Gate 398 — Gossip Peer Reputation Log (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks a per-peer reputation score updated each epoch. The score is an
//! integer in [0, 100]. Updates use saturating arithmetic:
//!   on_time delivery  → score.saturating_add(REPUTATION_REWARD)   (reward = 5)
//!   missed delivery   → score.saturating_sub(REPUTATION_PENALTY)  (penalty = 10)
//!   churn event       → score.saturating_sub(REPUTATION_CHURN_PENALTY) (churn = 3)
//! Score is clamped to [0, 100] after each update.
//!
//! ReputationClass: Trusted (score >= 80), Neutral (40..80), Untrusted (< 40).
//!
//! GossipPeerReputationEntry (hash-chained):
//!   peer_id:         u64
//!   epoch_end:       u64
//!   score:           u32  — [0, 100]
//!   reputation_class: ReputationClass
//!   delivered:       bool — whether this peer delivered on time this epoch
//!   churned:         bool — whether this peer had a churn event this epoch
//!   entry_hash:      [u8;32]
//!   prev_hash:       [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ peer_id_be8 ‖ epoch_end_be8 ‖ score_be4
//!                       ‖ class_byte ‖ delivered_byte ‖ churned_byte)
//!
//! GossipPeerReputationLog: record(peer_id, epoch_end, delivered, churned),
//!   score_for(peer_id), trusted_count(), untrusted_count(), verify_chain().

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const GOSSIP_PEER_REPUTATION_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const REPUTATION_INITIAL_SCORE:   u32 = 50;
pub const REPUTATION_REWARD:          u32 = 5;
pub const REPUTATION_PENALTY:         u32 = 10;
pub const REPUTATION_CHURN_PENALTY:   u32 = 3;
pub const REPUTATION_MAX:             u32 = 100;
pub const REPUTATION_TRUSTED_FLOOR:   u32 = 80;
pub const REPUTATION_UNTRUSTED_CEIL:  u32 = 40;

// ─── ReputationClass ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum ReputationClass {
    Trusted   = 0, // score >= 80
    Neutral   = 1, // 40 <= score < 80
    Untrusted = 2, // score < 40
}

impl ReputationClass {
    fn classify(score: u32) -> Self {
        if score >= REPUTATION_TRUSTED_FLOOR {
            ReputationClass::Trusted
        } else if score >= REPUTATION_UNTRUSTED_CEIL {
            ReputationClass::Neutral
        } else {
            ReputationClass::Untrusted
        }
    }
}

// ─── GossipPeerReputationEntry ────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPeerReputationEntry {
    pub peer_id:          u64,
    pub epoch_end:        u64,
    pub score:            u32,
    pub reputation_class: ReputationClass,
    pub delivered:        bool,
    pub churned:          bool,
    pub entry_hash:       [u8; 32],
    pub prev_hash:        [u8; 32],
}

fn compute_peer_reputation_hash(
    prev:             &[u8; 32],
    peer_id:          u64,
    epoch_end:        u64,
    score:            u32,
    reputation_class: ReputationClass,
    delivered:        bool,
    churned:          bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(epoch_end.to_be_bytes());
    h.update(score.to_be_bytes());
    h.update([reputation_class as u8]);
    h.update([delivered as u8]);
    h.update([churned as u8]);
    h.finalize().into()
}

// ─── GossipPeerReputationLog ──────────────────────────────────────────────────

pub struct GossipPeerReputationLog {
    entries: Vec<GossipPeerReputationEntry>,
    // per-peer current score for incremental updates
    peer_scores: BTreeMap<u64, u32>,
}

impl GossipPeerReputationLog {
    pub fn new() -> Self {
        Self {
            entries:     Vec::new(),
            peer_scores: BTreeMap::new(),
        }
    }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipPeerReputationEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipPeerReputationEntry> { self.entries.last() }

    /// Current score for a peer. Returns REPUTATION_INITIAL_SCORE if unseen.
    pub fn score_for(&self, peer_id: u64) -> u32 {
        *self.peer_scores.get(&peer_id).unwrap_or(&REPUTATION_INITIAL_SCORE)
    }

    /// Count of peers whose latest recorded score is Trusted (>= 80).
    pub fn trusted_count(&self) -> usize {
        self.peer_scores.values()
            .filter(|&&s| s >= REPUTATION_TRUSTED_FLOOR)
            .count()
    }

    /// Count of peers whose latest recorded score is Untrusted (< 40).
    pub fn untrusted_count(&self) -> usize {
        self.peer_scores.values()
            .filter(|&&s| s < REPUTATION_UNTRUSTED_CEIL)
            .count()
    }

    /// Record a reputation update for a peer in one epoch.
    /// Score starts at REPUTATION_INITIAL_SCORE for new peers.
    /// delivered=true → +REWARD; delivered=false → -PENALTY.
    /// churned=true → additional -CHURN_PENALTY.
    /// Score clamped to [0, REPUTATION_MAX].
    pub fn record(
        &mut self,
        peer_id:   u64,
        epoch_end: u64,
        delivered: bool,
        churned:   bool,
    ) -> &GossipPeerReputationEntry {
        let base = *self.peer_scores.get(&peer_id).unwrap_or(&REPUTATION_INITIAL_SCORE);
        let after_delivery = if delivered {
            base.saturating_add(REPUTATION_REWARD)
        } else {
            base.saturating_sub(REPUTATION_PENALTY)
        };
        let after_churn = if churned {
            after_delivery.saturating_sub(REPUTATION_CHURN_PENALTY)
        } else {
            after_delivery
        };
        let score = after_churn.min(REPUTATION_MAX);

        self.peer_scores.insert(peer_id, score);
        let reputation_class = ReputationClass::classify(score);

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_PEER_REPUTATION_GENESIS_HASH);

        let entry_hash = compute_peer_reputation_hash(
            &prev, peer_id, epoch_end, score, reputation_class, delivered, churned,
        );

        self.entries.push(GossipPeerReputationEntry {
            peer_id,
            epoch_end,
            score,
            reputation_class,
            delivered,
            churned,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_PEER_REPUTATION_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_peer_reputation_hash(
                &prev, e.peer_id, e.epoch_end, e.score,
                e.reputation_class, e.delivered, e.churned,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPeerReputationLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── score update logic ────────────────────────────────────────────────────

    #[test]
    fn new_peer_starts_at_initial_score() {
        let log = GossipPeerReputationLog::new();
        assert_eq!(log.score_for(42), REPUTATION_INITIAL_SCORE);
    }

    #[test]
    fn delivery_increases_score() {
        let mut log = GossipPeerReputationLog::new();
        let e = log.record(1, 1, true, false);
        assert_eq!(e.score, REPUTATION_INITIAL_SCORE + REPUTATION_REWARD);
    }

    #[test]
    fn miss_decreases_score() {
        let mut log = GossipPeerReputationLog::new();
        let e = log.record(1, 1, false, false);
        assert_eq!(e.score, REPUTATION_INITIAL_SCORE - REPUTATION_PENALTY);
    }

    #[test]
    fn churn_further_decreases_score() {
        let mut log = GossipPeerReputationLog::new();
        // delivered=false (-10) + churned=true (-3) = 50 - 10 - 3 = 37
        let e = log.record(1, 1, false, true);
        assert_eq!(e.score, REPUTATION_INITIAL_SCORE - REPUTATION_PENALTY - REPUTATION_CHURN_PENALTY);
    }

    #[test]
    fn score_clamped_at_max() {
        let mut log = GossipPeerReputationLog::new();
        // push score to max via many deliveries
        for i in 1u64..=20 { log.record(1, i, true, false); }
        assert_eq!(log.score_for(1), REPUTATION_MAX);
    }

    #[test]
    fn score_clamped_at_zero() {
        let mut log = GossipPeerReputationLog::new();
        // push score to zero via many misses
        for i in 1u64..=20 { log.record(1, i, false, true); }
        assert_eq!(log.score_for(1), 0);
    }

    #[test]
    fn scores_independent_per_peer() {
        let mut log = GossipPeerReputationLog::new();
        log.record(1, 1, true, false);   // peer 1: 55
        log.record(2, 1, false, false);  // peer 2: 40
        assert_eq!(log.score_for(1), 55);
        assert_eq!(log.score_for(2), 40);
    }

    // ── reputation_class ──────────────────────────────────────────────────────

    #[test]
    fn trusted_class_at_floor() {
        let mut log = GossipPeerReputationLog::new();
        // drive peer to score 80 (trusted floor)
        for i in 1u64..=6 { log.record(1, i, true, false); }  // 50+30=80
        assert_eq!(log.entries().last().unwrap().reputation_class, ReputationClass::Trusted);
    }

    #[test]
    fn neutral_class() {
        let mut log = GossipPeerReputationLog::new();
        // score 50 = initial → Neutral (40..80)
        let e = log.record(1, 1, true, true); // 50+5-3=52 → Neutral
        assert_eq!(e.reputation_class, ReputationClass::Neutral);
    }

    #[test]
    fn untrusted_class_below_ceil() {
        let mut log = GossipPeerReputationLog::new();
        // drive score below 40
        for i in 1u64..=2 { log.record(1, i, false, false); } // 50-10-10=30
        assert_eq!(log.entries().last().unwrap().reputation_class, ReputationClass::Untrusted);
    }

    // ── trusted/untrusted counts ──────────────────────────────────────────────

    #[test]
    fn trusted_and_untrusted_counts() {
        let mut log = GossipPeerReputationLog::new();
        for i in 1u64..=6 { log.record(1, i, true, false); }  // peer 1 → 80 (Trusted)
        for i in 1u64..=2 { log.record(2, i, false, false); } // peer 2 → 30 (Untrusted)
        assert_eq!(log.trusted_count(), 1);
        assert_eq!(log.untrusted_count(), 1);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipPeerReputationLog::new();
        let e = log.record(1, 1, true, false);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipPeerReputationLog::new();
        let e = log.record(1, 1, true, false);
        assert_eq!(e.prev_hash, GOSSIP_PEER_REPUTATION_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipPeerReputationLog::new();
        log.record(1, 1, true, false);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 2, false, true);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipPeerReputationLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipPeerReputationLog::new();
        for i in 1u64..=5 { log.record(i, i, i % 2 == 0, i % 3 == 0); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipPeerReputationLog::new();
        log.record(1, 1, true, false);
        log.record(2, 2, false, true);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipPeerReputationLog::new();
        let mut l2 = GossipPeerReputationLog::new();
        let h1 = l1.record(7, 3, true, false).entry_hash;
        let h2 = l2.record(7, 3, true, false).entry_hash;
        assert_eq!(h1, h2);
    }
}
