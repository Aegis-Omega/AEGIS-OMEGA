//! Gate 557 — Gossip Broadcast Partition Heal E5 Monitor (T2)
//! Tracks partition heal rate per gossip broadcast epoch.
//! HIGH_PARTITION_HEAL_E5_THRESHOLD = 22: heal_rate_pct > 22 → high_partition_heal_e5

use sha2::{Sha256, Digest};

pub const PARTITION_HEAL_E5_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_PARTITION_HEAL_E5_THRESHOLD: u32 = 22;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPartitionHealE5Entry {
    pub epoch_end:              u64,
    pub healed_partitions:      u32,
    pub total_partitions:       u32,
    pub heal_rate_pct:          u32,
    pub high_partition_heal_e5: bool,
    pub entry_hash:             [u8; 32],
    pub prev_hash:              [u8; 32],
}

fn compute_hash(prev: &[u8; 32], epoch_end: u64, healed_partitions: u32, total_partitions: u32, rate_pct: u32, high_partition_heal_e5: bool) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev); h.update(epoch_end.to_be_bytes());
    h.update(healed_partitions.to_be_bytes()); h.update(total_partitions.to_be_bytes());
    h.update(rate_pct.to_be_bytes()); h.update([high_partition_heal_e5 as u8]);
    h.finalize().into()
}

pub struct GossipPartitionHealE5Log { pub entries: Vec<GossipPartitionHealE5Entry> }

impl GossipPartitionHealE5Log {
    pub fn new() -> Self { Self { entries: Vec::new() } }
    pub fn record(&mut self, epoch_end: u64, healed_partitions: u32, total_partitions: u32) -> &GossipPartitionHealE5Entry {
        let denom = total_partitions.max(1) as u64;
        let heal_rate_pct = ((healed_partitions as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_partition_heal_e5 = heal_rate_pct > HIGH_PARTITION_HEAL_E5_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(PARTITION_HEAL_E5_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, healed_partitions, total_partitions, heal_rate_pct, high_partition_heal_e5);
        self.entries.push(GossipPartitionHealE5Entry { epoch_end, healed_partitions, total_partitions, heal_rate_pct, high_partition_heal_e5, entry_hash, prev_hash: prev });
        self.entries.last().unwrap()
    }
    pub fn high_partition_heal_e5_count(&self) -> usize { self.entries.iter().filter(|e| e.high_partition_heal_e5).count() }
    pub fn total_healed_partitions(&self) -> u64 { self.entries.iter().map(|e| e.healed_partitions as u64).sum() }
    pub fn mean_heal_rate_pct(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        (self.entries.iter().map(|e| e.heal_rate_pct as u64).sum::<u64>() / self.entries.len() as u64) as u32
    }
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = PARTITION_HEAL_E5_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev { return (false, Some(i)); }
            if e.entry_hash != compute_hash(&prev, e.epoch_end, e.healed_partitions, e.total_partitions, e.heal_rate_pct, e.high_partition_heal_e5) { return (false, Some(i)); }
            prev = e.entry_hash;
        }
        (true, None)
    }
}
impl Default for GossipPartitionHealE5Log { fn default() -> Self { Self::new() } }

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipPartitionHealE5Log::new();
        let e = log.record(1000, 28, 100);
        assert_eq!(e.epoch_end, 1000); assert_eq!(e.healed_partitions, 28);
        assert_eq!(e.total_partitions, 100); assert_eq!(e.heal_rate_pct, 28);
        assert!(e.high_partition_heal_e5);
    }
    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipPartitionHealE5Log::new();
        let e = log.record(2000, 22, 100);
        assert_eq!(e.heal_rate_pct, 22); assert!(!e.high_partition_heal_e5);
    }
    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipPartitionHealE5Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.heal_rate_pct, 100); assert!(e.high_partition_heal_e5);
    }
    #[test]
    fn total_partitions_zero_no_div_by_zero() {
        let mut log = GossipPartitionHealE5Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.heal_rate_pct, 0); assert!(!e.high_partition_heal_e5);
    }
    #[test]
    fn threshold_constant_value_is_22() { assert_eq!(HIGH_PARTITION_HEAL_E5_THRESHOLD, 22); }
    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipPartitionHealE5Log::new();
        assert_ne!(log.record(5000, 25, 80).entry_hash, [0u8; 32]);
    }
    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipPartitionHealE5Log::new();
        assert_eq!(log.record(6000, 18, 80).prev_hash, PARTITION_HEAL_E5_GENESIS_HASH);
    }
    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipPartitionHealE5Log::new();
        log.record(7000, 18, 80);
        let h = log.entries[0].entry_hash;
        log.record(8000, 28, 100);
        assert_eq!(log.entries[1].prev_hash, h);
    }
    #[test]
    fn verify_chain_empty_returns_true_none() { assert_eq!(GossipPartitionHealE5Log::new().verify_chain(), (true, None)); }
    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipPartitionHealE5Log::new();
        log.record(9000, 23, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }
    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipPartitionHealE5Log::new();
        log.record(10000, 14, 60); log.record(11000, 23, 80); log.record(12000, 30, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }
    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipPartitionHealE5Log::new();
        log.record(13000, 18, 80); log.record(14000, 28, 100);
        log.entries[0].healed_partitions = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }
    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipPartitionHealE5Log::new();
        log.record(15000, 18, 80); log.record(16000, 28, 100);
        log.entries[1].healed_partitions = 99;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }
    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut l1 = GossipPartitionHealE5Log::new(); let mut l2 = GossipPartitionHealE5Log::new(); let mut l3 = GossipPartitionHealE5Log::new();
        let e1 = l1.record(17000, 25, 90).entry_hash; let e2 = l2.record(17000, 25, 90).entry_hash; let e3 = l3.record(17000, 25, 90).entry_hash;
        assert_eq!(e1, e2); assert_eq!(e2, e3);
    }
    #[test]
    fn high_partition_heal_e5_count_mixed_log() {
        let mut log = GossipPartitionHealE5Log::new();
        log.record(18000, 18, 100); log.record(19000, 28, 100); log.record(20000, 22, 100); log.record(21000, 23, 100);
        assert_eq!(log.high_partition_heal_e5_count(), 2);
    }
    #[test]
    fn total_healed_partitions_sums_correctly() {
        let mut log = GossipPartitionHealE5Log::new();
        log.record(22000, 10, 100); log.record(23000, 25, 100); log.record(24000, 7, 100);
        assert_eq!(log.total_healed_partitions(), 42);
    }
    #[test]
    fn mean_heal_rate_pct_empty_returns_zero() { assert_eq!(GossipPartitionHealE5Log::new().mean_heal_rate_pct(), 0); }
    #[test]
    fn mean_heal_rate_pct_multi_entry_correct() {
        let mut log = GossipPartitionHealE5Log::new();
        log.record(25000, 10, 100); log.record(26000, 20, 100); log.record(27000, 30, 100);
        assert_eq!(log.mean_heal_rate_pct(), 20);
    }
    #[test]
    fn default_produces_zero_entries() { assert_eq!(GossipPartitionHealE5Log::default().entries.len(), 0); }
}
