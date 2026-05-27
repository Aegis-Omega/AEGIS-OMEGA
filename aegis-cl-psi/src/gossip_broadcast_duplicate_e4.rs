//! Gate 494 — Gossip Broadcast Duplicate E4 Monitor (T2)
//! Tracks duplicate e4 rate per gossip broadcast epoch.
//! HIGH_DUPLICATION_E4_THRESHOLD = 10: rate_pct > 10 → high_duplication_e4

use sha2::{Sha256, Digest};

pub const DUPLICATE_E4_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_DUPLICATION_E4_THRESHOLD: u32 = 10;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipDuplicateE4Entry {
    pub epoch_end:          u64,
    pub duplicate_count:    u32,
    pub total_received:     u32,
    pub duplicate_rate_pct: u32,
    pub high_duplication_e4: bool,
    pub entry_hash:         [u8; 32],
    pub prev_hash:          [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    duplicate_count: u32,
    total_received: u32,
    rate_pct: u32,
    high_duplication_e4: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(duplicate_count.to_be_bytes());
    h.update(total_received.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_duplication_e4 as u8]);
    h.finalize().into()
}

pub struct GossipDuplicateE4Log {
    pub entries: Vec<GossipDuplicateE4Entry>,
}

impl GossipDuplicateE4Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        duplicate_count: u32,
        total_received: u32,
    ) -> &GossipDuplicateE4Entry {
        let denom = total_received.max(1) as u64;
        let duplicate_rate_pct = ((duplicate_count as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_duplication_e4 = duplicate_rate_pct > HIGH_DUPLICATION_E4_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(DUPLICATE_E4_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, duplicate_count, total_received, duplicate_rate_pct, high_duplication_e4);
        self.entries.push(GossipDuplicateE4Entry {
            epoch_end,
            duplicate_count,
            total_received,
            duplicate_rate_pct,
            high_duplication_e4,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_duplication_e4_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_duplication_e4).count()
    }

    pub fn total_duplicate_count(&self) -> u64 {
        self.entries.iter().map(|e| e.duplicate_count as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.duplicate_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = DUPLICATE_E4_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.duplicate_count,
                e.total_received,
                e.duplicate_rate_pct,
                e.high_duplication_e4,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipDuplicateE4Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipDuplicateE4Log::new();
        let e = log.record(1000, 50, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.duplicate_count, 50);
        assert_eq!(e.total_received, 100);
        assert_eq!(e.duplicate_rate_pct, 50);
        assert!(e.high_duplication_e4);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipDuplicateE4Log::new();
        // rate = (10 * 100) / 100 = 10, which is NOT > 10
        let e = log.record(2000, 10, 100);
        assert_eq!(e.duplicate_rate_pct, 10);
        assert!(!e.high_duplication_e4);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipDuplicateE4Log::new();
        // duplicate_count > total_received
        let e = log.record(3000, 200, 100);
        assert_eq!(e.duplicate_rate_pct, 100);
        assert!(e.high_duplication_e4);
    }

    #[test]
    fn total_received_zero_no_div_by_zero() {
        let mut log = GossipDuplicateE4Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.duplicate_rate_pct, 0);
        assert!(!e.high_duplication_e4);
    }

    #[test]
    fn threshold_constant_value_is_10() {
        assert_eq!(HIGH_DUPLICATION_E4_THRESHOLD, 10);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipDuplicateE4Log::new();
        let e = log.record(5000, 5, 50);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipDuplicateE4Log::new();
        let e = log.record(6000, 3, 30);
        assert_eq!(e.prev_hash, DUPLICATE_E4_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipDuplicateE4Log::new();
        log.record(7000, 3, 30);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 5, 50);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipDuplicateE4Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_single_entry_returns_true_none() {
        let mut log = GossipDuplicateE4Log::new();
        log.record(9000, 2, 20);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipDuplicateE4Log::new();
        log.record(10000, 1, 10);
        log.record(11000, 2, 20);
        log.record(12000, 3, 30);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipDuplicateE4Log::new();
        log.record(13000, 1, 10);
        log.record(14000, 2, 20);
        log.entries[0].duplicate_count = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipDuplicateE4Log::new();
        log.record(15000, 1, 10);
        log.record(16000, 2, 20);
        log.entries[1].duplicate_count = 77;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut log1 = GossipDuplicateE4Log::new();
        let mut log2 = GossipDuplicateE4Log::new();
        let mut log3 = GossipDuplicateE4Log::new();
        let e1 = log1.record(17000, 15, 100).entry_hash;
        let e2 = log2.record(17000, 15, 100).entry_hash;
        let e3 = log3.record(17000, 15, 100).entry_hash;
        assert_eq!(e1, e2);
        assert_eq!(e2, e3);
    }

    #[test]
    fn high_duplication_e4_count_mixed_log() {
        let mut log = GossipDuplicateE4Log::new();
        // rate = 5% → false
        log.record(18000, 5, 100);
        // rate = 50% → true
        log.record(19000, 50, 100);
        // rate = 10% → false (boundary, not > 10)
        log.record(20000, 10, 100);
        // rate = 11% → true
        log.record(21000, 11, 100);
        assert_eq!(log.high_duplication_e4_count(), 2);
    }

    #[test]
    fn total_duplicate_count_sums_correctly() {
        let mut log = GossipDuplicateE4Log::new();
        log.record(22000, 7, 100);
        log.record(23000, 13, 100);
        log.record(24000, 20, 100);
        assert_eq!(log.total_duplicate_count(), 40);
    }

    #[test]
    fn mean_rate_pct_empty_returns_zero() {
        let log = GossipDuplicateE4Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn mean_rate_pct_multi_entry_correct() {
        let mut log = GossipDuplicateE4Log::new();
        // rate = 10
        log.record(25000, 10, 100);
        // rate = 20
        log.record(26000, 20, 100);
        // rate = 30
        log.record(27000, 30, 100);
        // mean = (10 + 20 + 30) / 3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn default_impl_zero_entries() {
        let log = GossipDuplicateE4Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}