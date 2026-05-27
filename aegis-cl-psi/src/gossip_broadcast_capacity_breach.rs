//! Gate 456 — Gossip Broadcast Capacity Breach Monitor (T2)
//! Tracks capacity breach rate per gossip broadcast epoch.
//! OVER_CAPACITY_THRESHOLD = 5: rate_pct > 5 → over_capacity

use sha2::{Sha256, Digest};

pub const CAPACITY_BREACH_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const OVER_CAPACITY_THRESHOLD: u32 = 5;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipCapacityBreachEntry {
    pub epoch_end:                  u64,
    pub capacity_breaches:          u32,
    pub total_epochs:               u32,
    pub capacity_breaches_rate_pct: u32,
    pub over_capacity:              bool,
    pub entry_hash:                 [u8; 32],
    pub prev_hash:                  [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    capacity_breaches: u32,
    total_epochs: u32,
    rate_pct: u32,
    over_capacity: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(capacity_breaches.to_be_bytes());
    h.update(total_epochs.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([over_capacity as u8]);
    h.finalize().into()
}

pub struct GossipCapacityBreachLog {
    pub entries: Vec<GossipCapacityBreachEntry>,
}

impl GossipCapacityBreachLog {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        capacity_breaches: u32,
        total_epochs: u32,
    ) -> &GossipCapacityBreachEntry {
        let denom = total_epochs.max(1) as u64;
        let rate_pct = ((capacity_breaches as u64).saturating_mul(100) / denom).min(100) as u32;
        let over_capacity = rate_pct > OVER_CAPACITY_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(CAPACITY_BREACH_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, capacity_breaches, total_epochs, rate_pct, over_capacity);
        self.entries.push(GossipCapacityBreachEntry {
            epoch_end,
            capacity_breaches,
            total_epochs,
            capacity_breaches_rate_pct: rate_pct,
            over_capacity,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn over_capacity_count(&self) -> usize {
        self.entries.iter().filter(|e| e.over_capacity).count()
    }

    pub fn total_capacity_breaches(&self) -> u64 {
        self.entries.iter().map(|e| e.capacity_breaches as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.capacity_breaches_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = CAPACITY_BREACH_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.capacity_breaches,
                e.total_epochs,
                e.capacity_breaches_rate_pct,
                e.over_capacity,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipCapacityBreachLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_with_flag_true() {
        let mut log = GossipCapacityBreachLog::new();
        let entry = log.record(1000, 10, 50);
        assert_eq!(entry.epoch_end, 1000);
        assert_eq!(entry.capacity_breaches, 10);
        assert_eq!(entry.total_epochs, 50);
        // rate = (10 * 100) / 50 = 20
        assert_eq!(entry.capacity_breaches_rate_pct, 20);
        // 20 > 5 => over_capacity = true
        assert!(entry.over_capacity);
    }

    #[test]
    fn test_flag_false_when_at_threshold() {
        let mut log = GossipCapacityBreachLog::new();
        // rate = (5 * 100) / 100 = 5, which is NOT > 5, so over_capacity = false
        let entry = log.record(2000, 5, 100);
        assert_eq!(entry.capacity_breaches_rate_pct, 5);
        assert!(!entry.over_capacity);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipCapacityBreachLog::new();
        // breaches > total_epochs would exceed 100 without cap
        let entry = log.record(3000, 200, 100);
        assert_eq!(entry.capacity_breaches_rate_pct, 100);
    }

    #[test]
    fn test_total_epochs_zero_no_div_by_zero() {
        let mut log = GossipCapacityBreachLog::new();
        // total_epochs = 0 => denom = max(0,1) = 1
        let entry = log.record(4000, 0, 0);
        assert_eq!(entry.capacity_breaches_rate_pct, 0);
        assert!(!entry.over_capacity);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(OVER_CAPACITY_THRESHOLD, 5);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipCapacityBreachLog::new();
        let entry = log.record(5000, 3, 10);
        assert_ne!(entry.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_equals_genesis() {
        let mut log = GossipCapacityBreachLog::new();
        let entry = log.record(6000, 2, 20);
        assert_eq!(entry.prev_hash, CAPACITY_BREACH_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipCapacityBreachLog::new();
        log.record(7000, 1, 10);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 2, 10);
        let second_prev = log.entries[1].prev_hash;
        assert_eq!(second_prev, first_hash);
    }

    #[test]
    fn test_verify_chain_empty_returns_true_none() {
        let log = GossipCapacityBreachLog::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_one_entry_valid() {
        let mut log = GossipCapacityBreachLog::new();
        log.record(9000, 3, 30);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries_valid() {
        let mut log = GossipCapacityBreachLog::new();
        log.record(10000, 1, 10);
        log.record(11000, 2, 20);
        log.record(12000, 3, 30);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0_detected() {
        let mut log = GossipCapacityBreachLog::new();
        log.record(13000, 1, 10);
        log.record(14000, 2, 20);
        // Tamper entry 0's capacity_breaches
        log.entries[0].capacity_breaches = 99;
        let result = log.verify_chain();
        assert_eq!(result, (false, Some(0)));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1_detected() {
        let mut log = GossipCapacityBreachLog::new();
        log.record(15000, 1, 10);
        log.record(16000, 2, 20);
        log.record(17000, 3, 30);
        // Tamper entry 1's total_epochs
        log.entries[1].total_epochs = 99;
        let result = log.verify_chain();
        assert_eq!(result, (false, Some(1)));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipCapacityBreachLog::new();
        log1.record(18000, 5, 50);
        let hash1 = log1.entries[0].entry_hash;

        let mut log2 = GossipCapacityBreachLog::new();
        log2.record(18000, 5, 50);
        let hash2 = log2.entries[0].entry_hash;

        let mut log3 = GossipCapacityBreachLog::new();
        log3.record(18000, 5, 50);
        let hash3 = log3.entries[0].entry_hash;

        assert_eq!(hash1, hash2);
        assert_eq!(hash2, hash3);
    }

    #[test]
    fn test_over_capacity_count_mixed_log() {
        let mut log = GossipCapacityBreachLog::new();
        // rate = (1*100)/100 = 1 => not over (1 <= 5)
        log.record(19000, 1, 100);
        // rate = (10*100)/100 = 10 => over (10 > 5)
        log.record(20000, 10, 100);
        // rate = (5*100)/100 = 5 => not over (5 == 5, not > 5)
        log.record(21000, 5, 100);
        // rate = (6*100)/100 = 6 => over (6 > 5)
        log.record(22000, 6, 100);
        assert_eq!(log.over_capacity_count(), 2);
    }

    #[test]
    fn test_total_capacity_breaches_sums_correctly() {
        let mut log = GossipCapacityBreachLog::new();
        log.record(23000, 10, 100);
        log.record(24000, 20, 100);
        log.record(25000, 30, 100);
        assert_eq!(log.total_capacity_breaches(), 60);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipCapacityBreachLog::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry_correct() {
        let mut log = GossipCapacityBreachLog::new();
        // rate = (10*100)/100 = 10
        log.record(26000, 10, 100);
        // rate = (20*100)/100 = 20
        log.record(27000, 20, 100);
        // rate = (30*100)/100 = 30
        log.record(28000, 30, 100);
        // mean = (10 + 20 + 30) / 3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn test_default_has_zero_entries() {
        let log = GossipCapacityBreachLog::default();
        assert_eq!(log.entries.len(), 0);
    }
}