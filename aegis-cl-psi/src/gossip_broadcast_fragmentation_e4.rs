//! Gate 497 — Gossip Broadcast Fragmentation E4 Monitor (T2)
//! Tracks fragmentation e4 rate per gossip broadcast epoch.
//! HIGH_FRAGMENTATION_E4_THRESHOLD = 25: rate_pct > 25 → high_fragmentation_e4

use sha2::{Sha256, Digest};

pub const FRAGMENTATION_E4_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_FRAGMENTATION_E4_THRESHOLD: u32 = 25;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipFragmentationE4Entry {
    pub epoch_end:            u64,
    pub fragmented_msgs:      u32,
    pub total_msgs:           u32,
    pub fragmented_rate_pct:  u32,
    pub high_fragmentation_e4: bool,
    pub entry_hash:           [u8; 32],
    pub prev_hash:            [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    fragmented_msgs: u32,
    total_msgs: u32,
    rate_pct: u32,
    high_fragmentation_e4: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(fragmented_msgs.to_be_bytes());
    h.update(total_msgs.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_fragmentation_e4 as u8]);
    h.finalize().into()
}

pub struct GossipFragmentationE4Log {
    pub entries: Vec<GossipFragmentationE4Entry>,
}

impl GossipFragmentationE4Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        fragmented_msgs: u32,
        total_msgs: u32,
    ) -> &GossipFragmentationE4Entry {
        let denom = total_msgs.max(1) as u64;
        let fragmented_rate_pct =
            ((fragmented_msgs as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_fragmentation_e4 = fragmented_rate_pct > HIGH_FRAGMENTATION_E4_THRESHOLD;
        let prev = self
            .entries
            .last()
            .map(|e| e.entry_hash)
            .unwrap_or(FRAGMENTATION_E4_GENESIS_HASH);
        let entry_hash = compute_hash(
            &prev,
            epoch_end,
            fragmented_msgs,
            total_msgs,
            fragmented_rate_pct,
            high_fragmentation_e4,
        );
        self.entries.push(GossipFragmentationE4Entry {
            epoch_end,
            fragmented_msgs,
            total_msgs,
            fragmented_rate_pct,
            high_fragmentation_e4,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_fragmentation_e4_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_fragmentation_e4).count()
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
        let mut prev = FRAGMENTATION_E4_GENESIS_HASH;
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
                e.high_fragmentation_e4,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipFragmentationE4Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_flag_true() {
        let mut log = GossipFragmentationE4Log::new();
        let e = log.record(1000, 30, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.fragmented_msgs, 30);
        assert_eq!(e.total_msgs, 100);
        assert_eq!(e.fragmented_rate_pct, 30);
        assert!(e.high_fragmentation_e4);
    }

    #[test]
    fn test_flag_false_when_exactly_at_threshold() {
        let mut log = GossipFragmentationE4Log::new();
        // rate = (25 * 100) / 100 = 25, not > 25, so flag = false
        let e = log.record(2000, 25, 100);
        assert_eq!(e.fragmented_rate_pct, 25);
        assert!(!e.high_fragmentation_e4);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipFragmentationE4Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.fragmented_rate_pct, 100);
    }

    #[test]
    fn test_total_msgs_zero_no_div_by_zero() {
        let mut log = GossipFragmentationE4Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.fragmented_rate_pct, 0);
        assert!(!e.high_fragmentation_e4);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(HIGH_FRAGMENTATION_E4_THRESHOLD, 25);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipFragmentationE4Log::new();
        let e = log.record(5000, 10, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipFragmentationE4Log::new();
        let e = log.record(6000, 5, 100);
        assert_eq!(e.prev_hash, FRAGMENTATION_E4_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipFragmentationE4Log::new();
        log.record(7000, 5, 100);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 10, 100);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipFragmentationE4Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_one_entry() {
        let mut log = GossipFragmentationE4Log::new();
        log.record(9000, 10, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipFragmentationE4Log::new();
        log.record(10000, 5, 100);
        log.record(11000, 15, 100);
        log.record(12000, 30, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipFragmentationE4Log::new();
        log.record(13000, 5, 100);
        log.record(14000, 10, 100);
        log.entries[0].fragmented_msgs = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipFragmentationE4Log::new();
        log.record(15000, 5, 100);
        log.record(16000, 10, 100);
        log.entries[1].fragmented_msgs = 77;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipFragmentationE4Log::new();
        let mut log2 = GossipFragmentationE4Log::new();
        let mut log3 = GossipFragmentationE4Log::new();
        log1.record(17000, 20, 100);
        log2.record(17000, 20, 100);
        log3.record(17000, 20, 100);
        assert_eq!(log1.entries[0].entry_hash, log2.entries[0].entry_hash);
        assert_eq!(log2.entries[0].entry_hash, log3.entries[0].entry_hash);
    }

    #[test]
    fn test_high_fragmentation_e4_count_mixed() {
        let mut log = GossipFragmentationE4Log::new();
        log.record(18000, 5, 100);   // rate=5, flag=false
        log.record(19000, 30, 100);  // rate=30, flag=true
        log.record(20000, 25, 100);  // rate=25, flag=false (boundary)
        log.record(21000, 50, 100);  // rate=50, flag=true
        assert_eq!(log.high_fragmentation_e4_count(), 2);
    }

    #[test]
    fn test_total_fragmented_msgs_sums_correctly() {
        let mut log = GossipFragmentationE4Log::new();
        log.record(22000, 10, 100);
        log.record(23000, 20, 100);
        log.record(24000, 30, 100);
        assert_eq!(log.total_fragmented_msgs(), 60);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipFragmentationE4Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry_correct() {
        let mut log = GossipFragmentationE4Log::new();
        log.record(25000, 10, 100); // rate=10
        log.record(26000, 20, 100); // rate=20
        log.record(27000, 30, 100); // rate=30
        // mean = (10+20+30)/3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn test_default_zero_entries() {
        let log = GossipFragmentationE4Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}