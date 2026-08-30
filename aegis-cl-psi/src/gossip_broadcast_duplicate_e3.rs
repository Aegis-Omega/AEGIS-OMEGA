//! Gate 459 — Gossip Broadcast Duplicate E3 Monitor (T2)
//! Tracks duplicate e3 rate per gossip broadcast epoch.
//! HIGH_DUPLICATION_E3_THRESHOLD = 10: rate_pct > 10 → high_duplication_e3

use sha2::{Sha256, Digest};

pub const DUPLICATE_E3_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_DUPLICATION_E3_THRESHOLD: u32 = 10;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipDuplicateE3Entry {
    pub epoch_end:           u64,
    pub duplicate_count:     u32,
    pub total_received:      u32,
    pub duplicate_rate_pct:  u32,
    pub high_duplication_e3: bool,
    pub entry_hash:          [u8; 32],
    pub prev_hash:           [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    duplicate_count: u32,
    total_received: u32,
    rate_pct: u32,
    high_duplication_e3: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(duplicate_count.to_be_bytes());
    h.update(total_received.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_duplication_e3 as u8]);
    h.finalize().into()
}

pub struct GossipDuplicateE3Log {
    pub entries: Vec<GossipDuplicateE3Entry>,
}

impl GossipDuplicateE3Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        duplicate_count: u32,
        total_received: u32,
    ) -> &GossipDuplicateE3Entry {
        let denom = total_received.max(1) as u64;
        let rate_pct = ((duplicate_count as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_duplication_e3 = rate_pct > HIGH_DUPLICATION_E3_THRESHOLD;
        let prev = self
            .entries
            .last()
            .map(|e| e.entry_hash)
            .unwrap_or(DUPLICATE_E3_GENESIS_HASH);
        let entry_hash = compute_hash(
            &prev,
            epoch_end,
            duplicate_count,
            total_received,
            rate_pct,
            high_duplication_e3,
        );
        self.entries.push(GossipDuplicateE3Entry {
            epoch_end,
            duplicate_count,
            total_received,
            duplicate_rate_pct: rate_pct,
            high_duplication_e3,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_duplication_e3_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_duplication_e3).count()
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
        let mut prev = DUPLICATE_E3_GENESIS_HASH;
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
                e.high_duplication_e3,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipDuplicateE3Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_flag_true() {
        let mut log = GossipDuplicateE3Log::new();
        let e = log.record(1000, 50, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.duplicate_count, 50);
        assert_eq!(e.total_received, 100);
        assert_eq!(e.duplicate_rate_pct, 50);
        assert!(e.high_duplication_e3);
    }

    #[test]
    fn test_flag_false_when_exactly_at_threshold() {
        let mut log = GossipDuplicateE3Log::new();
        // rate = (10 * 100) / 100 = 10, not > 10 → false
        let e = log.record(2000, 10, 100);
        assert_eq!(e.duplicate_rate_pct, 10);
        assert!(!e.high_duplication_e3);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipDuplicateE3Log::new();
        // duplicate_count > total_received → rate would exceed 100
        let e = log.record(3000, 200, 100);
        assert_eq!(e.duplicate_rate_pct, 100);
        assert!(e.high_duplication_e3);
    }

    #[test]
    fn test_total_received_zero_no_div_by_zero() {
        let mut log = GossipDuplicateE3Log::new();
        let e = log.record(4000, 5, 0);
        // denom = max(0,1) = 1, rate = 500 → capped at 100
        assert_eq!(e.duplicate_rate_pct, 100);
        assert!(e.high_duplication_e3);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(HIGH_DUPLICATION_E3_THRESHOLD, 10u32);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipDuplicateE3Log::new();
        let e = log.record(5000, 1, 10);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipDuplicateE3Log::new();
        let e = log.record(6000, 1, 10);
        assert_eq!(e.prev_hash, DUPLICATE_E3_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipDuplicateE3Log::new();
        log.record(7000, 1, 10);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 2, 20);
        let second_prev = log.entries[1].prev_hash;
        assert_eq!(second_prev, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipDuplicateE3Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_one_entry() {
        let mut log = GossipDuplicateE3Log::new();
        log.record(9000, 5, 50);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipDuplicateE3Log::new();
        log.record(10000, 5, 50);
        log.record(11000, 10, 100);
        log.record(12000, 0, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipDuplicateE3Log::new();
        log.record(13000, 5, 50);
        log.record(14000, 10, 100);
        // Tamper first entry
        log.entries[0].duplicate_count = 99;
        let (valid, idx) = log.verify_chain();
        assert!(!valid);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipDuplicateE3Log::new();
        log.record(15000, 5, 50);
        log.record(16000, 10, 100);
        log.record(17000, 2, 20);
        // Tamper second entry
        log.entries[1].duplicate_rate_pct = 77;
        let (valid, idx) = log.verify_chain();
        assert!(!valid);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipDuplicateE3Log::new();
        let e1 = log1.record(18000, 15, 100).entry_hash;

        let mut log2 = GossipDuplicateE3Log::new();
        let e2 = log2.record(18000, 15, 100).entry_hash;

        let mut log3 = GossipDuplicateE3Log::new();
        let e3 = log3.record(18000, 15, 100).entry_hash;

        assert_eq!(e1, e2);
        assert_eq!(e2, e3);
    }

    #[test]
    fn test_high_duplication_e3_count_mixed() {
        let mut log = GossipDuplicateE3Log::new();
        // rate = 5 → not high
        log.record(19000, 5, 100);
        // rate = 50 → high
        log.record(20000, 50, 100);
        // rate = 10 → not high (boundary)
        log.record(21000, 10, 100);
        // rate = 11 → high
        log.record(22000, 11, 100);
        assert_eq!(log.high_duplication_e3_count(), 2);
    }

    #[test]
    fn test_total_duplicate_count_sums_correctly() {
        let mut log = GossipDuplicateE3Log::new();
        log.record(23000, 10, 100);
        log.record(24000, 20, 100);
        log.record(25000, 30, 100);
        assert_eq!(log.total_duplicate_count(), 60u64);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipDuplicateE3Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry_correct() {
        let mut log = GossipDuplicateE3Log::new();
        // rate = 20
        log.record(26000, 20, 100);
        // rate = 40
        log.record(27000, 40, 100);
        // rate = 60
        log.record(28000, 60, 100);
        // mean = (20 + 40 + 60) / 3 = 40
        assert_eq!(log.mean_rate_pct(), 40);
    }

    #[test]
    fn test_default_zero_entries() {
        let log = GossipDuplicateE3Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}