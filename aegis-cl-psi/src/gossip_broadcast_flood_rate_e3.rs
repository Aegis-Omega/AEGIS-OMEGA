//! Gate 489 — Gossip Broadcast Flood Rate E3 Monitor (T2)
//! Tracks flood rate e3 rate per gossip broadcast epoch.
//! HIGH_FLOOD_E3_THRESHOLD = 15: rate_pct > 15 → high_flood_e3

use sha2::{Sha256, Digest};

pub const FLOOD_RATE_E3_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_FLOOD_E3_THRESHOLD: u32 = 15;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipFloodRateE3Entry {
    pub epoch_end:        u64,
    pub flooded_msgs:     u32,
    pub total_sent:       u32,
    pub flooded_rate_pct: u32,
    pub high_flood_e3:    bool,
    pub entry_hash:       [u8; 32],
    pub prev_hash:        [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    flooded_msgs: u32,
    total_sent: u32,
    rate_pct: u32,
    high_flood_e3: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(flooded_msgs.to_be_bytes());
    h.update(total_sent.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_flood_e3 as u8]);
    h.finalize().into()
}

pub struct GossipFloodRateE3Log {
    pub entries: Vec<GossipFloodRateE3Entry>,
}

impl GossipFloodRateE3Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        flooded_msgs: u32,
        total_sent: u32,
    ) -> &GossipFloodRateE3Entry {
        let denom = total_sent.max(1) as u64;
        let flooded_rate_pct = ((flooded_msgs as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_flood_e3 = flooded_rate_pct > HIGH_FLOOD_E3_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(FLOOD_RATE_E3_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, flooded_msgs, total_sent, flooded_rate_pct, high_flood_e3);
        self.entries.push(GossipFloodRateE3Entry {
            epoch_end,
            flooded_msgs,
            total_sent,
            flooded_rate_pct,
            high_flood_e3,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_flood_e3_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_flood_e3).count()
    }

    pub fn total_flooded_msgs(&self) -> u64 {
        self.entries.iter().map(|e| e.flooded_msgs as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.flooded_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = FLOOD_RATE_E3_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.flooded_msgs,
                e.total_sent,
                e.flooded_rate_pct,
                e.high_flood_e3,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipFloodRateE3Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipFloodRateE3Log::new();
        let e = log.record(1000, 20, 50);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.flooded_msgs, 20);
        assert_eq!(e.total_sent, 50);
        // rate = (20 * 100) / 50 = 40
        assert_eq!(e.flooded_rate_pct, 40);
        assert!(e.high_flood_e3);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipFloodRateE3Log::new();
        // rate = (15 * 100) / 100 = 15, which is NOT > 15
        let e = log.record(2000, 15, 100);
        assert_eq!(e.flooded_rate_pct, 15);
        assert!(!e.high_flood_e3);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipFloodRateE3Log::new();
        // flooded_msgs > total_sent → rate would exceed 100
        let e = log.record(3000, 200, 100);
        assert_eq!(e.flooded_rate_pct, 100);
        assert!(e.high_flood_e3);
    }

    #[test]
    fn total_sent_zero_no_div_by_zero() {
        let mut log = GossipFloodRateE3Log::new();
        let e = log.record(4000, 0, 0);
        // (0 * 100) / max(0,1) = 0
        assert_eq!(e.flooded_rate_pct, 0);
        assert!(!e.high_flood_e3);
    }

    #[test]
    fn threshold_constant_value_is_15() {
        assert_eq!(HIGH_FLOOD_E3_THRESHOLD, 15);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipFloodRateE3Log::new();
        let e = log.record(5000, 10, 50);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipFloodRateE3Log::new();
        let e = log.record(6000, 5, 20);
        assert_eq!(e.prev_hash, FLOOD_RATE_E3_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipFloodRateE3Log::new();
        log.record(7000, 5, 20);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 3, 30);
        let second = &log.entries[1];
        assert_eq!(second.prev_hash, first_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipFloodRateE3Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipFloodRateE3Log::new();
        log.record(9000, 5, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipFloodRateE3Log::new();
        log.record(10000, 5, 100);
        log.record(10001, 10, 100);
        log.record(10002, 20, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipFloodRateE3Log::new();
        log.record(11000, 5, 100);
        log.record(11001, 10, 100);
        // Tamper entry 0's flooded_msgs
        log.entries[0].flooded_msgs = 99;
        let result = log.verify_chain();
        assert_eq!(result, (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipFloodRateE3Log::new();
        log.record(12000, 5, 100);
        log.record(12001, 10, 100);
        // Tamper entry 1's flooded_rate_pct
        log.entries[1].flooded_rate_pct = 77;
        let result = log.verify_chain();
        assert_eq!(result, (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_produce_same_hash() {
        let inputs = (13000u64, 8u32, 40u32);
        let mut hashes = Vec::new();
        for _ in 0..3 {
            let mut log = GossipFloodRateE3Log::new();
            let e = log.record(inputs.0, inputs.1, inputs.2);
            hashes.push(e.entry_hash);
        }
        assert_eq!(hashes[0], hashes[1]);
        assert_eq!(hashes[1], hashes[2]);
    }

    #[test]
    fn high_flood_e3_count_mixed_log() {
        let mut log = GossipFloodRateE3Log::new();
        // rate = 5 → not high
        log.record(14000, 5, 100);
        // rate = 20 → high
        log.record(14001, 20, 100);
        // rate = 16 → high
        log.record(14002, 16, 100);
        // rate = 15 → not high (exactly at threshold)
        log.record(14003, 15, 100);
        assert_eq!(log.high_flood_e3_count(), 2);
    }

    #[test]
    fn total_flooded_msgs_sums_correctly() {
        let mut log = GossipFloodRateE3Log::new();
        log.record(15000, 10, 100);
        log.record(15001, 25, 100);
        log.record(15002, 5, 100);
        assert_eq!(log.total_flooded_msgs(), 40);
    }

    #[test]
    fn mean_rate_pct_empty_returns_zero() {
        let log = GossipFloodRateE3Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn mean_rate_pct_multi_entry_correct() {
        let mut log = GossipFloodRateE3Log::new();
        // rates: 10, 20, 30 → mean = 20
        log.record(16000, 10, 100);
        log.record(16001, 20, 100);
        log.record(16002, 30, 100);
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn default_produces_zero_entries() {
        let log = GossipFloodRateE3Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}