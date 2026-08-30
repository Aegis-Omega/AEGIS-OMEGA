//! Gate 472 — Gossip Broadcast Epoch Gap E3 Monitor (T2)
//! Tracks epoch gap e3 rate per gossip broadcast epoch.
//! FREQUENT_GAPS_E3_THRESHOLD = 5: rate_pct > 5 → frequent_gaps_e3

use sha2::{Sha256, Digest};

pub const EPOCH_GAP_E3_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const FREQUENT_GAPS_E3_THRESHOLD: u32 = 5;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipEpochGapE3Entry {
    pub epoch_end:          u64,
    pub epoch_gaps:         u32,
    pub total_epochs:       u32,
    pub epoch_gaps_rate_pct: u32,
    pub frequent_gaps_e3:   bool,
    pub entry_hash:         [u8; 32],
    pub prev_hash:          [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    epoch_gaps: u32,
    total_epochs: u32,
    rate_pct: u32,
    frequent_gaps_e3: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(epoch_gaps.to_be_bytes());
    h.update(total_epochs.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([frequent_gaps_e3 as u8]);
    h.finalize().into()
}

pub struct GossipEpochGapE3Log {
    pub entries: Vec<GossipEpochGapE3Entry>,
}

impl GossipEpochGapE3Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(&mut self, epoch_end: u64, epoch_gaps: u32, total_epochs: u32) -> &GossipEpochGapE3Entry {
        let denom = total_epochs.max(1) as u64;
        let rate_pct = ((epoch_gaps as u64).saturating_mul(100) / denom).min(100) as u32;
        let frequent_gaps_e3 = rate_pct > FREQUENT_GAPS_E3_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(EPOCH_GAP_E3_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, epoch_gaps, total_epochs, rate_pct, frequent_gaps_e3);
        self.entries.push(GossipEpochGapE3Entry {
            epoch_end,
            epoch_gaps,
            total_epochs,
            epoch_gaps_rate_pct: rate_pct,
            frequent_gaps_e3,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn frequent_gaps_e3_count(&self) -> usize {
        self.entries.iter().filter(|e| e.frequent_gaps_e3).count()
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
        let mut prev = EPOCH_GAP_E3_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(&prev, e.epoch_end, e.epoch_gaps, e.total_epochs, e.epoch_gaps_rate_pct, e.frequent_gaps_e3);
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipEpochGapE3Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_flag_true() {
        let mut log = GossipEpochGapE3Log::new();
        let e = log.record(1000, 10, 20);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.epoch_gaps, 10);
        assert_eq!(e.total_epochs, 20);
        assert_eq!(e.epoch_gaps_rate_pct, 50);
        assert!(e.frequent_gaps_e3);
    }

    #[test]
    fn test_flag_false_when_at_threshold() {
        // rate_pct == 5 → NOT > 5, so flag is false
        let mut log = GossipEpochGapE3Log::new();
        let e = log.record(2000, 5, 100);
        assert_eq!(e.epoch_gaps_rate_pct, 5);
        assert!(!e.frequent_gaps_e3);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipEpochGapE3Log::new();
        let e = log.record(3000, 200, 10);
        assert_eq!(e.epoch_gaps_rate_pct, 100);
    }

    #[test]
    fn test_total_epochs_zero_no_div_by_zero() {
        let mut log = GossipEpochGapE3Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.epoch_gaps_rate_pct, 0);
        assert!(!e.frequent_gaps_e3);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(FREQUENT_GAPS_E3_THRESHOLD, 5);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipEpochGapE3Log::new();
        let e = log.record(5000, 3, 10);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipEpochGapE3Log::new();
        let e = log.record(6000, 1, 10);
        assert_eq!(e.prev_hash, EPOCH_GAP_E3_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipEpochGapE3Log::new();
        log.record(7000, 1, 10);
        let first_hash = log.entries[0].entry_hash;
        log.record(7001, 2, 10);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipEpochGapE3Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_one_entry() {
        let mut log = GossipEpochGapE3Log::new();
        log.record(8000, 1, 20);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipEpochGapE3Log::new();
        log.record(9000, 1, 20);
        log.record(9001, 2, 20);
        log.record(9002, 3, 20);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipEpochGapE3Log::new();
        log.record(10000, 1, 20);
        log.record(10001, 2, 20);
        log.entries[0].epoch_gaps = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipEpochGapE3Log::new();
        log.record(11000, 1, 20);
        log.record(11001, 2, 20);
        log.record(11002, 3, 20);
        log.entries[1].epoch_gaps = 77;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipEpochGapE3Log::new();
        log1.record(12000, 4, 50);
        let mut log2 = GossipEpochGapE3Log::new();
        log2.record(12000, 4, 50);
        let mut log3 = GossipEpochGapE3Log::new();
        log3.record(12000, 4, 50);
        assert_eq!(log1.entries[0].entry_hash, log2.entries[0].entry_hash);
        assert_eq!(log2.entries[0].entry_hash, log3.entries[0].entry_hash);
    }

    #[test]
    fn test_frequent_gaps_e3_count_mixed_log() {
        let mut log = GossipEpochGapE3Log::new();
        log.record(13000, 1, 100);  // rate=1, flag=false
        log.record(13001, 10, 100); // rate=10, flag=true
        log.record(13002, 5, 100);  // rate=5, flag=false (boundary)
        log.record(13003, 6, 100);  // rate=6, flag=true
        assert_eq!(log.frequent_gaps_e3_count(), 2);
    }

    #[test]
    fn test_total_epoch_gaps_sums_correctly() {
        let mut log = GossipEpochGapE3Log::new();
        log.record(14000, 3, 50);
        log.record(14001, 7, 50);
        log.record(14002, 10, 50);
        assert_eq!(log.total_epoch_gaps(), 20);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipEpochGapE3Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry_correct() {
        let mut log = GossipEpochGapE3Log::new();
        log.record(15000, 10, 100); // rate=10
        log.record(15001, 20, 100); // rate=20
        log.record(15002, 30, 100); // rate=30
        // mean = (10 + 20 + 30) / 3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn test_default_has_zero_entries() {
        let log = GossipEpochGapE3Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}