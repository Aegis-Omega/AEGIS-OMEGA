//! Gate 436 — Gossip Broadcast Fanout Monitor (T2)
//! Tracks fanout rate per gossip broadcast epoch.
//! LOW_FANOUT_THRESHOLD = 40: rate_pct < 40 → low_fanout

use sha2::{Sha256, Digest};

pub const FANOUT_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const LOW_FANOUT_THRESHOLD: u32 = 40;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipFanoutEntry {
    pub epoch_end:          u64,
    pub low_fanout_msgs:    u32,
    pub total_msgs:         u32,
    pub low_fanout_rate_pct: u32,
    pub low_fanout:         bool,
    pub entry_hash:         [u8; 32],
    pub prev_hash:          [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    low_fanout_msgs: u32,
    total_msgs: u32,
    rate_pct: u32,
    low_fanout: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(low_fanout_msgs.to_be_bytes());
    h.update(total_msgs.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([low_fanout as u8]);
    h.finalize().into()
}

pub struct GossipFanoutLog {
    pub entries: Vec<GossipFanoutEntry>,
}

impl GossipFanoutLog {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(&mut self, epoch_end: u64, low_fanout_msgs: u32, total_msgs: u32) -> &GossipFanoutEntry {
        let denom = total_msgs.max(1) as u64;
        let rate_pct = ((low_fanout_msgs as u64).saturating_mul(100) / denom).min(100) as u32;
        let low_fanout = rate_pct < LOW_FANOUT_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(FANOUT_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, low_fanout_msgs, total_msgs, rate_pct, low_fanout);
        self.entries.push(GossipFanoutEntry {
            epoch_end,
            low_fanout_msgs,
            total_msgs,
            low_fanout_rate_pct: rate_pct,
            low_fanout,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn low_fanout_count(&self) -> usize {
        self.entries.iter().filter(|e| e.low_fanout).count()
    }

    pub fn total_low_fanout_msgs(&self) -> u64 {
        self.entries.iter().map(|e| e.low_fanout_msgs as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.low_fanout_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = FANOUT_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(&prev, e.epoch_end, e.low_fanout_msgs, e.total_msgs, e.low_fanout_rate_pct, e.low_fanout);
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipFanoutLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_flag_true() {
        let mut log = GossipFanoutLog::new();
        let e = log.record(1000, 10, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.low_fanout_msgs, 10);
        assert_eq!(e.total_msgs, 100);
        assert_eq!(e.low_fanout_rate_pct, 10);
        assert!(e.low_fanout);
    }

    #[test]
    fn test_flag_false_when_at_threshold() {
        let mut log = GossipFanoutLog::new();
        // rate_pct = (40 * 100) / 100 = 40, low_fanout = 40 < 40 = false
        let e = log.record(2000, 40, 100);
        assert_eq!(e.low_fanout_rate_pct, 40);
        assert!(!e.low_fanout);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipFanoutLog::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.low_fanout_rate_pct, 100);
        assert!(!e.low_fanout);
    }

    #[test]
    fn test_total_msgs_zero_no_div_by_zero() {
        let mut log = GossipFanoutLog::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.low_fanout_rate_pct, 0);
        assert!(e.low_fanout);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(LOW_FANOUT_THRESHOLD, 40);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipFanoutLog::new();
        let e = log.record(5000, 10, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipFanoutLog::new();
        let e = log.record(6000, 10, 100);
        assert_eq!(e.prev_hash, FANOUT_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipFanoutLog::new();
        log.record(7000, 10, 100);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 20, 100);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipFanoutLog::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_one_entry() {
        let mut log = GossipFanoutLog::new();
        log.record(9000, 5, 50);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipFanoutLog::new();
        log.record(10000, 5, 50);
        log.record(11000, 15, 100);
        log.record(12000, 30, 200);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipFanoutLog::new();
        log.record(13000, 5, 50);
        log.record(14000, 10, 100);
        log.entries[0].low_fanout_msgs = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipFanoutLog::new();
        log.record(15000, 5, 50);
        log.record(16000, 10, 100);
        log.entries[1].total_msgs = 999;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipFanoutLog::new();
        let h1 = log1.record(17000, 20, 80).entry_hash;

        let mut log2 = GossipFanoutLog::new();
        let h2 = log2.record(17000, 20, 80).entry_hash;

        let mut log3 = GossipFanoutLog::new();
        let h3 = log3.record(17000, 20, 80).entry_hash;

        assert_eq!(h1, h2);
        assert_eq!(h2, h3);
    }

    #[test]
    fn test_low_fanout_count_mixed() {
        let mut log = GossipFanoutLog::new();
        // rate = 10 < 40 → low_fanout = true
        log.record(18000, 10, 100);
        // rate = 50 >= 40 → low_fanout = false
        log.record(19000, 50, 100);
        // rate = 20 < 40 → low_fanout = true
        log.record(20000, 20, 100);
        assert_eq!(log.low_fanout_count(), 2);
    }

    #[test]
    fn test_total_low_fanout_msgs_sums_correctly() {
        let mut log = GossipFanoutLog::new();
        log.record(21000, 7, 100);
        log.record(22000, 13, 100);
        log.record(23000, 50, 100);
        assert_eq!(log.total_low_fanout_msgs(), 70);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipFanoutLog::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry() {
        let mut log = GossipFanoutLog::new();
        // rate = 20
        log.record(24000, 20, 100);
        // rate = 60
        log.record(25000, 60, 100);
        // rate = 40
        log.record(26000, 40, 100);
        // mean = (20 + 60 + 40) / 3 = 40
        assert_eq!(log.mean_rate_pct(), 40);
    }

    #[test]
    fn test_default_has_zero_entries() {
        let log = GossipFanoutLog::default();
        assert_eq!(log.entries.len(), 0);
    }
}