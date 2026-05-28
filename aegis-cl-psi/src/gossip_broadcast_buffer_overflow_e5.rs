//! Gate 554 — Gossip Broadcast Buffer Overflow E5 Monitor (T2)
//! Tracks buffer overflow rate per gossip broadcast epoch.
//! HIGH_BUFFER_OVERFLOW_E5_THRESHOLD = 8: overflow_rate_pct > 8 → high_buffer_overflow_e5

use sha2::{Sha256, Digest};

pub const BUFFER_OVERFLOW_E5_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_BUFFER_OVERFLOW_E5_THRESHOLD: u32 = 8;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipBufferOverflowE5Entry {
    pub epoch_end:              u64,
    pub overflow_events:        u32,
    pub total_buffer_ops:       u32,
    pub overflow_rate_pct:      u32,
    pub high_buffer_overflow_e5: bool,
    pub entry_hash:             [u8; 32],
    pub prev_hash:              [u8; 32],
}

fn compute_hash(prev: &[u8; 32], epoch_end: u64, overflow_events: u32, total_buffer_ops: u32, rate_pct: u32, high_buffer_overflow_e5: bool) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev); h.update(epoch_end.to_be_bytes());
    h.update(overflow_events.to_be_bytes()); h.update(total_buffer_ops.to_be_bytes());
    h.update(rate_pct.to_be_bytes()); h.update([high_buffer_overflow_e5 as u8]);
    h.finalize().into()
}

pub struct GossipBufferOverflowE5Log { pub entries: Vec<GossipBufferOverflowE5Entry> }

impl GossipBufferOverflowE5Log {
    pub fn new() -> Self { Self { entries: Vec::new() } }
    pub fn record(&mut self, epoch_end: u64, overflow_events: u32, total_buffer_ops: u32) -> &GossipBufferOverflowE5Entry {
        let denom = total_buffer_ops.max(1) as u64;
        let overflow_rate_pct = ((overflow_events as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_buffer_overflow_e5 = overflow_rate_pct > HIGH_BUFFER_OVERFLOW_E5_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(BUFFER_OVERFLOW_E5_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, overflow_events, total_buffer_ops, overflow_rate_pct, high_buffer_overflow_e5);
        self.entries.push(GossipBufferOverflowE5Entry { epoch_end, overflow_events, total_buffer_ops, overflow_rate_pct, high_buffer_overflow_e5, entry_hash, prev_hash: prev });
        self.entries.last().unwrap()
    }
    pub fn high_buffer_overflow_e5_count(&self) -> usize { self.entries.iter().filter(|e| e.high_buffer_overflow_e5).count() }
    pub fn total_overflow_events(&self) -> u64 { self.entries.iter().map(|e| e.overflow_events as u64).sum() }
    pub fn mean_overflow_rate_pct(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        (self.entries.iter().map(|e| e.overflow_rate_pct as u64).sum::<u64>() / self.entries.len() as u64) as u32
    }
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = BUFFER_OVERFLOW_E5_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev { return (false, Some(i)); }
            if e.entry_hash != compute_hash(&prev, e.epoch_end, e.overflow_events, e.total_buffer_ops, e.overflow_rate_pct, e.high_buffer_overflow_e5) { return (false, Some(i)); }
            prev = e.entry_hash;
        }
        (true, None)
    }
}
impl Default for GossipBufferOverflowE5Log { fn default() -> Self { Self::new() } }

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipBufferOverflowE5Log::new();
        let e = log.record(1000, 12, 100);
        assert_eq!(e.epoch_end, 1000); assert_eq!(e.overflow_events, 12);
        assert_eq!(e.total_buffer_ops, 100); assert_eq!(e.overflow_rate_pct, 12);
        assert!(e.high_buffer_overflow_e5);
    }
    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipBufferOverflowE5Log::new();
        let e = log.record(2000, 8, 100);
        assert_eq!(e.overflow_rate_pct, 8); assert!(!e.high_buffer_overflow_e5);
    }
    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipBufferOverflowE5Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.overflow_rate_pct, 100); assert!(e.high_buffer_overflow_e5);
    }
    #[test]
    fn total_buffer_ops_zero_no_div_by_zero() {
        let mut log = GossipBufferOverflowE5Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.overflow_rate_pct, 0); assert!(!e.high_buffer_overflow_e5);
    }
    #[test]
    fn threshold_constant_value_is_8() { assert_eq!(HIGH_BUFFER_OVERFLOW_E5_THRESHOLD, 8); }
    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipBufferOverflowE5Log::new();
        assert_ne!(log.record(5000, 10, 80).entry_hash, [0u8; 32]);
    }
    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipBufferOverflowE5Log::new();
        assert_eq!(log.record(6000, 5, 80).prev_hash, BUFFER_OVERFLOW_E5_GENESIS_HASH);
    }
    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipBufferOverflowE5Log::new();
        log.record(7000, 5, 80);
        let h = log.entries[0].entry_hash;
        log.record(8000, 12, 100);
        assert_eq!(log.entries[1].prev_hash, h);
    }
    #[test]
    fn verify_chain_empty_returns_true_none() { assert_eq!(GossipBufferOverflowE5Log::new().verify_chain(), (true, None)); }
    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipBufferOverflowE5Log::new();
        log.record(9000, 9, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }
    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipBufferOverflowE5Log::new();
        log.record(10000, 4, 60); log.record(11000, 9, 80); log.record(12000, 15, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }
    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipBufferOverflowE5Log::new();
        log.record(13000, 5, 80); log.record(14000, 12, 100);
        log.entries[0].overflow_events = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }
    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipBufferOverflowE5Log::new();
        log.record(15000, 5, 80); log.record(16000, 12, 100);
        log.entries[1].overflow_events = 99;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }
    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut l1 = GossipBufferOverflowE5Log::new(); let mut l2 = GossipBufferOverflowE5Log::new(); let mut l3 = GossipBufferOverflowE5Log::new();
        let e1 = l1.record(17000, 10, 90).entry_hash; let e2 = l2.record(17000, 10, 90).entry_hash; let e3 = l3.record(17000, 10, 90).entry_hash;
        assert_eq!(e1, e2); assert_eq!(e2, e3);
    }
    #[test]
    fn high_buffer_overflow_e5_count_mixed_log() {
        let mut log = GossipBufferOverflowE5Log::new();
        log.record(18000, 6, 100); log.record(19000, 12, 100); log.record(20000, 8, 100); log.record(21000, 9, 100);
        assert_eq!(log.high_buffer_overflow_e5_count(), 2);
    }
    #[test]
    fn total_overflow_events_sums_correctly() {
        let mut log = GossipBufferOverflowE5Log::new();
        log.record(22000, 10, 100); log.record(23000, 25, 100); log.record(24000, 7, 100);
        assert_eq!(log.total_overflow_events(), 42);
    }
    #[test]
    fn mean_overflow_rate_pct_empty_returns_zero() { assert_eq!(GossipBufferOverflowE5Log::new().mean_overflow_rate_pct(), 0); }
    #[test]
    fn mean_overflow_rate_pct_multi_entry_correct() {
        let mut log = GossipBufferOverflowE5Log::new();
        log.record(25000, 10, 100); log.record(26000, 20, 100); log.record(27000, 30, 100);
        assert_eq!(log.mean_overflow_rate_pct(), 20);
    }
    #[test]
    fn default_produces_zero_entries() { assert_eq!(GossipBufferOverflowE5Log::default().entries.len(), 0); }
}
