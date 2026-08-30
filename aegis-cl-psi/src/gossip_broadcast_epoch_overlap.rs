//! Gate 451 — Gossip Broadcast Epoch Overlap Monitor (T2)
//! Tracks epoch overlap rate per gossip broadcast epoch.
//! HIGH_OVERLAP_THRESHOLD = 3: rate_pct > 3 → high_overlap

use sha2::{Sha256, Digest};

pub const EPOCH_OVERLAP_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_OVERLAP_THRESHOLD: u32 = 3;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipEpochOverlapEntry {
    pub epoch_end:          u64,
    pub overlapping_epochs: u32,
    pub total_epochs:       u32,
    pub overlapping_rate_pct: u32,
    pub high_overlap:       bool,
    pub entry_hash:         [u8; 32],
    pub prev_hash:          [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    overlapping_epochs: u32,
    total_epochs: u32,
    rate_pct: u32,
    high_overlap: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(overlapping_epochs.to_be_bytes());
    h.update(total_epochs.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_overlap as u8]);
    h.finalize().into()
}

pub struct GossipEpochOverlapLog {
    pub entries: Vec<GossipEpochOverlapEntry>,
}

impl GossipEpochOverlapLog {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        overlapping_epochs: u32,
        total_epochs: u32,
    ) -> &GossipEpochOverlapEntry {
        let denom = total_epochs.max(1) as u64;
        let overlapping_rate_pct =
            ((overlapping_epochs as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_overlap = overlapping_rate_pct > HIGH_OVERLAP_THRESHOLD;
        let prev = self
            .entries
            .last()
            .map(|e| e.entry_hash)
            .unwrap_or(EPOCH_OVERLAP_GENESIS_HASH);
        let entry_hash = compute_hash(
            &prev,
            epoch_end,
            overlapping_epochs,
            total_epochs,
            overlapping_rate_pct,
            high_overlap,
        );
        self.entries.push(GossipEpochOverlapEntry {
            epoch_end,
            overlapping_epochs,
            total_epochs,
            overlapping_rate_pct,
            high_overlap,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_overlap_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_overlap).count()
    }

    pub fn total_overlapping_epochs(&self) -> u64 {
        self.entries
            .iter()
            .map(|e| e.overlapping_epochs as u64)
            .fold(0u64, |acc, v| acc.saturating_add(v))
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self
            .entries
            .iter()
            .map(|e| e.overlapping_rate_pct as u64)
            .sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = EPOCH_OVERLAP_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.overlapping_epochs,
                e.total_epochs,
                e.overlapping_rate_pct,
                e.high_overlap,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipEpochOverlapLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_high_overlap_true() {
        let mut log = GossipEpochOverlapLog::new();
        let e = log.record(1000, 10, 50);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.overlapping_epochs, 10);
        assert_eq!(e.total_epochs, 50);
        // rate = (10 * 100) / 50 = 20
        assert_eq!(e.overlapping_rate_pct, 20);
        assert!(e.high_overlap);
    }

    #[test]
    fn test_flag_false_when_exactly_at_threshold() {
        let mut log = GossipEpochOverlapLog::new();
        // rate = (3 * 100) / 100 = 3, not > 3 so false
        let e = log.record(2000, 3, 100);
        assert_eq!(e.overlapping_rate_pct, 3);
        assert!(!e.high_overlap);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipEpochOverlapLog::new();
        // overlapping_epochs > total_epochs
        let e = log.record(3000, 200, 50);
        assert_eq!(e.overlapping_rate_pct, 100);
        assert!(e.high_overlap);
    }

    #[test]
    fn test_total_epochs_zero_no_div_by_zero() {
        let mut log = GossipEpochOverlapLog::new();
        let e = log.record(4000, 0, 0);
        // denom = max(0,1) = 1, rate = 0
        assert_eq!(e.overlapping_rate_pct, 0);
        assert!(!e.high_overlap);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(HIGH_OVERLAP_THRESHOLD, 3);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipEpochOverlapLog::new();
        let e = log.record(5000, 5, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipEpochOverlapLog::new();
        let e = log.record(6000, 1, 10);
        assert_eq!(e.prev_hash, EPOCH_OVERLAP_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipEpochOverlapLog::new();
        log.record(7000, 1, 10);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 2, 20);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipEpochOverlapLog::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_single_entry() {
        let mut log = GossipEpochOverlapLog::new();
        log.record(9000, 2, 40);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipEpochOverlapLog::new();
        log.record(10000, 1, 20);
        log.record(11000, 3, 60);
        log.record(12000, 5, 80);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipEpochOverlapLog::new();
        log.record(13000, 2, 50);
        log.record(14000, 4, 80);
        // tamper the first entry
        log.entries[0].overlapping_epochs = 99;
        let result = log.verify_chain();
        assert_eq!(result, (false, Some(0)));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipEpochOverlapLog::new();
        log.record(15000, 1, 25);
        log.record(16000, 3, 75);
        log.record(17000, 5, 100);
        // tamper the second entry
        log.entries[1].overlapping_rate_pct = 99;
        let result = log.verify_chain();
        assert_eq!(result, (false, Some(1)));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipEpochOverlapLog::new();
        let e1 = log1.record(18000, 4, 80).entry_hash;

        let mut log2 = GossipEpochOverlapLog::new();
        let e2 = log2.record(18000, 4, 80).entry_hash;

        let mut log3 = GossipEpochOverlapLog::new();
        let e3 = log3.record(18000, 4, 80).entry_hash;

        assert_eq!(e1, e2);
        assert_eq!(e2, e3);
    }

    #[test]
    fn test_high_overlap_count_mixed_log() {
        let mut log = GossipEpochOverlapLog::new();
        // rate = 0 → false
        log.record(19000, 0, 100);
        // rate = 3 → false (not > 3)
        log.record(20000, 3, 100);
        // rate = 4 → true
        log.record(21000, 4, 100);
        // rate = 50 → true
        log.record(22000, 50, 100);
        assert_eq!(log.high_overlap_count(), 2);
    }

    #[test]
    fn test_total_overlapping_epochs_sums_correctly() {
        let mut log = GossipEpochOverlapLog::new();
        log.record(23000, 5, 100);
        log.record(24000, 10, 200);
        log.record(25000, 3, 50);
        assert_eq!(log.total_overlapping_epochs(), 18);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipEpochOverlapLog::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry() {
        let mut log = GossipEpochOverlapLog::new();
        // rate = (10*100)/100 = 10
        log.record(26000, 10, 100);
        // rate = (20*100)/100 = 20
        log.record(27000, 20, 100);
        // rate = (30*100)/100 = 30
        log.record(28000, 30, 100);
        // mean = (10+20+30)/3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn test_default_has_zero_entries() {
        let log = GossipEpochOverlapLog::default();
        assert_eq!(log.entries.len(), 0);
    }
}