//! Gate 475 — Gossip Broadcast Broadcast Drop E3 Monitor (T2)
//! Tracks broadcast drop e3 rate per gossip broadcast epoch.
//! HIGH_DROP_RATE_E3_THRESHOLD = 2: rate_pct > 2 → high_drop_rate_e3

use sha2::{Sha256, Digest};

pub const BROADCAST_DROP_E3_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_DROP_RATE_E3_THRESHOLD: u32 = 2;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipBroadcastDropE3Entry {
    pub epoch_end:                  u64,
    pub dropped_broadcasts:         u32,
    pub total_broadcasts:           u32,
    pub dropped_broadcasts_rate_pct: u32,
    pub high_drop_rate_e3:          bool,
    pub entry_hash:                 [u8; 32],
    pub prev_hash:                  [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    dropped_broadcasts: u32,
    total_broadcasts: u32,
    rate_pct: u32,
    high_drop_rate_e3: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(dropped_broadcasts.to_be_bytes());
    h.update(total_broadcasts.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_drop_rate_e3 as u8]);
    h.finalize().into()
}

pub struct GossipBroadcastDropE3Log {
    pub entries: Vec<GossipBroadcastDropE3Entry>,
}

impl GossipBroadcastDropE3Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        dropped_broadcasts: u32,
        total_broadcasts: u32,
    ) -> &GossipBroadcastDropE3Entry {
        let denom = total_broadcasts.max(1) as u64;
        let dropped_broadcasts_rate_pct =
            ((dropped_broadcasts as u64).saturating_mul(100) / denom)
                .min(100) as u32;
        let high_drop_rate_e3 = dropped_broadcasts_rate_pct > HIGH_DROP_RATE_E3_THRESHOLD;
        let prev = self
            .entries
            .last()
            .map(|e| e.entry_hash)
            .unwrap_or(BROADCAST_DROP_E3_GENESIS_HASH);
        let entry_hash = compute_hash(
            &prev,
            epoch_end,
            dropped_broadcasts,
            total_broadcasts,
            dropped_broadcasts_rate_pct,
            high_drop_rate_e3,
        );
        self.entries.push(GossipBroadcastDropE3Entry {
            epoch_end,
            dropped_broadcasts,
            total_broadcasts,
            dropped_broadcasts_rate_pct,
            high_drop_rate_e3,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_drop_rate_e3_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_drop_rate_e3).count()
    }

    pub fn total_dropped_broadcasts(&self) -> u64 {
        self.entries.iter().map(|e| e.dropped_broadcasts as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self
            .entries
            .iter()
            .map(|e| e.dropped_broadcasts_rate_pct as u64)
            .sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = BROADCAST_DROP_E3_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.dropped_broadcasts,
                e.total_broadcasts,
                e.dropped_broadcasts_rate_pct,
                e.high_drop_rate_e3,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipBroadcastDropE3Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_flag_true() {
        let mut log = GossipBroadcastDropE3Log::new();
        let e = log.record(1000, 10, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.dropped_broadcasts, 10);
        assert_eq!(e.total_broadcasts, 100);
        assert_eq!(e.dropped_broadcasts_rate_pct, 10);
        assert!(e.high_drop_rate_e3);
    }

    #[test]
    fn test_flag_false_when_at_threshold() {
        let mut log = GossipBroadcastDropE3Log::new();
        // rate_pct == 2, threshold is > 2, so flag should be false
        let e = log.record(2000, 2, 100);
        assert_eq!(e.dropped_broadcasts_rate_pct, 2);
        assert!(!e.high_drop_rate_e3);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipBroadcastDropE3Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.dropped_broadcasts_rate_pct, 100);
        assert!(e.high_drop_rate_e3);
    }

    #[test]
    fn test_total_broadcasts_zero_no_div_by_zero() {
        let mut log = GossipBroadcastDropE3Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.dropped_broadcasts_rate_pct, 0);
        assert!(!e.high_drop_rate_e3);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(HIGH_DROP_RATE_E3_THRESHOLD, 2);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipBroadcastDropE3Log::new();
        let e = log.record(5000, 5, 50);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipBroadcastDropE3Log::new();
        let e = log.record(6000, 3, 100);
        assert_eq!(e.prev_hash, BROADCAST_DROP_E3_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipBroadcastDropE3Log::new();
        log.record(7000, 3, 100);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 4, 100);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipBroadcastDropE3Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_one_entry() {
        let mut log = GossipBroadcastDropE3Log::new();
        log.record(9000, 1, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipBroadcastDropE3Log::new();
        log.record(10000, 1, 100);
        log.record(11000, 2, 100);
        log.record(12000, 3, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipBroadcastDropE3Log::new();
        log.record(13000, 1, 100);
        log.record(14000, 2, 100);
        log.entries[0].dropped_broadcasts = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipBroadcastDropE3Log::new();
        log.record(15000, 1, 100);
        log.record(16000, 2, 100);
        log.entries[1].dropped_broadcasts = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipBroadcastDropE3Log::new();
        let e1 = log1.record(17000, 5, 100).entry_hash;
        let mut log2 = GossipBroadcastDropE3Log::new();
        let e2 = log2.record(17000, 5, 100).entry_hash;
        let mut log3 = GossipBroadcastDropE3Log::new();
        let e3 = log3.record(17000, 5, 100).entry_hash;
        assert_eq!(e1, e2);
        assert_eq!(e2, e3);
    }

    #[test]
    fn test_high_drop_rate_e3_count_mixed() {
        let mut log = GossipBroadcastDropE3Log::new();
        log.record(18000, 1, 100); // rate=1, flag=false
        log.record(19000, 3, 100); // rate=3, flag=true
        log.record(20000, 2, 100); // rate=2, flag=false
        log.record(21000, 5, 100); // rate=5, flag=true
        assert_eq!(log.high_drop_rate_e3_count(), 2);
    }

    #[test]
    fn test_total_dropped_broadcasts_sums_correctly() {
        let mut log = GossipBroadcastDropE3Log::new();
        log.record(22000, 10, 100);
        log.record(23000, 20, 100);
        log.record(24000, 30, 100);
        assert_eq!(log.total_dropped_broadcasts(), 60);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipBroadcastDropE3Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry() {
        let mut log = GossipBroadcastDropE3Log::new();
        log.record(25000, 10, 100); // rate=10
        log.record(26000, 20, 100); // rate=20
        log.record(27000, 30, 100); // rate=30
        // mean = (10 + 20 + 30) / 3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn test_default_has_zero_entries() {
        let log = GossipBroadcastDropE3Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}