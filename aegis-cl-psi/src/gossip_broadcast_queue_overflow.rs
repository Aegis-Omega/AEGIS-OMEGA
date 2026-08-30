//! Gate 441 — Gossip Broadcast Queue Overflow Monitor (T2)
//! Tracks queue overflow rate per gossip broadcast epoch.
//! HIGH_OVERFLOW_THRESHOLD = 3: rate_pct > 3 → high_overflow

use sha2::{Sha256, Digest};

pub const QUEUE_OVERFLOW_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_OVERFLOW_THRESHOLD: u32 = 3;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipQueueOverflowEntry {
    pub epoch_end:               u64,
    pub overflow_events:         u32,
    pub total_enqueued:          u32,
    pub overflow_events_rate_pct: u32,
    pub high_overflow:           bool,
    pub entry_hash:              [u8; 32],
    pub prev_hash:               [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    overflow_events: u32,
    total_enqueued: u32,
    rate_pct: u32,
    high_overflow: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(overflow_events.to_be_bytes());
    h.update(total_enqueued.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_overflow as u8]);
    h.finalize().into()
}

pub struct GossipQueueOverflowLog {
    pub entries: Vec<GossipQueueOverflowEntry>,
}

impl GossipQueueOverflowLog {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        overflow_events: u32,
        total_enqueued: u32,
    ) -> &GossipQueueOverflowEntry {
        let denom = total_enqueued.max(1) as u64;
        let overflow_events_rate_pct =
            ((overflow_events as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_overflow = overflow_events_rate_pct > HIGH_OVERFLOW_THRESHOLD;
        let prev = self
            .entries
            .last()
            .map(|e| e.entry_hash)
            .unwrap_or(QUEUE_OVERFLOW_GENESIS_HASH);
        let entry_hash = compute_hash(
            &prev,
            epoch_end,
            overflow_events,
            total_enqueued,
            overflow_events_rate_pct,
            high_overflow,
        );
        self.entries.push(GossipQueueOverflowEntry {
            epoch_end,
            overflow_events,
            total_enqueued,
            overflow_events_rate_pct,
            high_overflow,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_overflow_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_overflow).count()
    }

    pub fn total_overflow_events(&self) -> u64 {
        self.entries.iter().map(|e| e.overflow_events as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.overflow_events_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = QUEUE_OVERFLOW_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.overflow_events,
                e.total_enqueued,
                e.overflow_events_rate_pct,
                e.high_overflow,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipQueueOverflowLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_high_overflow_true() {
        let mut log = GossipQueueOverflowLog::new();
        let entry = log.record(1000, 10, 100);
        assert_eq!(entry.epoch_end, 1000);
        assert_eq!(entry.overflow_events, 10);
        assert_eq!(entry.total_enqueued, 100);
        assert_eq!(entry.overflow_events_rate_pct, 10);
        assert!(entry.high_overflow);
    }

    #[test]
    fn test_flag_false_when_exactly_at_threshold() {
        let mut log = GossipQueueOverflowLog::new();
        // rate_pct == 3 exactly: 3 * 100 / 100 = 3, not > 3
        let entry = log.record(2000, 3, 100);
        assert_eq!(entry.overflow_events_rate_pct, 3);
        assert!(!entry.high_overflow);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipQueueOverflowLog::new();
        // overflow_events > total_enqueued
        let entry = log.record(3000, 200, 100);
        assert_eq!(entry.overflow_events_rate_pct, 100);
    }

    #[test]
    fn test_total_enqueued_zero_no_div_by_zero() {
        let mut log = GossipQueueOverflowLog::new();
        let entry = log.record(4000, 0, 0);
        assert_eq!(entry.overflow_events_rate_pct, 0);
        assert!(!entry.high_overflow);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(HIGH_OVERFLOW_THRESHOLD, 3);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipQueueOverflowLog::new();
        let entry = log.record(5000, 5, 50);
        assert_ne!(entry.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipQueueOverflowLog::new();
        let entry = log.record(6000, 1, 50);
        assert_eq!(entry.prev_hash, QUEUE_OVERFLOW_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipQueueOverflowLog::new();
        log.record(7000, 1, 50);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 2, 50);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipQueueOverflowLog::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_one_entry() {
        let mut log = GossipQueueOverflowLog::new();
        log.record(9000, 1, 20);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipQueueOverflowLog::new();
        log.record(10000, 1, 20);
        log.record(11000, 2, 40);
        log.record(12000, 3, 60);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipQueueOverflowLog::new();
        log.record(13000, 1, 20);
        log.record(14000, 2, 40);
        log.entries[0].overflow_events = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipQueueOverflowLog::new();
        log.record(15000, 1, 20);
        log.record(16000, 2, 40);
        log.record(17000, 3, 60);
        log.entries[1].total_enqueued = 999;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipQueueOverflowLog::new();
        log1.record(18000, 5, 50);
        let mut log2 = GossipQueueOverflowLog::new();
        log2.record(18000, 5, 50);
        let mut log3 = GossipQueueOverflowLog::new();
        log3.record(18000, 5, 50);
        assert_eq!(log1.entries[0].entry_hash, log2.entries[0].entry_hash);
        assert_eq!(log2.entries[0].entry_hash, log3.entries[0].entry_hash);
    }

    #[test]
    fn test_high_overflow_count_mixed_log() {
        let mut log = GossipQueueOverflowLog::new();
        // rate = 0/100 = 0, not high
        log.record(19000, 0, 100);
        // rate = 3/100 = 3, not high
        log.record(20000, 3, 100);
        // rate = 4/100 = 4, high
        log.record(21000, 4, 100);
        // rate = 50/100 = 50, high
        log.record(22000, 50, 100);
        assert_eq!(log.high_overflow_count(), 2);
    }

    #[test]
    fn test_total_overflow_events_sums_correctly() {
        let mut log = GossipQueueOverflowLog::new();
        log.record(23000, 10, 100);
        log.record(24000, 20, 100);
        log.record(25000, 30, 100);
        assert_eq!(log.total_overflow_events(), 60);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipQueueOverflowLog::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry_correct() {
        let mut log = GossipQueueOverflowLog::new();
        // rate = 10
        log.record(26000, 10, 100);
        // rate = 20
        log.record(27000, 20, 100);
        // rate = 30
        log.record(28000, 30, 100);
        // mean = (10 + 20 + 30) / 3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn test_default_zero_entries() {
        let log = GossipQueueOverflowLog::default();
        assert_eq!(log.entries.len(), 0);
    }
}