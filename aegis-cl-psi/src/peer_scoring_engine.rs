//! Gate 300 — Gossip Peer Scoring Engine: composite peer quality scoring for selection decisions (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Combines four sub-scores into a composite [0..100] peer quality score:
//!   latency_score    — Excellent=25, Good=20, Fair=12, Poor=5, Timeout=0
//!   reputation_score — (reputation_pct × 25) / 100  [0..25]
//!   delivery_score   — (delivery_pct × 25) / 100    [0..25]
//!   uptime_score     — (min(uptime_epochs, 100) × 25) / 100  [0..25]
//!
//! composite = latency + reputation + delivery + uptime (saturating at 100)
//!
//! Constants:
//!   SCORE_LATENCY_EXCELLENT: u8 = 25
//!   SCORE_LATENCY_GOOD:      u8 = 20
//!   SCORE_LATENCY_FAIR:      u8 = 12
//!   SCORE_LATENCY_POOR:      u8 = 5
//!   SCORE_MAX_SUB:           u8 = 25
//!   SCORE_MAX:               u8 = 100
//!   UPTIME_CAP_EPOCHS:       u32 = 100
//!
//! ScoreRecord:
//!   peer_id, epoch, latency_tier, reputation_pct, delivery_pct, uptime_epochs,
//!   composite_score, record_hash, prev_hash
//!   record_hash = SHA-256(prev ‖ peer_be4 ‖ epoch_be8 ‖ lat ‖ rep ‖ del ‖ uptime_be4 ‖ composite)
//!
//! ScoreLog: hash-chained ScoreRecords per peer.
//!   record(), avg_score(), min_score(), max_score(), verify_chain().
//!
//! PeerScoringEngine:
//!   update_score(peer_id, epoch, latency_tier, reputation_pct, delivery_pct, uptime_epochs) → ScoreRecord
//!   composite_score(peer_id) → Option<u8>
//!   top_peers(n) → Vec<u32>  (sorted composite DESC, peer_id ASC on tie)
//!   all_scores() → Vec<(u32, u8)>

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const SCORE_LATENCY_EXCELLENT: u8 = 25;
pub const SCORE_LATENCY_GOOD:      u8 = 20;
pub const SCORE_LATENCY_FAIR:      u8 = 12;
pub const SCORE_LATENCY_POOR:      u8 = 5;
pub const SCORE_MAX_SUB:           u8 = 25;
pub const SCORE_MAX:               u8 = 100;
pub const UPTIME_CAP_EPOCHS:       u32 = 100;

// ─── Sub-score helpers ────────────────────────────────────────────────────────

/// Map a LatencyTier byte (0=Excellent … 4=Timeout) to its sub-score contribution.
pub fn latency_tier_score(tier_byte: u8) -> u8 {
    match tier_byte {
        0 => SCORE_LATENCY_EXCELLENT,
        1 => SCORE_LATENCY_GOOD,
        2 => SCORE_LATENCY_FAIR,
        3 => SCORE_LATENCY_POOR,
        _ => 0,
    }
}

pub fn reputation_sub_score(reputation_pct: u8) -> u8 {
    (reputation_pct as u32 * SCORE_MAX_SUB as u32 / 100) as u8
}

pub fn delivery_sub_score(delivery_pct: u8) -> u8 {
    (delivery_pct as u32 * SCORE_MAX_SUB as u32 / 100) as u8
}

pub fn uptime_sub_score(uptime_epochs: u32) -> u8 {
    let capped = uptime_epochs.min(UPTIME_CAP_EPOCHS);
    (capped * SCORE_MAX_SUB as u32 / UPTIME_CAP_EPOCHS) as u8
}

pub fn compute_composite(
    latency_tier:   u8,
    reputation_pct: u8,
    delivery_pct:   u8,
    uptime_epochs:  u32,
) -> u8 {
    let lat = latency_tier_score(latency_tier) as u32;
    let rep = reputation_sub_score(reputation_pct) as u32;
    let del = delivery_sub_score(delivery_pct) as u32;
    let upt = uptime_sub_score(uptime_epochs) as u32;
    (lat + rep + del + upt).min(SCORE_MAX as u32) as u8
}

// ─── Score record ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct ScoreRecord {
    pub peer_id:         u32,
    pub epoch:           u64,
    pub latency_tier:    u8,
    pub reputation_pct:  u8,
    pub delivery_pct:    u8,
    pub uptime_epochs:   u32,
    pub composite_score: u8,
    pub record_hash:     [u8; 32],
    pub prev_hash:       [u8; 32],
}

pub const SCORE_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_score_hash(
    peer_id:         u32,
    epoch:           u64,
    latency_tier:    u8,
    reputation_pct:  u8,
    delivery_pct:    u8,
    uptime_epochs:   u32,
    composite_score: u8,
    prev:            &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update([latency_tier, reputation_pct, delivery_pct]);
    h.update(uptime_epochs.to_be_bytes());
    h.update([composite_score]);
    h.finalize().into()
}

pub fn build_score_record(
    peer_id:        u32,
    epoch:          u64,
    latency_tier:   u8,
    reputation_pct: u8,
    delivery_pct:   u8,
    uptime_epochs:  u32,
    prev_hash:      &[u8; 32],
) -> ScoreRecord {
    let composite_score = compute_composite(latency_tier, reputation_pct, delivery_pct, uptime_epochs);
    let record_hash = compute_score_hash(
        peer_id, epoch, latency_tier, reputation_pct, delivery_pct,
        uptime_epochs, composite_score, prev_hash,
    );
    ScoreRecord {
        peer_id, epoch, latency_tier, reputation_pct, delivery_pct,
        uptime_epochs, composite_score, record_hash, prev_hash: *prev_hash,
    }
}

// ─── Score log ────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct ScoreLog {
    peer_id: u32,
    records: Vec<ScoreRecord>,
}

impl ScoreLog {
    pub fn new(peer_id: u32) -> Self { Self { peer_id, records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[ScoreRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(SCORE_GENESIS_HASH)
    }

    pub fn record(
        &mut self,
        epoch:          u64,
        latency_tier:   u8,
        reputation_pct: u8,
        delivery_pct:   u8,
        uptime_epochs:  u32,
    ) -> &ScoreRecord {
        let prev = self.last_hash();
        let r = build_score_record(
            self.peer_id, epoch, latency_tier, reputation_pct,
            delivery_pct, uptime_epochs, &prev,
        );
        self.records.push(r);
        self.records.last().unwrap()
    }

    pub fn avg_score(&self) -> u8 {
        if self.records.is_empty() { return 0; }
        let sum: u32 = self.records.iter().map(|r| r.composite_score as u32).sum();
        (sum / self.records.len() as u32) as u8
    }

    pub fn min_score(&self) -> Option<u8> {
        self.records.iter().map(|r| r.composite_score).min()
    }

    pub fn max_score(&self) -> Option<u8> {
        self.records.iter().map(|r| r.composite_score).max()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = SCORE_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_score_hash(
                r.peer_id, r.epoch, r.latency_tier, r.reputation_pct, r.delivery_pct,
                r.uptime_epochs, r.composite_score, &r.prev_hash,
            );
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

// ─── Peer scoring engine ──────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct PeerScoringEngine {
    peers: BTreeMap<u32, ScoreLog>,
}

impl PeerScoringEngine {
    pub fn new() -> Self { Self { peers: BTreeMap::new() } }

    pub fn peer_count(&self) -> usize { self.peers.len() }

    pub fn update_score(
        &mut self,
        peer_id:        u32,
        epoch:          u64,
        latency_tier:   u8,
        reputation_pct: u8,
        delivery_pct:   u8,
        uptime_epochs:  u32,
    ) -> ScoreRecord {
        let log = self.peers.entry(peer_id).or_insert_with(|| ScoreLog::new(peer_id));
        log.record(epoch, latency_tier, reputation_pct, delivery_pct, uptime_epochs).clone()
    }

    pub fn composite_score(&self, peer_id: u32) -> Option<u8> {
        self.peers.get(&peer_id)
            .and_then(|l| l.records.last())
            .map(|r| r.composite_score)
    }

    /// Top n peers by composite score (descending). Ties broken by peer_id ascending.
    pub fn top_peers(&self, n: usize) -> Vec<u32> {
        let mut scored: Vec<(u32, u8)> = self.peers.iter()
            .filter_map(|(&pid, log)| log.records.last().map(|r| (pid, r.composite_score)))
            .collect();
        scored.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)));
        scored.into_iter().take(n).map(|(pid, _)| pid).collect()
    }

    pub fn all_scores(&self) -> Vec<(u32, u8)> {
        self.peers.iter()
            .filter_map(|(&pid, log)| log.records.last().map(|r| (pid, r.composite_score)))
            .collect()
    }

    pub fn get_log(&self, peer_id: u32) -> Option<&ScoreLog> {
        self.peers.get(&peer_id)
    }
}

impl Default for PeerScoringEngine {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── sub-score helpers ─────────────────────────────────────────────────────

    #[test]
    fn latency_tier_scores() {
        assert_eq!(latency_tier_score(0), 25); // Excellent
        assert_eq!(latency_tier_score(1), 20); // Good
        assert_eq!(latency_tier_score(2), 12); // Fair
        assert_eq!(latency_tier_score(3),  5); // Poor
        assert_eq!(latency_tier_score(4),  0); // Timeout
    }

    #[test]
    fn reputation_sub_score_values() {
        assert_eq!(reputation_sub_score(100), 25);
        assert_eq!(reputation_sub_score(50),  12);
        assert_eq!(reputation_sub_score(0),    0);
    }

    #[test]
    fn delivery_sub_score_values() {
        assert_eq!(delivery_sub_score(100), 25);
        assert_eq!(delivery_sub_score(50),  12);
        assert_eq!(delivery_sub_score(0),    0);
    }

    #[test]
    fn uptime_sub_score_values() {
        assert_eq!(uptime_sub_score(100), 25); // at cap
        assert_eq!(uptime_sub_score(50),  12);
        assert_eq!(uptime_sub_score(200), 25); // capped
        assert_eq!(uptime_sub_score(0),    0);
    }

    #[test]
    fn composite_all_max() {
        assert_eq!(compute_composite(0, 100, 100, 100), 100); // 25+25+25+25
    }

    #[test]
    fn composite_all_zero() {
        assert_eq!(compute_composite(4, 0, 0, 0), 0); // Timeout + zeros
    }

    // ── build_score_record ────────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let r = build_score_record(1, 1, 0, 100, 100, 100, &SCORE_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_score_record(1, 1, 0, 100, 100, 100, &SCORE_GENESIS_HASH);
        let r2 = build_score_record(1, 1, 0, 100, 100, 100, &SCORE_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    // ── ScoreLog ──────────────────────────────────────────────────────────────

    #[test]
    fn log_chain_links() {
        let mut l = ScoreLog::new(1);
        l.record(1, 0, 80, 70, 50);
        l.record(2, 1, 60, 80, 60);
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    #[test]
    fn log_verify_chain_valid() {
        let mut l = ScoreLog::new(1);
        for e in 1..=5u64 { l.record(e, 0, 80, 70, 50); }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    #[test]
    fn log_avg_min_max() {
        let mut l = ScoreLog::new(1);
        l.record(1, 0, 100, 100, 100); // composite = 100
        l.record(2, 4, 0, 0, 0);       // composite = 0
        assert_eq!(l.max_score(), Some(100));
        assert_eq!(l.min_score(), Some(0));
        assert_eq!(l.avg_score(), 50);
    }

    // ── PeerScoringEngine ─────────────────────────────────────────────────────

    #[test]
    fn new_engine_no_score() {
        let e = PeerScoringEngine::new();
        assert_eq!(e.composite_score(1), None);
        assert_eq!(e.peer_count(), 0);
    }

    #[test]
    fn update_score_returns_correct_record() {
        let mut e = PeerScoringEngine::new();
        let r = e.update_score(1, 1, 0, 100, 100, 100);
        assert_eq!(r.composite_score, 100);
        assert_eq!(e.composite_score(1), Some(100));
    }

    #[test]
    fn top_peers_sorted() {
        let mut e = PeerScoringEngine::new();
        e.update_score(1, 1, 3, 0, 0, 0);         // Poor: 5+0+0+0=5
        e.update_score(2, 1, 0, 100, 100, 100);    // Excellent: 100
        e.update_score(3, 1, 1, 60, 60, 60);       // Good+mid: 20+15+15+15=65
        let top = e.top_peers(2);
        assert_eq!(top, vec![2, 3]);
    }

    #[test]
    fn top_peers_n_exceeds_peers() {
        let mut e = PeerScoringEngine::new();
        e.update_score(1, 1, 0, 100, 100, 100);
        assert_eq!(e.top_peers(10).len(), 1);
    }

    #[test]
    fn all_scores_populated() {
        let mut e = PeerScoringEngine::new();
        e.update_score(1, 1, 0, 100, 100, 100);
        e.update_score(2, 1, 4, 0, 0, 0);
        assert_eq!(e.all_scores().len(), 2);
    }
}
