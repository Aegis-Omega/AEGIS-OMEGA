//! Gate 396 — Gossip Backpressure Epoch Log (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks per-epoch gossip backpressure event counts. A backpressure event
//! occurs when the gossip send queue is full and a frame must be dropped or
//! delayed. high_pressure = pressure_events >= BACKPRESSURE_SATURATION_THRESHOLD.
//!
//! BACKPRESSURE_SATURATION_THRESHOLD: u32 = 10
//!
//! GossipBackpressureEpochEntry (hash-chained):
//!   epoch_end:       u64
//!   pressure_events: u32  — count of backpressure events this epoch
//!   high_pressure:   bool — pressure_events >= BACKPRESSURE_SATURATION_THRESHOLD
//!   entry_hash:      [u8;32]
//!   prev_hash:       [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ pressure_events_be4
//!                       ‖ high_pressure_byte)
//!
//! GossipBackpressureEpochLog: record(epoch_end, pressure_events),
//!   total_pressure_events(), high_pressure_count(), max_pressure_events(),
//!   verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_BACKPRESSURE_EPOCH_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const BACKPRESSURE_SATURATION_THRESHOLD: u32 = 10;

// ─── GossipBackpressureEpochEntry ─────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipBackpressureEpochEntry {
    pub epoch_end:       u64,
    pub pressure_events: u32,
    pub high_pressure:   bool,
    pub entry_hash:      [u8; 32],
    pub prev_hash:       [u8; 32],
}

fn compute_backpressure_epoch_hash(
    prev:            &[u8; 32],
    epoch_end:       u64,
    pressure_events: u32,
    high_pressure:   bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(pressure_events.to_be_bytes());
    h.update([high_pressure as u8]);
    h.finalize().into()
}

// ─── GossipBackpressureEpochLog ───────────────────────────────────────────────

pub struct GossipBackpressureEpochLog {
    entries: Vec<GossipBackpressureEpochEntry>,
}

impl GossipBackpressureEpochLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipBackpressureEpochEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipBackpressureEpochEntry> { self.entries.last() }

    /// Total backpressure events across all epochs.
    pub fn total_pressure_events(&self) -> u64 {
        self.entries.iter().map(|e| e.pressure_events as u64).sum()
    }

    /// Count of epochs where high_pressure == true.
    pub fn high_pressure_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_pressure).count()
    }

    /// Maximum pressure_events in a single epoch. Returns 0 if empty.
    pub fn max_pressure_events(&self) -> u32 {
        self.entries.iter().map(|e| e.pressure_events).max().unwrap_or(0)
    }

    /// Record backpressure for one epoch.
    /// high_pressure = pressure_events >= BACKPRESSURE_SATURATION_THRESHOLD.
    pub fn record(
        &mut self,
        epoch_end:       u64,
        pressure_events: u32,
    ) -> &GossipBackpressureEpochEntry {
        let high_pressure = pressure_events >= BACKPRESSURE_SATURATION_THRESHOLD;

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_BACKPRESSURE_EPOCH_GENESIS_HASH);

        let entry_hash = compute_backpressure_epoch_hash(
            &prev, epoch_end, pressure_events, high_pressure,
        );

        self.entries.push(GossipBackpressureEpochEntry {
            epoch_end,
            pressure_events,
            high_pressure,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_BACKPRESSURE_EPOCH_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_backpressure_epoch_hash(
                &prev, e.epoch_end, e.pressure_events, e.high_pressure,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipBackpressureEpochLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipBackpressureEpochLog::new();
        let e = log.record(5, 3);
        assert_eq!(e.epoch_end, 5);
        assert_eq!(e.pressure_events, 3);
        assert!(!e.high_pressure);
    }

    #[test]
    fn zero_pressure_stored() {
        let mut log = GossipBackpressureEpochLog::new();
        let e = log.record(1, 0);
        assert_eq!(e.pressure_events, 0);
        assert!(!e.high_pressure);
    }

    // ── high_pressure threshold ───────────────────────────────────────────────

    #[test]
    fn high_pressure_below_threshold() {
        let mut log = GossipBackpressureEpochLog::new();
        // pressure_events = threshold - 1 = 9 → not saturated
        let e = log.record(1, BACKPRESSURE_SATURATION_THRESHOLD - 1);
        assert!(!e.high_pressure);
    }

    #[test]
    fn high_pressure_at_threshold() {
        let mut log = GossipBackpressureEpochLog::new();
        // pressure_events == threshold → saturated
        let e = log.record(1, BACKPRESSURE_SATURATION_THRESHOLD);
        assert!(e.high_pressure);
    }

    #[test]
    fn high_pressure_above_threshold() {
        let mut log = GossipBackpressureEpochLog::new();
        let e = log.record(1, BACKPRESSURE_SATURATION_THRESHOLD + 5);
        assert!(e.high_pressure);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn total_pressure_events_correct() {
        let mut log = GossipBackpressureEpochLog::new();
        log.record(1, 3);
        log.record(2, 7);
        log.record(3, 12);
        assert_eq!(log.total_pressure_events(), 22);
    }

    #[test]
    fn high_pressure_count_correct() {
        let mut log = GossipBackpressureEpochLog::new();
        log.record(1, 3);   // not high
        log.record(2, 10);  // high (== threshold)
        log.record(3, 15);  // high
        log.record(4, 9);   // not high
        assert_eq!(log.high_pressure_count(), 2);
    }

    #[test]
    fn max_pressure_events_correct() {
        let mut log = GossipBackpressureEpochLog::new();
        log.record(1, 5);
        log.record(2, 20);
        log.record(3, 8);
        assert_eq!(log.max_pressure_events(), 20);
    }

    #[test]
    fn max_pressure_empty_zero() {
        let log = GossipBackpressureEpochLog::new();
        assert_eq!(log.max_pressure_events(), 0);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipBackpressureEpochLog::new();
        let e = log.record(1, 5);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipBackpressureEpochLog::new();
        let e = log.record(1, 5);
        assert_eq!(e.prev_hash, GOSSIP_BACKPRESSURE_EPOCH_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipBackpressureEpochLog::new();
        log.record(1, 3);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 12);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipBackpressureEpochLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipBackpressureEpochLog::new();
        for i in 1u64..=5 { log.record(i, i as u32 * 3); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipBackpressureEpochLog::new();
        log.record(1, 3);
        log.record(2, 12);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipBackpressureEpochLog::new();
        let mut l2 = GossipBackpressureEpochLog::new();
        let h1 = l1.record(7, 15).entry_hash;
        let h2 = l2.record(7, 15).entry_hash;
        assert_eq!(h1, h2);
    }
}
