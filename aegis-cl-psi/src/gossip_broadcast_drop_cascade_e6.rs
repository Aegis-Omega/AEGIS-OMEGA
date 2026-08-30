//! Gate 570 — Gossip Broadcast Drop Cascade E6 Monitor (T2)
//! Tracks cascaded drop rate per gossip broadcast epoch.
//! HIGH_DROP_CASCADE_E6_THRESHOLD = 11: cascade_rate_pct > 11 → high_drop_cascade_e6

use sha2::{Sha256, Digest};

pub const DROP_CASCADE_E6_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_DROP_CASCADE_E6_THRESHOLD: u32 = 11;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipDropCascadeE6Entry {
    pub epoch_end:         u64,
    pub cascaded_drops:    u32,
    pub total_drops:       u32,
    pub cascade_rate_pct:  u32,
    pub high_drop_cascade_e6: bool,
    pub entry_hash:        [u8; 32],
    pub prev_hash:         [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    cascaded_drops: u32,
    total_drops: u32,
    rate_pct: u32,
    high_drop_cascade_e6: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(cascaded_drops.to_be_bytes());
    h.update(total_drops.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_drop_cascade_e6 as u8]);
    h.finalize().into()
}

pub struct GossipDropCascadeE6Log {
    pub entries: Vec<GossipDropCascadeE6Entry>,
}

impl GossipDropCascadeE6Log {
    pub fn new() -> Self { Self { entries: Vec::new() } }

    pub fn record(
        &mut self,
        epoch_end: u64,
        cascaded_drops: u32,
        total_drops: u32,
    ) -> &GossipDropCascadeE6Entry {
        let denom = total_drops.max(1) as u64;
        let cascade_rate_pct =
            ((cascaded_drops as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_drop_cascade_e6 = cascade_rate_pct > HIGH_DROP_CASCADE_E6_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(DROP_CASCADE_E6_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, cascaded_drops, total_drops, cascade_rate_pct, high_drop_cascade_e6);
        self.entries.push(GossipDropCascadeE6Entry {
            epoch_end, cascaded_drops, total_drops, cascade_rate_pct,
            high_drop_cascade_e6, entry_hash, prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_drop_cascade_e6_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_drop_cascade_e6).count()
    }
    pub fn total_cascaded_drops(&self) -> u64 {
        self.entries.iter().map(|e| e.cascaded_drops as u64).sum()
    }
    pub fn mean_cascade_rate_pct(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        let sum: u64 = self.entries.iter().map(|e| e.cascade_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = DROP_CASCADE_E6_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev { return (false, Some(i)); }
            let expected = compute_hash(&prev, e.epoch_end, e.cascaded_drops, e.total_drops, e.cascade_rate_pct, e.high_drop_cascade_e6);
            if e.entry_hash != expected { return (false, Some(i)); }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipDropCascadeE6Log {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipDropCascadeE6Log::new();
        let e = log.record(1000, 16, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.cascaded_drops, 16);
        assert_eq!(e.total_drops, 100);
        assert_eq!(e.cascade_rate_pct, 16);
        assert!(e.high_drop_cascade_e6);
    }
    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipDropCascadeE6Log::new();
        let e = log.record(2000, 11, 100);
        assert_eq!(e.cascade_rate_pct, 11);
        assert!(!e.high_drop_cascade_e6);
    }
    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipDropCascadeE6Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.cascade_rate_pct, 100);
        assert!(e.high_drop_cascade_e6);
    }
    #[test]
    fn total_drops_zero_no_div_by_zero() {
        let mut log = GossipDropCascadeE6Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.cascade_rate_pct, 0);
        assert!(!e.high_drop_cascade_e6);
    }
    #[test]
    fn threshold_constant_value_is_11() { assert_eq!(HIGH_DROP_CASCADE_E6_THRESHOLD, 11); }
    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipDropCascadeE6Log::new();
        let e = log.record(5000, 14, 80);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }
    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipDropCascadeE6Log::new();
        let e = log.record(6000, 8, 80);
        assert_eq!(e.prev_hash, DROP_CASCADE_E6_GENESIS_HASH);
    }
    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipDropCascadeE6Log::new();
        log.record(7000, 8, 80);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 16, 100);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }
    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipDropCascadeE6Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }
    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipDropCascadeE6Log::new();
        log.record(9000, 15, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }
    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipDropCascadeE6Log::new();
        log.record(10000, 8, 60);
        log.record(11000, 15, 80);
        log.record(12000, 16, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }
    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipDropCascadeE6Log::new();
        log.record(13000, 8, 80);
        log.record(14000, 16, 100);
        log.entries[0].cascaded_drops = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }
    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipDropCascadeE6Log::new();
        log.record(15000, 8, 80);
        log.record(16000, 16, 100);
        log.entries[1].cascaded_drops = 99;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }
    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut l1 = GossipDropCascadeE6Log::new();
        let mut l2 = GossipDropCascadeE6Log::new();
        let mut l3 = GossipDropCascadeE6Log::new();
        let e1 = l1.record(17000, 16, 90).entry_hash;
        let e2 = l2.record(17000, 16, 90).entry_hash;
        let e3 = l3.record(17000, 16, 90).entry_hash;
        assert_eq!(e1, e2); assert_eq!(e2, e3);
    }
    #[test]
    fn high_drop_cascade_e6_count_mixed_log() {
        let mut log = GossipDropCascadeE6Log::new();
        log.record(18000, 8, 100);  // rate=8, false
        log.record(19000, 16, 100); // rate=16, true
        log.record(20000, 11, 100); // rate=11, false (boundary)
        log.record(21000, 12, 100); // rate=12, true
        assert_eq!(log.high_drop_cascade_e6_count(), 2);
    }
    #[test]
    fn total_cascaded_drops_sums_correctly() {
        let mut log = GossipDropCascadeE6Log::new();
        log.record(22000, 10, 100);
        log.record(23000, 25, 100);
        log.record(24000, 7, 100);
        assert_eq!(log.total_cascaded_drops(), 42);
    }
    #[test]
    fn mean_cascade_rate_pct_empty_returns_zero() {
        let log = GossipDropCascadeE6Log::new();
        assert_eq!(log.mean_cascade_rate_pct(), 0);
    }
    #[test]
    fn mean_cascade_rate_pct_multi_entry_correct() {
        let mut log = GossipDropCascadeE6Log::new();
        log.record(25000, 10, 100);
        log.record(26000, 20, 100);
        log.record(27000, 30, 100);
        assert_eq!(log.mean_cascade_rate_pct(), 20);
    }
    #[test]
    fn default_produces_zero_entries() {
        let log = GossipDropCascadeE6Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}
