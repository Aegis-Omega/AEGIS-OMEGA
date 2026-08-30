//! Gate 466 — Gossip Broadcast Propagation E3 Monitor (T2)
//! Tracks propagation e3 rate per gossip broadcast epoch.
//! SLOW_PROPAGATION_E3_THRESHOLD = 10: rate_pct > 10 → slow_propagation_e3

use sha2::{Sha256, Digest};

pub const PROPAGATION_E3_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const SLOW_PROPAGATION_E3_THRESHOLD: u32 = 10;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPropagationE3Entry {
    pub epoch_end:            u64,
    pub slow_propagations:    u32,
    pub total_msgs:           u32,
    pub slow_rate_pct:        u32,
    pub slow_propagation_e3:  bool,
    pub entry_hash:           [u8; 32],
    pub prev_hash:            [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    slow_propagations: u32,
    total_msgs: u32,
    rate_pct: u32,
    slow_propagation_e3: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(slow_propagations.to_be_bytes());
    h.update(total_msgs.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([slow_propagation_e3 as u8]);
    h.finalize().into()
}

pub struct GossipPropagationE3Log {
    pub entries: Vec<GossipPropagationE3Entry>,
}

impl GossipPropagationE3Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        slow_propagations: u32,
        total_msgs: u32,
    ) -> &GossipPropagationE3Entry {
        let denom = total_msgs.max(1) as u64;
        let slow_rate_pct = ((slow_propagations as u64).saturating_mul(100) / denom).min(100) as u32;
        let slow_propagation_e3 = slow_rate_pct > SLOW_PROPAGATION_E3_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(PROPAGATION_E3_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, slow_propagations, total_msgs, slow_rate_pct, slow_propagation_e3);
        self.entries.push(GossipPropagationE3Entry {
            epoch_end,
            slow_propagations,
            total_msgs,
            slow_rate_pct,
            slow_propagation_e3,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn slow_propagation_e3_count(&self) -> usize {
        self.entries.iter().filter(|e| e.slow_propagation_e3).count()
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
        let mut prev = PROPAGATION_E3_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(&prev, e.epoch_end, e.slow_propagations, e.total_msgs, e.slow_rate_pct, e.slow_propagation_e3);
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPropagationE3Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_flag_true() {
        let mut log = GossipPropagationE3Log::new();
        let e = log.record(1000, 50, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.slow_propagations, 50);
        assert_eq!(e.total_msgs, 100);
        assert_eq!(e.slow_rate_pct, 50);
        assert!(e.slow_propagation_e3);
    }

    #[test]
    fn test_flag_false_when_at_threshold() {
        let mut log = GossipPropagationE3Log::new();
        // rate_pct = (10 * 100) / 100 = 10, which is NOT > 10
        let e = log.record(2000, 10, 100);
        assert_eq!(e.slow_rate_pct, 10);
        assert!(!e.slow_propagation_e3);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipPropagationE3Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.slow_rate_pct, 100);
        assert!(e.slow_propagation_e3);
    }

    #[test]
    fn test_total_msgs_zero_no_div_by_zero() {
        let mut log = GossipPropagationE3Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.slow_rate_pct, 0);
        assert!(!e.slow_propagation_e3);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(SLOW_PROPAGATION_E3_THRESHOLD, 10);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipPropagationE3Log::new();
        let e = log.record(5000, 15, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipPropagationE3Log::new();
        let e = log.record(6000, 5, 50);
        assert_eq!(e.prev_hash, PROPAGATION_E3_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipPropagationE3Log::new();
        log.record(7000, 5, 50);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 10, 80);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipPropagationE3Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_single_entry() {
        let mut log = GossipPropagationE3Log::new();
        log.record(9000, 3, 30);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipPropagationE3Log::new();
        log.record(10000, 5, 50);
        log.record(11000, 20, 100);
        log.record(12000, 1, 10);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipPropagationE3Log::new();
        log.record(13000, 5, 50);
        log.record(14000, 10, 80);
        log.entries[0].slow_propagations = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipPropagationE3Log::new();
        log.record(15000, 5, 50);
        log.record(16000, 10, 80);
        log.record(17000, 20, 100);
        log.entries[1].total_msgs = 999;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipPropagationE3Log::new();
        log1.record(18000, 11, 100);
        let mut log2 = GossipPropagationE3Log::new();
        log2.record(18000, 11, 100);
        let mut log3 = GossipPropagationE3Log::new();
        log3.record(18000, 11, 100);
        assert_eq!(log1.entries[0].entry_hash, log2.entries[0].entry_hash);
        assert_eq!(log2.entries[0].entry_hash, log3.entries[0].entry_hash);
    }

    #[test]
    fn test_slow_propagation_e3_count_mixed() {
        let mut log = GossipPropagationE3Log::new();
        log.record(19000, 5, 100);   // 5% → false
        log.record(20000, 15, 100);  // 15% → true
        log.record(21000, 10, 100);  // 10% → false (not > 10)
        log.record(22000, 11, 100);  // 11% → true
        assert_eq!(log.slow_propagation_e3_count(), 2);
    }

    #[test]
    fn test_total_slow_propagations_sums_correctly() {
        let mut log = GossipPropagationE3Log::new();
        log.record(23000, 7, 100);
        log.record(24000, 13, 100);
        log.record(25000, 20, 100);
        assert_eq!(log.total_slow_propagations(), 40);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipPropagationE3Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry() {
        let mut log = GossipPropagationE3Log::new();
        log.record(26000, 10, 100);  // 10%
        log.record(27000, 30, 100);  // 30%
        log.record(28000, 20, 100);  // 20%
        // mean = (10 + 30 + 20) / 3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn test_default_has_zero_entries() {
        let log = GossipPropagationE3Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}