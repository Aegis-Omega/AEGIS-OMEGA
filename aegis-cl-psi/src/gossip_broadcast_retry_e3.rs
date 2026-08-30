//! Gate 461 — Gossip Broadcast Retry E3 Monitor (T2)
//! Tracks retry e3 rate per gossip broadcast epoch.
//! HIGH_RETRY_RATE_E3_THRESHOLD = 8: rate_pct > 8 → high_retry_rate_e3

use sha2::{Sha256, Digest};

pub const RETRY_E3_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_RETRY_RATE_E3_THRESHOLD: u32 = 8;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipRetryE3Entry {
    pub epoch_end:         u64,
    pub retry_count:       u32,
    pub total_sent:        u32,
    pub retry_rate_pct:    u32,
    pub high_retry_rate_e3: bool,
    pub entry_hash:        [u8; 32],
    pub prev_hash:         [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    retry_count: u32,
    total_sent: u32,
    rate_pct: u32,
    high_retry_rate_e3: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(retry_count.to_be_bytes());
    h.update(total_sent.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_retry_rate_e3 as u8]);
    h.finalize().into()
}

pub struct GossipRetryE3Log {
    pub entries: Vec<GossipRetryE3Entry>,
}

impl GossipRetryE3Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(&mut self, epoch_end: u64, retry_count: u32, total_sent: u32) -> &GossipRetryE3Entry {
        let denom = total_sent.max(1) as u64;
        let retry_rate_pct = ((retry_count as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_retry_rate_e3 = retry_rate_pct > HIGH_RETRY_RATE_E3_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(RETRY_E3_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, retry_count, total_sent, retry_rate_pct, high_retry_rate_e3);
        self.entries.push(GossipRetryE3Entry {
            epoch_end,
            retry_count,
            total_sent,
            retry_rate_pct,
            high_retry_rate_e3,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_retry_rate_e3_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_retry_rate_e3).count()
    }

    pub fn total_retry_count(&self) -> u64 {
        self.entries.iter().map(|e| e.retry_count as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.retry_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = RETRY_E3_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(&prev, e.epoch_end, e.retry_count, e.total_sent, e.retry_rate_pct, e.high_retry_rate_e3);
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipRetryE3Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipRetryE3Log::new();
        let e = log.record(1000, 10, 50);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.retry_count, 10);
        assert_eq!(e.total_sent, 50);
        // rate = (10 * 100) / 50 = 20
        assert_eq!(e.retry_rate_pct, 20);
        assert!(e.high_retry_rate_e3);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipRetryE3Log::new();
        // rate_pct = (8 * 100) / 100 = 8, not > 8, so flag = false
        let e = log.record(2000, 8, 100);
        assert_eq!(e.retry_rate_pct, 8);
        assert!(!e.high_retry_rate_e3);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipRetryE3Log::new();
        // retry_count > total_sent → rate > 100 before cap
        let e = log.record(3000, 200, 50);
        assert_eq!(e.retry_rate_pct, 100);
        assert!(e.high_retry_rate_e3);
    }

    #[test]
    fn total_sent_zero_no_div_by_zero() {
        let mut log = GossipRetryE3Log::new();
        let e = log.record(4000, 5, 0);
        // denom = max(0, 1) = 1, rate = (5 * 100) / 1 = 500, capped at 100
        assert_eq!(e.retry_rate_pct, 100);
        assert!(e.high_retry_rate_e3);
    }

    #[test]
    fn threshold_constant_value_is_8() {
        assert_eq!(HIGH_RETRY_RATE_E3_THRESHOLD, 8);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipRetryE3Log::new();
        let e = log.record(5000, 1, 10);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipRetryE3Log::new();
        let e = log.record(6000, 1, 10);
        assert_eq!(e.prev_hash, RETRY_E3_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipRetryE3Log::new();
        log.record(7000, 1, 10);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 2, 20);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipRetryE3Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipRetryE3Log::new();
        log.record(9000, 1, 10);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipRetryE3Log::new();
        log.record(10000, 1, 10);
        log.record(11000, 2, 20);
        log.record(12000, 3, 30);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipRetryE3Log::new();
        log.record(13000, 1, 10);
        log.record(14000, 2, 20);
        // Tamper entry 0 entry_hash
        log.entries[0].entry_hash = [0xFFu8; 32];
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipRetryE3Log::new();
        log.record(15000, 1, 10);
        log.record(16000, 2, 20);
        log.record(17000, 3, 30);
        // Tamper entry 1 retry_count (content mismatch)
        log.entries[1].retry_count = 99;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut log1 = GossipRetryE3Log::new();
        let e1 = log1.record(18000, 5, 50).entry_hash;

        let mut log2 = GossipRetryE3Log::new();
        let e2 = log2.record(18000, 5, 50).entry_hash;

        let mut log3 = GossipRetryE3Log::new();
        let e3 = log3.record(18000, 5, 50).entry_hash;

        assert_eq!(e1, e2);
        assert_eq!(e2, e3);
    }

    #[test]
    fn high_retry_rate_e3_count_mixed_log() {
        let mut log = GossipRetryE3Log::new();
        // rate = (8*100)/100 = 8, not > 8 → false
        log.record(19000, 8, 100);
        // rate = (9*100)/100 = 9, > 8 → true
        log.record(20000, 9, 100);
        // rate = (1*100)/100 = 1, not > 8 → false
        log.record(21000, 1, 100);
        // rate = (50*100)/100 = 50, > 8 → true
        log.record(22000, 50, 100);
        assert_eq!(log.high_retry_rate_e3_count(), 2);
    }

    #[test]
    fn total_retry_count_sums_correctly() {
        let mut log = GossipRetryE3Log::new();
        log.record(23000, 10, 100);
        log.record(24000, 20, 100);
        log.record(25000, 30, 100);
        assert_eq!(log.total_retry_count(), 60);
    }

    #[test]
    fn mean_rate_pct_empty_returns_0() {
        let log = GossipRetryE3Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn mean_rate_pct_multi_entry_correct() {
        let mut log = GossipRetryE3Log::new();
        // rate = (10*100)/100 = 10
        log.record(26000, 10, 100);
        // rate = (20*100)/100 = 20
        log.record(27000, 20, 100);
        // rate = (30*100)/100 = 30
        log.record(28000, 30, 100);
        // mean = (10 + 20 + 30) / 3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn default_produces_zero_entries() {
        let log = GossipRetryE3Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}