//! Gate 529 — Gossip Broadcast Latency Spike E5 Monitor (T2)
//! Tracks latency spike rate per gossip broadcast epoch.
//! HIGH_LATENCY_SPIKE_E5_THRESHOLD = 13: spike_rate_pct > 13 → high_latency_spike_e5

use sha2::{Sha256, Digest};

pub const LATENCY_SPIKE_E5_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_LATENCY_SPIKE_E5_THRESHOLD: u32 = 13;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipLatencySpikeE5Entry {
    pub epoch_end:           u64,
    pub spiked_msgs:         u32,
    pub total_msgs:          u32,
    pub spike_rate_pct:      u32,
    pub high_latency_spike_e5: bool,
    pub entry_hash:          [u8; 32],
    pub prev_hash:           [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    spiked_msgs: u32,
    total_msgs: u32,
    rate_pct: u32,
    high_latency_spike_e5: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(spiked_msgs.to_be_bytes());
    h.update(total_msgs.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_latency_spike_e5 as u8]);
    h.finalize().into()
}

pub struct GossipLatencySpikeE5Log {
    pub entries: Vec<GossipLatencySpikeE5Entry>,
}

impl GossipLatencySpikeE5Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        spiked_msgs: u32,
        total_msgs: u32,
    ) -> &GossipLatencySpikeE5Entry {
        let denom = total_msgs.max(1) as u64;
        let spike_rate_pct =
            ((spiked_msgs as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_latency_spike_e5 = spike_rate_pct > HIGH_LATENCY_SPIKE_E5_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(LATENCY_SPIKE_E5_GENESIS_HASH);
        let entry_hash = compute_hash(
            &prev,
            epoch_end,
            spiked_msgs,
            total_msgs,
            spike_rate_pct,
            high_latency_spike_e5,
        );
        self.entries.push(GossipLatencySpikeE5Entry {
            epoch_end,
            spiked_msgs,
            total_msgs,
            spike_rate_pct,
            high_latency_spike_e5,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_latency_spike_e5_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_latency_spike_e5).count()
    }

    pub fn total_spiked_msgs(&self) -> u64 {
        self.entries.iter().map(|e| e.spiked_msgs as u64).sum()
    }

    pub fn mean_spike_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.spike_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = LATENCY_SPIKE_E5_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.spiked_msgs,
                e.total_msgs,
                e.spike_rate_pct,
                e.high_latency_spike_e5,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipLatencySpikeE5Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipLatencySpikeE5Log::new();
        let e = log.record(1000, 18, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.spiked_msgs, 18);
        assert_eq!(e.total_msgs, 100);
        assert_eq!(e.spike_rate_pct, 18);
        assert!(e.high_latency_spike_e5);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipLatencySpikeE5Log::new();
        // rate = (13 * 100) / 100 = 13, not > 13
        let e = log.record(2000, 13, 100);
        assert_eq!(e.spike_rate_pct, 13);
        assert!(!e.high_latency_spike_e5);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipLatencySpikeE5Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.spike_rate_pct, 100);
        assert!(e.high_latency_spike_e5);
    }

    #[test]
    fn total_msgs_zero_no_div_by_zero() {
        let mut log = GossipLatencySpikeE5Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.spike_rate_pct, 0);
        assert!(!e.high_latency_spike_e5);
    }

    #[test]
    fn threshold_constant_value_is_13() {
        assert_eq!(HIGH_LATENCY_SPIKE_E5_THRESHOLD, 13);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipLatencySpikeE5Log::new();
        let e = log.record(5000, 16, 80);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipLatencySpikeE5Log::new();
        let e = log.record(6000, 8, 80);
        assert_eq!(e.prev_hash, LATENCY_SPIKE_E5_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipLatencySpikeE5Log::new();
        log.record(7000, 8, 80);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 18, 100);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipLatencySpikeE5Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipLatencySpikeE5Log::new();
        log.record(9000, 14, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipLatencySpikeE5Log::new();
        log.record(10000, 8, 60);
        log.record(11000, 14, 80);
        log.record(12000, 18, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipLatencySpikeE5Log::new();
        log.record(13000, 8, 80);
        log.record(14000, 18, 100);
        log.entries[0].spiked_msgs = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipLatencySpikeE5Log::new();
        log.record(15000, 8, 80);
        log.record(16000, 18, 100);
        log.entries[1].spiked_msgs = 99;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut log1 = GossipLatencySpikeE5Log::new();
        let mut log2 = GossipLatencySpikeE5Log::new();
        let mut log3 = GossipLatencySpikeE5Log::new();
        let e1 = log1.record(17000, 16, 90).entry_hash;
        let e2 = log2.record(17000, 16, 90).entry_hash;
        let e3 = log3.record(17000, 16, 90).entry_hash;
        assert_eq!(e1, e2);
        assert_eq!(e2, e3);
    }

    #[test]
    fn high_latency_spike_e5_count_mixed_log() {
        let mut log = GossipLatencySpikeE5Log::new();
        log.record(18000, 10, 100); // rate=10, false
        log.record(19000, 20, 100); // rate=20, true
        log.record(20000, 13, 100); // rate=13, false (boundary)
        log.record(21000, 14, 100); // rate=14, true
        assert_eq!(log.high_latency_spike_e5_count(), 2);
    }

    #[test]
    fn total_spiked_msgs_sums_correctly() {
        let mut log = GossipLatencySpikeE5Log::new();
        log.record(22000, 10, 100);
        log.record(23000, 25, 100);
        log.record(24000, 7, 100);
        assert_eq!(log.total_spiked_msgs(), 42);
    }

    #[test]
    fn mean_spike_rate_pct_empty_returns_zero() {
        let log = GossipLatencySpikeE5Log::new();
        assert_eq!(log.mean_spike_rate_pct(), 0);
    }

    #[test]
    fn mean_spike_rate_pct_multi_entry_correct() {
        let mut log = GossipLatencySpikeE5Log::new();
        log.record(25000, 10, 100); // rate=10
        log.record(26000, 20, 100); // rate=20
        log.record(27000, 30, 100); // rate=30
        assert_eq!(log.mean_spike_rate_pct(), 20);
    }

    #[test]
    fn default_produces_zero_entries() {
        let log = GossipLatencySpikeE5Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}
