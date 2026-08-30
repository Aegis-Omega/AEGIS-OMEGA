//! Gate 422 — Gossip Broadcast Duplicate Detection Monitor (T2)
//! Tracks duplicate message rate per gossip broadcast epoch.
//! DUPLICATION_THRESHOLD = 10: dup_rate_pct > 10 → high_duplication

use sha2::{Sha256, Digest};

pub const DUPLICATE_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const DUPLICATION_THRESHOLD: u32 = 10;

// ─── GossipBroadcastDuplicateEntry ───────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipBroadcastDuplicateEntry {
    pub epoch_end:       u64,
    pub duplicate_count: u32,
    pub total_received:  u32,
    pub dup_rate_pct:    u32,
    pub high_duplication: bool,
    pub entry_hash:      [u8; 32],
    pub prev_hash:       [u8; 32],
}

fn compute_hash(
    prev:            &[u8; 32],
    epoch_end:       u64,
    duplicate_count: u32,
    total_received:  u32,
    dup_rate_pct:    u32,
    high_duplication: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(duplicate_count.to_be_bytes());
    h.update(total_received.to_be_bytes());
    h.update(dup_rate_pct.to_be_bytes());
    h.update([high_duplication as u8]);
    h.finalize().into()
}

// ─── GossipBroadcastDuplicateLog ─────────────────────────────────────────────

pub struct GossipBroadcastDuplicateLog {
    pub entries: Vec<GossipBroadcastDuplicateEntry>,
}

impl GossipBroadcastDuplicateLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    /// Count of epochs where high_duplication == true.
    pub fn high_duplication_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_duplication).count()
    }

    /// Sum of all duplicate_count values across all epochs.
    pub fn total_duplicates(&self) -> u64 {
        self.entries.iter().map(|e| e.duplicate_count as u64).sum()
    }

    /// Integer mean of all per-epoch dup_rate_pct values. Returns 0 if empty.
    pub fn mean_dup_rate_pct(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        let sum: u64 = self.entries.iter().map(|e| e.dup_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    /// Record duplicate stats for one epoch.
    /// dup_rate_pct = (duplicate_count * 100) / max(total_received, 1), capped at 100.
    /// high_duplication = dup_rate_pct > DUPLICATION_THRESHOLD.
    pub fn record(
        &mut self,
        epoch_end:       u64,
        duplicate_count: u32,
        total_received:  u32,
    ) -> &GossipBroadcastDuplicateEntry {
        let denom = total_received.max(1) as u64;
        let dup_rate_pct = ((duplicate_count as u64 * 100) / denom).min(100) as u32;
        let high_duplication = dup_rate_pct > DUPLICATION_THRESHOLD;

        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(DUPLICATE_GENESIS_HASH);

        let entry_hash = compute_hash(
            &prev, epoch_end, duplicate_count, total_received, dup_rate_pct, high_duplication,
        );

        self.entries.push(GossipBroadcastDuplicateEntry {
            epoch_end,
            duplicate_count,
            total_received,
            dup_rate_pct,
            high_duplication,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = DUPLICATE_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev, e.epoch_end, e.duplicate_count, e.total_received,
                e.dup_rate_pct, e.high_duplication,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipBroadcastDuplicateLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // 1. record fields set correctly (dup_rate_pct computed, high_duplication=true when rate > 10)
    #[test]
    fn record_fields_set_correctly() {
        let mut log = GossipBroadcastDuplicateLog::new();
        let e = log.record(42, 15, 100);
        assert_eq!(e.epoch_end, 42);
        assert_eq!(e.duplicate_count, 15);
        assert_eq!(e.total_received, 100);
        assert_eq!(e.dup_rate_pct, 15); // 15*100/100 = 15
        #[allow(clippy::bool_assert_comparison)]
        { assert_eq!(e.high_duplication, true); } // 15 > 10
    }

    // 2. high_duplication=false when dup_rate_pct == DUPLICATION_THRESHOLD (exactly at threshold = not high)
    #[test]
    fn high_duplication_false_at_exact_threshold() {
        let mut log = GossipBroadcastDuplicateLog::new();
        let e = log.record(1, 10, 100); // 10*100/100 = 10 == DUPLICATION_THRESHOLD
        assert_eq!(e.dup_rate_pct, 10);
        #[allow(clippy::bool_assert_comparison)]
        { assert_eq!(e.high_duplication, false); }
    }

    // 3. dup_rate_pct capped at 100 even when duplicate_count > total_received
    #[test]
    fn dup_rate_pct_capped_at_100() {
        let mut log = GossipBroadcastDuplicateLog::new();
        let e = log.record(1, 200, 50); // 200*100/50 = 400, capped at 100
        assert_eq!(e.dup_rate_pct, 100);
    }

    // 4. total_received=0 uses max(total_received,1)=1, no division by zero
    #[test]
    fn total_received_zero_no_div_by_zero() {
        let mut log = GossipBroadcastDuplicateLog::new();
        let e = log.record(1, 0, 0); // denom = max(0,1) = 1, 0*100/1 = 0
        assert_eq!(e.dup_rate_pct, 0);
    }

    // 5. DUPLICATION_THRESHOLD == 10
    #[test]
    fn duplication_threshold_value() {
        assert_eq!(DUPLICATION_THRESHOLD, 10);
    }

    // 6. entry_hash is 32 bytes (non-zero for non-genesis entry)
    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipBroadcastDuplicateLog::new();
        let e = log.record(1, 5, 50);
        assert_eq!(e.entry_hash.len(), 32);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    // 7. first entry prev_hash == DUPLICATE_GENESIS_HASH
    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipBroadcastDuplicateLog::new();
        let e = log.record(1, 5, 50);
        assert_eq!(e.prev_hash, DUPLICATE_GENESIS_HASH);
    }

    // 8. second entry prev_hash == first entry entry_hash
    #[test]
    fn second_entry_prev_links_to_first() {
        let mut log = GossipBroadcastDuplicateLog::new();
        log.record(1, 5, 50);
        let h0 = log.entries[0].entry_hash;
        log.record(2, 8, 80);
        assert_eq!(log.entries[1].prev_hash, h0);
    }

    // 9. verify_chain on empty log returns (true, None)
    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipBroadcastDuplicateLog::new();
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    // 10. verify_chain on 1-entry log returns (true, None)
    #[test]
    fn verify_chain_single_entry_ok() {
        let mut log = GossipBroadcastDuplicateLog::new();
        log.record(1, 3, 30);
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    // 11. verify_chain on 3-entry log returns (true, None)
    #[test]
    fn verify_chain_three_entries_ok() {
        let mut log = GossipBroadcastDuplicateLog::new();
        log.record(1, 3, 30);
        log.record(2, 6, 60);
        log.record(3, 9, 90);
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    // 12. verify_chain detects tamper in first entry (entry_hash changed) → (false, Some(0))
    #[test]
    fn verify_chain_detects_tamper_first_entry() {
        let mut log = GossipBroadcastDuplicateLog::new();
        log.record(1, 5, 50);
        log.record(2, 8, 80);
        log.entries[0].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // 13. verify_chain detects tamper in middle entry → (false, Some(1)) for 3-entry log
    #[test]
    fn verify_chain_detects_tamper_middle_entry() {
        let mut log = GossipBroadcastDuplicateLog::new();
        log.record(1, 5, 50);
        log.record(2, 8, 80);
        log.record(3, 3, 30);
        log.entries[1].entry_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    // 14. determinism: same inputs → same entry_hash across 3 separate record calls
    #[test]
    fn entry_hash_deterministic() {
        let mut l1 = GossipBroadcastDuplicateLog::new();
        let mut l2 = GossipBroadcastDuplicateLog::new();
        let mut l3 = GossipBroadcastDuplicateLog::new();
        let h1 = l1.record(7, 12, 80).entry_hash;
        let h2 = l2.record(7, 12, 80).entry_hash;
        let h3 = l3.record(7, 12, 80).entry_hash;
        assert_eq!(h1, h2);
        assert_eq!(h2, h3);
    }

    // 15. high_duplication_count() correct for mixed log
    #[test]
    fn high_duplication_count_correct() {
        let mut log = GossipBroadcastDuplicateLog::new();
        log.record(1, 5, 100);  //  5% — not high
        log.record(2, 15, 100); // 15% — high
        log.record(3, 10, 100); // 10% — exactly at threshold, not high
        log.record(4, 20, 100); // 20% — high
        assert_eq!(log.high_duplication_count(), 2);
    }

    // 16. total_duplicates() sums correctly
    #[test]
    fn total_duplicates_sums_correctly() {
        let mut log = GossipBroadcastDuplicateLog::new();
        log.record(1, 3, 50);
        log.record(2, 7, 80);
        log.record(3, 2, 30);
        assert_eq!(log.total_duplicates(), 12);
    }

    // 17. mean_dup_rate_pct() returns 0 for empty log
    #[test]
    fn mean_dup_rate_pct_empty_returns_zero() {
        let log = GossipBroadcastDuplicateLog::new();
        assert_eq!(log.mean_dup_rate_pct(), 0);
    }

    // 18. mean_dup_rate_pct() correct for multi-entry log (integer average)
    #[test]
    fn mean_dup_rate_pct_correct() {
        let mut log = GossipBroadcastDuplicateLog::new();
        log.record(1, 6, 100);  //  6%
        log.record(2, 12, 100); // 12%
        log.record(3, 9, 100);  //  9%
        // (6 + 12 + 9) / 3 = 9
        assert_eq!(log.mean_dup_rate_pct(), 9);
    }

    // 19. Default log has 0 entries
    #[test]
    fn default_log_has_zero_entries() {
        let log = GossipBroadcastDuplicateLog::default();
        assert_eq!(log.entries.len(), 0);
    }
}
