//! Gate 418 — Gossip Broadcast Acknowledgement Log (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Per-epoch tracking of gossip message acknowledgements. An acknowledgement
//! confirms that a peer received and processed a broadcast message.
//!
//! ack_count:    u32 — number of acks received this epoch
//! expected:     u32 — number of acks expected (sent × replication_factor)
//! ack_rate_pct: u32 — (ack_count * 100) / max(expected, 1), capped at 100
//! under_ack:    bool — ack_rate_pct < ACK_FLOOR (80)
//!
//! ACK_FLOOR: u32 = 80  (<80% ack rate indicates gossip propagation failure)
//!
//! GossipBroadcastAckEntry (hash-chained):
//!   epoch_end:    u64
//!   ack_count:    u32
//!   expected:     u32
//!   ack_rate_pct: u32
//!   under_ack:    bool
//!   entry_hash:   [u8;32]
//!   prev_hash:    [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ ack_count_be4
//!                       ‖ expected_be4 ‖ ack_rate_pct_be4 ‖ under_ack_byte)
//!
//! GossipBroadcastAckLog: record(epoch_end, ack_count, expected),
//!   under_ack_count(), mean_ack_rate_pct(), min_ack_rate_pct(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_BROADCAST_ACK_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const ACK_FLOOR: u32 = 80;

// ─── GossipBroadcastAckEntry ──────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipBroadcastAckEntry {
    pub epoch_end:    u64,
    pub ack_count:    u32,
    pub expected:     u32,
    pub ack_rate_pct: u32,
    pub under_ack:    bool,
    pub entry_hash:   [u8; 32],
    pub prev_hash:    [u8; 32],
}

fn compute_broadcast_ack_hash(
    prev:         &[u8; 32],
    epoch_end:    u64,
    ack_count:    u32,
    expected:     u32,
    ack_rate_pct: u32,
    under_ack:    bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(ack_count.to_be_bytes());
    h.update(expected.to_be_bytes());
    h.update(ack_rate_pct.to_be_bytes());
    h.update([under_ack as u8]);
    h.finalize().into()
}

// ─── GossipBroadcastAckLog ────────────────────────────────────────────────────

pub struct GossipBroadcastAckLog {
    entries: Vec<GossipBroadcastAckEntry>,
}

impl GossipBroadcastAckLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipBroadcastAckEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipBroadcastAckEntry> { self.entries.last() }

    /// Count of epochs where under_ack == true.
    pub fn under_ack_count(&self) -> usize {
        self.entries.iter().filter(|e| e.under_ack).count()
    }

    /// Integer mean of all per-epoch ack_rate_pct values. Returns 0 if empty.
    pub fn mean_ack_rate_pct(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        let sum: u64 = self.entries.iter().map(|e| e.ack_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    /// Minimum ack_rate_pct across all epochs. Returns 100 if empty.
    pub fn min_ack_rate_pct(&self) -> u32 {
        self.entries.iter().map(|e| e.ack_rate_pct).min().unwrap_or(100)
    }

    /// Record acknowledgement stats for one epoch.
    /// ack_rate_pct = (ack_count * 100) / max(expected, 1), capped at 100.
    /// under_ack = ack_rate_pct < ACK_FLOOR.
    pub fn record(
        &mut self,
        epoch_end: u64,
        ack_count: u32,
        expected:  u32,
    ) -> &GossipBroadcastAckEntry {
        let denom = expected.max(1) as u64;
        let ack_rate_pct = ((ack_count as u64 * 100) / denom).min(100) as u32;
        let under_ack = ack_rate_pct < ACK_FLOOR;

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_BROADCAST_ACK_GENESIS_HASH);

        let entry_hash = compute_broadcast_ack_hash(
            &prev, epoch_end, ack_count, expected, ack_rate_pct, under_ack,
        );

        self.entries.push(GossipBroadcastAckEntry {
            epoch_end,
            ack_count,
            expected,
            ack_rate_pct,
            under_ack,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_BROADCAST_ACK_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_broadcast_ack_hash(
                &prev, e.epoch_end, e.ack_count, e.expected,
                e.ack_rate_pct, e.under_ack,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipBroadcastAckLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipBroadcastAckLog::new();
        let e = log.record(1, 80, 100);
        assert_eq!(e.epoch_end, 1);
        assert_eq!(e.ack_count, 80);
        assert_eq!(e.expected, 100);
        assert_eq!(e.ack_rate_pct, 80); // 80*100/100 = 80
    }

    #[test]
    fn zero_acks_zero_rate() {
        let mut log = GossipBroadcastAckLog::new();
        let e = log.record(1, 0, 100);
        assert_eq!(e.ack_rate_pct, 0);
        assert!(e.under_ack);
    }

    #[test]
    fn expected_zero_uses_max_one() {
        let mut log = GossipBroadcastAckLog::new();
        let e = log.record(1, 0, 0);
        assert_eq!(e.ack_rate_pct, 0);
        assert!(e.under_ack);
    }

    #[test]
    fn ack_rate_capped_at_100() {
        let mut log = GossipBroadcastAckLog::new();
        // ack_count > expected — still capped at 100
        let e = log.record(1, 200, 100);
        assert_eq!(e.ack_rate_pct, 100);
    }

    // ── under_ack threshold ───────────────────────────────────────────────────

    #[test]
    fn under_ack_below_floor() {
        let mut log = GossipBroadcastAckLog::new();
        // 79*100/100 = 79 < 80
        let e = log.record(1, 79, 100);
        assert_eq!(e.ack_rate_pct, 79);
        assert!(e.under_ack);
    }

    #[test]
    fn under_ack_at_floor_not_under() {
        let mut log = GossipBroadcastAckLog::new();
        // exactly 80 — NOT under (< 80, not <=)
        let e = log.record(1, 80, 100);
        assert_eq!(e.ack_rate_pct, 80);
        assert!(!e.under_ack);
    }

    #[test]
    fn under_ack_above_floor_not_under() {
        let mut log = GossipBroadcastAckLog::new();
        let e = log.record(1, 95, 100);
        assert!(!e.under_ack);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn under_ack_count_correct() {
        let mut log = GossipBroadcastAckLog::new();
        log.record(1, 90, 100); // 90% — ok
        log.record(2, 70, 100); // 70% — under
        log.record(3, 80, 100); // 80% — at floor, not under
        log.record(4, 50, 100); // 50% — under
        assert_eq!(log.under_ack_count(), 2);
    }

    #[test]
    fn mean_ack_rate_correct() {
        let mut log = GossipBroadcastAckLog::new();
        log.record(1, 60, 100); // 60%
        log.record(2, 80, 100); // 80%
        log.record(3, 100, 100); // 100%
        // (60+80+100)/3 = 80
        assert_eq!(log.mean_ack_rate_pct(), 80);
    }

    #[test]
    fn mean_ack_rate_empty_zero() {
        let log = GossipBroadcastAckLog::new();
        assert_eq!(log.mean_ack_rate_pct(), 0);
    }

    #[test]
    fn min_ack_rate_correct() {
        let mut log = GossipBroadcastAckLog::new();
        log.record(1, 90, 100); // 90%
        log.record(2, 55, 100); // 55%
        log.record(3, 85, 100); // 85%
        assert_eq!(log.min_ack_rate_pct(), 55);
    }

    #[test]
    fn min_ack_rate_empty_100() {
        let log = GossipBroadcastAckLog::new();
        assert_eq!(log.min_ack_rate_pct(), 100);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipBroadcastAckLog::new();
        let e = log.record(1, 80, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipBroadcastAckLog::new();
        let e = log.record(1, 80, 100);
        assert_eq!(e.prev_hash, GOSSIP_BROADCAST_ACK_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipBroadcastAckLog::new();
        log.record(1, 80, 100);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 90, 100);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipBroadcastAckLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipBroadcastAckLog::new();
        for i in 1u64..=5 { log.record(i, i as u32 * 15, i as u32 * 20); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipBroadcastAckLog::new();
        log.record(1, 80, 100);
        log.record(2, 90, 100);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipBroadcastAckLog::new();
        let mut l2 = GossipBroadcastAckLog::new();
        let h1 = l1.record(4, 85, 100).entry_hash;
        let h2 = l2.record(4, 85, 100).entry_hash;
        assert_eq!(h1, h2);
    }
}
