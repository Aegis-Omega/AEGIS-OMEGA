//! Gate 298 — Gossip Link Quality Monitor: per-peer link quality assessment (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks the quality of gossip links to each peer using an exponential moving
//! average (integer approximation) of round-trip latency ticks. Classifies each
//! peer's link into a LatencyTier based on the smoothed latency.
//!
//! LatencyTier:
//!   Excellent = 0  — smoothed_latency ≤ 10 ticks
//!   Good      = 1  — smoothed_latency ≤ 30 ticks
//!   Fair      = 2  — smoothed_latency ≤ 100 ticks
//!   Poor      = 3  — smoothed_latency > 100 ticks
//!   Timeout   = 4  — no response received (sampled as MAX_LATENCY_TICKS)
//!
//! Smoothing: EMA with α=1/4 (integer: new = (3*old + sample) / 4).
//! MAX_LATENCY_TICKS: u32 = 1000 (used for timeout samples).
//!
//! LinkQualityRecord:
//!   peer_id          — u32
//!   epoch            — u64
//!   sample_latency   — u32 (raw tick; MAX_LATENCY_TICKS if timeout)
//!   smoothed_latency — u32 (EMA after update)
//!   tier             — LatencyTier
//!   record_hash      — SHA-256(prev ‖ peer_be4 ‖ epoch_be8 ‖ samp_be4 ‖ smooth_be4 ‖ tier_byte)
//!   prev_hash        — [u8; 32]
//!
//! LinkQualityLog: hash-chained records per peer.
//!   record(), timeout_count(), tier_count(tier), verify_chain().
//!
//! LinkQualityMonitor: BTreeMap<peer_id, PeerLinkState>.
//!   sample(peer_id, epoch, latency_ticks) — update EMA; record
//!   sample_timeout(peer_id, epoch)        — use MAX_LATENCY_TICKS
//!   current_tier(peer_id), smoothed_latency(peer_id), get_log(peer_id)
//!   peers_at_tier(tier) → Vec<u32>

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const MAX_LATENCY_TICKS: u32 = 1000;
pub const EMA_ALPHA_DENOM:   u32 = 4; // α = 1/4; new = (3*old + sample) / 4

pub const TIER_EXCELLENT: u32 = 10;
pub const TIER_GOOD:      u32 = 30;
pub const TIER_FAIR:      u32 = 100;

// ─── Latency tier ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum LatencyTier {
    Excellent = 0,
    Good      = 1,
    Fair      = 2,
    Poor      = 3,
    Timeout   = 4,
}

impl LatencyTier {
    pub fn tier_byte(self) -> u8 { self as u8 }

    pub fn from_smoothed(smoothed: u32, is_timeout: bool) -> Self {
        if is_timeout            { Self::Timeout }
        else if smoothed <= TIER_EXCELLENT { Self::Excellent }
        else if smoothed <= TIER_GOOD      { Self::Good }
        else if smoothed <= TIER_FAIR      { Self::Fair }
        else                               { Self::Poor }
    }
}

// ─── Link quality record ──────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct LinkQualityRecord {
    pub peer_id:          u32,
    pub epoch:            u64,
    pub sample_latency:   u32,
    pub smoothed_latency: u32,
    pub tier:             LatencyTier,
    pub record_hash:      [u8; 32],
    pub prev_hash:        [u8; 32],
}

pub const LINK_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_link_hash(
    peer_id:          u32,
    epoch:            u64,
    sample_latency:   u32,
    smoothed_latency: u32,
    tier:             LatencyTier,
    prev:             &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update(sample_latency.to_be_bytes());
    h.update(smoothed_latency.to_be_bytes());
    h.update([tier.tier_byte()]);
    h.finalize().into()
}

pub fn build_link_record(
    peer_id:          u32,
    epoch:            u64,
    sample_latency:   u32,
    smoothed_latency: u32,
    tier:             LatencyTier,
    prev_hash:        &[u8; 32],
) -> LinkQualityRecord {
    let record_hash = compute_link_hash(peer_id, epoch, sample_latency, smoothed_latency, tier, prev_hash);
    LinkQualityRecord { peer_id, epoch, sample_latency, smoothed_latency, tier, record_hash, prev_hash: *prev_hash }
}

// ─── Link quality log ─────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct LinkQualityLog {
    peer_id: u32,
    records: Vec<LinkQualityRecord>,
}

impl LinkQualityLog {
    pub fn new(peer_id: u32) -> Self { Self { peer_id, records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[LinkQualityRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(LINK_GENESIS_HASH)
    }

    pub fn push(
        &mut self,
        epoch:            u64,
        sample_latency:   u32,
        smoothed_latency: u32,
        tier:             LatencyTier,
    ) {
        let prev = self.last_hash();
        let r = build_link_record(self.peer_id, epoch, sample_latency, smoothed_latency, tier, &prev);
        self.records.push(r);
    }

    pub fn timeout_count(&self) -> usize {
        self.records.iter().filter(|r| r.tier == LatencyTier::Timeout).count()
    }

    pub fn tier_count(&self, tier: LatencyTier) -> usize {
        self.records.iter().filter(|r| r.tier == tier).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = LINK_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_link_hash(
                r.peer_id, r.epoch, r.sample_latency, r.smoothed_latency, r.tier, &r.prev_hash,
            );
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

// ─── Link quality monitor ─────────────────────────────────────────────────────

#[derive(Debug, Clone)]
struct PeerLinkState {
    smoothed: u32,
    log:      LinkQualityLog,
}

#[derive(Debug, Clone)]
pub struct LinkQualityMonitor {
    peers: BTreeMap<u32, PeerLinkState>,
}

impl LinkQualityMonitor {
    pub fn new() -> Self { Self { peers: BTreeMap::new() } }

    fn apply_sample(state: &mut PeerLinkState, epoch: u64, sample: u32, is_timeout: bool) {
        // EMA: new_smoothed = (3 * old + sample) / 4
        let new_smoothed = (3 * state.smoothed + sample) / EMA_ALPHA_DENOM;
        state.smoothed = new_smoothed;
        let tier = LatencyTier::from_smoothed(new_smoothed, is_timeout);
        state.log.push(epoch, sample, new_smoothed, tier);
    }

    pub fn sample(&mut self, peer_id: u32, epoch: u64, latency_ticks: u32) {
        let state = self.peers.entry(peer_id).or_insert_with(|| PeerLinkState {
            smoothed: latency_ticks,
            log:      LinkQualityLog::new(peer_id),
        });
        Self::apply_sample(state, epoch, latency_ticks, false);
    }

    pub fn sample_timeout(&mut self, peer_id: u32, epoch: u64) {
        let state = self.peers.entry(peer_id).or_insert_with(|| PeerLinkState {
            smoothed: MAX_LATENCY_TICKS,
            log:      LinkQualityLog::new(peer_id),
        });
        Self::apply_sample(state, epoch, MAX_LATENCY_TICKS, true);
    }

    pub fn current_tier(&self, peer_id: u32) -> Option<LatencyTier> {
        self.peers.get(&peer_id).and_then(|s| s.log.records().last().map(|r| r.tier))
    }

    pub fn smoothed_latency(&self, peer_id: u32) -> Option<u32> {
        self.peers.get(&peer_id).map(|s| s.smoothed)
    }

    pub fn get_log(&self, peer_id: u32) -> Option<&LinkQualityLog> {
        self.peers.get(&peer_id).map(|s| &s.log)
    }

    pub fn peers_at_tier(&self, tier: LatencyTier) -> Vec<u32> {
        self.peers.iter()
            .filter(|(_, s)| {
                s.log.records().last().map(|r| r.tier == tier).unwrap_or(false)
            })
            .map(|(&id, _)| id)
            .collect()
    }
}

impl Default for LinkQualityMonitor {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── LatencyTier ───────────────────────────────────────────────────────────

    #[test]
    fn tier_bytes() {
        assert_eq!(LatencyTier::Excellent.tier_byte(), 0);
        assert_eq!(LatencyTier::Good.tier_byte(),      1);
        assert_eq!(LatencyTier::Fair.tier_byte(),      2);
        assert_eq!(LatencyTier::Poor.tier_byte(),      3);
        assert_eq!(LatencyTier::Timeout.tier_byte(),   4);
    }

    #[test]
    fn tier_classification() {
        assert_eq!(LatencyTier::from_smoothed(5,   false), LatencyTier::Excellent);
        assert_eq!(LatencyTier::from_smoothed(10,  false), LatencyTier::Excellent);
        assert_eq!(LatencyTier::from_smoothed(11,  false), LatencyTier::Good);
        assert_eq!(LatencyTier::from_smoothed(30,  false), LatencyTier::Good);
        assert_eq!(LatencyTier::from_smoothed(31,  false), LatencyTier::Fair);
        assert_eq!(LatencyTier::from_smoothed(100, false), LatencyTier::Fair);
        assert_eq!(LatencyTier::from_smoothed(101, false), LatencyTier::Poor);
        assert_eq!(LatencyTier::from_smoothed(0,   true),  LatencyTier::Timeout);
    }

    // ── build_link_record ─────────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let r = build_link_record(1, 1, 10, 10, LatencyTier::Excellent, &LINK_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_link_record(1, 1, 10, 10, LatencyTier::Excellent, &LINK_GENESIS_HASH);
        let r2 = build_link_record(1, 1, 10, 10, LatencyTier::Excellent, &LINK_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    // ── LinkQualityLog ────────────────────────────────────────────────────────

    #[test]
    fn new_log_empty() {
        let l = LinkQualityLog::new(1);
        assert!(l.is_empty());
        assert_eq!(l.timeout_count(), 0);
    }

    #[test]
    fn tier_count_tracks() {
        let mut l = LinkQualityLog::new(1);
        l.push(1, 5,    5,    LatencyTier::Excellent);
        l.push(2, 1000, 1000, LatencyTier::Timeout);
        l.push(3, 50,   50,   LatencyTier::Fair);
        assert_eq!(l.tier_count(LatencyTier::Excellent), 1);
        assert_eq!(l.timeout_count(), 1);
        assert_eq!(l.tier_count(LatencyTier::Fair), 1);
    }

    #[test]
    fn chain_links() {
        let mut l = LinkQualityLog::new(1);
        l.push(1, 5, 5, LatencyTier::Excellent);
        l.push(2, 5, 5, LatencyTier::Excellent);
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    #[test]
    fn verify_chain_valid() {
        let mut l = LinkQualityLog::new(1);
        for e in 1..=5u64 {
            l.push(e, 5, 5, LatencyTier::Excellent);
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    // ── LinkQualityMonitor ────────────────────────────────────────────────────

    #[test]
    fn first_sample_sets_tier() {
        let mut m = LinkQualityMonitor::new();
        m.sample(1, 1, 5);
        assert_eq!(m.current_tier(1), Some(LatencyTier::Excellent));
    }

    #[test]
    fn ema_smooths_latency() {
        let mut m = LinkQualityMonitor::new();
        m.sample(1, 1, 8); // init smoothed=8
        m.sample(1, 2, 20); // (3*8 + 20)/4 = (24+20)/4 = 11 → Good
        assert_eq!(m.current_tier(1), Some(LatencyTier::Good));
    }

    #[test]
    fn timeout_sets_timeout_tier() {
        let mut m = LinkQualityMonitor::new();
        m.sample_timeout(1, 1);
        assert_eq!(m.current_tier(1), Some(LatencyTier::Timeout));
    }

    #[test]
    fn peers_at_tier_filters() {
        let mut m = LinkQualityMonitor::new();
        m.sample(1, 1, 5);   // Excellent
        m.sample(2, 1, 200); // Poor
        m.sample_timeout(3, 1); // Timeout
        assert_eq!(m.peers_at_tier(LatencyTier::Excellent), vec![1]);
        assert_eq!(m.peers_at_tier(LatencyTier::Poor), vec![2]);
        assert_eq!(m.peers_at_tier(LatencyTier::Timeout), vec![3]);
    }

    #[test]
    fn unknown_peer_returns_none() {
        let m = LinkQualityMonitor::new();
        assert!(m.current_tier(99).is_none());
        assert!(m.smoothed_latency(99).is_none());
        assert!(m.get_log(99).is_none());
    }

    #[test]
    fn log_grows_per_sample() {
        let mut m = LinkQualityMonitor::new();
        m.sample(1, 1, 5);
        m.sample(1, 2, 5);
        m.sample(1, 3, 5);
        assert_eq!(m.get_log(1).unwrap().len(), 3);
    }
}
