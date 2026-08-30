//! Gate 288 — Gossip Reputation Decay: epoch-based reputation erosion for inactive peers (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Peers that do not produce gossip activity within an epoch have their reputation
//! decremented by a configurable decay amount. Peers with no probed reachability
//! receive accelerated decay. Tracks per-peer decay history in a hash-linked log.
//!
//! DecayReason:
//!   Inactive          — peer produced no messages this epoch
//!   Unreachable       — peer produced no messages AND probe failed
//!   Overdue           — peer is behind expected gossip schedule by >2 epochs
//!
//! ReputationDecayRecord:
//!   peer_id           — u32
//!   epoch             — u64
//!   score_before      — u8 (0–100)
//!   score_after       — u8 (0–100, saturating)
//!   decay_amount      — u8
//!   reason            — DecayReason
//!   record_hash       — SHA-256(prev ‖ peer_be4 ‖ epoch_be8 ‖ before ‖ after ‖ decay ‖ reason_byte)
//!   prev_hash         — [u8; 32]
//!
//! PeerDecayLog: hash-chained ReputationDecayRecords per peer.
//!   record(), total_decayed(), avg_decay_per_epoch(), min_score(), verify_chain().
//!
//! DecayEngine: BTreeMap<peer_id, (PeerDecayLog, current_score)>.
//!   apply_decay(peer_id, epoch, reason) → ReputationDecayRecord
//!   bulk_decay(epoch, peer_reasons) — applies decay to multiple peers
//!   current_score(peer_id) → Option<u8>
//!   peers_below(threshold) → Vec<u32>

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const DECAY_INACTIVE:    u8 = 3;
pub const DECAY_UNREACHABLE: u8 = 8;
pub const DECAY_OVERDUE:     u8 = 5;
pub const INITIAL_SCORE:     u8 = 50;

// ─── Decay reason ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DecayReason {
    Inactive,
    Unreachable,
    Overdue,
}

impl DecayReason {
    pub fn reason_byte(self) -> u8 {
        match self {
            Self::Inactive    => 0,
            Self::Unreachable => 1,
            Self::Overdue     => 2,
        }
    }

    pub fn decay_amount(self) -> u8 {
        match self {
            Self::Inactive    => DECAY_INACTIVE,
            Self::Unreachable => DECAY_UNREACHABLE,
            Self::Overdue     => DECAY_OVERDUE,
        }
    }
}

// ─── Reputation decay record ──────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct ReputationDecayRecord {
    pub peer_id:      u32,
    pub epoch:        u64,
    pub score_before: u8,
    pub score_after:  u8,
    pub decay_amount: u8,
    pub reason:       DecayReason,
    pub record_hash:  [u8; 32],
    pub prev_hash:    [u8; 32],
}

pub const DECAY_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_decay_hash(
    peer_id:      u32,
    epoch:        u64,
    score_before: u8,
    score_after:  u8,
    decay_amount: u8,
    reason:       DecayReason,
    prev:         &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update([score_before, score_after, decay_amount, reason.reason_byte()]);
    h.finalize().into()
}

pub fn build_decay_record(
    peer_id:      u32,
    epoch:        u64,
    score_before: u8,
    reason:       DecayReason,
    prev_hash:    &[u8; 32],
) -> ReputationDecayRecord {
    let decay_amount = reason.decay_amount();
    let score_after  = score_before.saturating_sub(decay_amount);
    let record_hash  = compute_decay_hash(
        peer_id, epoch, score_before, score_after, decay_amount, reason, prev_hash,
    );
    ReputationDecayRecord {
        peer_id, epoch, score_before, score_after, decay_amount, reason,
        record_hash, prev_hash: *prev_hash,
    }
}

// ─── Peer decay log ────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct PeerDecayLog {
    peer_id: u32,
    records: Vec<ReputationDecayRecord>,
}

#[derive(Debug)]
pub enum DecayError {
    StaleEpoch,
}

impl PeerDecayLog {
    pub fn new(peer_id: u32) -> Self { Self { peer_id, records: Vec::new() } }

    pub fn len(&self)     -> usize { self.records.len() }
    pub fn is_empty(&self)-> bool  { self.records.is_empty() }
    pub fn records(&self) -> &[ReputationDecayRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(DECAY_GENESIS_HASH)
    }

    pub fn record(
        &mut self,
        epoch:        u64,
        score_before: u8,
        reason:       DecayReason,
    ) -> Result<&ReputationDecayRecord, DecayError> {
        if let Some(last) = self.records.last() {
            if epoch <= last.epoch { return Err(DecayError::StaleEpoch); }
        }
        let prev = self.last_hash();
        let r = build_decay_record(self.peer_id, epoch, score_before, reason, &prev);
        self.records.push(r);
        Ok(self.records.last().unwrap())
    }

    pub fn total_decayed(&self) -> u32 {
        self.records.iter().map(|r| r.decay_amount as u32).sum()
    }

    pub fn avg_decay_per_epoch(&self) -> u32 {
        if self.records.is_empty() { return 0; }
        self.total_decayed() / self.records.len() as u32
    }

    pub fn min_score(&self) -> Option<u8> {
        self.records.iter().map(|r| r.score_after).min()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = DECAY_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_decay_hash(
                r.peer_id, r.epoch, r.score_before, r.score_after,
                r.decay_amount, r.reason, &r.prev_hash,
            );
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

// ─── Decay engine ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
struct PeerState {
    log:           PeerDecayLog,
    current_score: u8,
}

#[derive(Debug, Clone)]
pub struct DecayEngine {
    peers: BTreeMap<u32, PeerState>,
}

impl DecayEngine {
    pub fn new() -> Self { Self { peers: BTreeMap::new() } }

    pub fn peer_count(&self) -> usize { self.peers.len() }

    /// Apply decay for a single peer at a given epoch.
    pub fn apply_decay(
        &mut self,
        peer_id: u32,
        epoch:   u64,
        reason:  DecayReason,
    ) -> Result<ReputationDecayRecord, DecayError> {
        let state = self.peers.entry(peer_id).or_insert_with(|| PeerState {
            log:           PeerDecayLog::new(peer_id),
            current_score: INITIAL_SCORE,
        });
        let score_before = state.current_score;
        let rec = state.log.record(epoch, score_before, reason)?;
        state.current_score = rec.score_after;
        Ok(rec.clone())
    }

    /// Apply decay to a batch of peers at the same epoch.
    /// Peers not in `peer_reasons` are not touched.
    pub fn bulk_decay(
        &mut self,
        epoch:        u64,
        peer_reasons: &[(u32, DecayReason)],
    ) -> Vec<Result<ReputationDecayRecord, DecayError>> {
        peer_reasons.iter()
            .map(|&(pid, reason)| self.apply_decay(pid, epoch, reason))
            .collect()
    }

    pub fn current_score(&self, peer_id: u32) -> Option<u8> {
        self.peers.get(&peer_id).map(|s| s.current_score)
    }

    /// All peers whose current score is strictly below the threshold.
    pub fn peers_below(&self, threshold: u8) -> Vec<u32> {
        self.peers.iter()
            .filter(|(_, s)| s.current_score < threshold)
            .map(|(&id, _)| id)
            .collect()
    }

    pub fn get_log(&self, peer_id: u32) -> Option<&PeerDecayLog> {
        self.peers.get(&peer_id).map(|s| &s.log)
    }
}

impl Default for DecayEngine {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── DecayReason ───────────────────────────────────────────────────────────

    #[test]
    fn reason_bytes() {
        assert_eq!(DecayReason::Inactive.reason_byte(),    0);
        assert_eq!(DecayReason::Unreachable.reason_byte(), 1);
        assert_eq!(DecayReason::Overdue.reason_byte(),     2);
    }

    #[test]
    fn decay_amounts() {
        assert_eq!(DecayReason::Inactive.decay_amount(),    DECAY_INACTIVE);
        assert_eq!(DecayReason::Unreachable.decay_amount(), DECAY_UNREACHABLE);
        assert_eq!(DecayReason::Overdue.decay_amount(),     DECAY_OVERDUE);
    }

    // ── build_decay_record ────────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let r = build_decay_record(1, 1, 50, DecayReason::Inactive, &DECAY_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_decay_record(1, 1, 50, DecayReason::Inactive, &DECAY_GENESIS_HASH);
        let r2 = build_decay_record(1, 1, 50, DecayReason::Inactive, &DECAY_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    #[test]
    fn score_after_saturates() {
        let r = build_decay_record(1, 1, 2, DecayReason::Unreachable, &DECAY_GENESIS_HASH);
        // DECAY_UNREACHABLE=8, score_before=2 → saturates at 0
        assert_eq!(r.score_after, 0);
        assert_eq!(r.decay_amount, DECAY_UNREACHABLE);
    }

    #[test]
    fn score_after_normal() {
        let r = build_decay_record(1, 1, 50, DecayReason::Inactive, &DECAY_GENESIS_HASH);
        assert_eq!(r.score_after, 50 - DECAY_INACTIVE);
    }

    // ── PeerDecayLog ──────────────────────────────────────────────────────────

    #[test]
    fn new_log_empty() {
        let l = PeerDecayLog::new(1);
        assert!(l.is_empty());
        assert_eq!(l.total_decayed(), 0);
        assert_eq!(l.avg_decay_per_epoch(), 0);
        assert_eq!(l.min_score(), None);
    }

    #[test]
    fn record_appends_and_chains() {
        let mut l = PeerDecayLog::new(1);
        l.record(1, 50, DecayReason::Inactive).unwrap();
        l.record(2, 47, DecayReason::Overdue).unwrap();
        assert_eq!(l.len(), 2);
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut l = PeerDecayLog::new(1);
        l.record(5, 50, DecayReason::Inactive).unwrap();
        assert!(matches!(l.record(4, 47, DecayReason::Inactive), Err(DecayError::StaleEpoch)));
    }

    #[test]
    fn total_decayed_sums() {
        let mut l = PeerDecayLog::new(1);
        l.record(1, 50, DecayReason::Inactive).unwrap();    // 3
        l.record(2, 47, DecayReason::Overdue).unwrap();     // 5
        l.record(3, 42, DecayReason::Unreachable).unwrap(); // 8
        assert_eq!(l.total_decayed(), 16);
    }

    #[test]
    fn min_score_tracked() {
        let mut l = PeerDecayLog::new(1);
        l.record(1, 50, DecayReason::Unreachable).unwrap(); // after=42
        l.record(2, 42, DecayReason::Unreachable).unwrap(); // after=34
        assert_eq!(l.min_score(), Some(34));
    }

    #[test]
    fn verify_chain_valid() {
        let mut l = PeerDecayLog::new(1);
        let mut score = 100u8;
        for e in 1..=5u64 {
            l.record(e, score, DecayReason::Inactive).unwrap();
            score = score.saturating_sub(DECAY_INACTIVE);
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    // ── DecayEngine ───────────────────────────────────────────────────────────

    #[test]
    fn initial_score_is_fifty() {
        let mut e = DecayEngine::new();
        e.apply_decay(1, 1, DecayReason::Inactive).unwrap();
        assert_eq!(e.current_score(1), Some(50 - DECAY_INACTIVE));
    }

    #[test]
    fn unknown_peer_returns_none() {
        let e = DecayEngine::new();
        assert_eq!(e.current_score(99), None);
    }

    #[test]
    fn multiple_decays_accumulate() {
        let mut e = DecayEngine::new();
        e.apply_decay(1, 1, DecayReason::Inactive).unwrap();
        e.apply_decay(1, 2, DecayReason::Inactive).unwrap();
        e.apply_decay(1, 3, DecayReason::Inactive).unwrap();
        assert_eq!(e.current_score(1), Some(50 - 3 * DECAY_INACTIVE));
    }

    #[test]
    fn peers_below_threshold() {
        let mut e = DecayEngine::new();
        // peer 1: start 50, decay by Unreachable×5 = 40 → 50-40=10
        for ep in 1..=5u64 {
            e.apply_decay(1, ep, DecayReason::Unreachable).unwrap();
        }
        // peer 2: single Inactive → 50-3=47
        e.apply_decay(2, 1, DecayReason::Inactive).unwrap();
        let below = e.peers_below(20);
        assert_eq!(below, vec![1]);
    }

    #[test]
    fn bulk_decay_applies_all() {
        let mut e = DecayEngine::new();
        let pairs = vec![
            (1u32, DecayReason::Inactive),
            (2u32, DecayReason::Overdue),
            (3u32, DecayReason::Unreachable),
        ];
        let results = e.bulk_decay(1, &pairs);
        assert!(results.iter().all(|r| r.is_ok()));
        assert_eq!(e.peer_count(), 3);
        assert_eq!(e.current_score(1), Some(50 - DECAY_INACTIVE));
        assert_eq!(e.current_score(2), Some(50 - DECAY_OVERDUE));
        assert_eq!(e.current_score(3), Some(50 - DECAY_UNREACHABLE));
    }

    #[test]
    fn score_saturates_at_zero() {
        let mut e = DecayEngine::new();
        for ep in 1..=20u64 {
            e.apply_decay(1, ep, DecayReason::Unreachable).unwrap();
        }
        assert_eq!(e.current_score(1), Some(0));
    }

    #[test]
    fn get_log_accessible() {
        let mut e = DecayEngine::new();
        e.apply_decay(1, 1, DecayReason::Inactive).unwrap();
        let log = e.get_log(1).unwrap();
        assert_eq!(log.len(), 1);
    }
}
