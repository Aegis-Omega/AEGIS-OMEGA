//! Gate 500 — Gossip Broadcast Fanout E4 Monitor (T2)
//! Tracks fanout e4 rate per gossip broadcast epoch.
//! LOW_FANOUT_E4_THRESHOLD = 40: rate_pct < 40 → low_fanout_e4

use sha2::{Sha256, Digest};

pub const FANOUT_E4_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const LOW_FANOUT_E4_THRESHOLD: u32 = 40;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipFanoutE4Entry {
    pub epoch_end:         u64,
    pub low_fanout_msgs:   u32,
    pub total_msgs:        u32,
    pub low_fanout_rate_pct: u32,
    pub low_fanout_e4:     bool,
    pub entry_hash:        [u8; 32],
    pub prev_hash:         [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    low_fanout_msgs: u32,
    total_msgs: u32,
    rate_pct: u32,
    low_fanout_e4: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(low_fanout_msgs.to_be_bytes());
    h.update(total_msgs.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([low_fanout_e4 as u8]);
    h.finalize().into()
}

pub struct GossipFanoutE4Log {
    pub entries: Vec<GossipFanoutE4Entry>,
}

impl GossipFanoutE4Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(&mut self, epoch_end: u64, low_fanout_msgs: u32, total_msgs: u32) -> &GossipFanoutE4Entry {
        let denom = total_msgs.max(1) as u64;
        let rate_pct = ((low_fanout_msgs as u64).saturating_mul(100) / denom).min(100) as u32;
        let low_fanout_e4 = rate_pct < LOW_FANOUT_E4_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(FANOUT_E4_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, low_fanout_msgs, total_msgs, rate_pct, low_fanout_e4);
        self.entries.push(GossipFanoutE4Entry {
            epoch_end,
            low_fanout_msgs,
            total_msgs,
            low_fanout_rate_pct: rate_pct,
            low_fanout_e4,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn low_fanout_e4_count(&self) -> usize {
        self.entries.iter().filter(|e| e.low_fanout_e4).count()
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
        let mut prev = FANOUT_E4_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(&prev, e.epoch_end, e.low_fanout_msgs, e.total_msgs, e.low_fanout_rate_pct, e.low_fanout_e4);
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipFanoutE4Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true_when_below_threshold() {
        let mut log = GossipFanoutE4Log::new();
        let e = log.record(1000, 30, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.low_fanout_msgs, 30);
        assert_eq!(e.total_msgs, 100);
        assert_eq!(e.low_fanout_rate_pct, 30);
        assert_eq!(e.low_fanout_e4, true);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipFanoutE4Log::new();
        // rate_pct = (40 * 100) / 100 = 40; 40 < 40 is false
        let e = log.record(2000, 40, 100);
        assert_eq!(e.low_fanout_rate_pct, 40);
        assert_eq!(e.low_fanout_e4, false);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipFanoutE4Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.low_fanout_rate_pct, 100);
    }

    #[test]
    fn total_msgs_zero_no_div_by_zero() {
        let mut log = GossipFanoutE4Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.low_fanout_rate_pct, 0);
        assert_eq!(e.low_fanout_e4, true);
    }

    #[test]
    fn threshold_constant_value_is_40() {
        assert_eq!(LOW_FANOUT_E4_THRESHOLD, 40u32);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipFanoutE4Log::new();
        let e = log.record(5000, 10, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipFanoutE4Log::new();
        let e = log.record(6000, 10, 100);
        assert_eq!(e.prev_hash, FANOUT_E4_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipFanoutE4Log::new();
        log.record(7000, 10, 100);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 20, 100);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipFanoutE4Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipFanoutE4Log::new();
        log.record(9000, 10, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipFanoutE4Log::new();
        log.record(10000, 10, 100);
        log.record(11000, 20, 100);
        log.record(12000, 30, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipFanoutE4Log::new();
        log.record(13000, 10, 100);
        log.record(14000, 20, 100);
        log.entries[0].low_fanout_msgs = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipFanoutE4Log::new();
        log.record(15000, 10, 100);
        log.record(16000, 20, 100);
        log.entries[1].total_msgs = 999;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut log1 = GossipFanoutE4Log::new();
        let h1 = log1.record(17000, 15, 100).entry_hash;
        let mut log2 = GossipFanoutE4Log::new();
        let h2 = log2.record(17000, 15, 100).entry_hash;
        let mut log3 = GossipFanoutE4Log::new();
        let h3 = log3.record(17000, 15, 100).entry_hash;
        assert_eq!(h1, h2);
        assert_eq!(h2, h3);
    }

    #[test]
    fn low_fanout_e4_count_mixed_log() {
        let mut log = GossipFanoutE4Log::new();
        // rate=10 < 40 → true
        log.record(18000, 10, 100);
        // rate=40 < 40 → false
        log.record(19000, 40, 100);
        // rate=50 < 40 → false
        log.record(20000, 50, 100);
        // rate=0 < 40 → true
        log.record(21000, 0, 100);
        assert_eq!(log.low_fanout_e4_count(), 2);
    }

    #[test]
    fn total_low_fanout_msgs_sums_correctly() {
        let mut log = GossipFanoutE4Log::new();
        log.record(22000, 10, 100);
        log.record(23000, 20, 100);
        log.record(24000, 30, 100);
        assert_eq!(log.total_low_fanout_msgs(), 60u64);
    }

    #[test]
    fn mean_rate_pct_empty_returns_zero() {
        let log = GossipFanoutE4Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn mean_rate_pct_multi_entry_correct() {
        let mut log = GossipFanoutE4Log::new();
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
    fn default_produces_zero_entries() {
        let log = GossipFanoutE4Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}