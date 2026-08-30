//! Gate 479 — Gossip Broadcast Bandwidth Exceed E3 Monitor (T2)
//! Tracks bandwidth exceed e3 rate per gossip broadcast epoch.
//! BANDWIDTH_EXCEEDED_E3_THRESHOLD = 20: rate_pct > 20 → bandwidth_exceeded_e3

use sha2::{Sha256, Digest};

pub const BANDWIDTH_EXCEED_E3_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const BANDWIDTH_EXCEEDED_E3_THRESHOLD: u32 = 20;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipBandwidthExceedE3Entry {
    pub epoch_end:            u64,
    pub over_limit_epochs:    u32,
    pub total_epochs:         u32,
    pub over_limit_rate_pct:  u32,
    pub bandwidth_exceeded_e3: bool,
    pub entry_hash:           [u8; 32],
    pub prev_hash:            [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    over_limit_epochs: u32,
    total_epochs: u32,
    rate_pct: u32,
    bandwidth_exceeded_e3: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(over_limit_epochs.to_be_bytes());
    h.update(total_epochs.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([bandwidth_exceeded_e3 as u8]);
    h.finalize().into()
}

pub struct GossipBandwidthExceedE3Log {
    pub entries: Vec<GossipBandwidthExceedE3Entry>,
}

impl GossipBandwidthExceedE3Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        over_limit_epochs: u32,
        total_epochs: u32,
    ) -> &GossipBandwidthExceedE3Entry {
        let denom = total_epochs.max(1) as u64;
        let rate_pct = ((over_limit_epochs as u64).saturating_mul(100) / denom).min(100) as u32;
        let bandwidth_exceeded_e3 = rate_pct > BANDWIDTH_EXCEEDED_E3_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(BANDWIDTH_EXCEED_E3_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, over_limit_epochs, total_epochs, rate_pct, bandwidth_exceeded_e3);
        self.entries.push(GossipBandwidthExceedE3Entry {
            epoch_end,
            over_limit_epochs,
            total_epochs,
            over_limit_rate_pct: rate_pct,
            bandwidth_exceeded_e3,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn bandwidth_exceeded_e3_count(&self) -> usize {
        self.entries.iter().filter(|e| e.bandwidth_exceeded_e3).count()
    }

    pub fn total_over_limit_epochs(&self) -> u64 {
        self.entries.iter().map(|e| e.over_limit_epochs as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.over_limit_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = BANDWIDTH_EXCEED_E3_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.over_limit_epochs,
                e.total_epochs,
                e.over_limit_rate_pct,
                e.bandwidth_exceeded_e3,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipBandwidthExceedE3Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipBandwidthExceedE3Log::new();
        let e = log.record(1000, 30, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.over_limit_epochs, 30);
        assert_eq!(e.total_epochs, 100);
        assert_eq!(e.over_limit_rate_pct, 30);
        assert!(e.bandwidth_exceeded_e3);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipBandwidthExceedE3Log::new();
        // rate_pct = (20 * 100) / 100 = 20, not > 20, so false
        let e = log.record(2000, 20, 100);
        assert_eq!(e.over_limit_rate_pct, 20);
        assert!(!e.bandwidth_exceeded_e3);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipBandwidthExceedE3Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.over_limit_rate_pct, 100);
        assert!(e.bandwidth_exceeded_e3);
    }

    #[test]
    fn total_epochs_zero_no_div_by_zero() {
        let mut log = GossipBandwidthExceedE3Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.over_limit_rate_pct, 0);
        assert!(!e.bandwidth_exceeded_e3);
    }

    #[test]
    fn threshold_constant_value_is_20() {
        assert_eq!(BANDWIDTH_EXCEEDED_E3_THRESHOLD, 20);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipBandwidthExceedE3Log::new();
        let e = log.record(5000, 25, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipBandwidthExceedE3Log::new();
        let e = log.record(6000, 10, 50);
        assert_eq!(e.prev_hash, BANDWIDTH_EXCEED_E3_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipBandwidthExceedE3Log::new();
        log.record(7000, 10, 50);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 15, 50);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipBandwidthExceedE3Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_single_entry_returns_true_none() {
        let mut log = GossipBandwidthExceedE3Log::new();
        log.record(9000, 5, 20);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipBandwidthExceedE3Log::new();
        log.record(10000, 5, 20);
        log.record(11000, 10, 40);
        log.record(12000, 15, 60);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipBandwidthExceedE3Log::new();
        log.record(13000, 5, 20);
        log.record(14000, 10, 40);
        log.entries[0].over_limit_epochs = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipBandwidthExceedE3Log::new();
        log.record(15000, 5, 20);
        log.record(16000, 10, 40);
        log.entries[1].total_epochs = 999;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut log1 = GossipBandwidthExceedE3Log::new();
        let mut log2 = GossipBandwidthExceedE3Log::new();
        let mut log3 = GossipBandwidthExceedE3Log::new();
        let e1 = log1.record(17000, 25, 100).entry_hash;
        let e2 = log2.record(17000, 25, 100).entry_hash;
        let e3 = log3.record(17000, 25, 100).entry_hash;
        assert_eq!(e1, e2);
        assert_eq!(e2, e3);
    }

    #[test]
    fn bandwidth_exceeded_e3_count_mixed_log() {
        let mut log = GossipBandwidthExceedE3Log::new();
        log.record(18000, 5, 100);   // 5% → false
        log.record(19000, 25, 100);  // 25% → true
        log.record(20000, 20, 100);  // 20% → false (boundary)
        log.record(21000, 50, 100);  // 50% → true
        assert_eq!(log.bandwidth_exceeded_e3_count(), 2);
    }

    #[test]
    fn total_over_limit_epochs_sums_correctly() {
        let mut log = GossipBandwidthExceedE3Log::new();
        log.record(22000, 10, 100);
        log.record(23000, 20, 100);
        log.record(24000, 30, 100);
        assert_eq!(log.total_over_limit_epochs(), 60u64);
    }

    #[test]
    fn mean_rate_pct_empty_returns_zero() {
        let log = GossipBandwidthExceedE3Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn mean_rate_pct_multi_entry_correct() {
        let mut log = GossipBandwidthExceedE3Log::new();
        log.record(25000, 10, 100); // 10%
        log.record(26000, 30, 100); // 30%
        log.record(27000, 50, 100); // 50%
        // mean = (10 + 30 + 50) / 3 = 30
        assert_eq!(log.mean_rate_pct(), 30);
    }

    #[test]
    fn default_has_zero_entries() {
        let log = GossipBandwidthExceedE3Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}