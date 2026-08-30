//! Gate 458 — Gossip Broadcast Batch E3 Monitor (T2)
//! Tracks batch e3 rate per gossip broadcast epoch.
//! UNDER_FILLED_E3_THRESHOLD = 50: rate_pct < 50 → under_filled_e3

use sha2::{Sha256, Digest};

pub const BATCH_E3_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const UNDER_FILLED_E3_THRESHOLD: u32 = 50;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipBatchE3Entry {
    pub epoch_end:                    u64,
    pub under_filled_batches:         u32,
    pub total_batches:                u32,
    pub under_filled_batches_rate_pct: u32,
    pub under_filled_e3:              bool,
    pub entry_hash:                   [u8; 32],
    pub prev_hash:                    [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    under_filled_batches: u32,
    total_batches: u32,
    rate_pct: u32,
    under_filled_e3: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(under_filled_batches.to_be_bytes());
    h.update(total_batches.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([under_filled_e3 as u8]);
    h.finalize().into()
}

pub struct GossipBatchE3Log {
    pub entries: Vec<GossipBatchE3Entry>,
}

impl GossipBatchE3Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        under_filled_batches: u32,
        total_batches: u32,
    ) -> &GossipBatchE3Entry {
        let denom = total_batches.max(1) as u64;
        let rate_pct = ((under_filled_batches as u64).saturating_mul(100) / denom)
            .min(100) as u32;
        let under_filled_e3 = rate_pct < UNDER_FILLED_E3_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(BATCH_E3_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, under_filled_batches, total_batches, rate_pct, under_filled_e3);
        self.entries.push(GossipBatchE3Entry {
            epoch_end,
            under_filled_batches,
            total_batches,
            under_filled_batches_rate_pct: rate_pct,
            under_filled_e3,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn under_filled_e3_count(&self) -> usize {
        self.entries.iter().filter(|e| e.under_filled_e3).count()
    }

    pub fn total_under_filled_batches(&self) -> u64 {
        self.entries.iter().map(|e| e.under_filled_batches as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.under_filled_batches_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = BATCH_E3_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.under_filled_batches,
                e.total_batches,
                e.under_filled_batches_rate_pct,
                e.under_filled_e3,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipBatchE3Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_rate_and_flag_true() {
        let mut log = GossipBatchE3Log::new();
        let e = log.record(1000, 10, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.under_filled_batches, 10);
        assert_eq!(e.total_batches, 100);
        assert_eq!(e.under_filled_batches_rate_pct, 10);
        assert!(e.under_filled_e3); // 10 < 50
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipBatchE3Log::new();
        // rate_pct = 50, flag = rate_pct < 50 = false
        let e = log.record(2000, 50, 100);
        assert_eq!(e.under_filled_batches_rate_pct, 50);
        assert!(!e.under_filled_e3);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipBatchE3Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.under_filled_batches_rate_pct, 100);
        assert!(!e.under_filled_e3); // 100 < 50 is false
    }

    #[test]
    fn total_batches_zero_no_div_by_zero() {
        let mut log = GossipBatchE3Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.under_filled_batches_rate_pct, 0);
        assert!(e.under_filled_e3); // 0 < 50
    }

    #[test]
    fn threshold_constant_value_is_50() {
        assert_eq!(UNDER_FILLED_E3_THRESHOLD, 50);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipBatchE3Log::new();
        let e = log.record(5000, 25, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipBatchE3Log::new();
        let e = log.record(6000, 10, 100);
        assert_eq!(e.prev_hash, BATCH_E3_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipBatchE3Log::new();
        log.record(7000, 10, 100);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 20, 100);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipBatchE3Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipBatchE3Log::new();
        log.record(9000, 10, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipBatchE3Log::new();
        log.record(10000, 10, 100);
        log.record(11000, 20, 100);
        log.record(12000, 30, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipBatchE3Log::new();
        log.record(13000, 10, 100);
        log.record(14000, 20, 100);
        log.entries[0].under_filled_batches = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipBatchE3Log::new();
        log.record(15000, 10, 100);
        log.record(16000, 20, 100);
        log.record(17000, 30, 100);
        log.entries[1].under_filled_batches = 99;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut log1 = GossipBatchE3Log::new();
        let e1 = log1.record(18000, 15, 100).entry_hash;

        let mut log2 = GossipBatchE3Log::new();
        let e2 = log2.record(18000, 15, 100).entry_hash;

        let mut log3 = GossipBatchE3Log::new();
        let e3 = log3.record(18000, 15, 100).entry_hash;

        assert_eq!(e1, e2);
        assert_eq!(e2, e3);
    }

    #[test]
    fn under_filled_e3_count_mixed_log() {
        let mut log = GossipBatchE3Log::new();
        // rate=10 < 50 → true
        log.record(19000, 10, 100);
        // rate=50 not < 50 → false
        log.record(20000, 50, 100);
        // rate=20 < 50 → true
        log.record(21000, 20, 100);
        // rate=75 not < 50 → false
        log.record(22000, 75, 100);
        assert_eq!(log.under_filled_e3_count(), 2);
    }

    #[test]
    fn total_under_filled_batches_sums_correctly() {
        let mut log = GossipBatchE3Log::new();
        log.record(23000, 10, 100);
        log.record(24000, 20, 100);
        log.record(25000, 30, 100);
        assert_eq!(log.total_under_filled_batches(), 60u64);
    }

    #[test]
    fn mean_rate_pct_empty_returns_zero() {
        let log = GossipBatchE3Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn mean_rate_pct_multi_entry_correct() {
        let mut log = GossipBatchE3Log::new();
        // rate = 10
        log.record(26000, 10, 100);
        // rate = 20
        log.record(27000, 20, 100);
        // rate = 30
        log.record(28000, 30, 100);
        // mean = (10+20+30)/3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn default_gives_zero_entries() {
        let log = GossipBatchE3Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}