//! Gate 467 — Gossip Broadcast Collision E3 Monitor (T2)
//! Tracks collision e3 rate per gossip broadcast epoch.
//! HIGH_COLLISION_E3_THRESHOLD = 5: rate_pct > 5 → high_collision_e3

use sha2::{Sha256, Digest};

pub const COLLISION_E3_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_COLLISION_E3_THRESHOLD: u32 = 5;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipCollisionE3Entry {
    pub epoch_end:          u64,
    pub collision_count:    u32,
    pub total_received:     u32,
    pub collision_rate_pct: u32,
    pub high_collision_e3:  bool,
    pub entry_hash:         [u8; 32],
    pub prev_hash:          [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    collision_count: u32,
    total_received: u32,
    collision_rate_pct: u32,
    high_collision_e3: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(collision_count.to_be_bytes());
    h.update(total_received.to_be_bytes());
    h.update(collision_rate_pct.to_be_bytes());
    h.update([high_collision_e3 as u8]);
    h.finalize().into()
}

pub struct GossipCollisionE3Log {
    pub entries: Vec<GossipCollisionE3Entry>,
}

impl GossipCollisionE3Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        collision_count: u32,
        total_received: u32,
    ) -> &GossipCollisionE3Entry {
        let denom = total_received.max(1) as u64;
        let collision_rate_pct = ((collision_count as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_collision_e3 = collision_rate_pct > HIGH_COLLISION_E3_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(COLLISION_E3_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, collision_count, total_received, collision_rate_pct, high_collision_e3);
        self.entries.push(GossipCollisionE3Entry {
            epoch_end,
            collision_count,
            total_received,
            collision_rate_pct,
            high_collision_e3,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_collision_e3_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_collision_e3).count()
    }

    pub fn total_collision_count(&self) -> u64 {
        self.entries.iter().map(|e| e.collision_count as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.collision_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = COLLISION_E3_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(&prev, e.epoch_end, e.collision_count, e.total_received, e.collision_rate_pct, e.high_collision_e3);
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipCollisionE3Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_high_flag_true() {
        let mut log = GossipCollisionE3Log::new();
        let e = log.record(1000, 10, 50);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.collision_count, 10);
        assert_eq!(e.total_received, 50);
        assert_eq!(e.collision_rate_pct, 20);
        assert!(e.high_collision_e3);
    }

    #[test]
    fn test_flag_false_when_exactly_at_threshold() {
        let mut log = GossipCollisionE3Log::new();
        // rate_pct = (5 * 100) / 100 = 5, which is NOT > 5
        let e = log.record(2000, 5, 100);
        assert_eq!(e.collision_rate_pct, 5);
        assert!(!e.high_collision_e3);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipCollisionE3Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.collision_rate_pct, 100);
        assert!(e.high_collision_e3);
    }

    #[test]
    fn test_total_received_zero_no_div_by_zero() {
        let mut log = GossipCollisionE3Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.collision_rate_pct, 0);
        assert!(!e.high_collision_e3);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(HIGH_COLLISION_E3_THRESHOLD, 5);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipCollisionE3Log::new();
        let e = log.record(5000, 10, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipCollisionE3Log::new();
        let e = log.record(6000, 10, 100);
        assert_eq!(e.prev_hash, COLLISION_E3_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipCollisionE3Log::new();
        log.record(7000, 10, 100);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 20, 200);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipCollisionE3Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_one_entry() {
        let mut log = GossipCollisionE3Log::new();
        log.record(9000, 5, 50);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipCollisionE3Log::new();
        log.record(10000, 5, 50);
        log.record(11000, 3, 60);
        log.record(12000, 8, 80);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipCollisionE3Log::new();
        log.record(13000, 5, 50);
        log.record(14000, 3, 60);
        log.entries[0].collision_count = 99;
        let (valid, idx) = log.verify_chain();
        assert!(!valid);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipCollisionE3Log::new();
        log.record(15000, 5, 50);
        log.record(16000, 3, 60);
        log.record(17000, 7, 70);
        log.entries[1].collision_count = 42;
        let (valid, idx) = log.verify_chain();
        assert!(!valid);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipCollisionE3Log::new();
        log1.record(18000, 10, 100);
        let mut log2 = GossipCollisionE3Log::new();
        log2.record(18000, 10, 100);
        let mut log3 = GossipCollisionE3Log::new();
        log3.record(18000, 10, 100);
        assert_eq!(log1.entries[0].entry_hash, log2.entries[0].entry_hash);
        assert_eq!(log2.entries[0].entry_hash, log3.entries[0].entry_hash);
    }

    #[test]
    fn test_high_collision_e3_count_mixed_log() {
        let mut log = GossipCollisionE3Log::new();
        // rate = 0 → flag false
        log.record(19000, 0, 100);
        // rate = 5 → flag false (not > 5)
        log.record(20000, 5, 100);
        // rate = 6 → flag true
        log.record(21000, 6, 100);
        // rate = 50 → flag true
        log.record(22000, 50, 100);
        assert_eq!(log.high_collision_e3_count(), 2);
    }

    #[test]
    fn test_total_collision_count_sums_correctly() {
        let mut log = GossipCollisionE3Log::new();
        log.record(23000, 10, 100);
        log.record(24000, 20, 200);
        log.record(25000, 30, 300);
        assert_eq!(log.total_collision_count(), 60);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipCollisionE3Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry_correct() {
        let mut log = GossipCollisionE3Log::new();
        // rate = 10
        log.record(26000, 10, 100);
        // rate = 20
        log.record(27000, 20, 100);
        // rate = 30
        log.record(28000, 30, 100);
        // mean = (10 + 20 + 30) / 3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn test_default_zero_entries() {
        let log = GossipCollisionE3Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}