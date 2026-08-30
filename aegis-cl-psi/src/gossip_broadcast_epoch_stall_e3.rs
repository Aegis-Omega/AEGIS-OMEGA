//! Gate 481 — Gossip Broadcast Epoch Stall E3 Monitor (T2)
//! Tracks epoch stall e3 rate per gossip broadcast epoch.
//! EPOCH_STALLING_E3_THRESHOLD = 5: rate_pct > 5 → epoch_stalling_e3

use sha2::{Sha256, Digest};

pub const EPOCH_STALL_E3_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const EPOCH_STALLING_E3_THRESHOLD: u32 = 5;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipEpochStallE3Entry {
    pub epoch_end:         u64,
    pub stalled_epochs:    u32,
    pub total_epochs:      u32,
    pub stalled_rate_pct:  u32,
    pub epoch_stalling_e3: bool,
    pub entry_hash:        [u8; 32],
    pub prev_hash:         [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    stalled_epochs: u32,
    total_epochs: u32,
    rate_pct: u32,
    epoch_stalling_e3: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(stalled_epochs.to_be_bytes());
    h.update(total_epochs.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([epoch_stalling_e3 as u8]);
    h.finalize().into()
}

pub struct GossipEpochStallE3Log {
    pub entries: Vec<GossipEpochStallE3Entry>,
}

impl GossipEpochStallE3Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        stalled_epochs: u32,
        total_epochs: u32,
    ) -> &GossipEpochStallE3Entry {
        let denom = total_epochs.max(1) as u64;
        let stalled_rate_pct = ((stalled_epochs as u64).saturating_mul(100) / denom).min(100) as u32;
        let epoch_stalling_e3 = stalled_rate_pct > EPOCH_STALLING_E3_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(EPOCH_STALL_E3_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, stalled_epochs, total_epochs, stalled_rate_pct, epoch_stalling_e3);
        self.entries.push(GossipEpochStallE3Entry {
            epoch_end,
            stalled_epochs,
            total_epochs,
            stalled_rate_pct,
            epoch_stalling_e3,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn epoch_stalling_e3_count(&self) -> usize {
        self.entries.iter().filter(|e| e.epoch_stalling_e3).count()
    }

    pub fn total_stalled_epochs(&self) -> u64 {
        self.entries.iter().map(|e| e.stalled_epochs as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.stalled_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = EPOCH_STALL_E3_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(&prev, e.epoch_end, e.stalled_epochs, e.total_epochs, e.stalled_rate_pct, e.epoch_stalling_e3);
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipEpochStallE3Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipEpochStallE3Log::new();
        let e = log.record(1000, 10, 50);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.stalled_epochs, 10);
        assert_eq!(e.total_epochs, 50);
        assert_eq!(e.stalled_rate_pct, 20);
        assert!(e.epoch_stalling_e3);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipEpochStallE3Log::new();
        // rate = (5 * 100) / 100 = 5, which is NOT > 5, so flag = false
        let e = log.record(2000, 5, 100);
        assert_eq!(e.stalled_rate_pct, 5);
        assert!(!e.epoch_stalling_e3);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipEpochStallE3Log::new();
        let e = log.record(3000, 200, 50);
        assert_eq!(e.stalled_rate_pct, 100);
        assert!(e.epoch_stalling_e3);
    }

    #[test]
    fn total_epochs_zero_no_div_by_zero() {
        let mut log = GossipEpochStallE3Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.stalled_rate_pct, 0);
        assert!(!e.epoch_stalling_e3);
    }

    #[test]
    fn threshold_constant_value_is_five() {
        assert_eq!(EPOCH_STALLING_E3_THRESHOLD, 5);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipEpochStallE3Log::new();
        let e = log.record(5000, 10, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipEpochStallE3Log::new();
        let e = log.record(6000, 3, 10);
        assert_eq!(e.prev_hash, EPOCH_STALL_E3_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipEpochStallE3Log::new();
        log.record(7000, 3, 10);
        let first_hash = log.entries[0].entry_hash;
        let e2 = log.record(8000, 5, 20);
        assert_eq!(e2.prev_hash, first_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipEpochStallE3Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipEpochStallE3Log::new();
        log.record(9000, 2, 40);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipEpochStallE3Log::new();
        log.record(10000, 1, 20);
        log.record(11000, 4, 80);
        log.record(12000, 6, 60);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_zero_returns_false_some_zero() {
        let mut log = GossipEpochStallE3Log::new();
        log.record(13000, 2, 40);
        log.record(14000, 3, 60);
        log.entries[0].stalled_epochs = 99;
        let result = log.verify_chain();
        assert_eq!(result, (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_one_returns_false_some_one() {
        let mut log = GossipEpochStallE3Log::new();
        log.record(15000, 2, 40);
        log.record(16000, 3, 60);
        log.entries[1].stalled_epochs = 99;
        let result = log.verify_chain();
        assert_eq!(result, (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut log1 = GossipEpochStallE3Log::new();
        let e1 = log1.record(17000, 7, 70).clone();

        let mut log2 = GossipEpochStallE3Log::new();
        let e2 = log2.record(17000, 7, 70).clone();

        let mut log3 = GossipEpochStallE3Log::new();
        let e3 = log3.record(17000, 7, 70).clone();

        assert_eq!(e1.entry_hash, e2.entry_hash);
        assert_eq!(e2.entry_hash, e3.entry_hash);
    }

    #[test]
    fn epoch_stalling_e3_count_mixed_log() {
        let mut log = GossipEpochStallE3Log::new();
        log.record(18000, 1, 100); // rate=1, false
        log.record(18100, 6, 100); // rate=6, true
        log.record(18200, 5, 100); // rate=5, false
        log.record(18300, 10, 100); // rate=10, true
        assert_eq!(log.epoch_stalling_e3_count(), 2);
    }

    #[test]
    fn total_stalled_epochs_sums_correctly() {
        let mut log = GossipEpochStallE3Log::new();
        log.record(19000, 3, 100);
        log.record(19100, 7, 100);
        log.record(19200, 2, 100);
        assert_eq!(log.total_stalled_epochs(), 12);
    }

    #[test]
    fn mean_rate_pct_empty_returns_zero() {
        let log = GossipEpochStallE3Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn mean_rate_pct_multi_entry_correct() {
        let mut log = GossipEpochStallE3Log::new();
        log.record(20000, 10, 100); // rate=10
        log.record(20100, 20, 100); // rate=20
        log.record(20200, 30, 100); // rate=30
        // mean = (10 + 20 + 30) / 3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn default_produces_zero_entries() {
        let log = GossipEpochStallE3Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}