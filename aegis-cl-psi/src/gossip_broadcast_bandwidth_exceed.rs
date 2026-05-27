//! Gate 444 — Gossip Broadcast Bandwidth Exceed Monitor (T2)
//! Tracks bandwidth exceed rate per gossip broadcast epoch.
//! BANDWIDTH_EXCEEDED_THRESHOLD = 20: rate_pct > 20 → bandwidth_exceeded

use sha2::{Sha256, Digest};

pub const BANDWIDTH_EXCEED_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const BANDWIDTH_EXCEEDED_THRESHOLD: u32 = 20;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipBandwidthExceedEntry {
    pub epoch_end:          u64,
    pub over_limit_epochs:  u32,
    pub total_epochs:       u32,
    pub over_limit_rate_pct: u32,
    pub bandwidth_exceeded: bool,
    pub entry_hash:         [u8; 32],
    pub prev_hash:          [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    over_limit_epochs: u32,
    total_epochs: u32,
    rate_pct: u32,
    bandwidth_exceeded: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(over_limit_epochs.to_be_bytes());
    h.update(total_epochs.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([bandwidth_exceeded as u8]);
    h.finalize().into()
}

pub struct GossipBandwidthExceedLog {
    pub entries: Vec<GossipBandwidthExceedEntry>,
}

impl GossipBandwidthExceedLog {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        over_limit_epochs: u32,
        total_epochs: u32,
    ) -> &GossipBandwidthExceedEntry {
        let denom = total_epochs.max(1) as u64;
        let over_limit_rate_pct = ((over_limit_epochs as u64).saturating_mul(100) / denom)
            .min(100) as u32;
        let bandwidth_exceeded = over_limit_rate_pct > BANDWIDTH_EXCEEDED_THRESHOLD;
        let prev = self
            .entries
            .last()
            .map(|e| e.entry_hash)
            .unwrap_or(BANDWIDTH_EXCEED_GENESIS_HASH);
        let entry_hash = compute_hash(
            &prev,
            epoch_end,
            over_limit_epochs,
            total_epochs,
            over_limit_rate_pct,
            bandwidth_exceeded,
        );
        self.entries.push(GossipBandwidthExceedEntry {
            epoch_end,
            over_limit_epochs,
            total_epochs,
            over_limit_rate_pct,
            bandwidth_exceeded,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn bandwidth_exceeded_count(&self) -> usize {
        self.entries.iter().filter(|e| e.bandwidth_exceeded).count()
    }

    pub fn total_over_limit_epochs(&self) -> u64 {
        self.entries
            .iter()
            .map(|e| e.over_limit_epochs as u64)
            .fold(0u64, |acc, x| acc.saturating_add(x))
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self
            .entries
            .iter()
            .map(|e| e.over_limit_rate_pct as u64)
            .fold(0u64, |acc, x| acc.saturating_add(x));
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = BANDWIDTH_EXCEED_GENESIS_HASH;
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
                e.bandwidth_exceeded,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipBandwidthExceedLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipBandwidthExceedLog::new();
        let e = log.record(1000, 30, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.over_limit_epochs, 30);
        assert_eq!(e.total_epochs, 100);
        assert_eq!(e.over_limit_rate_pct, 30);
        assert!(e.bandwidth_exceeded);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipBandwidthExceedLog::new();
        // rate_pct = (20 * 100) / 100 = 20, which is NOT > 20
        let e = log.record(2000, 20, 100);
        assert_eq!(e.over_limit_rate_pct, 20);
        assert!(!e.bandwidth_exceeded);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipBandwidthExceedLog::new();
        // over_limit_epochs > total_epochs
        let e = log.record(3000, 200, 100);
        assert_eq!(e.over_limit_rate_pct, 100);
        assert!(e.bandwidth_exceeded);
    }

    #[test]
    fn total_epochs_zero_no_div_by_zero() {
        let mut log = GossipBandwidthExceedLog::new();
        let e = log.record(4000, 5, 0);
        // denom = max(0,1) = 1, rate = 500 capped at 100
        assert_eq!(e.over_limit_rate_pct, 100);
        assert!(e.bandwidth_exceeded);
    }

    #[test]
    fn threshold_constant_value_is_20() {
        assert_eq!(BANDWIDTH_EXCEEDED_THRESHOLD, 20);
    }

    #[test]
    fn entry_hash_is_non_zero() {
        let mut log = GossipBandwidthExceedLog::new();
        let e = log.record(5000, 10, 50);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipBandwidthExceedLog::new();
        let e = log.record(6000, 5, 50);
        assert_eq!(e.prev_hash, BANDWIDTH_EXCEED_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipBandwidthExceedLog::new();
        log.record(7000, 5, 50);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 10, 50);
        let second = &log.entries[1];
        assert_eq!(second.prev_hash, first_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipBandwidthExceedLog::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_single_entry_returns_true_none() {
        let mut log = GossipBandwidthExceedLog::new();
        log.record(9000, 5, 25);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipBandwidthExceedLog::new();
        log.record(10000, 5, 25);
        log.record(11000, 10, 50);
        log.record(12000, 15, 75);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipBandwidthExceedLog::new();
        log.record(13000, 5, 25);
        log.record(14000, 10, 50);
        // Tamper entry 0's entry_hash
        log.entries[0].entry_hash = [0xABu8; 32];
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipBandwidthExceedLog::new();
        log.record(15000, 5, 25);
        log.record(16000, 10, 50);
        log.record(17000, 15, 75);
        // Tamper entry 1's over_limit_epochs so hash is wrong
        log.entries[1].over_limit_epochs = 99;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut log1 = GossipBandwidthExceedLog::new();
        let mut log2 = GossipBandwidthExceedLog::new();
        let mut log3 = GossipBandwidthExceedLog::new();
        log1.record(18000, 7, 35);
        log2.record(18000, 7, 35);
        log3.record(18000, 7, 35);
        assert_eq!(log1.entries[0].entry_hash, log2.entries[0].entry_hash);
        assert_eq!(log2.entries[0].entry_hash, log3.entries[0].entry_hash);
    }

    #[test]
    fn bandwidth_exceeded_count_mixed_log() {
        let mut log = GossipBandwidthExceedLog::new();
        log.record(19000, 5, 100);   // rate=5, not exceeded
        log.record(20000, 25, 100);  // rate=25, exceeded
        log.record(21000, 15, 100);  // rate=15, not exceeded
        log.record(22000, 50, 100);  // rate=50, exceeded
        assert_eq!(log.bandwidth_exceeded_count(), 2);
    }

    #[test]
    fn total_over_limit_epochs_sums_correctly() {
        let mut log = GossipBandwidthExceedLog::new();
        log.record(23000, 10, 100);
        log.record(24000, 20, 100);
        log.record(25000, 30, 100);
        assert_eq!(log.total_over_limit_epochs(), 60u64);
    }

    #[test]
    fn mean_rate_pct_empty_returns_zero() {
        let log = GossipBandwidthExceedLog::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn mean_rate_pct_multi_entry_correct() {
        let mut log = GossipBandwidthExceedLog::new();
        log.record(26000, 10, 100); // rate=10
        log.record(27000, 20, 100); // rate=20
        log.record(28000, 30, 100); // rate=30
        // mean = (10+20+30)/3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn default_produces_zero_entries() {
        let log = GossipBandwidthExceedLog::default();
        assert_eq!(log.entries.len(), 0);
    }
}