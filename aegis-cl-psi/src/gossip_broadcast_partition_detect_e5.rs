//! Gate 535 — Gossip Broadcast Partition Detect E5 Monitor (T2)
//! Tracks network partition detection rate per gossip broadcast epoch.
//! HIGH_PARTITION_DETECT_E5_THRESHOLD = 5: partition_rate_pct > 5 → high_partition_detect_e5

use sha2::{Sha256, Digest};

pub const PARTITION_DETECT_E5_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_PARTITION_DETECT_E5_THRESHOLD: u32 = 5;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPartitionDetectE5Entry {
    pub epoch_end:              u64,
    pub partitioned_peers:      u32,
    pub total_peers:            u32,
    pub partition_rate_pct:     u32,
    pub high_partition_detect_e5: bool,
    pub entry_hash:             [u8; 32],
    pub prev_hash:              [u8; 32],
}

fn compute_hash(prev: &[u8; 32], epoch_end: u64, partitioned_peers: u32, total_peers: u32, rate_pct: u32, high_partition_detect_e5: bool) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev); h.update(epoch_end.to_be_bytes());
    h.update(partitioned_peers.to_be_bytes()); h.update(total_peers.to_be_bytes());
    h.update(rate_pct.to_be_bytes()); h.update([high_partition_detect_e5 as u8]);
    h.finalize().into()
}

pub struct GossipPartitionDetectE5Log { pub entries: Vec<GossipPartitionDetectE5Entry> }

impl GossipPartitionDetectE5Log {
    pub fn new() -> Self { Self { entries: Vec::new() } }
    pub fn record(&mut self, epoch_end: u64, partitioned_peers: u32, total_peers: u32) -> &GossipPartitionDetectE5Entry {
        let denom = total_peers.max(1) as u64;
        let partition_rate_pct = ((partitioned_peers as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_partition_detect_e5 = partition_rate_pct > HIGH_PARTITION_DETECT_E5_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(PARTITION_DETECT_E5_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, partitioned_peers, total_peers, partition_rate_pct, high_partition_detect_e5);
        self.entries.push(GossipPartitionDetectE5Entry { epoch_end, partitioned_peers, total_peers, partition_rate_pct, high_partition_detect_e5, entry_hash, prev_hash: prev });
        self.entries.last().unwrap()
    }
    pub fn high_partition_detect_e5_count(&self) -> usize { self.entries.iter().filter(|e| e.high_partition_detect_e5).count() }
    pub fn total_partitioned_peers(&self) -> u64 { self.entries.iter().map(|e| e.partitioned_peers as u64).sum() }
    pub fn mean_partition_rate_pct(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        (self.entries.iter().map(|e| e.partition_rate_pct as u64).sum::<u64>() / self.entries.len() as u64) as u32
    }
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = PARTITION_DETECT_E5_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev { return (false, Some(i)); }
            if e.entry_hash != compute_hash(&prev, e.epoch_end, e.partitioned_peers, e.total_peers, e.partition_rate_pct, e.high_partition_detect_e5) { return (false, Some(i)); }
            prev = e.entry_hash;
        }
        (true, None)
    }
}
impl Default for GossipPartitionDetectE5Log { fn default() -> Self { Self::new() } }

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipPartitionDetectE5Log::new();
        let e = log.record(1000, 8, 100);
        assert_eq!(e.epoch_end, 1000); assert_eq!(e.partitioned_peers, 8);
        assert_eq!(e.total_peers, 100); assert_eq!(e.partition_rate_pct, 8);
        assert!(e.high_partition_detect_e5);
    }
    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipPartitionDetectE5Log::new();
        let e = log.record(2000, 5, 100);
        assert_eq!(e.partition_rate_pct, 5); assert!(!e.high_partition_detect_e5);
    }
    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipPartitionDetectE5Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.partition_rate_pct, 100); assert!(e.high_partition_detect_e5);
    }
    #[test]
    fn total_peers_zero_no_div_by_zero() {
        let mut log = GossipPartitionDetectE5Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.partition_rate_pct, 0); assert!(!e.high_partition_detect_e5);
    }
    #[test]
    fn threshold_constant_value_is_5() { assert_eq!(HIGH_PARTITION_DETECT_E5_THRESHOLD, 5); }
    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipPartitionDetectE5Log::new();
        assert_ne!(log.record(5000, 7, 80).entry_hash, [0u8; 32]);
    }
    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipPartitionDetectE5Log::new();
        assert_eq!(log.record(6000, 4, 80).prev_hash, PARTITION_DETECT_E5_GENESIS_HASH);
    }
    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipPartitionDetectE5Log::new();
        log.record(7000, 4, 80);
        let h = log.entries[0].entry_hash;
        log.record(8000, 8, 100);
        assert_eq!(log.entries[1].prev_hash, h);
    }
    #[test]
    fn verify_chain_empty_returns_true_none() { assert_eq!(GossipPartitionDetectE5Log::new().verify_chain(), (true, None)); }
    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipPartitionDetectE5Log::new();
        log.record(9000, 6, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }
    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipPartitionDetectE5Log::new();
        log.record(10000, 3, 50); log.record(11000, 6, 80); log.record(12000, 9, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }
    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipPartitionDetectE5Log::new();
        log.record(13000, 4, 80); log.record(14000, 8, 100);
        log.entries[0].partitioned_peers = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }
    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipPartitionDetectE5Log::new();
        log.record(15000, 4, 80); log.record(16000, 8, 100);
        log.entries[1].partitioned_peers = 99;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }
    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut l1 = GossipPartitionDetectE5Log::new(); let mut l2 = GossipPartitionDetectE5Log::new(); let mut l3 = GossipPartitionDetectE5Log::new();
        let e1 = l1.record(17000, 7, 90).entry_hash; let e2 = l2.record(17000, 7, 90).entry_hash; let e3 = l3.record(17000, 7, 90).entry_hash;
        assert_eq!(e1, e2); assert_eq!(e2, e3);
    }
    #[test]
    fn high_partition_detect_e5_count_mixed_log() {
        let mut log = GossipPartitionDetectE5Log::new();
        log.record(18000, 4, 100); log.record(19000, 12, 100); log.record(20000, 5, 100); log.record(21000, 6, 100);
        assert_eq!(log.high_partition_detect_e5_count(), 2);
    }
    #[test]
    fn total_partitioned_peers_sums_correctly() {
        let mut log = GossipPartitionDetectE5Log::new();
        log.record(22000, 10, 100); log.record(23000, 25, 100); log.record(24000, 7, 100);
        assert_eq!(log.total_partitioned_peers(), 42);
    }
    #[test]
    fn mean_partition_rate_pct_empty_returns_zero() { assert_eq!(GossipPartitionDetectE5Log::new().mean_partition_rate_pct(), 0); }
    #[test]
    fn mean_partition_rate_pct_multi_entry_correct() {
        let mut log = GossipPartitionDetectE5Log::new();
        log.record(25000, 10, 100); log.record(26000, 20, 100); log.record(27000, 30, 100);
        assert_eq!(log.mean_partition_rate_pct(), 20);
    }
    #[test]
    fn default_produces_zero_entries() { assert_eq!(GossipPartitionDetectE5Log::default().entries.len(), 0); }
}
