//! Gate 483 — Gossip Broadcast Partial Delivery E3 Monitor (T2)
//! Tracks partial delivery e3 rate per gossip broadcast epoch.
//! HIGH_PARTIAL_RATE_E3_THRESHOLD = 8: rate_pct > 8 → high_partial_rate_e3

use sha2::{Sha256, Digest};

pub const PARTIAL_DELIVERY_E3_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_PARTIAL_RATE_E3_THRESHOLD: u32 = 8;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPartialDeliveryE3Entry {
    pub epoch_end:                 u64,
    pub partial_deliveries:        u32,
    pub total_delivered:           u32,
    pub partial_deliveries_rate_pct: u32,
    pub high_partial_rate_e3:      bool,
    pub entry_hash:                [u8; 32],
    pub prev_hash:                 [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    partial_deliveries: u32,
    total_delivered: u32,
    rate_pct: u32,
    high_partial_rate_e3: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(partial_deliveries.to_be_bytes());
    h.update(total_delivered.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_partial_rate_e3 as u8]);
    h.finalize().into()
}

pub struct GossipPartialDeliveryE3Log {
    pub entries: Vec<GossipPartialDeliveryE3Entry>,
}

impl GossipPartialDeliveryE3Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        partial_deliveries: u32,
        total_delivered: u32,
    ) -> &GossipPartialDeliveryE3Entry {
        let denom = total_delivered.max(1) as u64;
        let rate_pct = ((partial_deliveries as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_partial_rate_e3 = rate_pct > HIGH_PARTIAL_RATE_E3_THRESHOLD;
        let prev = self
            .entries
            .last()
            .map(|e| e.entry_hash)
            .unwrap_or(PARTIAL_DELIVERY_E3_GENESIS_HASH);
        let entry_hash = compute_hash(
            &prev,
            epoch_end,
            partial_deliveries,
            total_delivered,
            rate_pct,
            high_partial_rate_e3,
        );
        self.entries.push(GossipPartialDeliveryE3Entry {
            epoch_end,
            partial_deliveries,
            total_delivered,
            partial_deliveries_rate_pct: rate_pct,
            high_partial_rate_e3,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_partial_rate_e3_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_partial_rate_e3).count()
    }

    pub fn total_partial_deliveries(&self) -> u64 {
        self.entries.iter().map(|e| e.partial_deliveries as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self
            .entries
            .iter()
            .map(|e| e.partial_deliveries_rate_pct as u64)
            .sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = PARTIAL_DELIVERY_E3_GENESIS_HASH;
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
                e.high_partial_rate_e3,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPartialDeliveryE3Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipPartialDeliveryE3Log::new();
        // partial=10, total=50 => rate=20 => > 8 => true
        let e = log.record(1000, 10, 50);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.partial_deliveries, 10);
        assert_eq!(e.total_delivered, 50);
        assert_eq!(e.partial_deliveries_rate_pct, 20);
        assert!(e.high_partial_rate_e3);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipPartialDeliveryE3Log::new();
        // partial=8, total=100 => rate=8 => NOT > 8 => false
        let e = log.record(2000, 8, 100);
        assert_eq!(e.partial_deliveries_rate_pct, 8);
        assert!(!e.high_partial_rate_e3);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipPartialDeliveryE3Log::new();
        // partial=200, total=50 => (200*100)/50=400, capped at 100
        let e = log.record(3000, 200, 50);
        assert_eq!(e.partial_deliveries_rate_pct, 100);
    }

    #[test]
    fn total_delivered_zero_no_div_by_zero() {
        let mut log = GossipPartialDeliveryE3Log::new();
        // total_delivered=0 => denom=1, rate=(5*100)/1=500 capped at 100
        let e = log.record(4000, 5, 0);
        assert_eq!(e.partial_deliveries_rate_pct, 100);
        assert!(e.high_partial_rate_e3);
    }

    #[test]
    fn threshold_constant_value_is_8() {
        assert_eq!(HIGH_PARTIAL_RATE_E3_THRESHOLD, 8);
    }

    #[test]
    fn entry_hash_is_nonzero() {
        let mut log = GossipPartialDeliveryE3Log::new();
        let e = log.record(5000, 3, 30);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipPartialDeliveryE3Log::new();
        let e = log.record(6000, 1, 10);
        assert_eq!(e.prev_hash, PARTIAL_DELIVERY_E3_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipPartialDeliveryE3Log::new();
        log.record(7000, 1, 10);
        let first_hash = log.entries[0].entry_hash;
        log.record(7001, 2, 20);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipPartialDeliveryE3Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_single_entry_returns_true_none() {
        let mut log = GossipPartialDeliveryE3Log::new();
        log.record(8000, 5, 50);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipPartialDeliveryE3Log::new();
        log.record(9000, 5, 50);
        log.record(9001, 3, 40);
        log.record(9002, 7, 60);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipPartialDeliveryE3Log::new();
        log.record(10000, 5, 50);
        log.record(10001, 3, 40);
        log.entries[0].partial_deliveries = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipPartialDeliveryE3Log::new();
        log.record(11000, 5, 50);
        log.record(11001, 3, 40);
        log.record(11002, 7, 60);
        log.entries[1].partial_deliveries = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn determinism_same_inputs_produce_same_hash() {
        let mut log1 = GossipPartialDeliveryE3Log::new();
        let mut log2 = GossipPartialDeliveryE3Log::new();
        let mut log3 = GossipPartialDeliveryE3Log::new();
        log1.record(12000, 9, 90);
        log2.record(12000, 9, 90);
        log3.record(12000, 9, 90);
        assert_eq!(log1.entries[0].entry_hash, log2.entries[0].entry_hash);
        assert_eq!(log2.entries[0].entry_hash, log3.entries[0].entry_hash);
    }

    #[test]
    fn high_partial_rate_e3_count_mixed_log() {
        let mut log = GossipPartialDeliveryE3Log::new();
        // rate=8 => not high
        log.record(13000, 8, 100);
        // rate=9 => high
        log.record(13001, 9, 100);
        // rate=20 => high
        log.record(13002, 20, 100);
        // rate=5 => not high
        log.record(13003, 5, 100);
        assert_eq!(log.high_partial_rate_e3_count(), 2);
    }

    #[test]
    fn total_partial_deliveries_sums_correctly() {
        let mut log = GossipPartialDeliveryE3Log::new();
        log.record(14000, 10, 100);
        log.record(14001, 20, 200);
        log.record(14002, 30, 300);
        assert_eq!(log.total_partial_deliveries(), 60);
    }

    #[test]
    fn mean_rate_pct_empty_returns_zero() {
        let log = GossipPartialDeliveryE3Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn mean_rate_pct_multi_entry_correct() {
        let mut log = GossipPartialDeliveryE3Log::new();
        // rate = 10
        log.record(15000, 10, 100);
        // rate = 20
        log.record(15001, 20, 100);
        // rate = 30
        log.record(15002, 30, 100);
        // mean = (10+20+30)/3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn default_produces_zero_entries() {
        let log = GossipPartialDeliveryE3Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}