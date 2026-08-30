//! Gate 440 — Gossip Broadcast Broadcast Drop Monitor (T2)
//! Tracks broadcast drop rate per gossip broadcast epoch.
//! HIGH_DROP_RATE_THRESHOLD = 2: rate_pct > 2 → high_drop_rate

use sha2::{Sha256, Digest};

pub const BROADCAST_DROP_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_DROP_RATE_THRESHOLD: u32 = 2;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipBroadcastDropEntry {
    pub epoch_end:                  u64,
    pub dropped_broadcasts:         u32,
    pub total_broadcasts:           u32,
    pub dropped_broadcasts_rate_pct: u32,
    pub high_drop_rate:             bool,
    pub entry_hash:                 [u8; 32],
    pub prev_hash:                  [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    dropped_broadcasts: u32,
    total_broadcasts: u32,
    rate_pct: u32,
    high_drop_rate: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(dropped_broadcasts.to_be_bytes());
    h.update(total_broadcasts.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_drop_rate as u8]);
    h.finalize().into()
}

pub struct GossipBroadcastDropLog {
    pub entries: Vec<GossipBroadcastDropEntry>,
}

impl GossipBroadcastDropLog {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        dropped_broadcasts: u32,
        total_broadcasts: u32,
    ) -> &GossipBroadcastDropEntry {
        let denom = total_broadcasts.max(1) as u64;
        let dropped_broadcasts_rate_pct =
            ((dropped_broadcasts as u64).saturating_mul(100) / denom)
                .min(100) as u32;
        let high_drop_rate = dropped_broadcasts_rate_pct > HIGH_DROP_RATE_THRESHOLD;
        let prev = self
            .entries
            .last()
            .map(|e| e.entry_hash)
            .unwrap_or(BROADCAST_DROP_GENESIS_HASH);
        let entry_hash = compute_hash(
            &prev,
            epoch_end,
            dropped_broadcasts,
            total_broadcasts,
            dropped_broadcasts_rate_pct,
            high_drop_rate,
        );
        self.entries.push(GossipBroadcastDropEntry {
            epoch_end,
            dropped_broadcasts,
            total_broadcasts,
            dropped_broadcasts_rate_pct,
            high_drop_rate,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_drop_rate_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_drop_rate).count()
    }

    pub fn total_dropped_broadcasts(&self) -> u64 {
        self.entries
            .iter()
            .map(|e| e.dropped_broadcasts as u64)
            .fold(0u64, |acc, v| acc.saturating_add(v))
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self
            .entries
            .iter()
            .map(|e| e.dropped_broadcasts_rate_pct as u64)
            .fold(0u64, |acc, v| acc.saturating_add(v));
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = BROADCAST_DROP_GENESIS_HASH;
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
                e.high_drop_rate,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipBroadcastDropLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_flag_true() {
        let mut log = GossipBroadcastDropLog::new();
        // 10 dropped out of 100 = 10% > 2 → high_drop_rate = true
        let e = log.record(1000, 10, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.dropped_broadcasts, 10);
        assert_eq!(e.total_broadcasts, 100);
        assert_eq!(e.dropped_broadcasts_rate_pct, 10);
        assert!(e.high_drop_rate);
    }

    #[test]
    fn test_flag_false_when_exactly_at_threshold() {
        let mut log = GossipBroadcastDropLog::new();
        // 2 dropped out of 100 = 2% == 2, NOT > 2 → high_drop_rate = false
        let e = log.record(2000, 2, 100);
        assert_eq!(e.dropped_broadcasts_rate_pct, 2);
        assert!(!e.high_drop_rate);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipBroadcastDropLog::new();
        // 200 dropped out of 100 total → would be 200%, capped at 100
        let e = log.record(3000, 200, 100);
        assert_eq!(e.dropped_broadcasts_rate_pct, 100);
        assert!(e.high_drop_rate);
    }

    #[test]
    fn test_total_broadcasts_zero_no_div_by_zero() {
        let mut log = GossipBroadcastDropLog::new();
        // total_broadcasts = 0, max(0,1) = 1, so dropped * 100 / 1
        let e = log.record(4000, 0, 0);
        assert_eq!(e.dropped_broadcasts_rate_pct, 0);
        assert!(!e.high_drop_rate);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(HIGH_DROP_RATE_THRESHOLD, 2);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipBroadcastDropLog::new();
        let e = log.record(5000, 5, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipBroadcastDropLog::new();
        let e = log.record(6000, 3, 100);
        assert_eq!(e.prev_hash, BROADCAST_DROP_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipBroadcastDropLog::new();
        log.record(7000, 1, 100);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 2, 100);
        let second = &log.entries[1];
        assert_eq!(second.prev_hash, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipBroadcastDropLog::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_one_entry() {
        let mut log = GossipBroadcastDropLog::new();
        log.record(9000, 1, 50);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipBroadcastDropLog::new();
        log.record(10000, 1, 50);
        log.record(11000, 2, 50);
        log.record(12000, 3, 50);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipBroadcastDropLog::new();
        log.record(13000, 1, 50);
        log.record(14000, 2, 50);
        // Tamper with entry 0's dropped_broadcasts
        log.entries[0].dropped_broadcasts = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipBroadcastDropLog::new();
        log.record(15000, 1, 50);
        log.record(16000, 2, 50);
        log.record(17000, 3, 50);
        // Tamper with entry 1's total_broadcasts
        log.entries[1].total_broadcasts = 999;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipBroadcastDropLog::new();
        let mut log2 = GossipBroadcastDropLog::new();
        let mut log3 = GossipBroadcastDropLog::new();
        log1.record(18000, 5, 100);
        log2.record(18000, 5, 100);
        log3.record(18000, 5, 100);
        assert_eq!(log1.entries[0].entry_hash, log2.entries[0].entry_hash);
        assert_eq!(log2.entries[0].entry_hash, log3.entries[0].entry_hash);
    }

    #[test]
    fn test_high_drop_rate_count_mixed_log() {
        let mut log = GossipBroadcastDropLog::new();
        // rate = 2% → flag false
        log.record(20000, 2, 100);
        // rate = 3% → flag true
        log.record(21000, 3, 100);
        // rate = 0% → flag false
        log.record(22000, 0, 100);
        // rate = 50% → flag true
        log.record(23000, 50, 100);
        assert_eq!(log.high_drop_rate_count(), 2);
    }

    #[test]
    fn test_total_dropped_broadcasts_sums_correctly() {
        let mut log = GossipBroadcastDropLog::new();
        log.record(24000, 10, 200);
        log.record(25000, 20, 200);
        log.record(26000, 30, 200);
        assert_eq!(log.total_dropped_broadcasts(), 60);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipBroadcastDropLog::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry_correct() {
        let mut log = GossipBroadcastDropLog::new();
        // rate = 10%
        log.record(27000, 10, 100);
        // rate = 20%
        log.record(28000, 20, 100);
        // rate = 30%
        log.record(29000, 30, 100);
        // mean = (10 + 20 + 30) / 3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn test_default_has_zero_entries() {
        let log = GossipBroadcastDropLog::default();
        assert_eq!(log.entries.len(), 0);
    }
}