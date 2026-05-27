//! Gate 438 — Gossip Broadcast Ack Timeout Monitor (T2)
//! Tracks ack timeout rate per gossip broadcast epoch.
//! HIGH_ACK_TIMEOUT_THRESHOLD = 8: rate_pct > 8 → high_ack_timeout

use sha2::{Sha256, Digest};

pub const ACK_TIMEOUT_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_ACK_TIMEOUT_THRESHOLD: u32 = 8;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipAckTimeoutEntry {
    pub epoch_end:             u64,
    pub unacknowledged_msgs:   u32,
    pub total_sent:            u32,
    pub unacknowledged_rate_pct: u32,
    pub high_ack_timeout:      bool,
    pub entry_hash:            [u8; 32],
    pub prev_hash:             [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    unacknowledged_msgs: u32,
    total_sent: u32,
    rate_pct: u32,
    high_ack_timeout: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(unacknowledged_msgs.to_be_bytes());
    h.update(total_sent.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_ack_timeout as u8]);
    h.finalize().into()
}

pub struct GossipAckTimeoutLog {
    pub entries: Vec<GossipAckTimeoutEntry>,
}

impl GossipAckTimeoutLog {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        unacknowledged_msgs: u32,
        total_sent: u32,
    ) -> &GossipAckTimeoutEntry {
        let denom = total_sent.max(1) as u64;
        let rate_pct = ((unacknowledged_msgs as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_ack_timeout = rate_pct > HIGH_ACK_TIMEOUT_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(ACK_TIMEOUT_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, unacknowledged_msgs, total_sent, rate_pct, high_ack_timeout);
        self.entries.push(GossipAckTimeoutEntry {
            epoch_end,
            unacknowledged_msgs,
            total_sent,
            unacknowledged_rate_pct: rate_pct,
            high_ack_timeout,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_ack_timeout_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_ack_timeout).count()
    }

    pub fn total_unacknowledged_msgs(&self) -> u64 {
        self.entries.iter().map(|e| e.unacknowledged_msgs as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.unacknowledged_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = ACK_TIMEOUT_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.unacknowledged_msgs,
                e.total_sent,
                e.unacknowledged_rate_pct,
                e.high_ack_timeout,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipAckTimeoutLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_flag_true() {
        let mut log = GossipAckTimeoutLog::new();
        let e = log.record(1000, 50, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.unacknowledged_msgs, 50);
        assert_eq!(e.total_sent, 100);
        assert_eq!(e.unacknowledged_rate_pct, 50);
        assert!(e.high_ack_timeout);
    }

    #[test]
    fn test_flag_false_when_exactly_at_threshold() {
        let mut log = GossipAckTimeoutLog::new();
        // rate_pct = (8 * 100) / 100 = 8, which is NOT > 8
        let e = log.record(2000, 8, 100);
        assert_eq!(e.unacknowledged_rate_pct, 8);
        assert!(!e.high_ack_timeout);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipAckTimeoutLog::new();
        // unacknowledged_msgs > total_sent
        let e = log.record(3000, 200, 100);
        assert_eq!(e.unacknowledged_rate_pct, 100);
        assert!(e.high_ack_timeout);
    }

    #[test]
    fn test_total_sent_zero_no_div_by_zero() {
        let mut log = GossipAckTimeoutLog::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.unacknowledged_rate_pct, 0);
        assert!(!e.high_ack_timeout);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(HIGH_ACK_TIMEOUT_THRESHOLD, 8u32);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipAckTimeoutLog::new();
        let e = log.record(5000, 10, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipAckTimeoutLog::new();
        let e = log.record(6000, 5, 50);
        assert_eq!(e.prev_hash, ACK_TIMEOUT_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipAckTimeoutLog::new();
        log.record(7000, 5, 50);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 10, 100);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipAckTimeoutLog::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_one_entry() {
        let mut log = GossipAckTimeoutLog::new();
        log.record(9000, 3, 30);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipAckTimeoutLog::new();
        log.record(10000, 1, 10);
        log.record(11000, 2, 20);
        log.record(12000, 3, 30);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipAckTimeoutLog::new();
        log.record(13000, 5, 50);
        log.record(14000, 10, 100);
        // Tamper entry 0's unacknowledged_msgs
        log.entries[0].unacknowledged_msgs = 99;
        let (valid, idx) = log.verify_chain();
        assert!(!valid);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipAckTimeoutLog::new();
        log.record(15000, 5, 50);
        log.record(16000, 10, 100);
        log.record(17000, 15, 150);
        // Tamper entry 1's total_sent
        log.entries[1].total_sent = 999;
        let (valid, idx) = log.verify_chain();
        assert!(!valid);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipAckTimeoutLog::new();
        let h1 = log1.record(18000, 7, 70).entry_hash;

        let mut log2 = GossipAckTimeoutLog::new();
        let h2 = log2.record(18000, 7, 70).entry_hash;

        let mut log3 = GossipAckTimeoutLog::new();
        let h3 = log3.record(18000, 7, 70).entry_hash;

        assert_eq!(h1, h2);
        assert_eq!(h2, h3);
    }

    #[test]
    fn test_high_ack_timeout_count_mixed_log() {
        let mut log = GossipAckTimeoutLog::new();
        log.record(19000, 1, 100);  // rate=1, not high
        log.record(20000, 9, 100);  // rate=9, high
        log.record(21000, 50, 100); // rate=50, high
        log.record(22000, 8, 100);  // rate=8, not high (boundary)
        assert_eq!(log.high_ack_timeout_count(), 2);
    }

    #[test]
    fn test_total_unacknowledged_msgs_sums_correctly() {
        let mut log = GossipAckTimeoutLog::new();
        log.record(23000, 10, 100);
        log.record(24000, 20, 200);
        log.record(25000, 30, 300);
        assert_eq!(log.total_unacknowledged_msgs(), 60u64);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipAckTimeoutLog::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry_correct() {
        let mut log = GossipAckTimeoutLog::new();
        log.record(26000, 10, 100); // rate=10
        log.record(27000, 20, 100); // rate=20
        log.record(28000, 30, 100); // rate=30
        // mean = (10 + 20 + 30) / 3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn test_default_zero_entries() {
        let log = GossipAckTimeoutLog::default();
        assert_eq!(log.entries.len(), 0);
    }
}