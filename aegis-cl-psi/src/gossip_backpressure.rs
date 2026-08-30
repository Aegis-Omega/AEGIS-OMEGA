//! Gate 388 — Gossip Backpressure Signal (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Records whether the gossip pipeline experienced backpressure during each
//! epoch. Backpressure is signalled when the pending frame queue depth
//! exceeds a threshold. Tracks the depth and a binary under_pressure flag
//! per epoch in a hash-chained log.
//!
//! GossipBackpressureEntry (hash-chained):
//!   epoch_end:       u64
//!   queue_depth:     u32   — pending frames at end of epoch
//!   threshold:       u32   — backpressure trigger level
//!   under_pressure:  bool  — queue_depth > threshold
//!   entry_hash:      [u8;32]
//!   prev_hash:       [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ queue_depth_be4
//!                        ‖ threshold_be4 ‖ under_pressure_byte)
//!
//! GossipBackpressureLog: record(epoch_end, queue_depth, threshold),
//!   latest(), entry_count(), pressure_epoch_count(), max_queue_depth(),
//!   verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_BACKPRESSURE_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── GossipBackpressureEntry ──────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipBackpressureEntry {
    pub epoch_end:      u64,
    pub queue_depth:    u32,
    pub threshold:      u32,
    pub under_pressure: bool,
    pub entry_hash:     [u8; 32],
    pub prev_hash:      [u8; 32],
}

fn compute_backpressure_hash(
    prev:           &[u8; 32],
    epoch_end:      u64,
    queue_depth:    u32,
    threshold:      u32,
    under_pressure: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(queue_depth.to_be_bytes());
    h.update(threshold.to_be_bytes());
    h.update([under_pressure as u8]);
    h.finalize().into()
}

// ─── GossipBackpressureLog ────────────────────────────────────────────────────

pub struct GossipBackpressureLog {
    entries: Vec<GossipBackpressureEntry>,
}

impl GossipBackpressureLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self)  -> usize { self.entries.len() }
    pub fn is_empty(&self)     -> bool  { self.entries.is_empty() }
    pub fn entries(&self)      -> &[GossipBackpressureEntry] { &self.entries }
    pub fn latest(&self)       -> Option<&GossipBackpressureEntry> { self.entries.last() }

    /// Count of epochs where under_pressure == true.
    pub fn pressure_epoch_count(&self) -> usize {
        self.entries.iter().filter(|e| e.under_pressure).count()
    }

    /// Maximum queue_depth observed across all entries. Returns 0 if empty.
    pub fn max_queue_depth(&self) -> u32 {
        self.entries.iter().map(|e| e.queue_depth).max().unwrap_or(0)
    }

    /// Record backpressure state for one epoch.
    /// under_pressure = queue_depth > threshold.
    pub fn record(
        &mut self,
        epoch_end:   u64,
        queue_depth: u32,
        threshold:   u32,
    ) -> &GossipBackpressureEntry {
        let under_pressure = queue_depth > threshold;

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_BACKPRESSURE_GENESIS_HASH);

        let entry_hash = compute_backpressure_hash(
            &prev, epoch_end, queue_depth, threshold, under_pressure,
        );

        self.entries.push(GossipBackpressureEntry {
            epoch_end,
            queue_depth,
            threshold,
            under_pressure,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_BACKPRESSURE_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_backpressure_hash(
                &prev,
                e.epoch_end,
                e.queue_depth,
                e.threshold,
                e.under_pressure,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipBackpressureLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── under_pressure classification ─────────────────────────────────────────

    #[test]
    fn pressure_when_depth_exceeds_threshold() {
        let mut log = GossipBackpressureLog::new();
        let e = log.record(1, 101, 100);
        assert!(e.under_pressure);
    }

    #[test]
    fn no_pressure_at_threshold() {
        let mut log = GossipBackpressureLog::new();
        let e = log.record(1, 100, 100);
        assert!(!e.under_pressure);
    }

    #[test]
    fn no_pressure_below_threshold() {
        let mut log = GossipBackpressureLog::new();
        let e = log.record(1, 50, 100);
        assert!(!e.under_pressure);
    }

    #[test]
    fn no_pressure_when_depth_zero() {
        let mut log = GossipBackpressureLog::new();
        let e = log.record(1, 0, 100);
        assert!(!e.under_pressure);
    }

    #[test]
    fn pressure_with_zero_threshold_and_positive_depth() {
        let mut log = GossipBackpressureLog::new();
        let e = log.record(1, 1, 0);
        assert!(e.under_pressure);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn pressure_epoch_count_correct() {
        let mut log = GossipBackpressureLog::new();
        log.record(1, 50, 100);   // no pressure
        log.record(2, 150, 100);  // pressure
        log.record(3, 200, 100);  // pressure
        assert_eq!(log.pressure_epoch_count(), 2);
    }

    #[test]
    fn max_queue_depth_empty_zero() {
        let log = GossipBackpressureLog::new();
        assert_eq!(log.max_queue_depth(), 0);
    }

    #[test]
    fn max_queue_depth_correct() {
        let mut log = GossipBackpressureLog::new();
        log.record(1, 50, 100);
        log.record(2, 200, 100);
        log.record(3, 80, 100);
        assert_eq!(log.max_queue_depth(), 200);
    }

    // ── fields ────────────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipBackpressureLog::new();
        let e = log.record(7, 120, 100);
        assert_eq!(e.epoch_end, 7);
        assert_eq!(e.queue_depth, 120);
        assert_eq!(e.threshold, 100);
        assert!(e.under_pressure);
    }

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipBackpressureLog::new();
        let e = log.record(1, 50, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipBackpressureLog::new();
        let e = log.record(1, 50, 100);
        assert_eq!(e.prev_hash, GOSSIP_BACKPRESSURE_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipBackpressureLog::new();
        log.record(1, 50, 100);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 60, 100);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipBackpressureLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipBackpressureLog::new();
        for i in 1u64..=5 { log.record(i, i as u32 * 20, 50); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipBackpressureLog::new();
        log.record(1, 50, 100);
        log.record(2, 60, 100);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipBackpressureLog::new();
        let mut l2 = GossipBackpressureLog::new();
        let h1 = l1.record(5, 75, 50).entry_hash;
        let h2 = l2.record(5, 75, 50).entry_hash;
        assert_eq!(h1, h2);
    }
}
