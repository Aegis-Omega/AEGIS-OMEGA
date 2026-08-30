//! Gate 317 — Gossip Peer Liveness Oracle: composite liveness classification (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Classifies each peer as Live, Degraded, Suspect, or Dead based on three integer
//! inputs: consecutive miss count, latency tier (0=Excellent…4=Timeout), and
//! reputation score (0–100). The rules are deterministic and stateless per call.
//!
//! Classification rules (evaluated top-to-bottom, first match wins):
//!   Dead    — miss_count ≥ DEAD_MISS_THRESHOLD (6)
//!   Suspect — miss_count ≥ SUSPECT_MISS_THRESHOLD (3)
//!             OR reputation_score < SUSPECT_REPUTATION_THRESHOLD (20)
//!             OR latency_tier ≥ TIMEOUT_LATENCY_TIER (4)
//!   Degraded — miss_count ≥ 1
//!              OR reputation_score < DEGRADED_REPUTATION_THRESHOLD (50)
//!              OR latency_tier ≥ SLOW_LATENCY_TIER (3)
//!   Live    — all other cases
//!
//! Constants:
//!   DEAD_MISS_THRESHOLD:           u8  = 6
//!   SUSPECT_MISS_THRESHOLD:        u8  = 3
//!   SUSPECT_REPUTATION_THRESHOLD:  u8  = 20
//!   DEGRADED_REPUTATION_THRESHOLD: u8  = 50
//!   TIMEOUT_LATENCY_TIER:          u8  = 4
//!   SLOW_LATENCY_TIER:             u8  = 3
//!
//! LivenessRecord:
//!   peer_id, epoch, miss_count, latency_tier, reputation_score, verdict
//!   record_hash = SHA-256(prev ‖ peer_be4 ‖ epoch_be8 ‖ miss ‖ lat ‖ rep ‖ verdict_byte)
//!   prev_hash
//!
//! LivenessLog: hash-chained LivenessRecords (per-peer).
//!   push(), live_count(), dead_count(), suspect_count(), verify_chain().
//!
//! PeerLivenessOracle:
//!   assess(peer_id, epoch, miss_count, latency_tier, reputation_score) → LivenessVerdict
//!   dead_peers() → Vec<u32>   (sorted)
//!   suspect_peers() → Vec<u32> (sorted)
//!   live_peers() → Vec<u32>   (sorted)
//!   latest_verdict(peer_id) → Option<LivenessVerdict>
//!   get_log(peer_id) → Option<&LivenessLog>

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const DEAD_MISS_THRESHOLD:           u8 = 6;
pub const SUSPECT_MISS_THRESHOLD:        u8 = 3;
pub const SUSPECT_REPUTATION_THRESHOLD:  u8 = 20;
pub const DEGRADED_REPUTATION_THRESHOLD: u8 = 50;
pub const TIMEOUT_LATENCY_TIER:          u8 = 4;
pub const SLOW_LATENCY_TIER:             u8 = 3;

// ─── Liveness verdict ─────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LivenessVerdict {
    Live     = 0,
    Degraded = 1,
    Suspect  = 2,
    Dead     = 3,
}

impl LivenessVerdict {
    pub fn verdict_byte(self) -> u8 { self as u8 }
}

/// Deterministic classification — same inputs always produce the same verdict.
pub fn classify_liveness(miss_count: u8, latency_tier: u8, reputation_score: u8) -> LivenessVerdict {
    if miss_count >= DEAD_MISS_THRESHOLD {
        return LivenessVerdict::Dead;
    }
    if miss_count >= SUSPECT_MISS_THRESHOLD
        || reputation_score < SUSPECT_REPUTATION_THRESHOLD
        || latency_tier >= TIMEOUT_LATENCY_TIER
    {
        return LivenessVerdict::Suspect;
    }
    if miss_count >= 1
        || reputation_score < DEGRADED_REPUTATION_THRESHOLD
        || latency_tier >= SLOW_LATENCY_TIER
    {
        return LivenessVerdict::Degraded;
    }
    LivenessVerdict::Live
}

// ─── Liveness record ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct LivenessRecord {
    pub peer_id:          u32,
    pub epoch:            u64,
    pub miss_count:       u8,
    pub latency_tier:     u8,
    pub reputation_score: u8,
    pub verdict:          LivenessVerdict,
    pub record_hash:      [u8; 32],
    pub prev_hash:        [u8; 32],
}

pub const LIVENESS_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_liveness_hash(
    peer_id:          u32,
    epoch:            u64,
    miss_count:       u8,
    latency_tier:     u8,
    reputation_score: u8,
    verdict:          LivenessVerdict,
    prev:             &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update([miss_count, latency_tier, reputation_score, verdict.verdict_byte()]);
    h.finalize().into()
}

pub fn build_liveness_record(
    peer_id:          u32,
    epoch:            u64,
    miss_count:       u8,
    latency_tier:     u8,
    reputation_score: u8,
    verdict:          LivenessVerdict,
    prev_hash:        &[u8; 32],
) -> LivenessRecord {
    let record_hash = compute_liveness_hash(peer_id, epoch, miss_count, latency_tier, reputation_score, verdict, prev_hash);
    LivenessRecord { peer_id, epoch, miss_count, latency_tier, reputation_score, verdict, record_hash, prev_hash: *prev_hash }
}

// ─── Liveness log (per-peer) ──────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct LivenessLog {
    records: Vec<LivenessRecord>,
}

impl LivenessLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[LivenessRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(LIVENESS_GENESIS_HASH)
    }

    pub fn push(
        &mut self,
        peer_id:          u32,
        epoch:            u64,
        miss_count:       u8,
        latency_tier:     u8,
        reputation_score: u8,
        verdict:          LivenessVerdict,
    ) -> &LivenessRecord {
        let prev = self.last_hash();
        let r = build_liveness_record(peer_id, epoch, miss_count, latency_tier, reputation_score, verdict, &prev);
        self.records.push(r);
        self.records.last().unwrap()
    }

    pub fn live_count(&self) -> usize {
        self.records.iter().filter(|r| r.verdict == LivenessVerdict::Live).count()
    }

    pub fn dead_count(&self) -> usize {
        self.records.iter().filter(|r| r.verdict == LivenessVerdict::Dead).count()
    }

    pub fn suspect_count(&self) -> usize {
        self.records.iter().filter(|r| r.verdict == LivenessVerdict::Suspect).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = LIVENESS_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_liveness_hash(
                r.peer_id, r.epoch, r.miss_count, r.latency_tier, r.reputation_score, r.verdict, &r.prev_hash
            );
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for LivenessLog {
    fn default() -> Self { Self::new() }
}

// ─── PeerLivenessOracle ───────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct PeerLivenessOracle {
    latest:  BTreeMap<u32, LivenessVerdict>,
    pub logs: BTreeMap<u32, LivenessLog>,
}

impl PeerLivenessOracle {
    pub fn new() -> Self {
        Self { latest: BTreeMap::new(), logs: BTreeMap::new() }
    }

    /// Assess a peer and record the verdict.
    pub fn assess(
        &mut self,
        peer_id:          u32,
        epoch:            u64,
        miss_count:       u8,
        latency_tier:     u8,
        reputation_score: u8,
    ) -> LivenessVerdict {
        let verdict = classify_liveness(miss_count, latency_tier, reputation_score);
        self.latest.insert(peer_id, verdict);
        let log = self.logs.entry(peer_id).or_insert_with(LivenessLog::new);
        log.push(peer_id, epoch, miss_count, latency_tier, reputation_score, verdict);
        verdict
    }

    pub fn latest_verdict(&self, peer_id: u32) -> Option<LivenessVerdict> {
        self.latest.get(&peer_id).copied()
    }

    pub fn dead_peers(&self) -> Vec<u32> {
        self.latest.iter()
            .filter(|(_, &v)| v == LivenessVerdict::Dead)
            .map(|(&pid, _)| pid)
            .collect()
    }

    pub fn suspect_peers(&self) -> Vec<u32> {
        self.latest.iter()
            .filter(|(_, &v)| v == LivenessVerdict::Suspect)
            .map(|(&pid, _)| pid)
            .collect()
    }

    pub fn live_peers(&self) -> Vec<u32> {
        self.latest.iter()
            .filter(|(_, &v)| v == LivenessVerdict::Live)
            .map(|(&pid, _)| pid)
            .collect()
    }

    pub fn get_log(&self, peer_id: u32) -> Option<&LivenessLog> {
        self.logs.get(&peer_id)
    }
}

impl Default for PeerLivenessOracle {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── classify_liveness ─────────────────────────────────────────────────────

    #[test]
    fn clean_peer_is_live() {
        // 0 misses, tier 0 (Excellent), rep 80
        assert_eq!(classify_liveness(0, 0, 80), LivenessVerdict::Live);
    }

    #[test]
    fn one_miss_is_degraded() {
        assert_eq!(classify_liveness(1, 0, 80), LivenessVerdict::Degraded);
    }

    #[test]
    fn low_rep_is_degraded() {
        // rep 30 < DEGRADED_REPUTATION_THRESHOLD(50) but ≥ SUSPECT(20)
        assert_eq!(classify_liveness(0, 0, 30), LivenessVerdict::Degraded);
    }

    #[test]
    fn slow_latency_is_degraded() {
        // tier 3 = SLOW_LATENCY_TIER
        assert_eq!(classify_liveness(0, 3, 80), LivenessVerdict::Degraded);
    }

    #[test]
    fn three_misses_is_suspect() {
        assert_eq!(classify_liveness(3, 0, 80), LivenessVerdict::Suspect);
    }

    #[test]
    fn very_low_rep_is_suspect() {
        // rep 10 < SUSPECT_REPUTATION_THRESHOLD(20)
        assert_eq!(classify_liveness(0, 0, 10), LivenessVerdict::Suspect);
    }

    #[test]
    fn timeout_latency_is_suspect() {
        // tier 4 = TIMEOUT_LATENCY_TIER
        assert_eq!(classify_liveness(0, 4, 80), LivenessVerdict::Suspect);
    }

    #[test]
    fn six_misses_is_dead() {
        assert_eq!(classify_liveness(6, 0, 80), LivenessVerdict::Dead);
    }

    #[test]
    fn dead_overrides_reputation() {
        // Even with good rep, 6 misses → Dead
        assert_eq!(classify_liveness(6, 0, 100), LivenessVerdict::Dead);
    }

    // ── build_liveness_record ─────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let r = build_liveness_record(1, 1, 0, 0, 80, LivenessVerdict::Live, &LIVENESS_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_liveness_record(1, 1, 0, 0, 80, LivenessVerdict::Live, &LIVENESS_GENESIS_HASH);
        let r2 = build_liveness_record(1, 1, 0, 0, 80, LivenessVerdict::Live, &LIVENESS_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    // ── LivenessLog ───────────────────────────────────────────────────────────

    #[test]
    fn log_counts() {
        let mut l = LivenessLog::new();
        l.push(1, 1, 0, 0, 80, LivenessVerdict::Live);
        l.push(1, 2, 3, 0, 80, LivenessVerdict::Suspect);
        l.push(1, 3, 6, 0, 80, LivenessVerdict::Dead);
        assert_eq!(l.live_count(),    1);
        assert_eq!(l.suspect_count(), 1);
        assert_eq!(l.dead_count(),    1);
    }

    #[test]
    fn log_chain_links() {
        let mut l = LivenessLog::new();
        l.push(1, 1, 0, 0, 80, LivenessVerdict::Live);
        l.push(1, 2, 1, 0, 80, LivenessVerdict::Degraded);
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    #[test]
    fn log_verify_chain_valid() {
        let mut l = LivenessLog::new();
        for i in 0..5u8 {
            l.push(1, i as u64, i, 0, 80, LivenessVerdict::Live);
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    // ── PeerLivenessOracle ────────────────────────────────────────────────────

    #[test]
    fn oracle_assess_and_query() {
        let mut o = PeerLivenessOracle::new();
        assert_eq!(o.assess(1, 1, 0, 0, 80), LivenessVerdict::Live);
        assert_eq!(o.assess(2, 1, 6, 0, 80), LivenessVerdict::Dead);
        assert_eq!(o.latest_verdict(1), Some(LivenessVerdict::Live));
        assert_eq!(o.latest_verdict(99), None);
    }

    #[test]
    fn dead_and_live_peer_lists() {
        let mut o = PeerLivenessOracle::new();
        o.assess(1, 1, 0, 0, 80);
        o.assess(2, 1, 6, 0, 80);
        o.assess(3, 1, 0, 0, 80);
        assert_eq!(o.live_peers(), vec![1, 3]);
        assert_eq!(o.dead_peers(), vec![2]);
    }

    #[test]
    fn log_accessible_per_peer() {
        let mut o = PeerLivenessOracle::new();
        o.assess(1, 1, 0, 0, 80);
        o.assess(1, 2, 1, 0, 80);
        let log = o.get_log(1).unwrap();
        assert_eq!(log.len(), 2);
        let (valid, _) = log.verify_chain();
        assert!(valid);
    }
}
