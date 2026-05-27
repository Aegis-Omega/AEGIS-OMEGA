//! Gate 415 — Gossip Broadcast Fanout Log (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Per-epoch tracking of gossip broadcast fanout. Fanout is the number of
//! peers each message is forwarded to during the epoch.
//!
//! min_fanout:   u32 — minimum fanout observed this epoch
//! max_fanout:   u32 — maximum fanout observed this epoch
//! mean_fanout:  u32 — (min_fanout + max_fanout) / 2
//! low_fanout:   bool — mean_fanout < FANOUT_FLOOR (3)
//!
//! FANOUT_FLOOR: u32 = 3
//!
//! GossipBroadcastFanoutEntry (hash-chained):
//!   epoch_end:    u64
//!   min_fanout:   u32
//!   max_fanout:   u32
//!   mean_fanout:  u32
//!   low_fanout:   bool
//!   entry_hash:   [u8;32]
//!   prev_hash:    [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ min_fanout_be4
//!                       ‖ max_fanout_be4 ‖ mean_fanout_be4 ‖ low_fanout_byte)
//!
//! GossipBroadcastFanoutLog: record(epoch_end, min_fanout, max_fanout),
//!   low_fanout_count(), max_ever_fanout(), mean_of_means(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_BROADCAST_FANOUT_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const FANOUT_FLOOR: u32 = 3;

// ─── GossipBroadcastFanoutEntry ───────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipBroadcastFanoutEntry {
    pub epoch_end:   u64,
    pub min_fanout:  u32,
    pub max_fanout:  u32,
    pub mean_fanout: u32,
    pub low_fanout:  bool,
    pub entry_hash:  [u8; 32],
    pub prev_hash:   [u8; 32],
}

fn compute_broadcast_fanout_hash(
    prev:        &[u8; 32],
    epoch_end:   u64,
    min_fanout:  u32,
    max_fanout:  u32,
    mean_fanout: u32,
    low_fanout:  bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(min_fanout.to_be_bytes());
    h.update(max_fanout.to_be_bytes());
    h.update(mean_fanout.to_be_bytes());
    h.update([low_fanout as u8]);
    h.finalize().into()
}

// ─── GossipBroadcastFanoutLog ─────────────────────────────────────────────────

pub struct GossipBroadcastFanoutLog {
    entries: Vec<GossipBroadcastFanoutEntry>,
}

impl GossipBroadcastFanoutLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipBroadcastFanoutEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipBroadcastFanoutEntry> { self.entries.last() }

    /// Count of epochs where low_fanout == true.
    pub fn low_fanout_count(&self) -> usize {
        self.entries.iter().filter(|e| e.low_fanout).count()
    }

    /// Maximum max_fanout seen across all epochs. Returns 0 if empty.
    pub fn max_ever_fanout(&self) -> u32 {
        self.entries.iter().map(|e| e.max_fanout).max().unwrap_or(0)
    }

    /// Integer mean of all per-epoch mean_fanout values. Returns 0 if empty.
    pub fn mean_of_means(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        let sum: u64 = self.entries.iter().map(|e| e.mean_fanout as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    /// Record broadcast fanout for one epoch.
    /// mean_fanout = (min_fanout + max_fanout) / 2.
    /// low_fanout = mean_fanout < FANOUT_FLOOR.
    pub fn record(
        &mut self,
        epoch_end:  u64,
        min_fanout: u32,
        max_fanout: u32,
    ) -> &GossipBroadcastFanoutEntry {
        let mean_fanout = (min_fanout as u64 + max_fanout as u64) as u32 / 2;
        let low_fanout  = mean_fanout < FANOUT_FLOOR;

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_BROADCAST_FANOUT_GENESIS_HASH);

        let entry_hash = compute_broadcast_fanout_hash(
            &prev, epoch_end, min_fanout, max_fanout, mean_fanout, low_fanout,
        );

        self.entries.push(GossipBroadcastFanoutEntry {
            epoch_end,
            min_fanout,
            max_fanout,
            mean_fanout,
            low_fanout,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_BROADCAST_FANOUT_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_broadcast_fanout_hash(
                &prev, e.epoch_end, e.min_fanout, e.max_fanout,
                e.mean_fanout, e.low_fanout,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipBroadcastFanoutLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipBroadcastFanoutLog::new();
        let e = log.record(1, 2, 8);
        assert_eq!(e.epoch_end, 1);
        assert_eq!(e.min_fanout, 2);
        assert_eq!(e.max_fanout, 8);
        assert_eq!(e.mean_fanout, 5); // (2+8)/2
    }

    #[test]
    fn zero_fanout_stored() {
        let mut log = GossipBroadcastFanoutLog::new();
        let e = log.record(1, 0, 0);
        assert_eq!(e.mean_fanout, 0);
        assert!(e.low_fanout);
    }

    #[test]
    fn mean_rounds_down() {
        let mut log = GossipBroadcastFanoutLog::new();
        // (1+4)/2 = 2 (rounds down)
        let e = log.record(1, 1, 4);
        assert_eq!(e.mean_fanout, 2);
    }

    // ── low_fanout threshold ──────────────────────────────────────────────────

    #[test]
    fn low_fanout_below_floor() {
        let mut log = GossipBroadcastFanoutLog::new();
        // mean = (0+4)/2 = 2 < 3
        let e = log.record(1, 0, 4);
        assert_eq!(e.mean_fanout, 2);
        assert!(e.low_fanout);
    }

    #[test]
    fn fanout_at_floor_not_low() {
        let mut log = GossipBroadcastFanoutLog::new();
        // mean = (2+4)/2 = 3 — at floor, not low
        let e = log.record(1, 2, 4);
        assert_eq!(e.mean_fanout, 3);
        assert!(!e.low_fanout);
    }

    #[test]
    fn fanout_above_floor_not_low() {
        let mut log = GossipBroadcastFanoutLog::new();
        let e = log.record(1, 4, 10);
        assert!(!e.low_fanout);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn low_fanout_count_correct() {
        let mut log = GossipBroadcastFanoutLog::new();
        log.record(1, 4, 8);  // mean=6 — ok
        log.record(2, 0, 2);  // mean=1 — low
        log.record(3, 2, 4);  // mean=3 — ok (at floor)
        log.record(4, 0, 0);  // mean=0 — low
        assert_eq!(log.low_fanout_count(), 2);
    }

    #[test]
    fn max_ever_fanout_correct() {
        let mut log = GossipBroadcastFanoutLog::new();
        log.record(1, 2, 6);
        log.record(2, 3, 12);
        log.record(3, 1, 8);
        assert_eq!(log.max_ever_fanout(), 12);
    }

    #[test]
    fn max_ever_fanout_empty_zero() {
        let log = GossipBroadcastFanoutLog::new();
        assert_eq!(log.max_ever_fanout(), 0);
    }

    #[test]
    fn mean_of_means_correct() {
        let mut log = GossipBroadcastFanoutLog::new();
        log.record(1, 2, 8);  // mean=5
        log.record(2, 4, 10); // mean=7
        log.record(3, 0, 6);  // mean=3
        // (5+7+3)/3 = 5
        assert_eq!(log.mean_of_means(), 5);
    }

    #[test]
    fn mean_of_means_empty_zero() {
        let log = GossipBroadcastFanoutLog::new();
        assert_eq!(log.mean_of_means(), 0);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipBroadcastFanoutLog::new();
        let e = log.record(1, 3, 9);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipBroadcastFanoutLog::new();
        let e = log.record(1, 3, 9);
        assert_eq!(e.prev_hash, GOSSIP_BROADCAST_FANOUT_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipBroadcastFanoutLog::new();
        log.record(1, 3, 9);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 4, 10);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipBroadcastFanoutLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipBroadcastFanoutLog::new();
        for i in 1u64..=5 { log.record(i, i as u32, i as u32 * 3); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipBroadcastFanoutLog::new();
        log.record(1, 3, 9);
        log.record(2, 4, 10);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipBroadcastFanoutLog::new();
        let mut l2 = GossipBroadcastFanoutLog::new();
        let h1 = l1.record(5, 3, 9).entry_hash;
        let h2 = l2.record(5, 3, 9).entry_hash;
        assert_eq!(h1, h2);
    }
}
