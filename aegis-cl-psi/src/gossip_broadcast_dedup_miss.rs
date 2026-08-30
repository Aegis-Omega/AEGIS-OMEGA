//! Gate 455 — Gossip Broadcast Dedup Miss Monitor (T2)
//! Tracks dedup miss rate per gossip broadcast epoch.
//! HIGH_DEDUP_MISS_THRESHOLD = 3: rate_pct > 3 → high_dedup_miss

use sha2::{Sha256, Digest};

pub const DEDUP_MISS_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_DEDUP_MISS_THRESHOLD: u32 = 3;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipDedupMissEntry {
    pub epoch_end:           u64,
    pub dedup_misses:        u32,
    pub total_received:      u32,
    pub dedup_misses_rate_pct: u32,
    pub high_dedup_miss:     bool,
    pub entry_hash:          [u8; 32],
    pub prev_hash:           [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    dedup_misses: u32,
    total_received: u32,
    rate_pct: u32,
    high_dedup_miss: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(dedup_misses.to_be_bytes());
    h.update(total_received.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_dedup_miss as u8]);
    h.finalize().into()
}

pub struct GossipDedupMissLog {
    pub entries: Vec<GossipDedupMissEntry>,
}

impl GossipDedupMissLog {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        dedup_misses: u32,
        total_received: u32,
    ) -> &GossipDedupMissEntry {
        let denom = total_received.max(1) as u64;
        let rate_pct = ((dedup_misses as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_dedup_miss = rate_pct > HIGH_DEDUP_MISS_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(DEDUP_MISS_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, dedup_misses, total_received, rate_pct, high_dedup_miss);
        self.entries.push(GossipDedupMissEntry {
            epoch_end,
            dedup_misses,
            total_received,
            dedup_misses_rate_pct: rate_pct,
            high_dedup_miss,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_dedup_miss_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_dedup_miss).count()
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
        let mut prev = DEDUP_MISS_GENESIS_HASH;
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
                e.high_dedup_miss,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipDedupMissLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_flag_true() {
        let mut log = GossipDedupMissLog::new();
        let e = log.record(1000, 50, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.dedup_misses, 50);
        assert_eq!(e.total_received, 100);
        assert_eq!(e.dedup_misses_rate_pct, 50);
        assert!(e.high_dedup_miss);
    }

    #[test]
    fn test_flag_false_when_exactly_at_threshold() {
        let mut log = GossipDedupMissLog::new();
        // rate_pct == 3 → not > 3 → high_dedup_miss = false
        let e = log.record(2000, 3, 100);
        assert_eq!(e.dedup_misses_rate_pct, 3);
        assert!(!e.high_dedup_miss);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipDedupMissLog::new();
        // dedup_misses > total_received
        let e = log.record(3000, 200, 100);
        assert_eq!(e.dedup_misses_rate_pct, 100);
        assert!(e.high_dedup_miss);
    }

    #[test]
    fn test_total_received_zero_no_div_by_zero() {
        let mut log = GossipDedupMissLog::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.dedup_misses_rate_pct, 0);
        assert!(!e.high_dedup_miss);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(HIGH_DEDUP_MISS_THRESHOLD, 3);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipDedupMissLog::new();
        let e = log.record(5000, 10, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipDedupMissLog::new();
        let e = log.record(6000, 5, 100);
        assert_eq!(e.prev_hash, DEDUP_MISS_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipDedupMissLog::new();
        log.record(7000, 5, 100);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 10, 100);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipDedupMissLog::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_one_entry() {
        let mut log = GossipDedupMissLog::new();
        log.record(9000, 5, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipDedupMissLog::new();
        log.record(10000, 5, 100);
        log.record(11000, 10, 200);
        log.record(12000, 15, 300);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipDedupMissLog::new();
        log.record(13000, 5, 100);
        log.record(14000, 10, 200);
        // Tamper entry 0's dedup_misses
        log.entries[0].dedup_misses = 99;
        let result = log.verify_chain();
        assert_eq!(result, (false, Some(0)));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipDedupMissLog::new();
        log.record(15000, 5, 100);
        log.record(16000, 10, 200);
        log.record(17000, 15, 300);
        // Tamper entry 1's epoch_end
        log.entries[1].epoch_end = 99999;
        let result = log.verify_chain();
        assert_eq!(result, (false, Some(1)));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipDedupMissLog::new();
        let h1 = log1.record(18000, 5, 100).entry_hash;

        let mut log2 = GossipDedupMissLog::new();
        let h2 = log2.record(18000, 5, 100).entry_hash;

        let mut log3 = GossipDedupMissLog::new();
        let h3 = log3.record(18000, 5, 100).entry_hash;

        assert_eq!(h1, h2);
        assert_eq!(h2, h3);
    }

    #[test]
    fn test_high_dedup_miss_count_mixed_log() {
        let mut log = GossipDedupMissLog::new();
        log.record(19000, 1, 100);  // rate=1, not high
        log.record(20000, 3, 100);  // rate=3, not high (boundary)
        log.record(21000, 4, 100);  // rate=4, high
        log.record(22000, 50, 100); // rate=50, high
        log.record(23000, 0, 100);  // rate=0, not high
        assert_eq!(log.high_dedup_miss_count(), 2);
    }

    #[test]
    fn test_total_dedup_misses_sums_correctly() {
        let mut log = GossipDedupMissLog::new();
        log.record(24000, 10, 100);
        log.record(25000, 20, 200);
        log.record(26000, 30, 300);
        assert_eq!(log.total_dedup_misses(), 60);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipDedupMissLog::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry_correct() {
        let mut log = GossipDedupMissLog::new();
        log.record(27000, 10, 100); // rate=10
        log.record(28000, 20, 100); // rate=20
        log.record(29000, 30, 100); // rate=30
        // mean = (10+20+30)/3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn test_default_zero_entries() {
        let log = GossipDedupMissLog::default();
        assert_eq!(log.entries.len(), 0);
    }
}