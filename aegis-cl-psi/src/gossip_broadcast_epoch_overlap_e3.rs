//! Gate 486 — Gossip Broadcast Epoch Overlap E3 Monitor (T2)
//! Tracks epoch overlap e3 rate per gossip broadcast epoch.
//! HIGH_OVERLAP_E3_THRESHOLD = 3: rate_pct > 3 → high_overlap_e3

use sha2::{Sha256, Digest};

pub const EPOCH_OVERLAP_E3_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_OVERLAP_E3_THRESHOLD: u32 = 3;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipEpochOverlapE3Entry {
    pub epoch_end:            u64,
    pub overlapping_epochs:   u32,
    pub total_epochs:         u32,
    pub overlapping_rate_pct: u32,
    pub high_overlap_e3:      bool,
    pub entry_hash:           [u8; 32],
    pub prev_hash:             [u8; 32],
}

fn compute_hash(
    prev:               &[u8; 32],
    epoch_end:          u64,
    overlapping_epochs: u32,
    total_epochs:       u32,
    rate_pct:           u32,
    high_overlap_e3:    bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(overlapping_epochs.to_be_bytes());
    h.update(total_epochs.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_overlap_e3 as u8]);
    h.finalize().into()
}

pub struct GossipEpochOverlapE3Log {
    pub entries: Vec<GossipEpochOverlapE3Entry>,
}

impl GossipEpochOverlapE3Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end:          u64,
        overlapping_epochs: u32,
        total_epochs:       u32,
    ) -> &GossipEpochOverlapE3Entry {
        let denom = total_epochs.max(1) as u64;
        let overlapping_rate_pct =
            ((overlapping_epochs as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_overlap_e3 = overlapping_rate_pct > HIGH_OVERLAP_E3_THRESHOLD;
        let prev = self
            .entries
            .last()
            .map(|e| e.entry_hash)
            .unwrap_or(EPOCH_OVERLAP_E3_GENESIS_HASH);
        let entry_hash = compute_hash(
            &prev,
            epoch_end,
            overlapping_epochs,
            total_epochs,
            overlapping_rate_pct,
            high_overlap_e3,
        );
        self.entries.push(GossipEpochOverlapE3Entry {
            epoch_end,
            overlapping_epochs,
            total_epochs,
            overlapping_rate_pct,
            high_overlap_e3,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_overlap_e3_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_overlap_e3).count()
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
        let mut prev = EPOCH_OVERLAP_E3_GENESIS_HASH;
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
                e.high_overlap_e3,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipEpochOverlapE3Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_high_flag_true() {
        let mut log = GossipEpochOverlapE3Log::new();
        // overlapping=5, total=10 → rate=50 → high_overlap_e3=true
        let e = log.record(1000, 5, 10);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.overlapping_epochs, 5);
        assert_eq!(e.total_epochs, 10);
        assert_eq!(e.overlapping_rate_pct, 50);
        assert!(e.high_overlap_e3);
    }

    #[test]
    fn test_flag_false_exactly_at_threshold() {
        let mut log = GossipEpochOverlapE3Log::new();
        // overlapping=3, total=100 → rate=3 → NOT > 3, so false
        let e = log.record(2000, 3, 100);
        assert_eq!(e.overlapping_rate_pct, 3);
        assert!(!e.high_overlap_e3);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipEpochOverlapE3Log::new();
        // overlapping > total → would exceed 100 without cap
        let e = log.record(3000, 200, 10);
        assert_eq!(e.overlapping_rate_pct, 100);
        assert!(e.high_overlap_e3);
    }

    #[test]
    fn test_total_epochs_zero_no_div_by_zero() {
        let mut log = GossipEpochOverlapE3Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.overlapping_rate_pct, 0);
        assert!(!e.high_overlap_e3);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(HIGH_OVERLAP_E3_THRESHOLD, 3);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipEpochOverlapE3Log::new();
        let e = log.record(5000, 10, 20);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipEpochOverlapE3Log::new();
        let e = log.record(6000, 1, 10);
        assert_eq!(e.prev_hash, EPOCH_OVERLAP_E3_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipEpochOverlapE3Log::new();
        log.record(7000, 1, 10);
        let first_hash = log.entries[0].entry_hash;
        log.record(7001, 2, 10);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipEpochOverlapE3Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_one_entry() {
        let mut log = GossipEpochOverlapE3Log::new();
        log.record(8000, 1, 10);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipEpochOverlapE3Log::new();
        log.record(9000, 1, 10);
        log.record(9001, 2, 20);
        log.record(9002, 3, 30);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipEpochOverlapE3Log::new();
        log.record(10000, 1, 10);
        log.record(10001, 2, 20);
        // Tamper entry 0's overlapping_epochs
        log.entries[0].overlapping_epochs = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipEpochOverlapE3Log::new();
        log.record(11000, 1, 10);
        log.record(11001, 2, 20);
        log.record(11002, 3, 30);
        // Tamper entry 1's rate
        log.entries[1].overlapping_rate_pct = 77;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipEpochOverlapE3Log::new();
        let mut log2 = GossipEpochOverlapE3Log::new();
        let mut log3 = GossipEpochOverlapE3Log::new();
        let h1 = log1.record(12000, 4, 10).entry_hash;
        let h2 = log2.record(12000, 4, 10).entry_hash;
        let h3 = log3.record(12000, 4, 10).entry_hash;
        assert_eq!(h1, h2);
        assert_eq!(h2, h3);
    }

    #[test]
    fn test_high_overlap_e3_count_mixed() {
        let mut log = GossipEpochOverlapE3Log::new();
        // rate=0 → false
        log.record(13000, 0, 100);
        // rate=3 → false (boundary)
        log.record(13001, 3, 100);
        // rate=4 → true
        log.record(13002, 4, 100);
        // rate=50 → true
        log.record(13003, 50, 100);
        assert_eq!(log.high_overlap_e3_count(), 2);
    }

    #[test]
    fn test_total_overlapping_epochs_sums_correctly() {
        let mut log = GossipEpochOverlapE3Log::new();
        log.record(14000, 5, 100);
        log.record(14001, 10, 100);
        log.record(14002, 15, 100);
        assert_eq!(log.total_overlapping_epochs(), 30u64);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipEpochOverlapE3Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry() {
        let mut log = GossipEpochOverlapE3Log::new();
        // rates: 10, 20, 30 → mean=20
        log.record(15000, 10, 100);
        log.record(15001, 20, 100);
        log.record(15002, 30, 100);
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn test_default_has_zero_entries() {
        let log = GossipEpochOverlapE3Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}