//! Gate 462 — Gossip Broadcast Fragmentation E3 Monitor (T2)
//! Tracks fragmentation e3 rate per gossip broadcast epoch.
//! HIGH_FRAGMENTATION_E3_THRESHOLD = 25: rate_pct > 25 → high_fragmentation_e3

use sha2::{Sha256, Digest};

pub const FRAGMENTATION_E3_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_FRAGMENTATION_E3_THRESHOLD: u32 = 25;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipFragmentationE3Entry {
    pub epoch_end:             u64,
    pub fragmented_msgs:       u32,
    pub total_msgs:            u32,
    pub fragmented_rate_pct:   u32,
    pub high_fragmentation_e3: bool,
    pub entry_hash:            [u8; 32],
    pub prev_hash:             [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    fragmented_msgs: u32,
    total_msgs: u32,
    rate_pct: u32,
    high_fragmentation_e3: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(fragmented_msgs.to_be_bytes());
    h.update(total_msgs.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_fragmentation_e3 as u8]);
    h.finalize().into()
}

pub struct GossipFragmentationE3Log {
    pub entries: Vec<GossipFragmentationE3Entry>,
}

impl GossipFragmentationE3Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        fragmented_msgs: u32,
        total_msgs: u32,
    ) -> &GossipFragmentationE3Entry {
        let denom = total_msgs.max(1) as u64;
        let fragmented_rate_pct =
            ((fragmented_msgs as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_fragmentation_e3 = fragmented_rate_pct > HIGH_FRAGMENTATION_E3_THRESHOLD;
        let prev = self
            .entries
            .last()
            .map(|e| e.entry_hash)
            .unwrap_or(FRAGMENTATION_E3_GENESIS_HASH);
        let entry_hash = compute_hash(
            &prev,
            epoch_end,
            fragmented_msgs,
            total_msgs,
            fragmented_rate_pct,
            high_fragmentation_e3,
        );
        self.entries.push(GossipFragmentationE3Entry {
            epoch_end,
            fragmented_msgs,
            total_msgs,
            fragmented_rate_pct,
            high_fragmentation_e3,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_fragmentation_e3_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_fragmentation_e3).count()
    }

    pub fn total_fragmented_msgs(&self) -> u64 {
        self.entries.iter().map(|e| e.fragmented_msgs as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.fragmented_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = FRAGMENTATION_E3_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.fragmented_msgs,
                e.total_msgs,
                e.fragmented_rate_pct,
                e.high_fragmentation_e3,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipFragmentationE3Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_01_record_fields_correct_flag_true() {
        let mut log = GossipFragmentationE3Log::new();
        let e = log.record(1000, 30, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.fragmented_msgs, 30);
        assert_eq!(e.total_msgs, 100);
        assert_eq!(e.fragmented_rate_pct, 30);
        assert_eq!(e.high_fragmentation_e3, true);
    }

    #[test]
    fn test_02_flag_false_at_threshold_boundary() {
        let mut log = GossipFragmentationE3Log::new();
        // rate_pct == 25 → not > 25 → flag = false
        let e = log.record(2000, 25, 100);
        assert_eq!(e.fragmented_rate_pct, 25);
        assert_eq!(e.high_fragmentation_e3, false);
    }

    #[test]
    fn test_03_rate_pct_capped_at_100() {
        let mut log = GossipFragmentationE3Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.fragmented_rate_pct, 100);
        assert_eq!(e.high_fragmentation_e3, true);
    }

    #[test]
    fn test_04_total_msgs_zero_no_div_by_zero() {
        let mut log = GossipFragmentationE3Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.fragmented_rate_pct, 0);
        assert_eq!(e.high_fragmentation_e3, false);
    }

    #[test]
    fn test_05_threshold_constant_value() {
        assert_eq!(HIGH_FRAGMENTATION_E3_THRESHOLD, 25);
    }

    #[test]
    fn test_06_entry_hash_non_zero() {
        let mut log = GossipFragmentationE3Log::new();
        let e = log.record(5000, 10, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_07_first_prev_hash_is_genesis() {
        let mut log = GossipFragmentationE3Log::new();
        let e = log.record(6000, 5, 100);
        assert_eq!(e.prev_hash, FRAGMENTATION_E3_GENESIS_HASH);
    }

    #[test]
    fn test_08_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipFragmentationE3Log::new();
        log.record(7000, 5, 100);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 10, 100);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn test_09_verify_chain_empty() {
        let log = GossipFragmentationE3Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_10_verify_chain_one_entry() {
        let mut log = GossipFragmentationE3Log::new();
        log.record(9000, 5, 50);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_11_verify_chain_three_entries() {
        let mut log = GossipFragmentationE3Log::new();
        log.record(10000, 5, 50);
        log.record(11000, 15, 50);
        log.record(12000, 30, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_12_verify_chain_tamper_entry_0() {
        let mut log = GossipFragmentationE3Log::new();
        log.record(13000, 5, 50);
        log.record(14000, 10, 50);
        log.entries[0].fragmented_msgs = 99;
        let (ok, idx) = log.verify_chain();
        assert_eq!(ok, false);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn test_13_verify_chain_tamper_entry_1() {
        let mut log = GossipFragmentationE3Log::new();
        log.record(15000, 5, 50);
        log.record(16000, 10, 50);
        log.record(17000, 15, 50);
        log.entries[1].total_msgs = 999;
        let (ok, idx) = log.verify_chain();
        assert_eq!(ok, false);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn test_14_determinism_same_inputs_same_hash() {
        let mut log1 = GossipFragmentationE3Log::new();
        let h1 = log1.record(18000, 20, 80).entry_hash;
        let mut log2 = GossipFragmentationE3Log::new();
        let h2 = log2.record(18000, 20, 80).entry_hash;
        let mut log3 = GossipFragmentationE3Log::new();
        let h3 = log3.record(18000, 20, 80).entry_hash;
        assert_eq!(h1, h2);
        assert_eq!(h2, h3);
    }

    #[test]
    fn test_15_high_fragmentation_e3_count_mixed() {
        let mut log = GossipFragmentationE3Log::new();
        log.record(19000, 5, 100);   // 5%  → false
        log.record(20000, 26, 100);  // 26% → true
        log.record(21000, 25, 100);  // 25% → false (boundary)
        log.record(22000, 50, 100);  // 50% → true
        assert_eq!(log.high_fragmentation_e3_count(), 2);
    }

    #[test]
    fn test_16_total_fragmented_msgs_sums_correctly() {
        let mut log = GossipFragmentationE3Log::new();
        log.record(23000, 10, 100);
        log.record(24000, 20, 100);
        log.record(25000, 30, 100);
        assert_eq!(log.total_fragmented_msgs(), 60);
    }

    #[test]
    fn test_17_mean_rate_pct_empty_returns_zero() {
        let log = GossipFragmentationE3Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_18_mean_rate_pct_multi_entry_correct() {
        let mut log = GossipFragmentationE3Log::new();
        log.record(26000, 10, 100); // 10%
        log.record(27000, 30, 100); // 30%
        log.record(28000, 50, 100); // 50%
        // mean = (10 + 30 + 50) / 3 = 30
        assert_eq!(log.mean_rate_pct(), 30);
    }

    #[test]
    fn test_19_default_has_zero_entries() {
        let log = GossipFragmentationE3Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}