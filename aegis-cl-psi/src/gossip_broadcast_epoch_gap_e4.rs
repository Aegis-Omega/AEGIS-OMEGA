//! Gate 507 — Gossip Broadcast Epoch Gap E4 Monitor (T2)
//! Tracks epoch gap e4 rate per gossip broadcast epoch.
//! FREQUENT_GAPS_E4_THRESHOLD = 5: rate_pct > 5 → frequent_gaps_e4

use sha2::{Sha256, Digest};

pub const EPOCH_GAP_E4_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const FREQUENT_GAPS_E4_THRESHOLD: u32 = 5;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipEpochGapE4Entry {
    pub epoch_end:           u64,
    pub epoch_gaps:          u32,
    pub total_epochs:        u32,
    pub epoch_gaps_rate_pct: u32,
    pub frequent_gaps_e4:    bool,
    pub entry_hash:          [u8; 32],
    pub prev_hash:           [u8; 32],
}

fn compute_hash(
    prev:                &[u8; 32],
    epoch_end:           u64,
    epoch_gaps:          u32,
    total_epochs:        u32,
    epoch_gaps_rate_pct: u32,
    frequent_gaps_e4:    bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(epoch_gaps.to_be_bytes());
    h.update(total_epochs.to_be_bytes());
    h.update(epoch_gaps_rate_pct.to_be_bytes());
    h.update([frequent_gaps_e4 as u8]);
    h.finalize().into()
}

pub struct GossipEpochGapE4Log {
    pub entries: Vec<GossipEpochGapE4Entry>,
}

impl GossipEpochGapE4Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end:    u64,
        epoch_gaps:   u32,
        total_epochs: u32,
    ) -> &GossipEpochGapE4Entry {
        let denom = total_epochs.max(1) as u64;
        let epoch_gaps_rate_pct = ((epoch_gaps as u64).saturating_mul(100) / denom).min(100) as u32;
        let frequent_gaps_e4 = epoch_gaps_rate_pct > FREQUENT_GAPS_E4_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(EPOCH_GAP_E4_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, epoch_gaps, total_epochs, epoch_gaps_rate_pct, frequent_gaps_e4);
        self.entries.push(GossipEpochGapE4Entry {
            epoch_end,
            epoch_gaps,
            total_epochs,
            epoch_gaps_rate_pct,
            frequent_gaps_e4,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn frequent_gaps_e4_count(&self) -> usize {
        self.entries.iter().filter(|e| e.frequent_gaps_e4).count()
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
        let mut prev = EPOCH_GAP_E4_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.epoch_gaps,
                e.total_epochs,
                e.epoch_gaps_rate_pct,
                e.frequent_gaps_e4,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipEpochGapE4Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true() {
        let mut log = GossipEpochGapE4Log::new();
        let e = log.record(1000, 10, 50);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.epoch_gaps, 10);
        assert_eq!(e.total_epochs, 50);
        assert_eq!(e.epoch_gaps_rate_pct, 20);
        assert!(e.frequent_gaps_e4);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        // rate_pct = (5 * 100) / 100 = 5, not > 5, so flag = false
        let mut log = GossipEpochGapE4Log::new();
        let e = log.record(2000, 5, 100);
        assert_eq!(e.epoch_gaps_rate_pct, 5);
        assert!(!e.frequent_gaps_e4);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipEpochGapE4Log::new();
        let e = log.record(3000, 200, 10);
        assert_eq!(e.epoch_gaps_rate_pct, 100);
        assert!(e.frequent_gaps_e4);
    }

    #[test]
    fn total_epochs_zero_no_div_by_zero() {
        let mut log = GossipEpochGapE4Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.epoch_gaps_rate_pct, 0);
        assert!(!e.frequent_gaps_e4);
    }

    #[test]
    fn threshold_constant_value_is_5() {
        assert_eq!(FREQUENT_GAPS_E4_THRESHOLD, 5);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipEpochGapE4Log::new();
        let e = log.record(5000, 3, 20);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_is_genesis() {
        let mut log = GossipEpochGapE4Log::new();
        log.record(6000, 1, 10);
        assert_eq!(log.entries[0].prev_hash, EPOCH_GAP_E4_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipEpochGapE4Log::new();
        log.record(7000, 1, 10);
        log.record(8000, 2, 20);
        assert_eq!(log.entries[1].prev_hash, log.entries[0].entry_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipEpochGapE4Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipEpochGapE4Log::new();
        log.record(9000, 1, 10);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipEpochGapE4Log::new();
        log.record(10000, 1, 10);
        log.record(11000, 2, 20);
        log.record(12000, 3, 30);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipEpochGapE4Log::new();
        log.record(13000, 1, 10);
        log.record(14000, 2, 20);
        log.entries[0].epoch_gaps = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipEpochGapE4Log::new();
        log.record(15000, 1, 10);
        log.record(16000, 2, 20);
        log.entries[1].epoch_gaps = 99;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut log1 = GossipEpochGapE4Log::new();
        let mut log2 = GossipEpochGapE4Log::new();
        let mut log3 = GossipEpochGapE4Log::new();
        let h1 = log1.record(17000, 4, 40).entry_hash;
        let h2 = log2.record(17000, 4, 40).entry_hash;
        let h3 = log3.record(17000, 4, 40).entry_hash;
        assert_eq!(h1, h2);
        assert_eq!(h2, h3);
    }

    #[test]
    fn frequent_gaps_e4_count_mixed_log() {
        let mut log = GossipEpochGapE4Log::new();
        log.record(18000, 1, 100);  // rate=1, flag=false
        log.record(19000, 10, 100); // rate=10, flag=true
        log.record(20000, 5, 100);  // rate=5, flag=false (boundary)
        log.record(21000, 6, 100);  // rate=6, flag=true
        assert_eq!(log.frequent_gaps_e4_count(), 2);
    }

    #[test]
    fn total_epoch_gaps_sums_correctly() {
        let mut log = GossipEpochGapE4Log::new();
        log.record(22000, 7, 100);
        log.record(23000, 3, 100);
        log.record(24000, 10, 100);
        assert_eq!(log.total_epoch_gaps(), 20);
    }

    #[test]
    fn mean_rate_pct_empty_returns_zero() {
        let log = GossipEpochGapE4Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn mean_rate_pct_multi_entry_correct() {
        let mut log = GossipEpochGapE4Log::new();
        log.record(25000, 10, 100); // rate=10
        log.record(26000, 20, 100); // rate=20
        log.record(27000, 30, 100); // rate=30
        // mean = (10+20+30)/3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn default_has_zero_entries() {
        let log = GossipEpochGapE4Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}