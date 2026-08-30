//! Gate 411 — Gossip Round-Trip Time Log (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Per-epoch tracking of gossip message round-trip times (RTT) in milliseconds.
//!
//! min_rtt_ms:  u32 — minimum RTT observed this epoch
//! max_rtt_ms:  u32 — maximum RTT observed this epoch
//! mean_rtt_ms: u32 — (min_rtt_ms + max_rtt_ms) / 2 (integer average of extremes)
//! high_rtt:    bool — max_rtt_ms >= RTT_HIGH_THRESHOLD (500 ms)
//!
//! RTT_HIGH_THRESHOLD: u32 = 500
//!
//! GossipRoundTripTimeEntry (hash-chained):
//!   epoch_end:   u64
//!   min_rtt_ms:  u32
//!   max_rtt_ms:  u32
//!   mean_rtt_ms: u32
//!   high_rtt:    bool
//!   entry_hash:  [u8;32]
//!   prev_hash:   [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ min_rtt_be4
//!                       ‖ max_rtt_be4 ‖ mean_rtt_be4 ‖ high_rtt_byte)
//!
//! GossipRoundTripTimeLog: record(epoch_end, min_rtt_ms, max_rtt_ms),
//!   high_rtt_count(), max_ever_rtt(), mean_of_means(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_ROUND_TRIP_TIME_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const RTT_HIGH_THRESHOLD: u32 = 500; // ms

// ─── GossipRoundTripTimeEntry ─────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipRoundTripTimeEntry {
    pub epoch_end:   u64,
    pub min_rtt_ms:  u32,
    pub max_rtt_ms:  u32,
    pub mean_rtt_ms: u32,
    pub high_rtt:    bool,
    pub entry_hash:  [u8; 32],
    pub prev_hash:   [u8; 32],
}

fn compute_round_trip_time_hash(
    prev:        &[u8; 32],
    epoch_end:   u64,
    min_rtt_ms:  u32,
    max_rtt_ms:  u32,
    mean_rtt_ms: u32,
    high_rtt:    bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(min_rtt_ms.to_be_bytes());
    h.update(max_rtt_ms.to_be_bytes());
    h.update(mean_rtt_ms.to_be_bytes());
    h.update([high_rtt as u8]);
    h.finalize().into()
}

// ─── GossipRoundTripTimeLog ───────────────────────────────────────────────────

pub struct GossipRoundTripTimeLog {
    entries: Vec<GossipRoundTripTimeEntry>,
}

impl GossipRoundTripTimeLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipRoundTripTimeEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipRoundTripTimeEntry> { self.entries.last() }

    /// Count of epochs where high_rtt == true.
    pub fn high_rtt_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_rtt).count()
    }

    /// Maximum max_rtt_ms ever recorded. Returns 0 if empty.
    pub fn max_ever_rtt(&self) -> u32 {
        self.entries.iter().map(|e| e.max_rtt_ms).max().unwrap_or(0)
    }

    /// Integer mean of all per-epoch mean_rtt_ms values. Returns 0 if empty.
    pub fn mean_of_means(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        let sum: u64 = self.entries.iter().map(|e| e.mean_rtt_ms as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    /// Record RTT stats for one epoch.
    /// mean_rtt_ms = (min_rtt_ms + max_rtt_ms) / 2 (integer).
    /// high_rtt = max_rtt_ms >= RTT_HIGH_THRESHOLD.
    pub fn record(
        &mut self,
        epoch_end:  u64,
        min_rtt_ms: u32,
        max_rtt_ms: u32,
    ) -> &GossipRoundTripTimeEntry {
        let mean_rtt_ms = min_rtt_ms.saturating_add(max_rtt_ms) / 2;
        let high_rtt = max_rtt_ms >= RTT_HIGH_THRESHOLD;

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_ROUND_TRIP_TIME_GENESIS_HASH);

        let entry_hash = compute_round_trip_time_hash(
            &prev, epoch_end, min_rtt_ms, max_rtt_ms, mean_rtt_ms, high_rtt,
        );

        self.entries.push(GossipRoundTripTimeEntry {
            epoch_end,
            min_rtt_ms,
            max_rtt_ms,
            mean_rtt_ms,
            high_rtt,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_ROUND_TRIP_TIME_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_round_trip_time_hash(
                &prev, e.epoch_end, e.min_rtt_ms, e.max_rtt_ms,
                e.mean_rtt_ms, e.high_rtt,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipRoundTripTimeLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipRoundTripTimeLog::new();
        let e = log.record(1, 10, 200);
        assert_eq!(e.epoch_end, 1);
        assert_eq!(e.min_rtt_ms, 10);
        assert_eq!(e.max_rtt_ms, 200);
        assert_eq!(e.mean_rtt_ms, 105);
    }

    #[test]
    fn zero_rtt_stored() {
        let mut log = GossipRoundTripTimeLog::new();
        let e = log.record(1, 0, 0);
        assert_eq!(e.mean_rtt_ms, 0);
        assert!(!e.high_rtt);
    }

    #[test]
    fn mean_rounds_down() {
        let mut log = GossipRoundTripTimeLog::new();
        // (10 + 201) / 2 = 105
        let e = log.record(1, 10, 201);
        assert_eq!(e.mean_rtt_ms, 105);
    }

    // ── high_rtt threshold ────────────────────────────────────────────────────

    #[test]
    fn high_rtt_below_threshold() {
        let mut log = GossipRoundTripTimeLog::new();
        let e = log.record(1, 0, RTT_HIGH_THRESHOLD - 1);
        assert!(!e.high_rtt);
    }

    #[test]
    fn high_rtt_at_threshold() {
        let mut log = GossipRoundTripTimeLog::new();
        let e = log.record(1, 0, RTT_HIGH_THRESHOLD);
        assert!(e.high_rtt);
    }

    #[test]
    fn high_rtt_above_threshold() {
        let mut log = GossipRoundTripTimeLog::new();
        let e = log.record(1, 100, RTT_HIGH_THRESHOLD + 200);
        assert!(e.high_rtt);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn high_rtt_count_correct() {
        let mut log = GossipRoundTripTimeLog::new();
        log.record(1, 10, 200);  // not high
        log.record(2, 50, 500);  // high (at threshold)
        log.record(3, 20, 800);  // high
        log.record(4, 5,  100);  // not high
        assert_eq!(log.high_rtt_count(), 2);
    }

    #[test]
    fn max_ever_rtt_correct() {
        let mut log = GossipRoundTripTimeLog::new();
        log.record(1, 10, 200);
        log.record(2, 50, 1200);
        log.record(3, 20, 300);
        assert_eq!(log.max_ever_rtt(), 1200);
    }

    #[test]
    fn max_ever_rtt_empty_zero() {
        let log = GossipRoundTripTimeLog::new();
        assert_eq!(log.max_ever_rtt(), 0);
    }

    #[test]
    fn mean_of_means_correct() {
        let mut log = GossipRoundTripTimeLog::new();
        log.record(1, 0, 200);   // mean=100
        log.record(2, 100, 500); // mean=300
        log.record(3, 200, 600); // mean=400
        // (100+300+400)/3=266
        assert_eq!(log.mean_of_means(), 266);
    }

    #[test]
    fn mean_of_means_empty_zero() {
        let log = GossipRoundTripTimeLog::new();
        assert_eq!(log.mean_of_means(), 0);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipRoundTripTimeLog::new();
        let e = log.record(1, 10, 200);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipRoundTripTimeLog::new();
        let e = log.record(1, 10, 200);
        assert_eq!(e.prev_hash, GOSSIP_ROUND_TRIP_TIME_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipRoundTripTimeLog::new();
        log.record(1, 10, 200);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 20, 300);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipRoundTripTimeLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipRoundTripTimeLog::new();
        for i in 1u64..=5 { log.record(i, i as u32 * 10, i as u32 * 100); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipRoundTripTimeLog::new();
        log.record(1, 10, 200);
        log.record(2, 20, 300);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipRoundTripTimeLog::new();
        let mut l2 = GossipRoundTripTimeLog::new();
        let h1 = l1.record(4, 15, 250).entry_hash;
        let h2 = l2.record(4, 15, 250).entry_hash;
        assert_eq!(h1, h2);
    }
}
