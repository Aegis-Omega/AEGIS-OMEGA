//! Gate 448 — Gossip Broadcast Partial Delivery Monitor (T2)
//! Tracks partial delivery rate per gossip broadcast epoch.
//! HIGH_PARTIAL_RATE_THRESHOLD = 8: rate_pct > 8 → high_partial_rate

use sha2::{Sha256, Digest};

pub const PARTIAL_DELIVERY_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_PARTIAL_RATE_THRESHOLD: u32 = 8;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPartialDeliveryEntry {
    pub epoch_end:                u64,
    pub partial_deliveries:       u32,
    pub total_delivered:          u32,
    pub partial_deliveries_rate_pct: u32,
    pub high_partial_rate:        bool,
    pub entry_hash:               [u8; 32],
    pub prev_hash:                [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    partial_deliveries: u32,
    total_delivered: u32,
    rate_pct: u32,
    high_partial_rate: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(partial_deliveries.to_be_bytes());
    h.update(total_delivered.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_partial_rate as u8]);
    h.finalize().into()
}

pub struct GossipPartialDeliveryLog {
    pub entries: Vec<GossipPartialDeliveryEntry>,
}

impl GossipPartialDeliveryLog {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        partial_deliveries: u32,
        total_delivered: u32,
    ) -> &GossipPartialDeliveryEntry {
        let denom = total_delivered.max(1) as u64;
        let rate_pct = ((partial_deliveries as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_partial_rate = rate_pct > HIGH_PARTIAL_RATE_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(PARTIAL_DELIVERY_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, partial_deliveries, total_delivered, rate_pct, high_partial_rate);
        self.entries.push(GossipPartialDeliveryEntry {
            epoch_end,
            partial_deliveries,
            total_delivered,
            partial_deliveries_rate_pct: rate_pct,
            high_partial_rate,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_partial_rate_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_partial_rate).count()
    }

    pub fn total_partial_deliveries(&self) -> u64 {
        self.entries.iter().map(|e| e.partial_deliveries as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.partial_deliveries_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = PARTIAL_DELIVERY_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.partial_deliveries,
                e.total_delivered,
                e.partial_deliveries_rate_pct,
                e.high_partial_rate,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPartialDeliveryLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipPartialDeliveryLog::new();
        let e = log.record(1000, 10, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.partial_deliveries, 10);
        assert_eq!(e.total_delivered, 100);
        assert_eq!(e.partial_deliveries_rate_pct, 10);
        assert!(e.high_partial_rate);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipPartialDeliveryLog::new();
        // rate_pct = (8 * 100) / 100 = 8, which is NOT > 8, so flag = false
        let e = log.record(2000, 8, 100);
        assert_eq!(e.partial_deliveries_rate_pct, 8);
        assert!(!e.high_partial_rate);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipPartialDeliveryLog::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.partial_deliveries_rate_pct, 100);
        assert!(e.high_partial_rate);
    }

    #[test]
    fn total_delivered_zero_no_div_by_zero() {
        let mut log = GossipPartialDeliveryLog::new();
        let e = log.record(4000, 5, 0);
        // denom = max(0,1) = 1, rate = 5*100/1 = 500 capped to 100
        assert_eq!(e.partial_deliveries_rate_pct, 100);
        assert!(e.high_partial_rate);
    }

    #[test]
    fn threshold_constant_value_is_8() {
        assert_eq!(HIGH_PARTIAL_RATE_THRESHOLD, 8);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipPartialDeliveryLog::new();
        let e = log.record(5000, 1, 10);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipPartialDeliveryLog::new();
        let e = log.record(6000, 1, 10);
        assert_eq!(e.prev_hash, PARTIAL_DELIVERY_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipPartialDeliveryLog::new();
        log.record(7000, 1, 10);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 2, 20);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipPartialDeliveryLog::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipPartialDeliveryLog::new();
        log.record(9000, 1, 10);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipPartialDeliveryLog::new();
        log.record(10000, 1, 10);
        log.record(11000, 2, 20);
        log.record(12000, 3, 30);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipPartialDeliveryLog::new();
        log.record(13000, 1, 10);
        log.record(14000, 2, 20);
        log.entries[0].partial_deliveries = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipPartialDeliveryLog::new();
        log.record(15000, 1, 10);
        log.record(16000, 2, 20);
        log.record(17000, 3, 30);
        log.entries[1].partial_deliveries = 99;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut log1 = GossipPartialDeliveryLog::new();
        let h1 = log1.record(18000, 5, 50).entry_hash;

        let mut log2 = GossipPartialDeliveryLog::new();
        let h2 = log2.record(18000, 5, 50).entry_hash;

        let mut log3 = GossipPartialDeliveryLog::new();
        let h3 = log3.record(18000, 5, 50).entry_hash;

        assert_eq!(h1, h2);
        assert_eq!(h2, h3);
    }

    #[test]
    fn high_partial_rate_count_mixed_log() {
        let mut log = GossipPartialDeliveryLog::new();
        log.record(19000, 1, 100);  // 1% -> false
        log.record(20000, 9, 100);  // 9% -> true
        log.record(21000, 8, 100);  // 8% -> false (not > 8)
        log.record(22000, 50, 100); // 50% -> true
        assert_eq!(log.high_partial_rate_count(), 2);
    }

    #[test]
    fn total_partial_deliveries_sums_correctly() {
        let mut log = GossipPartialDeliveryLog::new();
        log.record(23000, 10, 100);
        log.record(24000, 20, 200);
        log.record(25000, 30, 300);
        assert_eq!(log.total_partial_deliveries(), 60);
    }

    #[test]
    fn mean_rate_pct_empty_returns_zero() {
        let log = GossipPartialDeliveryLog::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn mean_rate_pct_multi_entry_correct() {
        let mut log = GossipPartialDeliveryLog::new();
        log.record(26000, 10, 100); // 10%
        log.record(27000, 20, 100); // 20%
        log.record(28000, 30, 100); // 30%
        // mean = (10 + 20 + 30) / 3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn default_produces_zero_entries() {
        let log = GossipPartialDeliveryLog::default();
        assert_eq!(log.entries.len(), 0);
    }
}