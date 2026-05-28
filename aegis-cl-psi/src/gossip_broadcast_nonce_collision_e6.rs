//! Gate 576 — Gossip Broadcast Nonce Collision E6 Monitor (T2)
//! Tracks collided nonces per gossip broadcast epoch.
//! HIGH_NONCE_COLLISION_E6_THRESHOLD = 5: collision_rate_pct > 5 → high_nonce_collision_e6

use sha2::{Sha256, Digest};

pub const NONCE_COLLISION_E6_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_NONCE_COLLISION_E6_THRESHOLD: u32 = 5;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipNonceCollisionE6Entry {
    pub epoch_end:             u64,
    pub collided_nonces:       u32,
    pub total_nonces:          u32,
    pub collision_rate_pct:    u32,
    pub high_nonce_collision_e6: bool,
    pub entry_hash:            [u8; 32],
    pub prev_hash:             [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    collided_nonces: u32,
    total_nonces: u32,
    rate_pct: u32,
    high_nonce_collision_e6: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(collided_nonces.to_be_bytes());
    h.update(total_nonces.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_nonce_collision_e6 as u8]);
    h.finalize().into()
}

pub struct GossipNonceCollisionE6Log {
    pub entries: Vec<GossipNonceCollisionE6Entry>,
}

impl GossipNonceCollisionE6Log {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn record(
        &mut self,
        epoch_end: u64,
        collided_nonces: u32,
        total_nonces: u32,
    ) -> &GossipNonceCollisionE6Entry {
        let denom = total_nonces.max(1) as u64;
        let collision_rate_pct =
            ((collided_nonces as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_nonce_collision_e6 = collision_rate_pct > HIGH_NONCE_COLLISION_E6_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(NONCE_COLLISION_E6_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, collided_nonces, total_nonces, collision_rate_pct, high_nonce_collision_e6);
        self.entries.push(GossipNonceCollisionE6Entry {
            epoch_end, collided_nonces, total_nonces, collision_rate_pct,
            high_nonce_collision_e6, entry_hash, prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_nonce_collision_e6_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_nonce_collision_e6).count()
    }
    pub fn total_collided_nonces(&self) -> u64 {
        self.entries.iter().map(|e| e.collided_nonces as u64).sum()
    }
    pub fn mean_collision_rate_pct(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        let sum: u64 = self.entries.iter().map(|e| e.collision_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = NONCE_COLLISION_E6_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev { return (false, Some(i)); }
            let expected = compute_hash(&prev, e.epoch_end, e.collided_nonces, e.total_nonces, e.collision_rate_pct, e.high_nonce_collision_e6);
            if e.entry_hash != expected { return (false, Some(i)); }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipNonceCollisionE6Log {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipNonceCollisionE6Log::new();
        let e = log.record(1000, 9, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.collided_nonces, 9);
        assert_eq!(e.total_nonces, 100);
        assert_eq!(e.collision_rate_pct, 9);
        assert!(e.high_nonce_collision_e6);
    }
    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipNonceCollisionE6Log::new();
        let e = log.record(2000, 5, 100);
        assert_eq!(e.collision_rate_pct, 5);
        assert!(!e.high_nonce_collision_e6);
    }
    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipNonceCollisionE6Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.collision_rate_pct, 100);
        assert!(e.high_nonce_collision_e6);
    }
    #[test]
    fn total_nonces_zero_no_div_by_zero() {
        let mut log = GossipNonceCollisionE6Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.collision_rate_pct, 0);
        assert!(!e.high_nonce_collision_e6);
    }
    #[test]
    fn threshold_constant_value_is_5() { assert_eq!(HIGH_NONCE_COLLISION_E6_THRESHOLD, 5); }
    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipNonceCollisionE6Log::new();
        let e = log.record(5000, 7, 80);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }
    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipNonceCollisionE6Log::new();
        let e = log.record(6000, 2, 80);
        assert_eq!(e.prev_hash, NONCE_COLLISION_E6_GENESIS_HASH);
    }
    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipNonceCollisionE6Log::new();
        log.record(7000, 2, 80);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 9, 100);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }
    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipNonceCollisionE6Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }
    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipNonceCollisionE6Log::new();
        log.record(9000, 4, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }
    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipNonceCollisionE6Log::new();
        log.record(10000, 2, 60);
        log.record(11000, 4, 80);
        log.record(12000, 9, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }
    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipNonceCollisionE6Log::new();
        log.record(13000, 2, 80);
        log.record(14000, 9, 100);
        log.entries[0].collided_nonces = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }
    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipNonceCollisionE6Log::new();
        log.record(15000, 2, 80);
        log.record(16000, 9, 100);
        log.entries[1].collided_nonces = 99;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }
    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut l1 = GossipNonceCollisionE6Log::new();
        let mut l2 = GossipNonceCollisionE6Log::new();
        let mut l3 = GossipNonceCollisionE6Log::new();
        let e1 = l1.record(17000, 9, 90).entry_hash;
        let e2 = l2.record(17000, 9, 90).entry_hash;
        let e3 = l3.record(17000, 9, 90).entry_hash;
        assert_eq!(e1, e2); assert_eq!(e2, e3);
    }
    #[test]
    fn high_nonce_collision_e6_count_mixed_log() {
        let mut log = GossipNonceCollisionE6Log::new();
        log.record(18000, 3, 100); // rate=3, false
        log.record(19000, 9, 100); // rate=9, true
        log.record(20000, 5, 100); // rate=5, false (boundary)
        log.record(21000, 6, 100); // rate=6, true
        assert_eq!(log.high_nonce_collision_e6_count(), 2);
    }
    #[test]
    fn total_collided_nonces_sums_correctly() {
        let mut log = GossipNonceCollisionE6Log::new();
        log.record(22000, 10, 100);
        log.record(23000, 25, 100);
        log.record(24000, 7, 100);
        assert_eq!(log.total_collided_nonces(), 42);
    }
    #[test]
    fn mean_collision_rate_pct_empty_returns_zero() {
        let log = GossipNonceCollisionE6Log::new();
        assert_eq!(log.mean_collision_rate_pct(), 0);
    }
    #[test]
    fn mean_collision_rate_pct_multi_entry_correct() {
        let mut log = GossipNonceCollisionE6Log::new();
        log.record(25000, 10, 100);
        log.record(26000, 20, 100);
        log.record(27000, 30, 100);
        assert_eq!(log.mean_collision_rate_pct(), 20);
    }
    #[test]
    fn default_produces_zero_entries() {
        let log = GossipNonceCollisionE6Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}
