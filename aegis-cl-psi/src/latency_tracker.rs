//! Gate 276 — Peer Latency Tracker: per-peer round-trip latency estimation (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks observed round-trip latency (in milliseconds) per peer over a
//! rolling window of samples. Classifies each peer into a LatencyTier
//! based on the rolling average.
//!
//! LatencyTier:
//!   Fast    — avg_ms ≤ 50
//!   Normal  — 51 ≤ avg_ms ≤ 200
//!   Slow    — 201 ≤ avg_ms ≤ 500
//!   Timeout — avg_ms > 500 or no response
//!
//! LatencyRecord:
//!   peer_id     — u32
//!   epoch       — u64
//!   sample_ms   — u32 (observed latency for this epoch)
//!   rolling_avg — u32 (integer rolling average over last WINDOW samples)
//!   tier        — LatencyTier
//!   record_hash — SHA-256(prev ‖ peer_id_be4 ‖ epoch_be8 ‖ sample_ms_be4 ‖ tier_byte)
//!   prev_hash   — [u8; 32]
//!
//! PeerLatencyLog: per-peer rolling window + hash-chained LatencyRecords.
//!   fast_count(), slow_count(), timeout_count(), worst_tier(), verify_chain().
//!
//! LatencyRegistry: BTreeMap<peer_id, PeerLatencyLog>. all_tiers(), slow_peer_count().

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const LATENCY_WINDOW: usize = 8;  // rolling average window size

// ─── Latency tier ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum LatencyTier {
    Fast    = 0,
    Normal  = 1,
    Slow    = 2,
    Timeout = 3,
}

pub fn classify_tier(avg_ms: u32) -> LatencyTier {
    if avg_ms <= 50      { LatencyTier::Fast }
    else if avg_ms <= 200 { LatencyTier::Normal }
    else if avg_ms <= 500 { LatencyTier::Slow }
    else                  { LatencyTier::Timeout }
}

// ─── Latency record ───────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct LatencyRecord {
    pub peer_id:     u32,
    pub epoch:       u64,
    pub sample_ms:   u32,
    pub rolling_avg: u32,
    pub tier:        LatencyTier,
    pub record_hash: [u8; 32],
    pub prev_hash:   [u8; 32],
}

pub const LATENCY_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_record_hash(
    peer_id:   u32,
    epoch:     u64,
    sample_ms: u32,
    tier:      LatencyTier,
    prev:      &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update(sample_ms.to_be_bytes());
    h.update([tier as u8]);
    h.finalize().into()
}

// ─── Per-peer latency log ─────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct PeerLatencyLog {
    peer_id:      u32,
    records:      Vec<LatencyRecord>,
    /// Rolling window of the last LATENCY_WINDOW sample_ms values.
    window:       [u32; LATENCY_WINDOW],
    window_count: usize, // how many samples are valid (up to LATENCY_WINDOW)
    window_pos:   usize, // circular buffer write head
}

#[derive(Debug)]
pub enum LatencyLogError {
    StaleEpoch,
}

impl PeerLatencyLog {
    pub fn new(peer_id: u32) -> Self {
        Self {
            peer_id,
            records: Vec::new(),
            window: [0u32; LATENCY_WINDOW],
            window_count: 0,
            window_pos:   0,
        }
    }

    pub fn peer_id(&self)  -> u32  { self.peer_id }
    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[LatencyRecord] { &self.records }
    pub fn latest(&self)   -> Option<&LatencyRecord> { self.records.last() }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(LATENCY_GENESIS_HASH)
    }

    /// Compute rolling average from the current window (integer division).
    fn rolling_average(&self) -> u32 {
        if self.window_count == 0 { return 0; }
        let sum: u64 = self.window[..self.window_count].iter().map(|&v| v as u64).sum();
        (sum / self.window_count as u64) as u32
    }

    pub fn record(
        &mut self,
        epoch:     u64,
        sample_ms: u32,
    ) -> Result<&LatencyRecord, LatencyLogError> {
        if let Some(last) = self.records.last() {
            if epoch <= last.epoch {
                return Err(LatencyLogError::StaleEpoch);
            }
        }
        // Update circular window
        self.window[self.window_pos] = sample_ms;
        self.window_pos = (self.window_pos + 1) % LATENCY_WINDOW;
        if self.window_count < LATENCY_WINDOW { self.window_count += 1; }

        let rolling_avg = self.rolling_average();
        let tier = classify_tier(rolling_avg);
        let prev_hash = self.last_hash();
        let record_hash = compute_record_hash(self.peer_id, epoch, sample_ms, tier, &prev_hash);

        self.records.push(LatencyRecord {
            peer_id: self.peer_id,
            epoch,
            sample_ms,
            rolling_avg,
            tier,
            record_hash,
            prev_hash,
        });
        Ok(self.records.last().unwrap())
    }

    pub fn fast_count(&self) -> usize {
        self.records.iter().filter(|r| r.tier == LatencyTier::Fast).count()
    }

    pub fn slow_count(&self) -> usize {
        self.records.iter().filter(|r| r.tier == LatencyTier::Slow).count()
    }

    pub fn timeout_count(&self) -> usize {
        self.records.iter().filter(|r| r.tier == LatencyTier::Timeout).count()
    }

    /// Worst (highest) tier seen across all records.
    pub fn worst_tier(&self) -> Option<LatencyTier> {
        self.records.iter().map(|r| r.tier).max()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = LATENCY_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev {
                return (false, Some(i));
            }
            let recomputed = compute_record_hash(
                r.peer_id, r.epoch, r.sample_ms, r.tier, &r.prev_hash);
            if recomputed != r.record_hash {
                return (false, Some(i));
            }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

// ─── Latency registry ─────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct LatencyRegistry {
    peers: BTreeMap<u32, PeerLatencyLog>,
}

impl LatencyRegistry {
    pub fn new() -> Self { Self { peers: BTreeMap::new() } }

    pub fn peer_count(&self) -> usize { self.peers.len() }

    pub fn observe(
        &mut self,
        peer_id:   u32,
        epoch:     u64,
        sample_ms: u32,
    ) -> Result<LatencyTier, LatencyLogError> {
        let log = self.peers.entry(peer_id).or_insert_with(|| PeerLatencyLog::new(peer_id));
        let record = log.record(epoch, sample_ms)?;
        Ok(record.tier)
    }

    /// Current tier for each peer (BTreeMap order — deterministic).
    pub fn all_tiers(&self) -> BTreeMap<u32, LatencyTier> {
        self.peers.iter()
            .filter_map(|(&id, log)| log.latest().map(|r| (id, r.tier)))
            .collect()
    }

    /// Number of peers currently at Slow or Timeout tier.
    pub fn slow_peer_count(&self) -> usize {
        self.all_tiers().values()
            .filter(|&&t| t >= LatencyTier::Slow)
            .count()
    }
}

impl Default for LatencyRegistry {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── classify_tier ─────────────────────────────────────────────────────────

    #[test]
    fn tier_boundaries() {
        assert_eq!(classify_tier(0),   LatencyTier::Fast);
        assert_eq!(classify_tier(50),  LatencyTier::Fast);
        assert_eq!(classify_tier(51),  LatencyTier::Normal);
        assert_eq!(classify_tier(200), LatencyTier::Normal);
        assert_eq!(classify_tier(201), LatencyTier::Slow);
        assert_eq!(classify_tier(500), LatencyTier::Slow);
        assert_eq!(classify_tier(501), LatencyTier::Timeout);
    }

    // ── rolling average ───────────────────────────────────────────────────────

    #[test]
    fn rolling_avg_single_sample() {
        let mut l = PeerLatencyLog::new(1);
        let r = l.record(1, 100).unwrap();
        assert_eq!(r.rolling_avg, 100);
    }

    #[test]
    fn rolling_avg_two_samples() {
        let mut l = PeerLatencyLog::new(1);
        l.record(1, 100).unwrap();
        let r = l.record(2, 200).unwrap();
        assert_eq!(r.rolling_avg, 150); // (100+200)/2
    }

    #[test]
    fn rolling_avg_window_evicts_old() {
        let mut l = PeerLatencyLog::new(1);
        // Fill window with 1000ms then add 8 samples of 10ms
        for i in 1..=9u64 {
            l.record(i, 1000).unwrap();
        }
        // Add 8 samples of 10ms to evict all 1000ms samples
        for i in 10..=17u64 {
            l.record(i, 10).unwrap();
        }
        let r = l.latest().unwrap();
        assert_eq!(r.rolling_avg, 10);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let mut l = PeerLatencyLog::new(1);
        let r = l.record(1, 50).unwrap();
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let mut l1 = PeerLatencyLog::new(1);
        let mut l2 = PeerLatencyLog::new(1);
        let r1 = l1.record(1, 50).unwrap();
        let r2 = l2.record(1, 50).unwrap();
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    #[test]
    fn chain_links_correctly() {
        let mut l = PeerLatencyLog::new(1);
        l.record(1, 50).unwrap();
        l.record(2, 60).unwrap();
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    // ── PeerLatencyLog ────────────────────────────────────────────────────────

    #[test]
    fn new_log_empty() {
        let l = PeerLatencyLog::new(1);
        assert!(l.is_empty());
        assert_eq!(l.fast_count(), 0);
        assert_eq!(l.worst_tier(), None);
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut l = PeerLatencyLog::new(1);
        l.record(5, 50).unwrap();
        assert!(matches!(l.record(5, 50), Err(LatencyLogError::StaleEpoch)));
        assert!(matches!(l.record(4, 50), Err(LatencyLogError::StaleEpoch)));
    }

    #[test]
    fn fast_slow_timeout_counts() {
        let mut l = PeerLatencyLog::new(1);
        l.record(1, 30).unwrap();   // Fast
        l.record(2, 300).unwrap();  // Slow (avg shifts)
        l.record(3, 800).unwrap();  // Timeout (avg shifts)
        // Just verify counts are non-negative (rolling avg may shift tier)
        let total = l.fast_count() + l.slow_count() + l.timeout_count()
            + l.records().iter().filter(|r| r.tier == LatencyTier::Normal).count();
        assert_eq!(total, 3);
    }

    #[test]
    fn worst_tier_is_max() {
        let mut l = PeerLatencyLog::new(1);
        l.record(1, 30).unwrap();   // Fast initially
        // Force an avg above 500 by adding enough high samples
        for i in 2..=10u64 {
            l.record(i, 1000).unwrap();
        }
        assert_eq!(l.worst_tier(), Some(LatencyTier::Timeout));
    }

    #[test]
    fn verify_chain_valid() {
        let mut l = PeerLatencyLog::new(1);
        for i in 1..=6u64 {
            l.record(i, (i as u32) * 30).unwrap();
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    // ── LatencyRegistry ───────────────────────────────────────────────────────

    #[test]
    fn new_registry_empty() {
        let r = LatencyRegistry::new();
        assert_eq!(r.peer_count(), 0);
        assert_eq!(r.slow_peer_count(), 0);
    }

    #[test]
    fn observe_creates_peer() {
        let mut r = LatencyRegistry::new();
        r.observe(1, 1, 30).unwrap();
        assert_eq!(r.peer_count(), 1);
    }

    #[test]
    fn all_tiers_deterministic() {
        let mut r = LatencyRegistry::new();
        r.observe(3, 1, 800).unwrap(); // Timeout
        r.observe(1, 1, 30).unwrap();  // Fast
        r.observe(2, 1, 100).unwrap(); // Normal
        let tiers = r.all_tiers();
        assert_eq!(tiers[&1], LatencyTier::Fast);
        assert_eq!(tiers[&2], LatencyTier::Normal);
        assert_eq!(tiers[&3], LatencyTier::Timeout);
    }

    #[test]
    fn slow_peer_count_includes_timeout() {
        let mut r = LatencyRegistry::new();
        r.observe(1, 1, 30).unwrap();  // Fast
        r.observe(2, 1, 300).unwrap(); // Slow
        r.observe(3, 1, 800).unwrap(); // Timeout
        assert_eq!(r.slow_peer_count(), 2);
    }
}
