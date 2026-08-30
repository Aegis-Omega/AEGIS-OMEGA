//! Gate 420 — Gossip Broadcast Sequence Disorder Log (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Per-epoch tracking of out-of-order gossip message delivery. Sequence
//! disorder occurs when messages arrive at peers in a different order than
//! they were sent, indicating routing instability.
//!
//! out_of_order_count: u32 — messages received out of expected sequence order
//! total_received:     u32 — total messages received this epoch
//! disorder_rate_pct:  u32 — (out_of_order_count * 100) / max(total_received, 1), capped at 100
//! disordered:         bool — disorder_rate_pct > DISORDER_THRESHOLD (15)
//!
//! DISORDER_THRESHOLD: u32 = 15  (>15% disorder indicates routing instability)
//!
//! GossipBroadcastSequenceEntry (hash-chained):
//!   epoch_end:          u64
//!   out_of_order_count: u32
//!   total_received:     u32
//!   disorder_rate_pct:  u32
//!   disordered:         bool
//!   entry_hash:         [u8;32]
//!   prev_hash:          [u8;32]
//!
//! entry_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ out_of_order_count_be4
//!                       ‖ total_received_be4 ‖ disorder_rate_pct_be4 ‖ disordered_byte)
//!
//! GossipBroadcastSequenceLog: record(epoch_end, out_of_order_count, total_received),
//!   disordered_count(), total_out_of_order(), mean_disorder_rate_pct(), verify_chain().

use sha2::{Sha256, Digest};

pub const GOSSIP_BROADCAST_SEQUENCE_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const DISORDER_THRESHOLD: u32 = 15;

// ─── GossipBroadcastSequenceEntry ────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipBroadcastSequenceEntry {
    pub epoch_end:          u64,
    pub out_of_order_count: u32,
    pub total_received:     u32,
    pub disorder_rate_pct:  u32,
    pub disordered:         bool,
    pub entry_hash:         [u8; 32],
    pub prev_hash:          [u8; 32],
}

fn compute_broadcast_sequence_hash(
    prev:               &[u8; 32],
    epoch_end:          u64,
    out_of_order_count: u32,
    total_received:     u32,
    disorder_rate_pct:  u32,
    disordered:         bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(out_of_order_count.to_be_bytes());
    h.update(total_received.to_be_bytes());
    h.update(disorder_rate_pct.to_be_bytes());
    h.update([disordered as u8]);
    h.finalize().into()
}

// ─── GossipBroadcastSequenceLog ──────────────────────────────────────────────

pub struct GossipBroadcastSequenceLog {
    entries: Vec<GossipBroadcastSequenceEntry>,
}

impl GossipBroadcastSequenceLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn entry_count(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self)    -> bool  { self.entries.is_empty() }
    pub fn entries(&self)     -> &[GossipBroadcastSequenceEntry] { &self.entries }
    pub fn latest(&self)      -> Option<&GossipBroadcastSequenceEntry> { self.entries.last() }

    /// Count of epochs where disordered == true.
    pub fn disordered_count(&self) -> usize {
        self.entries.iter().filter(|e| e.disordered).count()
    }

    /// Sum of all out_of_order_count values across epochs.
    pub fn total_out_of_order(&self) -> u64 {
        self.entries.iter().map(|e| e.out_of_order_count as u64).sum()
    }

    /// Integer mean of all per-epoch disorder_rate_pct values. Returns 0 if empty.
    pub fn mean_disorder_rate_pct(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        let sum: u64 = self.entries.iter().map(|e| e.disorder_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    /// Record sequence disorder stats for one epoch.
    /// disorder_rate_pct = (out_of_order_count * 100) / max(total_received, 1), capped at 100.
    /// disordered = disorder_rate_pct > DISORDER_THRESHOLD.
    pub fn record(
        &mut self,
        epoch_end:          u64,
        out_of_order_count: u32,
        total_received:     u32,
    ) -> &GossipBroadcastSequenceEntry {
        let denom = total_received.max(1) as u64;
        let disorder_rate_pct = ((out_of_order_count as u64 * 100) / denom).min(100) as u32;
        let disordered = disorder_rate_pct > DISORDER_THRESHOLD;

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_BROADCAST_SEQUENCE_GENESIS_HASH);

        let entry_hash = compute_broadcast_sequence_hash(
            &prev, epoch_end, out_of_order_count, total_received, disorder_rate_pct, disordered,
        );

        self.entries.push(GossipBroadcastSequenceEntry {
            epoch_end,
            out_of_order_count,
            total_received,
            disorder_rate_pct,
            disordered,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_BROADCAST_SEQUENCE_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_broadcast_sequence_hash(
                &prev, e.epoch_end, e.out_of_order_count, e.total_received,
                e.disorder_rate_pct, e.disordered,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipBroadcastSequenceLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────

    #[test]
    fn record_fields_stored() {
        let mut log = GossipBroadcastSequenceLog::new();
        let e = log.record(1, 10, 100);
        assert_eq!(e.epoch_end, 1);
        assert_eq!(e.out_of_order_count, 10);
        assert_eq!(e.total_received, 100);
        assert_eq!(e.disorder_rate_pct, 10); // 10*100/100 = 10
    }

    #[test]
    fn zero_disorder_zero_rate() {
        let mut log = GossipBroadcastSequenceLog::new();
        let e = log.record(1, 0, 100);
        assert_eq!(e.disorder_rate_pct, 0);
        assert!(!e.disordered);
    }

    #[test]
    fn total_received_zero_uses_max_one() {
        let mut log = GossipBroadcastSequenceLog::new();
        let e = log.record(1, 0, 0);
        assert_eq!(e.disorder_rate_pct, 0);
        assert!(!e.disordered);
    }

    #[test]
    fn disorder_rate_capped_at_100() {
        let mut log = GossipBroadcastSequenceLog::new();
        let e = log.record(1, 200, 100);
        assert_eq!(e.disorder_rate_pct, 100);
    }

    // ── disordered threshold ──────────────────────────────────────────────────

    #[test]
    fn at_threshold_not_disordered() {
        let mut log = GossipBroadcastSequenceLog::new();
        // exactly 15% — NOT disordered (> 15, not >=)
        let e = log.record(1, 15, 100);
        assert_eq!(e.disorder_rate_pct, 15);
        assert!(!e.disordered);
    }

    #[test]
    fn above_threshold_disordered() {
        let mut log = GossipBroadcastSequenceLog::new();
        // 16% > DISORDER_THRESHOLD(15)
        let e = log.record(1, 16, 100);
        assert_eq!(e.disorder_rate_pct, 16);
        assert!(e.disordered);
    }

    #[test]
    fn below_threshold_not_disordered() {
        let mut log = GossipBroadcastSequenceLog::new();
        let e = log.record(1, 10, 100);
        assert!(!e.disordered);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn disordered_count_correct() {
        let mut log = GossipBroadcastSequenceLog::new();
        log.record(1, 5, 100);  // 5% — ok
        log.record(2, 20, 100); // 20% — disordered
        log.record(3, 15, 100); // 15% — at threshold, not disordered
        log.record(4, 30, 100); // 30% — disordered
        assert_eq!(log.disordered_count(), 2);
    }

    #[test]
    fn total_out_of_order_correct() {
        let mut log = GossipBroadcastSequenceLog::new();
        log.record(1, 4, 100);
        log.record(2, 8, 100);
        log.record(3, 12, 100);
        assert_eq!(log.total_out_of_order(), 24);
    }

    #[test]
    fn mean_disorder_rate_correct() {
        let mut log = GossipBroadcastSequenceLog::new();
        log.record(1, 10, 100); // 10%
        log.record(2, 20, 100); // 20%
        log.record(3, 30, 100); // 30%
        // (10+20+30)/3 = 20
        assert_eq!(log.mean_disorder_rate_pct(), 20);
    }

    #[test]
    fn mean_disorder_rate_empty_zero() {
        let log = GossipBroadcastSequenceLog::new();
        assert_eq!(log.mean_disorder_rate_pct(), 0);
    }

    #[test]
    fn total_out_of_order_empty_zero() {
        let log = GossipBroadcastSequenceLog::new();
        assert_eq!(log.total_out_of_order(), 0);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipBroadcastSequenceLog::new();
        let e = log.record(1, 10, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipBroadcastSequenceLog::new();
        let e = log.record(1, 10, 100);
        assert_eq!(e.prev_hash, GOSSIP_BROADCAST_SEQUENCE_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipBroadcastSequenceLog::new();
        log.record(1, 10, 100);
        let h0 = log.entries()[0].entry_hash;
        log.record(2, 20, 100);
        assert_eq!(log.entries()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipBroadcastSequenceLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipBroadcastSequenceLog::new();
        for i in 1u64..=5 { log.record(i, i as u32 * 5, i as u32 * 30); }
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipBroadcastSequenceLog::new();
        log.record(1, 10, 100);
        log.record(2, 20, 100);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipBroadcastSequenceLog::new();
        let mut l2 = GossipBroadcastSequenceLog::new();
        let h1 = l1.record(9, 12, 80).entry_hash;
        let h2 = l2.record(9, 12, 80).entry_hash;
        assert_eq!(h1, h2);
    }
}
