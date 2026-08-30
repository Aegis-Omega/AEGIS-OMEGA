//! Gate 421 — Gossip Broadcast Batch Fill Monitor (T2)
//! Tracks batch fill efficiency per gossip broadcast epoch.
//! UNDERFILL_THRESHOLD = 50: fill_rate_pct < 50 → under_filled

use sha2::{Sha256, Digest};

pub const BATCH_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const UNDERFILL_THRESHOLD: u32 = 50;

// ─── GossipBroadcastBatchEntry ────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipBroadcastBatchEntry {
    pub epoch_end:         u64,
    pub messages_in_batch: u32,
    pub batch_capacity:    u32,
    pub fill_rate_pct:     u32,
    pub under_filled:      bool,
    pub entry_hash:        [u8; 32],
    pub prev_hash:         [u8; 32],
}

fn compute_hash(
    prev:              &[u8; 32],
    epoch_end:         u64,
    messages_in_batch: u32,
    batch_capacity:    u32,
    fill_rate_pct:     u32,
    under_filled:      bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(messages_in_batch.to_be_bytes());
    h.update(batch_capacity.to_be_bytes());
    h.update(fill_rate_pct.to_be_bytes());
    h.update([under_filled as u8]);
    h.finalize().into()
}

// ─── GossipBroadcastBatchLog ──────────────────────────────────────────────────

pub struct GossipBroadcastBatchLog {
    pub entries: Vec<GossipBroadcastBatchEntry>,
}

impl GossipBroadcastBatchLog {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    /// Record one epoch's batch fill statistics and append a hash-chained entry.
    pub fn record(
        &mut self,
        epoch_end:         u64,
        messages_in_batch: u32,
        batch_capacity:    u32,
    ) -> &GossipBroadcastBatchEntry {
        let denom = batch_capacity.max(1);
        let raw_rate = (messages_in_batch as u64 * 100) / denom as u64;
        let fill_rate_pct = raw_rate.min(100) as u32;
        let under_filled = fill_rate_pct < UNDERFILL_THRESHOLD;

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(BATCH_GENESIS_HASH);

        let entry_hash = compute_hash(
            &prev,
            epoch_end,
            messages_in_batch,
            batch_capacity,
            fill_rate_pct,
            under_filled,
        );

        self.entries.push(GossipBroadcastBatchEntry {
            epoch_end,
            messages_in_batch,
            batch_capacity,
            fill_rate_pct,
            under_filled,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    /// Count entries where under_filled is true.
    pub fn under_filled_count(&self) -> usize {
        self.entries.iter().filter(|e| e.under_filled).count()
    }

    /// Sum of messages_in_batch across all entries.
    pub fn total_messages(&self) -> u64 {
        self.entries.iter().map(|e| e.messages_in_batch as u64).sum()
    }

    /// Integer average of fill_rate_pct; returns 0 for an empty log.
    pub fn mean_fill_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.fill_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    /// Recompute every hash and verify the chain is intact.
    /// Returns (true, None) when valid; (false, Some(i)) at the first broken link.
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = BATCH_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.messages_in_batch,
                e.batch_capacity,
                e.fill_rate_pct,
                e.under_filled,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipBroadcastBatchLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // 1. record fields set correctly; fill_rate_pct computed; under_filled=true when rate < 50
    #[test]
    fn record_fields_set_correctly() {
        let mut log = GossipBroadcastBatchLog::new();
        let e = log.record(10, 20, 100);
        assert_eq!(e.epoch_end, 10);
        assert_eq!(e.messages_in_batch, 20);
        assert_eq!(e.batch_capacity, 100);
        assert_eq!(e.fill_rate_pct, 20);
        #[allow(clippy::bool_assert_comparison)]
        { assert_eq!(e.under_filled, true); }
    }

    // 2. under_filled=false when fill_rate_pct >= 50 (exactly at threshold = not under_filled)
    #[test]
    fn under_filled_false_at_threshold() {
        let mut log = GossipBroadcastBatchLog::new();
        let e = log.record(1, 50, 100);
        assert_eq!(e.fill_rate_pct, 50);
        #[allow(clippy::bool_assert_comparison)]
        { assert_eq!(e.under_filled, false); }
    }

    // 3. fill_rate_pct capped at 100 even when messages_in_batch > batch_capacity
    #[test]
    fn fill_rate_pct_capped_at_100() {
        let mut log = GossipBroadcastBatchLog::new();
        let e = log.record(1, 200, 100);
        assert_eq!(e.fill_rate_pct, 100);
    }

    // 4. batch_capacity=0 uses max(batch_capacity,1)=1, no division by zero
    #[test]
    fn batch_capacity_zero_no_div_by_zero() {
        let mut log = GossipBroadcastBatchLog::new();
        let e = log.record(1, 0, 0);
        // 0 * 100 / 1 = 0, capped at 100 → 0
        assert_eq!(e.fill_rate_pct, 0);
        #[allow(clippy::bool_assert_comparison)]
        { assert_eq!(e.under_filled, true); }
    }

    // 5. UNDERFILL_THRESHOLD == 50
    #[test]
    fn underfill_threshold_is_50() {
        assert_eq!(UNDERFILL_THRESHOLD, 50);
    }

    // 6. entry_hash is 32 bytes (non-zero for non-genesis entry)
    #[test]
    fn entry_hash_nonzero_for_non_genesis() {
        let mut log = GossipBroadcastBatchLog::new();
        let e = log.record(1, 60, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
        assert_eq!(e.entry_hash.len(), 32);
    }

    // 7. first entry prev_hash == BATCH_GENESIS_HASH
    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipBroadcastBatchLog::new();
        log.record(1, 50, 100);
        assert_eq!(log.entries[0].prev_hash, BATCH_GENESIS_HASH);
    }

    // 8. second entry prev_hash == first entry entry_hash
    #[test]
    fn second_entry_links_to_first() {
        let mut log = GossipBroadcastBatchLog::new();
        log.record(1, 50, 100);
        let h0 = log.entries[0].entry_hash;
        log.record(2, 60, 100);
        assert_eq!(log.entries[1].prev_hash, h0);
    }

    // 9. verify_chain on empty log returns (true, None)
    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipBroadcastBatchLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    // 10. verify_chain on 1-entry log returns (true, None)
    #[test]
    fn verify_chain_single_entry_ok() {
        let mut log = GossipBroadcastBatchLog::new();
        log.record(1, 50, 100);
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    // 11. verify_chain on 3-entry log returns (true, None)
    #[test]
    fn verify_chain_three_entries_ok() {
        let mut log = GossipBroadcastBatchLog::new();
        log.record(1, 30, 100);
        log.record(2, 60, 100);
        log.record(3, 80, 100);
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    // 12. verify_chain detects tamper in first entry → (false, Some(0))
    #[test]
    fn verify_chain_detects_tamper_first_entry() {
        let mut log = GossipBroadcastBatchLog::new();
        log.record(1, 50, 100);
        log.record(2, 60, 100);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // 13. verify_chain detects tamper in middle entry → (false, Some(1)) for 3-entry log
    #[test]
    fn verify_chain_detects_tamper_middle_entry() {
        let mut log = GossipBroadcastBatchLog::new();
        log.record(1, 50, 100);
        log.record(2, 60, 100);
        log.record(3, 70, 100);
        log.entries[1].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    // 14. determinism: same inputs → same entry_hash across 3 separate record calls
    #[test]
    fn hash_is_deterministic() {
        let mut l1 = GossipBroadcastBatchLog::new();
        let mut l2 = GossipBroadcastBatchLog::new();
        let mut l3 = GossipBroadcastBatchLog::new();
        let h1 = l1.record(5, 40, 100).entry_hash;
        let h2 = l2.record(5, 40, 100).entry_hash;
        let h3 = l3.record(5, 40, 100).entry_hash;
        assert_eq!(h1, h2);
        assert_eq!(h2, h3);
    }

    // 15. under_filled_count() correct for mixed log
    #[test]
    fn under_filled_count_mixed() {
        let mut log = GossipBroadcastBatchLog::new();
        log.record(1, 20, 100); // fill 20% → under_filled
        log.record(2, 50, 100); // fill 50% → not under_filled
        log.record(3, 80, 100); // fill 80% → not under_filled
        log.record(4, 10, 100); // fill 10% → under_filled
        assert_eq!(log.under_filled_count(), 2);
    }

    // 16. total_messages() sums correctly
    #[test]
    fn total_messages_sums_correctly() {
        let mut log = GossipBroadcastBatchLog::new();
        log.record(1, 10, 100);
        log.record(2, 25, 100);
        log.record(3, 40, 100);
        assert_eq!(log.total_messages(), 75);
    }

    // 17. mean_fill_rate_pct() returns 0 for empty log
    #[test]
    fn mean_fill_rate_pct_empty_returns_zero() {
        let log = GossipBroadcastBatchLog::new();
        assert_eq!(log.mean_fill_rate_pct(), 0);
    }

    // 18. mean_fill_rate_pct() correct for multi-entry log (integer average)
    #[test]
    fn mean_fill_rate_pct_multi_entry() {
        let mut log = GossipBroadcastBatchLog::new();
        log.record(1, 20, 100); // 20%
        log.record(2, 60, 100); // 60%
        log.record(3, 70, 100); // 70%
        // (20 + 60 + 70) / 3 = 150 / 3 = 50
        assert_eq!(log.mean_fill_rate_pct(), 50);
    }

    // 19. Default log has 0 entries
    #[test]
    fn default_log_has_zero_entries() {
        let log = GossipBroadcastBatchLog::default();
        assert_eq!(log.entries.len(), 0);
    }
}
