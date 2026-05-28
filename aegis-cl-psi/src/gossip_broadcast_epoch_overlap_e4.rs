//! Gate 521 — Gossip Broadcast Epoch Overlap E4 Monitor (T2)
//! Tracks message overlap between consecutive gossip broadcast epochs.
//! HIGH_OVERLAP_E4_THRESHOLD = 15: overlap_rate_pct > 15 → high_overlap_e4

use sha2::{Sha256, Digest};

pub const EPOCH_OVERLAP_E4_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_OVERLAP_E4_THRESHOLD: u32 = 15;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipEpochOverlapE4Entry {
    pub epoch_end:        u64,
    pub overlapping_msgs: u32,
    pub total_msgs:       u32,
    pub overlap_rate_pct: u32,
    pub high_overlap_e4:  bool,
    pub entry_hash:       [u8; 32],
    pub prev_hash:        [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    overlapping_msgs: u32,
    total_msgs: u32,
    rate_pct: u32,
    high_overlap_e4: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(overlapping_msgs.to_be_bytes());
    h.update(total_msgs.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_overlap_e4 as u8]);
    h.finalize().into()
}

pub struct GossipEpochOverlapE4Log {
    pub entries: Vec<GossipEpochOverlapE4Entry>,
}

impl GossipEpochOverlapE4Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        overlapping_msgs: u32,
        total_msgs: u32,
    ) -> &GossipEpochOverlapE4Entry {
        let denom = total_msgs.max(1) as u64;
        let overlap_rate_pct =
            ((overlapping_msgs as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_overlap_e4 = overlap_rate_pct > HIGH_OVERLAP_E4_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(EPOCH_OVERLAP_E4_GENESIS_HASH);
        let entry_hash = compute_hash(
            &prev,
            epoch_end,
            overlapping_msgs,
            total_msgs,
            overlap_rate_pct,
            high_overlap_e4,
        );
        self.entries.push(GossipEpochOverlapE4Entry {
            epoch_end,
            overlapping_msgs,
            total_msgs,
            overlap_rate_pct,
            high_overlap_e4,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_overlap_e4_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_overlap_e4).count()
    }

    pub fn total_overlapping_msgs(&self) -> u64 {
        self.entries.iter().map(|e| e.overlapping_msgs as u64).sum()
    }

    pub fn mean_overlap_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.overlap_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = EPOCH_OVERLAP_E4_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.overlapping_msgs,
                e.total_msgs,
                e.overlap_rate_pct,
                e.high_overlap_e4,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipEpochOverlapE4Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipEpochOverlapE4Log::new();
        let e = log.record(1000, 20, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.overlapping_msgs, 20);
        assert_eq!(e.total_msgs, 100);
        assert_eq!(e.overlap_rate_pct, 20);
        assert!(e.high_overlap_e4);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipEpochOverlapE4Log::new();
        // rate = (15 * 100) / 100 = 15, not > 15
        let e = log.record(2000, 15, 100);
        assert_eq!(e.overlap_rate_pct, 15);
        assert!(!e.high_overlap_e4);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipEpochOverlapE4Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.overlap_rate_pct, 100);
        assert!(e.high_overlap_e4);
    }

    #[test]
    fn total_msgs_zero_no_div_by_zero() {
        let mut log = GossipEpochOverlapE4Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.overlap_rate_pct, 0);
        assert!(!e.high_overlap_e4);
    }

    #[test]
    fn threshold_constant_value_is_15() {
        assert_eq!(HIGH_OVERLAP_E4_THRESHOLD, 15);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipEpochOverlapE4Log::new();
        let e = log.record(5000, 25, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipEpochOverlapE4Log::new();
        let e = log.record(6000, 10, 100);
        assert_eq!(e.prev_hash, EPOCH_OVERLAP_E4_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipEpochOverlapE4Log::new();
        log.record(7000, 10, 100);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 20, 100);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipEpochOverlapE4Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipEpochOverlapE4Log::new();
        log.record(9000, 10, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipEpochOverlapE4Log::new();
        log.record(10000, 5, 50);
        log.record(11000, 12, 80);
        log.record(12000, 18, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipEpochOverlapE4Log::new();
        log.record(13000, 10, 100);
        log.record(14000, 20, 100);
        log.entries[0].overlapping_msgs = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipEpochOverlapE4Log::new();
        log.record(15000, 10, 100);
        log.record(16000, 20, 100);
        log.entries[1].overlapping_msgs = 99;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut log1 = GossipEpochOverlapE4Log::new();
        let mut log2 = GossipEpochOverlapE4Log::new();
        let mut log3 = GossipEpochOverlapE4Log::new();
        let e1 = log1.record(17000, 18, 90).entry_hash;
        let e2 = log2.record(17000, 18, 90).entry_hash;
        let e3 = log3.record(17000, 18, 90).entry_hash;
        assert_eq!(e1, e2);
        assert_eq!(e2, e3);
    }

    #[test]
    fn high_overlap_e4_count_mixed_log() {
        let mut log = GossipEpochOverlapE4Log::new();
        log.record(18000, 10, 100); // rate=10, false
        log.record(19000, 20, 100); // rate=20, true
        log.record(20000, 15, 100); // rate=15, false (boundary)
        log.record(21000, 16, 100); // rate=16, true
        assert_eq!(log.high_overlap_e4_count(), 2);
    }

    #[test]
    fn total_overlapping_msgs_sums_correctly() {
        let mut log = GossipEpochOverlapE4Log::new();
        log.record(22000, 10, 100);
        log.record(23000, 25, 100);
        log.record(24000, 7, 100);
        assert_eq!(log.total_overlapping_msgs(), 42);
    }

    #[test]
    fn mean_overlap_rate_pct_empty_returns_zero() {
        let log = GossipEpochOverlapE4Log::new();
        assert_eq!(log.mean_overlap_rate_pct(), 0);
    }

    #[test]
    fn mean_overlap_rate_pct_multi_entry_correct() {
        let mut log = GossipEpochOverlapE4Log::new();
        log.record(25000, 10, 100); // rate=10
        log.record(26000, 20, 100); // rate=20
        log.record(27000, 30, 100); // rate=30
        assert_eq!(log.mean_overlap_rate_pct(), 20);
    }

    #[test]
    fn default_produces_zero_entries() {
        let log = GossipEpochOverlapE4Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}
