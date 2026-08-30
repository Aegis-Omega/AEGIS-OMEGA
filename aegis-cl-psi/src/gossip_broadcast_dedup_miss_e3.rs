//! Gate 490 — Gossip Broadcast Dedup Miss E3 Monitor (T2)
//! Tracks dedup miss e3 rate per gossip broadcast epoch.
//! HIGH_DEDUP_MISS_E3_THRESHOLD = 3: rate_pct > 3 → high_dedup_miss_e3

use sha2::{Sha256, Digest};

pub const DEDUP_MISS_E3_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_DEDUP_MISS_E3_THRESHOLD: u32 = 3;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipDedupMissE3Entry {
    pub epoch_end:            u64,
    pub dedup_misses:         u32,
    pub total_received:       u32,
    pub dedup_misses_rate_pct: u32,
    pub high_dedup_miss_e3:   bool,
    pub entry_hash:           [u8; 32],
    pub prev_hash:            [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    dedup_misses: u32,
    total_received: u32,
    rate_pct: u32,
    high_dedup_miss_e3: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(dedup_misses.to_be_bytes());
    h.update(total_received.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_dedup_miss_e3 as u8]);
    h.finalize().into()
}

pub struct GossipDedupMissE3Log {
    pub entries: Vec<GossipDedupMissE3Entry>,
}

impl GossipDedupMissE3Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        dedup_misses: u32,
        total_received: u32,
    ) -> &GossipDedupMissE3Entry {
        let denom = total_received.max(1) as u64;
        let dedup_misses_rate_pct = ((dedup_misses as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_dedup_miss_e3 = dedup_misses_rate_pct > HIGH_DEDUP_MISS_E3_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(DEDUP_MISS_E3_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, dedup_misses, total_received, dedup_misses_rate_pct, high_dedup_miss_e3);
        self.entries.push(GossipDedupMissE3Entry {
            epoch_end,
            dedup_misses,
            total_received,
            dedup_misses_rate_pct,
            high_dedup_miss_e3,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_dedup_miss_e3_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_dedup_miss_e3).count()
    }

    pub fn total_dedup_misses(&self) -> u64 {
        self.entries.iter().map(|e| e.dedup_misses as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.dedup_misses_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = DEDUP_MISS_E3_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.dedup_misses,
                e.total_received,
                e.dedup_misses_rate_pct,
                e.high_dedup_miss_e3,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipDedupMissE3Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipDedupMissE3Log::new();
        let e = log.record(1000, 10, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.dedup_misses, 10);
        assert_eq!(e.total_received, 100);
        assert_eq!(e.dedup_misses_rate_pct, 10);
        assert!(e.high_dedup_miss_e3);
    }

    #[test]
    fn test_flag_false_when_exactly_at_threshold() {
        let mut log = GossipDedupMissE3Log::new();
        // rate_pct == 3 → not > 3, so flag should be false
        let e = log.record(2000, 3, 100);
        assert_eq!(e.dedup_misses_rate_pct, 3);
        assert!(!e.high_dedup_miss_e3);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipDedupMissE3Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.dedup_misses_rate_pct, 100);
    }

    #[test]
    fn test_total_received_zero_no_div_by_zero() {
        let mut log = GossipDedupMissE3Log::new();
        let e = log.record(4000, 5, 0);
        // denom = max(0,1) = 1, rate = 500/1 capped at 100
        assert_eq!(e.dedup_misses_rate_pct, 100);
        assert!(e.high_dedup_miss_e3);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(HIGH_DEDUP_MISS_E3_THRESHOLD, 3);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipDedupMissE3Log::new();
        let e = log.record(5000, 1, 10);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_equals_genesis() {
        let mut log = GossipDedupMissE3Log::new();
        let e = log.record(6000, 1, 10);
        assert_eq!(e.prev_hash, DEDUP_MISS_E3_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipDedupMissE3Log::new();
        log.record(7000, 1, 10);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 2, 20);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn test_verify_chain_empty_returns_true_none() {
        let log = GossipDedupMissE3Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_one_entry_returns_true_none() {
        let mut log = GossipDedupMissE3Log::new();
        log.record(9000, 1, 10);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries_returns_true_none() {
        let mut log = GossipDedupMissE3Log::new();
        log.record(10000, 1, 10);
        log.record(11000, 2, 20);
        log.record(12000, 3, 30);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipDedupMissE3Log::new();
        log.record(13000, 1, 10);
        log.record(14000, 2, 20);
        log.entries[0].dedup_misses = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipDedupMissE3Log::new();
        log.record(15000, 1, 10);
        log.record(16000, 2, 20);
        log.entries[1].dedup_misses = 99;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipDedupMissE3Log::new();
        let mut log2 = GossipDedupMissE3Log::new();
        let mut log3 = GossipDedupMissE3Log::new();
        log1.record(17000, 5, 50);
        log2.record(17000, 5, 50);
        log3.record(17000, 5, 50);
        assert_eq!(log1.entries[0].entry_hash, log2.entries[0].entry_hash);
        assert_eq!(log2.entries[0].entry_hash, log3.entries[0].entry_hash);
    }

    #[test]
    fn test_high_dedup_miss_e3_count_mixed_log() {
        let mut log = GossipDedupMissE3Log::new();
        log.record(18000, 1, 100);  // rate=1, flag=false
        log.record(19000, 4, 100);  // rate=4, flag=true
        log.record(20000, 3, 100);  // rate=3, flag=false
        log.record(21000, 10, 100); // rate=10, flag=true
        assert_eq!(log.high_dedup_miss_e3_count(), 2);
    }

    #[test]
    fn test_total_dedup_misses_sums_correctly() {
        let mut log = GossipDedupMissE3Log::new();
        log.record(22000, 5, 100);
        log.record(23000, 10, 100);
        log.record(24000, 15, 100);
        assert_eq!(log.total_dedup_misses(), 30);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipDedupMissE3Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry_correct() {
        let mut log = GossipDedupMissE3Log::new();
        log.record(25000, 10, 100); // rate=10
        log.record(26000, 20, 100); // rate=20
        log.record(27000, 30, 100); // rate=30
        // mean = (10+20+30)/3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn test_default_has_zero_entries() {
        let log = GossipDedupMissE3Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}