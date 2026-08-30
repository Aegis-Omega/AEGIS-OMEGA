//! Gate 491 — Gossip Broadcast Capacity Breach E3 Monitor (T2)
//! Tracks capacity breach e3 rate per gossip broadcast epoch.
//! OVER_CAPACITY_E3_THRESHOLD = 5: rate_pct > 5 → over_capacity_e3

use sha2::{Sha256, Digest};

pub const CAPACITY_BREACH_E3_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const OVER_CAPACITY_E3_THRESHOLD: u32 = 5;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipCapacityBreachE3Entry {
    pub epoch_end:                  u64,
    pub capacity_breaches:          u32,
    pub total_epochs:               u32,
    pub capacity_breaches_rate_pct: u32,
    pub over_capacity_e3:           bool,
    pub entry_hash:                 [u8; 32],
    pub prev_hash:                  [u8; 32],
}

fn compute_hash(
    prev:                      &[u8; 32],
    epoch_end:                 u64,
    capacity_breaches:         u32,
    total_epochs:              u32,
    capacity_breaches_rate_pct: u32,
    over_capacity_e3:          bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(capacity_breaches.to_be_bytes());
    h.update(total_epochs.to_be_bytes());
    h.update(capacity_breaches_rate_pct.to_be_bytes());
    h.update([over_capacity_e3 as u8]);
    h.finalize().into()
}

pub struct GossipCapacityBreachE3Log {
    pub entries: Vec<GossipCapacityBreachE3Entry>,
}

impl GossipCapacityBreachE3Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end:         u64,
        capacity_breaches: u32,
        total_epochs:      u32,
    ) -> &GossipCapacityBreachE3Entry {
        let denom = total_epochs.max(1) as u64;
        let rate_pct = ((capacity_breaches as u64).saturating_mul(100) / denom).min(100) as u32;
        let over_capacity_e3 = rate_pct > OVER_CAPACITY_E3_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(CAPACITY_BREACH_E3_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, capacity_breaches, total_epochs, rate_pct, over_capacity_e3);
        self.entries.push(GossipCapacityBreachE3Entry {
            epoch_end,
            capacity_breaches,
            total_epochs,
            capacity_breaches_rate_pct: rate_pct,
            over_capacity_e3,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn over_capacity_e3_count(&self) -> usize {
        self.entries.iter().filter(|e| e.over_capacity_e3).count()
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
        let mut prev = CAPACITY_BREACH_E3_GENESIS_HASH;
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
                e.over_capacity_e3,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipCapacityBreachE3Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipCapacityBreachE3Log::new();
        let e = log.record(1000, 10, 50);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.capacity_breaches, 10);
        assert_eq!(e.total_epochs, 50);
        // rate = 10*100/50 = 20
        assert_eq!(e.capacity_breaches_rate_pct, 20);
        assert!(e.over_capacity_e3);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipCapacityBreachE3Log::new();
        // rate = 5*100/100 = 5, which is NOT > 5
        let e = log.record(2000, 5, 100);
        assert_eq!(e.capacity_breaches_rate_pct, 5);
        assert!(!e.over_capacity_e3);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipCapacityBreachE3Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.capacity_breaches_rate_pct, 100);
        assert!(e.over_capacity_e3);
    }

    #[test]
    fn total_epochs_zero_no_div_by_zero() {
        let mut log = GossipCapacityBreachE3Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.capacity_breaches_rate_pct, 0);
        assert!(!e.over_capacity_e3);
    }

    #[test]
    fn threshold_constant_value_is_5() {
        assert_eq!(OVER_CAPACITY_E3_THRESHOLD, 5);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipCapacityBreachE3Log::new();
        let e = log.record(5000, 10, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipCapacityBreachE3Log::new();
        let e = log.record(6000, 1, 10);
        assert_eq!(e.prev_hash, CAPACITY_BREACH_E3_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipCapacityBreachE3Log::new();
        let e1_hash = log.record(7000, 1, 10).entry_hash;
        let e2 = log.record(8000, 2, 20);
        assert_eq!(e2.prev_hash, e1_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipCapacityBreachE3Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipCapacityBreachE3Log::new();
        log.record(9000, 3, 30);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipCapacityBreachE3Log::new();
        log.record(10000, 1, 10);
        log.record(11000, 2, 20);
        log.record(12000, 3, 30);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipCapacityBreachE3Log::new();
        log.record(13000, 1, 10);
        log.record(14000, 2, 20);
        log.entries[0].capacity_breaches = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipCapacityBreachE3Log::new();
        log.record(15000, 1, 10);
        log.record(16000, 2, 20);
        log.record(17000, 3, 30);
        log.entries[1].capacity_breaches = 99;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut log1 = GossipCapacityBreachE3Log::new();
        let h1 = log1.record(18000, 5, 50).entry_hash;
        let mut log2 = GossipCapacityBreachE3Log::new();
        let h2 = log2.record(18000, 5, 50).entry_hash;
        let mut log3 = GossipCapacityBreachE3Log::new();
        let h3 = log3.record(18000, 5, 50).entry_hash;
        assert_eq!(h1, h2);
        assert_eq!(h2, h3);
    }

    #[test]
    fn over_capacity_e3_count_mixed_log() {
        let mut log = GossipCapacityBreachE3Log::new();
        // rate = 0 → false
        log.record(19000, 0, 100);
        // rate = 20 → true
        log.record(20000, 20, 100);
        // rate = 5 → false (exactly at threshold)
        log.record(21000, 5, 100);
        // rate = 6 → true
        log.record(22000, 6, 100);
        assert_eq!(log.over_capacity_e3_count(), 2);
    }

    #[test]
    fn total_capacity_breaches_sums_correctly() {
        let mut log = GossipCapacityBreachE3Log::new();
        log.record(23000, 10, 100);
        log.record(24000, 20, 100);
        log.record(25000, 30, 100);
        assert_eq!(log.total_capacity_breaches(), 60);
    }

    #[test]
    fn mean_rate_pct_empty_returns_zero() {
        let log = GossipCapacityBreachE3Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn mean_rate_pct_multi_entry_correct() {
        let mut log = GossipCapacityBreachE3Log::new();
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
    fn default_yields_zero_entries() {
        let log = GossipCapacityBreachE3Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}