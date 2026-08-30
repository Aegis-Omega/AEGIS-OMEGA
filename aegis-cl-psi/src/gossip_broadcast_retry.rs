//! Gate 432 — Gossip Broadcast Retry Monitor (T2)
//! Tracks retry rate per gossip broadcast epoch.
//! HIGH_RETRY_RATE_THRESHOLD = 8: rate_pct > 8 → high_retry_rate

use sha2::{Sha256, Digest};

pub const RETRY_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_RETRY_RATE_THRESHOLD: u32 = 8;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipRetryEntry {
    pub epoch_end:        u64,
    pub retry_count:      u32,
    pub total_sent:       u32,
    pub retry_rate_pct:   u32,
    pub high_retry_rate:  bool,
    pub entry_hash:       [u8; 32],
    pub prev_hash:        [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    retry_count: u32,
    total_sent: u32,
    rate_pct: u32,
    high_retry_rate: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(retry_count.to_be_bytes());
    h.update(total_sent.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_retry_rate as u8]);
    h.finalize().into()
}

pub struct GossipRetryLog {
    pub entries: Vec<GossipRetryEntry>,
}

impl GossipRetryLog {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(&mut self, epoch_end: u64, retry_count: u32, total_sent: u32) -> &GossipRetryEntry {
        let denom = total_sent.max(1) as u64;
        let retry_rate_pct = ((retry_count as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_retry_rate = retry_rate_pct > HIGH_RETRY_RATE_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(RETRY_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, retry_count, total_sent, retry_rate_pct, high_retry_rate);
        self.entries.push(GossipRetryEntry {
            epoch_end,
            retry_count,
            total_sent,
            retry_rate_pct,
            high_retry_rate,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_retry_rate_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_retry_rate).count()
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
        let mut prev = RETRY_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(&prev, e.epoch_end, e.retry_count, e.total_sent, e.retry_rate_pct, e.high_retry_rate);
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipRetryLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_high_flag_true() {
        let mut log = GossipRetryLog::new();
        let e = log.record(1000, 50, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.retry_count, 50);
        assert_eq!(e.total_sent, 100);
        assert_eq!(e.retry_rate_pct, 50);
        assert!(e.high_retry_rate);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipRetryLog::new();
        // rate_pct == 8 exactly: 8 * 100 / 100 = 8, not > 8 so false
        let e = log.record(2000, 8, 100);
        assert_eq!(e.retry_rate_pct, 8);
        assert!(!e.high_retry_rate);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipRetryLog::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.retry_rate_pct, 100);
        assert!(e.high_retry_rate);
    }

    #[test]
    fn total_sent_zero_no_div_by_zero() {
        let mut log = GossipRetryLog::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.retry_rate_pct, 0);
        assert!(!e.high_retry_rate);
    }

    #[test]
    fn threshold_constant_value_is_8() {
        assert_eq!(HIGH_RETRY_RATE_THRESHOLD, 8);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipRetryLog::new();
        let e = log.record(5000, 10, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipRetryLog::new();
        let e = log.record(6000, 10, 100);
        assert_eq!(e.prev_hash, RETRY_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipRetryLog::new();
        log.record(7000, 10, 100);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 20, 200);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipRetryLog::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipRetryLog::new();
        log.record(9000, 5, 50);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipRetryLog::new();
        log.record(10000, 5, 50);
        log.record(11000, 10, 100);
        log.record(12000, 15, 150);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipRetryLog::new();
        log.record(13000, 5, 50);
        log.record(14000, 10, 100);
        log.entries[0].retry_count = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipRetryLog::new();
        log.record(15000, 5, 50);
        log.record(16000, 10, 100);
        log.entries[1].retry_count = 77;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut log1 = GossipRetryLog::new();
        log1.record(17000, 9, 90);
        let mut log2 = GossipRetryLog::new();
        log2.record(17000, 9, 90);
        let mut log3 = GossipRetryLog::new();
        log3.record(17000, 9, 90);
        assert_eq!(log1.entries[0].entry_hash, log2.entries[0].entry_hash);
        assert_eq!(log2.entries[0].entry_hash, log3.entries[0].entry_hash);
    }

    #[test]
    fn high_retry_rate_count_mixed_log() {
        let mut log = GossipRetryLog::new();
        log.record(18000, 1, 100);  // rate=1, not high
        log.record(19000, 50, 100); // rate=50, high
        log.record(20000, 8, 100);  // rate=8, not high (boundary)
        log.record(21000, 9, 100);  // rate=9, high
        assert_eq!(log.high_retry_rate_count(), 2);
    }

    #[test]
    fn total_retry_count_sums_correctly() {
        let mut log = GossipRetryLog::new();
        log.record(22000, 10, 100);
        log.record(23000, 20, 200);
        log.record(24000, 30, 300);
        assert_eq!(log.total_retry_count(), 60);
    }

    #[test]
    fn mean_rate_pct_empty_returns_zero() {
        let log = GossipRetryLog::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn mean_rate_pct_multi_entry_correct() {
        let mut log = GossipRetryLog::new();
        log.record(25000, 10, 100); // rate=10
        log.record(26000, 20, 100); // rate=20
        log.record(27000, 30, 100); // rate=30
        // mean = (10 + 20 + 30) / 3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn default_produces_zero_entries() {
        let log = GossipRetryLog::default();
        assert_eq!(log.entries.len(), 0);
    }
}