//! Gate 504 — Gossip Broadcast Jitter E4 Monitor (T2)
//! Tracks jitter e4 rate per gossip broadcast epoch.
//! HIGH_JITTER_E4_THRESHOLD = 15: rate_pct > 15 → high_jitter_e4

use sha2::{Sha256, Digest};

pub const JITTER_E4_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_JITTER_E4_THRESHOLD: u32 = 15;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipJitterE4Entry {
    pub epoch_end:           u64,
    pub high_jitter_epochs:  u32,
    pub total_epochs:        u32,
    pub high_jitter_rate_pct: u32,
    pub high_jitter_e4:      bool,
    pub entry_hash:          [u8; 32],
    pub prev_hash:           [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    high_jitter_epochs: u32,
    total_epochs: u32,
    rate_pct: u32,
    high_jitter_e4: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(high_jitter_epochs.to_be_bytes());
    h.update(total_epochs.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_jitter_e4 as u8]);
    h.finalize().into()
}

pub struct GossipJitterE4Log {
    pub entries: Vec<GossipJitterE4Entry>,
}

impl GossipJitterE4Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        high_jitter_epochs: u32,
        total_epochs: u32,
    ) -> &GossipJitterE4Entry {
        let denom = total_epochs.max(1) as u64;
        let rate_pct = ((high_jitter_epochs as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_jitter_e4 = rate_pct > HIGH_JITTER_E4_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(JITTER_E4_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, high_jitter_epochs, total_epochs, rate_pct, high_jitter_e4);
        self.entries.push(GossipJitterE4Entry {
            epoch_end,
            high_jitter_epochs,
            total_epochs,
            high_jitter_rate_pct: rate_pct,
            high_jitter_e4,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_jitter_e4_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_jitter_e4).count()
    }

    pub fn total_high_jitter_epochs(&self) -> u64 {
        self.entries.iter().map(|e| e.high_jitter_epochs as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.high_jitter_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = JITTER_E4_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.high_jitter_epochs,
                e.total_epochs,
                e.high_jitter_rate_pct,
                e.high_jitter_e4,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipJitterE4Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true() {
        let mut log = GossipJitterE4Log::new();
        let e = log.record(1000, 20, 50);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.high_jitter_epochs, 20);
        assert_eq!(e.total_epochs, 50);
        assert_eq!(e.high_jitter_rate_pct, 40);
        assert!(e.high_jitter_e4);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipJitterE4Log::new();
        // rate = (15 * 100) / 100 = 15, which is NOT > 15
        let e = log.record(2000, 15, 100);
        assert_eq!(e.high_jitter_rate_pct, 15);
        assert!(!e.high_jitter_e4);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipJitterE4Log::new();
        let e = log.record(3000, 200, 50);
        assert_eq!(e.high_jitter_rate_pct, 100);
        assert!(e.high_jitter_e4);
    }

    #[test]
    fn total_epochs_zero_no_div_by_zero() {
        let mut log = GossipJitterE4Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.high_jitter_rate_pct, 0);
        assert!(!e.high_jitter_e4);
    }

    #[test]
    fn threshold_constant_value() {
        assert_eq!(HIGH_JITTER_E4_THRESHOLD, 15);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipJitterE4Log::new();
        let e = log.record(5000, 10, 50);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipJitterE4Log::new();
        let e = log.record(6000, 5, 20);
        assert_eq!(e.prev_hash, JITTER_E4_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipJitterE4Log::new();
        log.record(7000, 5, 20);
        let first_hash = log.entries[0].entry_hash;
        let e2 = log.record(8000, 3, 10);
        assert_eq!(e2.prev_hash, first_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipJitterE4Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipJitterE4Log::new();
        log.record(9000, 5, 30);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipJitterE4Log::new();
        log.record(10000, 5, 30);
        log.record(11000, 8, 40);
        log.record(12000, 2, 10);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipJitterE4Log::new();
        log.record(13000, 5, 30);
        log.record(14000, 8, 40);
        log.entries[0].high_jitter_epochs = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipJitterE4Log::new();
        log.record(15000, 5, 30);
        log.record(16000, 8, 40);
        log.entries[1].total_epochs = 999;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut log1 = GossipJitterE4Log::new();
        let mut log2 = GossipJitterE4Log::new();
        let mut log3 = GossipJitterE4Log::new();
        let e1 = log1.record(17000, 7, 35);
        let e2 = log2.record(17000, 7, 35);
        let e3 = log3.record(17000, 7, 35);
        assert_eq!(e1.entry_hash, e2.entry_hash);
        assert_eq!(e2.entry_hash, e3.entry_hash);
    }

    #[test]
    fn high_jitter_e4_count_mixed_log() {
        let mut log = GossipJitterE4Log::new();
        log.record(18000, 5, 100);  // 5% → false
        log.record(18001, 20, 100); // 20% → true
        log.record(18002, 16, 100); // 16% → true
        log.record(18003, 15, 100); // 15% → false
        assert_eq!(log.high_jitter_e4_count(), 2);
    }

    #[test]
    fn total_high_jitter_epochs_sums_correctly() {
        let mut log = GossipJitterE4Log::new();
        log.record(19000, 10, 100);
        log.record(19001, 25, 100);
        log.record(19002, 5, 100);
        assert_eq!(log.total_high_jitter_epochs(), 40u64);
    }

    #[test]
    fn mean_rate_pct_empty_returns_zero() {
        let log = GossipJitterE4Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn mean_rate_pct_multi_entry_correct() {
        let mut log = GossipJitterE4Log::new();
        log.record(20000, 10, 100); // 10%
        log.record(20001, 20, 100); // 20%
        log.record(20002, 30, 100); // 30%
        // mean = (10 + 20 + 30) / 3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn default_produces_zero_entries() {
        let log = GossipJitterE4Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}