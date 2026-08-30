//! Gate 384 — Gossip Frame Rate Monitor (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks the number of gossip frames processed per epoch and detects
//! throughput anomalies — epochs where the frame rate deviates more than
//! a configurable threshold from the rolling average (spike detection).
//!
//! GossipFrameRateEntry (hash-chained):
//!   epoch_end:      u64
//!   frame_count:    u32   — frames processed this epoch
//!   rolling_avg:    u32   — floor average of last ≤4 frame counts
//!   is_spike:       bool  — frame_count > rolling_avg * SPIKE_FACTOR (integer: *2)
//!   entry_hash:     [u8;32]
//!   prev_hash:      [u8;32]
//!
//! Spike threshold: frame_count > rolling_avg * 2 (integer multiply, no f64).
//! A frame count of 0 never triggers a spike (0 <= anything).
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ frame_count_be4
//!                        ‖ rolling_avg_be4 ‖ is_spike_byte)
//!
//! GossipFrameRateLog: record(epoch_end, frame_count),
//!   latest(), entry_count(), spike_count(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_FRAME_RATE_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const GOSSIP_FRAME_RATE_WINDOW: usize = 4;
/// Spike if frame_count > rolling_avg * SPIKE_FACTOR
pub const SPIKE_FACTOR: u32 = 2;

// ─── GossipFrameRateEntry ─────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipFrameRateEntry {
    pub epoch_end:   u64,
    pub frame_count: u32,
    pub rolling_avg: u32,
    pub is_spike:    bool,
    pub entry_hash:  [u8; 32],
    pub prev_hash:   [u8; 32],
}

fn compute_frame_rate_hash(
    prev:        &[u8; 32],
    epoch_end:   u64,
    frame_count: u32,
    rolling_avg: u32,
    is_spike:    bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(frame_count.to_be_bytes());
    h.update(rolling_avg.to_be_bytes());
    h.update([is_spike as u8]);
    h.finalize().into()
}

// ─── GossipFrameRateLog ───────────────────────────────────────────────────────

pub struct GossipFrameRateLog {
    entries: Vec<GossipFrameRateEntry>,
    window:  Vec<u32>, // rolling window of frame_count values
}

impl GossipFrameRateLog {
    pub fn new() -> Self {
        Self {
            entries: Vec::new(),
            window:  Vec::new(),
        }
    }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipFrameRateEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipFrameRateEntry> { self.entries.last() }

    pub fn spike_count(&self) -> usize {
        self.entries.iter().filter(|e| e.is_spike).count()
    }

    /// Record frame count for one epoch.
    pub fn record(&mut self, epoch_end: u64, frame_count: u32) -> &GossipFrameRateEntry {
        // Compute rolling average BEFORE adding this epoch's count
        // (spike compares current count against historical average)
        let rolling_avg = if self.window.is_empty() {
            0u32
        } else {
            let sum: u64 = self.window.iter().map(|&v| v as u64).sum();
            (sum / self.window.len() as u64) as u32
        };

        // Spike: frame_count > rolling_avg * SPIKE_FACTOR
        // If rolling_avg == 0 (first entry or all zeros): no spike
        let is_spike = rolling_avg > 0 && frame_count > rolling_avg.saturating_mul(SPIKE_FACTOR);

        // Update rolling window
        self.window.push(frame_count);
        if self.window.len() > GOSSIP_FRAME_RATE_WINDOW {
            self.window.remove(0);
        }

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_FRAME_RATE_GENESIS_HASH);

        let entry_hash = compute_frame_rate_hash(
            &prev, epoch_end, frame_count, rolling_avg, is_spike,
        );

        self.entries.push(GossipFrameRateEntry {
            epoch_end,
            frame_count,
            rolling_avg,
            is_spike,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_FRAME_RATE_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_frame_rate_hash(
                &prev,
                e.epoch_end,
                e.frame_count,
                e.rolling_avg,
                e.is_spike,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipFrameRateLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── first entry ───────────────────────────────────────────────────────────

    #[test]
    fn first_entry_rolling_avg_zero() {
        // No history before first entry → rolling_avg = 0
        let mut log = GossipFrameRateLog::new();
        let e = log.record(1, 100);
        assert_eq!(e.rolling_avg, 0);
    }

    #[test]
    fn first_entry_no_spike() {
        // rolling_avg=0 → no spike regardless of frame_count
        let mut log = GossipFrameRateLog::new();
        let e = log.record(1, 1000);
        assert!(!e.is_spike);
    }

    // ── rolling average ───────────────────────────────────────────────────────

    #[test]
    fn second_entry_rolling_avg_is_first() {
        let mut log = GossipFrameRateLog::new();
        log.record(1, 100);
        let e = log.record(2, 50);
        assert_eq!(e.rolling_avg, 100);
    }

    #[test]
    fn rolling_avg_floor_division() {
        let mut log = GossipFrameRateLog::new();
        log.record(1, 10);
        log.record(2, 11);
        // Before epoch 3: window = [10, 11], avg = floor(21/2) = 10
        let e = log.record(3, 5);
        assert_eq!(e.rolling_avg, 10);
    }

    #[test]
    fn window_caps_at_4() {
        let mut log = GossipFrameRateLog::new();
        for i in 1u64..=4 { log.record(i, 100); }
        // epoch 5: window = [100,100,100,100] → avg = 100
        // After push of 100: window still [100,100,100,100]
        let e = log.record(5, 0);
        assert_eq!(e.rolling_avg, 100);
    }

    // ── spike detection ───────────────────────────────────────────────────────

    #[test]
    fn spike_when_exceeds_double() {
        let mut log = GossipFrameRateLog::new();
        log.record(1, 50);
        // rolling_avg = 50; frame_count = 101 > 50*2=100 → spike
        let e = log.record(2, 101);
        assert!(e.is_spike);
    }

    #[test]
    fn no_spike_at_double() {
        let mut log = GossipFrameRateLog::new();
        log.record(1, 50);
        // frame_count = 100 = 50*2 → NOT > threshold → no spike
        let e = log.record(2, 100);
        assert!(!e.is_spike);
    }

    #[test]
    fn no_spike_when_below_double() {
        let mut log = GossipFrameRateLog::new();
        log.record(1, 50);
        let e = log.record(2, 80);
        assert!(!e.is_spike);
    }

    #[test]
    fn zero_frame_count_no_spike() {
        let mut log = GossipFrameRateLog::new();
        log.record(1, 50);
        // frame_count=0 ≤ anything → no spike
        let e = log.record(2, 0);
        assert!(!e.is_spike);
    }

    // ── spike_count ───────────────────────────────────────────────────────────

    #[test]
    fn spike_count_correct() {
        let mut log = GossipFrameRateLog::new();
        log.record(1, 50);  // no spike (first entry comparison)
        log.record(2, 101); // spike (> 50*2=100)
        log.record(3, 60);  // no spike (avg [50,101] = 75; 60 < 75*2=150)
        assert_eq!(log.spike_count(), 1);
    }

    // ── fields stored ─────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipFrameRateLog::new();
        let e = log.record(7, 42);
        assert_eq!(e.epoch_end, 7);
        assert_eq!(e.frame_count, 42);
    }

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipFrameRateLog::new();
        let e = log.record(1, 50);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipFrameRateLog::new();
        let e = log.record(1, 50);
        assert_eq!(e.prev_hash, GOSSIP_FRAME_RATE_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipFrameRateLog::new();
        log.record(1, 50);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 60);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipFrameRateLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipFrameRateLog::new();
        for i in 1u64..=5 { log.record(i, i as u32 * 10); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipFrameRateLog::new();
        log.record(1, 50);
        log.record(2, 60);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipFrameRateLog::new();
        let mut l2 = GossipFrameRateLog::new();
        let h1 = l1.record(5, 75).entry_hash;
        let h2 = l2.record(5, 75).entry_hash;
        assert_eq!(h1, h2);
    }
}
