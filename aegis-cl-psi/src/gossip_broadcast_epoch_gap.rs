//! Gate 437 — Gossip Broadcast Epoch Gap Monitor (T2)
//! Tracks epoch gap rate per gossip broadcast epoch.
//! FREQUENT_GAPS_THRESHOLD = 5: rate_pct > 5 → frequent_gaps

use sha2::{Sha256, Digest};

pub const EPOCH_GAP_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const FREQUENT_GAPS_THRESHOLD: u32 = 5;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipEpochGapEntry {
    pub epoch_end:           u64,
    pub epoch_gaps:          u32,
    pub total_epochs:        u32,
    pub epoch_gaps_rate_pct: u32,
    pub frequent_gaps:       bool,
    pub entry_hash:          [u8; 32],
    pub prev_hash:           [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    epoch_gaps: u32,
    total_epochs: u32,
    rate_pct: u32,
    frequent_gaps: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(epoch_gaps.to_be_bytes());
    h.update(total_epochs.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([frequent_gaps as u8]);
    h.finalize().into()
}

pub struct GossipEpochGapLog {
    pub entries: Vec<GossipEpochGapEntry>,
}

impl GossipEpochGapLog {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(&mut self, epoch_end: u64, epoch_gaps: u32, total_epochs: u32) -> &GossipEpochGapEntry {
        let denom = total_epochs.max(1) as u64;
        let rate_pct = ((epoch_gaps as u64).saturating_mul(100) / denom).min(100) as u32;
        let frequent_gaps = rate_pct > FREQUENT_GAPS_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(EPOCH_GAP_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, epoch_gaps, total_epochs, rate_pct, frequent_gaps);
        self.entries.push(GossipEpochGapEntry {
            epoch_end,
            epoch_gaps,
            total_epochs,
            epoch_gaps_rate_pct: rate_pct,
            frequent_gaps,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn frequent_gaps_count(&self) -> usize {
        self.entries.iter().filter(|e| e.frequent_gaps).count()
    }

    pub fn total_epoch_gaps(&self) -> u64 {
        self.entries.iter().map(|e| e.epoch_gaps as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.epoch_gaps_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = EPOCH_GAP_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(&prev, e.epoch_end, e.epoch_gaps, e.total_epochs, e.epoch_gaps_rate_pct, e.frequent_gaps);
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipEpochGapLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_flag_true() {
        let mut log = GossipEpochGapLog::new();
        let e = log.record(1000, 10, 50);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.epoch_gaps, 10);
        assert_eq!(e.total_epochs, 50);
        // rate = (10 * 100) / 50 = 20
        assert_eq!(e.epoch_gaps_rate_pct, 20);
        // 20 > 5 → frequent_gaps = true
        assert!(e.frequent_gaps);
    }

    #[test]
    fn test_flag_false_when_exactly_at_threshold() {
        let mut log = GossipEpochGapLog::new();
        // rate = (5 * 100) / 100 = 5, which is NOT > 5
        let e = log.record(2000, 5, 100);
        assert_eq!(e.epoch_gaps_rate_pct, 5);
        assert!(!e.frequent_gaps);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipEpochGapLog::new();
        // epoch_gaps > total_epochs → rate would exceed 100
        let e = log.record(3000, 200, 50);
        assert_eq!(e.epoch_gaps_rate_pct, 100);
        assert!(e.frequent_gaps);
    }

    #[test]
    fn test_total_epochs_zero_no_div_by_zero() {
        let mut log = GossipEpochGapLog::new();
        // total_epochs = 0 → denom = max(0,1) = 1
        let e = log.record(4000, 0, 0);
        assert_eq!(e.epoch_gaps_rate_pct, 0);
        assert!(!e.frequent_gaps);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(FREQUENT_GAPS_THRESHOLD, 5);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipEpochGapLog::new();
        let e = log.record(5000, 3, 30);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipEpochGapLog::new();
        let e = log.record(6000, 1, 10);
        assert_eq!(e.prev_hash, EPOCH_GAP_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipEpochGapLog::new();
        log.record(7000, 1, 10);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 2, 20);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipEpochGapLog::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_single_entry() {
        let mut log = GossipEpochGapLog::new();
        log.record(9000, 2, 20);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipEpochGapLog::new();
        log.record(10000, 1, 10);
        log.record(11000, 2, 20);
        log.record(12000, 3, 30);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipEpochGapLog::new();
        log.record(13000, 1, 10);
        log.record(14000, 2, 20);
        // Tamper with entry 0's epoch_gaps
        log.entries[0].epoch_gaps = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipEpochGapLog::new();
        log.record(15000, 1, 10);
        log.record(16000, 2, 20);
        log.record(17000, 3, 30);
        // Tamper with entry 1's epoch_gaps
        log.entries[1].epoch_gaps = 77;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipEpochGapLog::new();
        let e1 = log1.record(18000, 4, 40).entry_hash;

        let mut log2 = GossipEpochGapLog::new();
        let e2 = log2.record(18000, 4, 40).entry_hash;

        let mut log3 = GossipEpochGapLog::new();
        let e3 = log3.record(18000, 4, 40).entry_hash;

        assert_eq!(e1, e2);
        assert_eq!(e2, e3);
    }

    #[test]
    fn test_frequent_gaps_count_mixed_log() {
        let mut log = GossipEpochGapLog::new();
        // rate = 0 → not frequent
        log.record(19000, 0, 100);
        // rate = 20 → frequent
        log.record(20000, 20, 100);
        // rate = 5 → not frequent (boundary)
        log.record(21000, 5, 100);
        // rate = 6 → frequent
        log.record(22000, 6, 100);
        assert_eq!(log.frequent_gaps_count(), 2);
    }

    #[test]
    fn test_total_epoch_gaps_sums_correctly() {
        let mut log = GossipEpochGapLog::new();
        log.record(23000, 3, 30);
        log.record(24000, 7, 70);
        log.record(25000, 5, 50);
        assert_eq!(log.total_epoch_gaps(), 15);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipEpochGapLog::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry_correct() {
        let mut log = GossipEpochGapLog::new();
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
    fn test_default_has_zero_entries() {
        let log = GossipEpochGapLog::default();
        assert_eq!(log.entries.len(), 0);
    }
}