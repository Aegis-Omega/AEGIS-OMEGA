//! Gate 526 — Gossip Broadcast Capacity Breach E4 Monitor (T2)
//! Tracks capacity breach events per gossip broadcast epoch.
//! HIGH_CAPACITY_BREACH_E4_THRESHOLD = 5: breach_rate_pct > 5 → high_capacity_breach_e4

use sha2::{Sha256, Digest};

pub const CAPACITY_BREACH_E4_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_CAPACITY_BREACH_E4_THRESHOLD: u32 = 5;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipCapacityBreachE4Entry {
    pub epoch_end:              u64,
    pub breached_slots:         u32,
    pub total_slots:            u32,
    pub breach_rate_pct:        u32,
    pub high_capacity_breach_e4: bool,
    pub entry_hash:             [u8; 32],
    pub prev_hash:              [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    breached_slots: u32,
    total_slots: u32,
    rate_pct: u32,
    high_capacity_breach_e4: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(breached_slots.to_be_bytes());
    h.update(total_slots.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_capacity_breach_e4 as u8]);
    h.finalize().into()
}

pub struct GossipCapacityBreachE4Log {
    pub entries: Vec<GossipCapacityBreachE4Entry>,
}

impl GossipCapacityBreachE4Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        breached_slots: u32,
        total_slots: u32,
    ) -> &GossipCapacityBreachE4Entry {
        let denom = total_slots.max(1) as u64;
        let breach_rate_pct =
            ((breached_slots as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_capacity_breach_e4 = breach_rate_pct > HIGH_CAPACITY_BREACH_E4_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(CAPACITY_BREACH_E4_GENESIS_HASH);
        let entry_hash = compute_hash(
            &prev,
            epoch_end,
            breached_slots,
            total_slots,
            breach_rate_pct,
            high_capacity_breach_e4,
        );
        self.entries.push(GossipCapacityBreachE4Entry {
            epoch_end,
            breached_slots,
            total_slots,
            breach_rate_pct,
            high_capacity_breach_e4,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_capacity_breach_e4_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_capacity_breach_e4).count()
    }

    pub fn total_breached_slots(&self) -> u64 {
        self.entries.iter().map(|e| e.breached_slots as u64).sum()
    }

    pub fn mean_breach_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.breach_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = CAPACITY_BREACH_E4_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.breached_slots,
                e.total_slots,
                e.breach_rate_pct,
                e.high_capacity_breach_e4,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipCapacityBreachE4Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipCapacityBreachE4Log::new();
        let e = log.record(1000, 8, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.breached_slots, 8);
        assert_eq!(e.total_slots, 100);
        assert_eq!(e.breach_rate_pct, 8);
        assert!(e.high_capacity_breach_e4);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipCapacityBreachE4Log::new();
        // rate = (5 * 100) / 100 = 5, not > 5
        let e = log.record(2000, 5, 100);
        assert_eq!(e.breach_rate_pct, 5);
        assert!(!e.high_capacity_breach_e4);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipCapacityBreachE4Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.breach_rate_pct, 100);
        assert!(e.high_capacity_breach_e4);
    }

    #[test]
    fn total_slots_zero_no_div_by_zero() {
        let mut log = GossipCapacityBreachE4Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.breach_rate_pct, 0);
        assert!(!e.high_capacity_breach_e4);
    }

    #[test]
    fn threshold_constant_value_is_5() {
        assert_eq!(HIGH_CAPACITY_BREACH_E4_THRESHOLD, 5);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipCapacityBreachE4Log::new();
        let e = log.record(5000, 7, 80);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipCapacityBreachE4Log::new();
        let e = log.record(6000, 4, 80);
        assert_eq!(e.prev_hash, CAPACITY_BREACH_E4_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipCapacityBreachE4Log::new();
        log.record(7000, 4, 80);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 8, 100);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipCapacityBreachE4Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipCapacityBreachE4Log::new();
        log.record(9000, 6, 80);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipCapacityBreachE4Log::new();
        log.record(10000, 3, 60);
        log.record(11000, 6, 80);
        log.record(12000, 10, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipCapacityBreachE4Log::new();
        log.record(13000, 4, 80);
        log.record(14000, 8, 100);
        log.entries[0].breached_slots = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipCapacityBreachE4Log::new();
        log.record(15000, 4, 80);
        log.record(16000, 8, 100);
        log.entries[1].breached_slots = 99;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut log1 = GossipCapacityBreachE4Log::new();
        let mut log2 = GossipCapacityBreachE4Log::new();
        let mut log3 = GossipCapacityBreachE4Log::new();
        let e1 = log1.record(17000, 7, 90).entry_hash;
        let e2 = log2.record(17000, 7, 90).entry_hash;
        let e3 = log3.record(17000, 7, 90).entry_hash;
        assert_eq!(e1, e2);
        assert_eq!(e2, e3);
    }

    #[test]
    fn high_capacity_breach_e4_count_mixed_log() {
        let mut log = GossipCapacityBreachE4Log::new();
        log.record(18000, 4, 100);  // rate=4,  false
        log.record(19000, 15, 100); // rate=15, true
        log.record(20000, 5, 100);  // rate=5,  false (boundary)
        log.record(21000, 6, 100);  // rate=6,  true
        assert_eq!(log.high_capacity_breach_e4_count(), 2);
    }

    #[test]
    fn total_breached_slots_sums_correctly() {
        let mut log = GossipCapacityBreachE4Log::new();
        log.record(22000, 10, 100);
        log.record(23000, 25, 100);
        log.record(24000, 7, 100);
        assert_eq!(log.total_breached_slots(), 42);
    }

    #[test]
    fn mean_breach_rate_pct_empty_returns_zero() {
        let log = GossipCapacityBreachE4Log::new();
        assert_eq!(log.mean_breach_rate_pct(), 0);
    }

    #[test]
    fn mean_breach_rate_pct_multi_entry_correct() {
        let mut log = GossipCapacityBreachE4Log::new();
        log.record(25000, 10, 100); // rate=10
        log.record(26000, 20, 100); // rate=20
        log.record(27000, 30, 100); // rate=30
        assert_eq!(log.mean_breach_rate_pct(), 20);
    }

    #[test]
    fn default_produces_zero_entries() {
        let log = GossipCapacityBreachE4Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}
