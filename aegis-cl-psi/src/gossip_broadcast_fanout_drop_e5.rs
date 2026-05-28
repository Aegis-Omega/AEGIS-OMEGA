//! Gate 555 — Gossip Broadcast Fanout Drop E5 Monitor (T2)
//! Tracks fanout drop rate per gossip broadcast epoch.
//! HIGH_FANOUT_DROP_E5_THRESHOLD = 13: drop_rate_pct > 13 → high_fanout_drop_e5

use sha2::{Sha256, Digest};

pub const FANOUT_DROP_E5_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_FANOUT_DROP_E5_THRESHOLD: u32 = 13;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipFanoutDropE5Entry {
    pub epoch_end:          u64,
    pub dropped_fanouts:    u32,
    pub total_fanouts:      u32,
    pub drop_rate_pct:      u32,
    pub high_fanout_drop_e5: bool,
    pub entry_hash:         [u8; 32],
    pub prev_hash:          [u8; 32],
}

fn compute_hash(prev: &[u8; 32], epoch_end: u64, dropped_fanouts: u32, total_fanouts: u32, rate_pct: u32, high_fanout_drop_e5: bool) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev); h.update(epoch_end.to_be_bytes());
    h.update(dropped_fanouts.to_be_bytes()); h.update(total_fanouts.to_be_bytes());
    h.update(rate_pct.to_be_bytes()); h.update([high_fanout_drop_e5 as u8]);
    h.finalize().into()
}

pub struct GossipFanoutDropE5Log { pub entries: Vec<GossipFanoutDropE5Entry> }

impl GossipFanoutDropE5Log {
    pub fn new() -> Self { Self { entries: Vec::new() } }
    pub fn record(&mut self, epoch_end: u64, dropped_fanouts: u32, total_fanouts: u32) -> &GossipFanoutDropE5Entry {
        let denom = total_fanouts.max(1) as u64;
        let drop_rate_pct = ((dropped_fanouts as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_fanout_drop_e5 = drop_rate_pct > HIGH_FANOUT_DROP_E5_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(FANOUT_DROP_E5_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, dropped_fanouts, total_fanouts, drop_rate_pct, high_fanout_drop_e5);
        self.entries.push(GossipFanoutDropE5Entry { epoch_end, dropped_fanouts, total_fanouts, drop_rate_pct, high_fanout_drop_e5, entry_hash, prev_hash: prev });
        self.entries.last().unwrap()
    }
    pub fn high_fanout_drop_e5_count(&self) -> usize { self.entries.iter().filter(|e| e.high_fanout_drop_e5).count() }
    pub fn total_dropped_fanouts(&self) -> u64 { self.entries.iter().map(|e| e.dropped_fanouts as u64).sum() }
    pub fn mean_drop_rate_pct(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        (self.entries.iter().map(|e| e.drop_rate_pct as u64).sum::<u64>() / self.entries.len() as u64) as u32
    }
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = FANOUT_DROP_E5_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev { return (false, Some(i)); }
            if e.entry_hash != compute_hash(&prev, e.epoch_end, e.dropped_fanouts, e.total_fanouts, e.drop_rate_pct, e.high_fanout_drop_e5) { return (false, Some(i)); }
            prev = e.entry_hash;
        }
        (true, None)
    }
}
impl Default for GossipFanoutDropE5Log { fn default() -> Self { Self::new() } }

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipFanoutDropE5Log::new();
        let e = log.record(1000, 18, 100);
        assert_eq!(e.epoch_end, 1000); assert_eq!(e.dropped_fanouts, 18);
        assert_eq!(e.total_fanouts, 100); assert_eq!(e.drop_rate_pct, 18);
        assert!(e.high_fanout_drop_e5);
    }
    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipFanoutDropE5Log::new();
        let e = log.record(2000, 13, 100);
        assert_eq!(e.drop_rate_pct, 13); assert!(!e.high_fanout_drop_e5);
    }
    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipFanoutDropE5Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.drop_rate_pct, 100); assert!(e.high_fanout_drop_e5);
    }
    #[test]
    fn total_fanouts_zero_no_div_by_zero() {
        let mut log = GossipFanoutDropE5Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.drop_rate_pct, 0); assert!(!e.high_fanout_drop_e5);
    }
    #[test]
    fn threshold_constant_value_is_13() { assert_eq!(HIGH_FANOUT_DROP_E5_THRESHOLD, 13); }
    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipFanoutDropE5Log::new();
        assert_ne!(log.record(5000, 15, 80).entry_hash, [0u8; 32]);
    }
    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipFanoutDropE5Log::new();
        assert_eq!(log.record(6000, 10, 80).prev_hash, FANOUT_DROP_E5_GENESIS_HASH);
    }
    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipFanoutDropE5Log::new();
        log.record(7000, 10, 80);
        let h = log.entries[0].entry_hash;
        log.record(8000, 18, 100);
        assert_eq!(log.entries[1].prev_hash, h);
    }
    #[test]
    fn verify_chain_empty_returns_true_none() { assert_eq!(GossipFanoutDropE5Log::new().verify_chain(), (true, None)); }
    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipFanoutDropE5Log::new();
        log.record(9000, 14, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }
    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipFanoutDropE5Log::new();
        log.record(10000, 7, 60); log.record(11000, 14, 80); log.record(12000, 20, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }
    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipFanoutDropE5Log::new();
        log.record(13000, 10, 80); log.record(14000, 18, 100);
        log.entries[0].dropped_fanouts = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }
    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipFanoutDropE5Log::new();
        log.record(15000, 10, 80); log.record(16000, 18, 100);
        log.entries[1].dropped_fanouts = 99;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }
    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut l1 = GossipFanoutDropE5Log::new(); let mut l2 = GossipFanoutDropE5Log::new(); let mut l3 = GossipFanoutDropE5Log::new();
        let e1 = l1.record(17000, 15, 90).entry_hash; let e2 = l2.record(17000, 15, 90).entry_hash; let e3 = l3.record(17000, 15, 90).entry_hash;
        assert_eq!(e1, e2); assert_eq!(e2, e3);
    }
    #[test]
    fn high_fanout_drop_e5_count_mixed_log() {
        let mut log = GossipFanoutDropE5Log::new();
        log.record(18000, 10, 100); log.record(19000, 18, 100); log.record(20000, 13, 100); log.record(21000, 14, 100);
        assert_eq!(log.high_fanout_drop_e5_count(), 2);
    }
    #[test]
    fn total_dropped_fanouts_sums_correctly() {
        let mut log = GossipFanoutDropE5Log::new();
        log.record(22000, 10, 100); log.record(23000, 25, 100); log.record(24000, 7, 100);
        assert_eq!(log.total_dropped_fanouts(), 42);
    }
    #[test]
    fn mean_drop_rate_pct_empty_returns_zero() { assert_eq!(GossipFanoutDropE5Log::new().mean_drop_rate_pct(), 0); }
    #[test]
    fn mean_drop_rate_pct_multi_entry_correct() {
        let mut log = GossipFanoutDropE5Log::new();
        log.record(25000, 10, 100); log.record(26000, 20, 100); log.record(27000, 30, 100);
        assert_eq!(log.mean_drop_rate_pct(), 20);
    }
    #[test]
    fn default_produces_zero_entries() { assert_eq!(GossipFanoutDropE5Log::default().entries.len(), 0); }
}
