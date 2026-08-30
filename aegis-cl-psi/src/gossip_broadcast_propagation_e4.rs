//! Gate 501 — Gossip Broadcast Propagation E4 Monitor (T2)
//! Tracks propagation e4 rate per gossip broadcast epoch.
//! SLOW_PROPAGATION_E4_THRESHOLD = 10: rate_pct > 10 → slow_propagation_e4

use sha2::{Sha256, Digest};

pub const PROPAGATION_E4_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const SLOW_PROPAGATION_E4_THRESHOLD: u32 = 10;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPropagationE4Entry {
    pub epoch_end:           u64,
    pub slow_propagations:   u32,
    pub total_msgs:          u32,
    pub slow_rate_pct:       u32,
    pub slow_propagation_e4: bool,
    pub entry_hash:          [u8; 32],
    pub prev_hash:           [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    slow_propagations: u32,
    total_msgs: u32,
    rate_pct: u32,
    slow_propagation_e4: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(slow_propagations.to_be_bytes());
    h.update(total_msgs.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([slow_propagation_e4 as u8]);
    h.finalize().into()
}

pub struct GossipPropagationE4Log {
    pub entries: Vec<GossipPropagationE4Entry>,
}

impl GossipPropagationE4Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        slow_propagations: u32,
        total_msgs: u32,
    ) -> &GossipPropagationE4Entry {
        let denom = total_msgs.max(1) as u64;
        let slow_rate_pct = ((slow_propagations as u64).saturating_mul(100) / denom)
            .min(100) as u32;
        let slow_propagation_e4 = slow_rate_pct > SLOW_PROPAGATION_E4_THRESHOLD;
        let prev = self
            .entries
            .last()
            .map(|e| e.entry_hash)
            .unwrap_or(PROPAGATION_E4_GENESIS_HASH);
        let entry_hash = compute_hash(
            &prev,
            epoch_end,
            slow_propagations,
            total_msgs,
            slow_rate_pct,
            slow_propagation_e4,
        );
        self.entries.push(GossipPropagationE4Entry {
            epoch_end,
            slow_propagations,
            total_msgs,
            slow_rate_pct,
            slow_propagation_e4,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn slow_propagation_e4_count(&self) -> usize {
        self.entries.iter().filter(|e| e.slow_propagation_e4).count()
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
        let mut prev = PROPAGATION_E4_GENESIS_HASH;
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
                e.slow_propagation_e4,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPropagationE4Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_flag_true() {
        let mut log = GossipPropagationE4Log::new();
        let e = log.record(1000, 50, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.slow_propagations, 50);
        assert_eq!(e.total_msgs, 100);
        assert_eq!(e.slow_rate_pct, 50);
        assert!(e.slow_propagation_e4);
    }

    #[test]
    fn test_flag_false_when_exactly_at_threshold() {
        let mut log = GossipPropagationE4Log::new();
        // rate = (10 * 100) / 100 = 10, which is NOT > 10
        let e = log.record(2000, 10, 100);
        assert_eq!(e.slow_rate_pct, 10);
        assert!(!e.slow_propagation_e4);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipPropagationE4Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.slow_rate_pct, 100);
        assert!(e.slow_propagation_e4);
    }

    #[test]
    fn test_total_msgs_zero_no_div_by_zero() {
        let mut log = GossipPropagationE4Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.slow_rate_pct, 0);
        assert!(!e.slow_propagation_e4);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(SLOW_PROPAGATION_E4_THRESHOLD, 10);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipPropagationE4Log::new();
        let e = log.record(5000, 5, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_equals_genesis() {
        let mut log = GossipPropagationE4Log::new();
        let e = log.record(6000, 5, 100);
        assert_eq!(e.prev_hash, PROPAGATION_E4_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipPropagationE4Log::new();
        let e1_hash = log.record(7000, 5, 100).entry_hash;
        let e2 = log.record(8000, 10, 100);
        assert_eq!(e2.prev_hash, e1_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipPropagationE4Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_one_entry() {
        let mut log = GossipPropagationE4Log::new();
        log.record(9000, 5, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipPropagationE4Log::new();
        log.record(10000, 5, 100);
        log.record(11000, 15, 100);
        log.record(12000, 0, 50);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipPropagationE4Log::new();
        log.record(13000, 5, 100);
        log.record(14000, 15, 100);
        log.entries[0].slow_propagations = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipPropagationE4Log::new();
        log.record(15000, 5, 100);
        log.record(16000, 15, 100);
        log.entries[1].slow_propagations = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let make_hash = || {
            let mut log = GossipPropagationE4Log::new();
            log.record(17000, 25, 100).entry_hash
        };
        let h1 = make_hash();
        let h2 = make_hash();
        let h3 = make_hash();
        assert_eq!(h1, h2);
        assert_eq!(h2, h3);
    }

    #[test]
    fn test_slow_propagation_e4_count_mixed_log() {
        let mut log = GossipPropagationE4Log::new();
        log.record(18000, 5, 100);   // rate=5, flag=false
        log.record(19000, 15, 100);  // rate=15, flag=true
        log.record(20000, 10, 100);  // rate=10, flag=false
        log.record(21000, 11, 100);  // rate=11, flag=true
        assert_eq!(log.slow_propagation_e4_count(), 2);
    }

    #[test]
    fn test_total_slow_propagations_sums_correctly() {
        let mut log = GossipPropagationE4Log::new();
        log.record(22000, 10, 200);
        log.record(23000, 30, 200);
        log.record(24000, 20, 200);
        assert_eq!(log.total_slow_propagations(), 60);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipPropagationE4Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry() {
        let mut log = GossipPropagationE4Log::new();
        log.record(25000, 20, 100); // rate=20
        log.record(26000, 40, 100); // rate=40
        log.record(27000, 60, 100); // rate=60
        // mean = (20 + 40 + 60) / 3 = 40
        assert_eq!(log.mean_rate_pct(), 40);
    }

    #[test]
    fn test_default_zero_entries() {
        let log = GossipPropagationE4Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}