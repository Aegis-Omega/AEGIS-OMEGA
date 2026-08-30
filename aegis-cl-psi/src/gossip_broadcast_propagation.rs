//! Gate 429 — Gossip Broadcast Propagation Monitor (T2)
//! Tracks propagation rate per gossip broadcast epoch.
//! SLOW_PROPAGATION_THRESHOLD = 10: rate_pct > 10 → slow_propagation

use sha2::{Sha256, Digest};

pub const PROPAGATION_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const SLOW_PROPAGATION_THRESHOLD: u32 = 10;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPropagationEntry {
    pub epoch_end:          u64,
    pub slow_propagations:  u32,
    pub total_msgs:         u32,
    pub slow_rate_pct:      u32,
    pub slow_propagation:   bool,
    pub entry_hash:         [u8; 32],
    pub prev_hash:          [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    slow_propagations: u32,
    total_msgs: u32,
    rate_pct: u32,
    slow_propagation: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(slow_propagations.to_be_bytes());
    h.update(total_msgs.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([slow_propagation as u8]);
    h.finalize().into()
}

pub struct GossipPropagationLog {
    pub entries: Vec<GossipPropagationEntry>,
}

impl GossipPropagationLog {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        slow_propagations: u32,
        total_msgs: u32,
    ) -> &GossipPropagationEntry {
        let denom = total_msgs.max(1) as u64;
        let rate_pct = ((slow_propagations as u64).saturating_mul(100) / denom).min(100) as u32;
        let slow_propagation = rate_pct > SLOW_PROPAGATION_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(PROPAGATION_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, slow_propagations, total_msgs, rate_pct, slow_propagation);
        self.entries.push(GossipPropagationEntry {
            epoch_end,
            slow_propagations,
            total_msgs,
            slow_rate_pct: rate_pct,
            slow_propagation,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn slow_propagation_count(&self) -> usize {
        self.entries.iter().filter(|e| e.slow_propagation).count()
    }

    pub fn total_slow_propagations(&self) -> u64 {
        self.entries.iter().map(|e| e.slow_propagations as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.slow_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = PROPAGATION_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.slow_propagations,
                e.total_msgs,
                e.slow_rate_pct,
                e.slow_propagation,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPropagationLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipPropagationLog::new();
        let e = log.record(1000, 20, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.slow_propagations, 20);
        assert_eq!(e.total_msgs, 100);
        assert_eq!(e.slow_rate_pct, 20);
        assert!(e.slow_propagation);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipPropagationLog::new();
        // rate_pct = (10 * 100) / 100 = 10, which is NOT > 10
        let e = log.record(2000, 10, 100);
        assert_eq!(e.slow_rate_pct, 10);
        assert!(!e.slow_propagation);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipPropagationLog::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.slow_rate_pct, 100);
        assert!(e.slow_propagation);
    }

    #[test]
    fn total_msgs_zero_no_div_by_zero() {
        let mut log = GossipPropagationLog::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.slow_rate_pct, 0);
        assert!(!e.slow_propagation);
    }

    #[test]
    fn threshold_constant_value_is_10() {
        assert_eq!(SLOW_PROPAGATION_THRESHOLD, 10);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipPropagationLog::new();
        let e = log.record(5000, 5, 50);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipPropagationLog::new();
        let e = log.record(6000, 3, 30);
        assert_eq!(e.prev_hash, PROPAGATION_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipPropagationLog::new();
        log.record(7000, 3, 30);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 4, 40);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipPropagationLog::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_single_entry_returns_true_none() {
        let mut log = GossipPropagationLog::new();
        log.record(9000, 2, 20);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipPropagationLog::new();
        log.record(10000, 1, 10);
        log.record(11000, 2, 20);
        log.record(12000, 3, 30);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipPropagationLog::new();
        log.record(13000, 5, 50);
        log.record(14000, 6, 60);
        log.entries[0].slow_propagations = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipPropagationLog::new();
        log.record(15000, 5, 50);
        log.record(16000, 6, 60);
        log.entries[1].total_msgs = 999;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut log1 = GossipPropagationLog::new();
        log1.record(17000, 7, 70);
        let mut log2 = GossipPropagationLog::new();
        log2.record(17000, 7, 70);
        let mut log3 = GossipPropagationLog::new();
        log3.record(17000, 7, 70);
        assert_eq!(log1.entries[0].entry_hash, log2.entries[0].entry_hash);
        assert_eq!(log2.entries[0].entry_hash, log3.entries[0].entry_hash);
    }

    #[test]
    fn slow_propagation_count_mixed_log() {
        let mut log = GossipPropagationLog::new();
        log.record(18000, 1, 100);  // 1% — false
        log.record(19000, 15, 100); // 15% — true
        log.record(20000, 10, 100); // 10% — false (exactly at threshold)
        log.record(21000, 50, 100); // 50% — true
        assert_eq!(log.slow_propagation_count(), 2);
    }

    #[test]
    fn total_slow_propagations_sums_correctly() {
        let mut log = GossipPropagationLog::new();
        log.record(22000, 3, 30);
        log.record(23000, 7, 70);
        log.record(24000, 11, 100);
        assert_eq!(log.total_slow_propagations(), 21u64);
    }

    #[test]
    fn mean_rate_pct_empty_returns_zero() {
        let log = GossipPropagationLog::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn mean_rate_pct_multi_entry_correct() {
        let mut log = GossipPropagationLog::new();
        log.record(25000, 20, 100); // 20%
        log.record(26000, 40, 100); // 40%
        log.record(27000, 60, 100); // 60%
        // mean = (20 + 40 + 60) / 3 = 40
        assert_eq!(log.mean_rate_pct(), 40);
    }

    #[test]
    fn default_produces_zero_entries() {
        let log = GossipPropagationLog::default();
        assert_eq!(log.entries.len(), 0);
    }
}