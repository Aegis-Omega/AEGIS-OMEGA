//! Gate 502 — Gossip Broadcast Collision E4 Monitor (T2)
//! Tracks collision e4 rate per gossip broadcast epoch.
//! HIGH_COLLISION_E4_THRESHOLD = 5: rate_pct > 5 → high_collision_e4

use sha2::{Sha256, Digest};

pub const COLLISION_E4_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_COLLISION_E4_THRESHOLD: u32 = 5;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipCollisionE4Entry {
    pub epoch_end:          u64,
    pub collision_count:    u32,
    pub total_received:     u32,
    pub collision_rate_pct: u32,
    pub high_collision_e4:  bool,
    pub entry_hash:         [u8; 32],
    pub prev_hash:          [u8; 32],
}

fn compute_hash(
    prev:               &[u8; 32],
    epoch_end:          u64,
    collision_count:    u32,
    total_received:     u32,
    rate_pct:           u32,
    high_collision_e4:  bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(collision_count.to_be_bytes());
    h.update(total_received.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_collision_e4 as u8]);
    h.finalize().into()
}

pub struct GossipCollisionE4Log {
    pub entries: Vec<GossipCollisionE4Entry>,
}

impl GossipCollisionE4Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end:       u64,
        collision_count: u32,
        total_received:  u32,
    ) -> &GossipCollisionE4Entry {
        let denom = total_received.max(1) as u64;
        let collision_rate_pct =
            ((collision_count as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_collision_e4 = collision_rate_pct > HIGH_COLLISION_E4_THRESHOLD;
        let prev = self
            .entries
            .last()
            .map(|e| e.entry_hash)
            .unwrap_or(COLLISION_E4_GENESIS_HASH);
        let entry_hash = compute_hash(
            &prev,
            epoch_end,
            collision_count,
            total_received,
            collision_rate_pct,
            high_collision_e4,
        );
        self.entries.push(GossipCollisionE4Entry {
            epoch_end,
            collision_count,
            total_received,
            collision_rate_pct,
            high_collision_e4,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_collision_e4_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_collision_e4).count()
    }

    pub fn total_collision_count(&self) -> u64 {
        self.entries
            .iter()
            .map(|e| e.collision_count as u64)
            .fold(0u64, |acc, v| acc.saturating_add(v))
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self
            .entries
            .iter()
            .map(|e| e.collision_rate_pct as u64)
            .fold(0u64, |acc, v| acc.saturating_add(v));
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = COLLISION_E4_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.collision_count,
                e.total_received,
                e.collision_rate_pct,
                e.high_collision_e4,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipCollisionE4Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // Test 1: record fields correct (rate computed, flag=true when > threshold)
    #[test]
    fn test_record_fields_correct_high_flag() {
        let mut log = GossipCollisionE4Log::new();
        let e = log.record(1000, 10, 50);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.collision_count, 10);
        assert_eq!(e.total_received, 50);
        // rate = (10 * 100) / 50 = 20
        assert_eq!(e.collision_rate_pct, 20);
        // 20 > 5 → true
        assert!(e.high_collision_e4);
    }

    // Test 2: flag=false when exactly at threshold (rate_pct == 5, not > 5)
    #[test]
    fn test_flag_false_at_threshold_boundary() {
        let mut log = GossipCollisionE4Log::new();
        // rate = (5 * 100) / 100 = 5, 5 > 5 is false
        let e = log.record(2000, 5, 100);
        assert_eq!(e.collision_rate_pct, 5);
        assert!(!e.high_collision_e4);
    }

    // Test 3: rate_pct capped at 100
    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipCollisionE4Log::new();
        // collision_count > total_received would exceed 100
        let e = log.record(3000, 200, 100);
        assert_eq!(e.collision_rate_pct, 100);
    }

    // Test 4: total_received=0 no div-by-zero
    #[test]
    fn test_total_received_zero_no_div_by_zero() {
        let mut log = GossipCollisionE4Log::new();
        let e = log.record(4000, 0, 0);
        // (0 * 100) / max(0,1) = 0
        assert_eq!(e.collision_rate_pct, 0);
        assert!(!e.high_collision_e4);
    }

    // Test 5: threshold constant value == 5
    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(HIGH_COLLISION_E4_THRESHOLD, 5u32);
    }

    // Test 6: entry_hash non-zero
    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipCollisionE4Log::new();
        let e = log.record(5000, 3, 30);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    // Test 7: first prev_hash == genesis
    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipCollisionE4Log::new();
        let e = log.record(6000, 1, 10);
        assert_eq!(e.prev_hash, COLLISION_E4_GENESIS_HASH);
    }

    // Test 8: second prev_hash == first entry_hash
    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipCollisionE4Log::new();
        log.record(7000, 1, 10);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 2, 20);
        let second_prev = log.entries[1].prev_hash;
        assert_eq!(second_prev, first_hash);
    }

    // Test 9: verify_chain empty → (true, None)
    #[test]
    fn test_verify_chain_empty() {
        let log = GossipCollisionE4Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    // Test 10: verify_chain 1-entry → (true, None)
    #[test]
    fn test_verify_chain_single_entry() {
        let mut log = GossipCollisionE4Log::new();
        log.record(9000, 2, 40);
        assert_eq!(log.verify_chain(), (true, None));
    }

    // Test 11: verify_chain 3-entry → (true, None)
    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipCollisionE4Log::new();
        log.record(10000, 1, 20);
        log.record(11000, 3, 60);
        log.record(12000, 5, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    // Test 12: verify_chain tamper entry 0 → (false, Some(0))
    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipCollisionE4Log::new();
        log.record(13000, 1, 10);
        log.record(14000, 2, 20);
        // Tamper entry 0's entry_hash
        log.entries[0].entry_hash = [0xABu8; 32];
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }

    // Test 13: verify_chain tamper entry 1 → (false, Some(1))
    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipCollisionE4Log::new();
        log.record(15000, 1, 10);
        log.record(16000, 2, 20);
        log.record(17000, 3, 30);
        // Tamper entry 1's collision_count
        log.entries[1].collision_count = 99;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    // Test 14: determinism: same inputs × 3 → same hash
    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipCollisionE4Log::new();
        log1.record(18000, 4, 80);
        let mut log2 = GossipCollisionE4Log::new();
        log2.record(18000, 4, 80);
        let mut log3 = GossipCollisionE4Log::new();
        log3.record(18000, 4, 80);
        assert_eq!(log1.entries[0].entry_hash, log2.entries[0].entry_hash);
        assert_eq!(log2.entries[0].entry_hash, log3.entries[0].entry_hash);
    }

    // Test 15: high_collision_e4_count() mixed log
    #[test]
    fn test_high_collision_e4_count_mixed() {
        let mut log = GossipCollisionE4Log::new();
        // rate = 0, flag=false
        log.record(19000, 0, 100);
        // rate = 5, flag=false (boundary)
        log.record(20000, 5, 100);
        // rate = 6, flag=true
        log.record(21000, 6, 100);
        // rate = 50, flag=true
        log.record(22000, 50, 100);
        assert_eq!(log.high_collision_e4_count(), 2);
    }

    // Test 16: total_collision_count() sums correctly
    #[test]
    fn test_total_collision_count_sums_correctly() {
        let mut log = GossipCollisionE4Log::new();
        log.record(23000, 10, 200);
        log.record(24000, 20, 200);
        log.record(25000, 30, 200);
        assert_eq!(log.total_collision_count(), 60u64);
    }

    // Test 17: mean_rate_pct() empty → 0
    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipCollisionE4Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    // Test 18: mean_rate_pct() multi-entry correct
    #[test]
    fn test_mean_rate_pct_multi_entry() {
        let mut log = GossipCollisionE4Log::new();
        // rate = (10*100)/100 = 10
        log.record(26000, 10, 100);
        // rate = (20*100)/100 = 20
        log.record(27000, 20, 100);
        // rate = (30*100)/100 = 30
        log.record(28000, 30, 100);
        // mean = (10 + 20 + 30) / 3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    // Test 19: Default → 0 entries
    #[test]
    fn test_default_has_zero_entries() {
        let log = GossipCollisionE4Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}