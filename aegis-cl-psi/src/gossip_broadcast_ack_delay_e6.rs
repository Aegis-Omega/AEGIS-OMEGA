//! Gate 578 — Gossip Broadcast Ack Delay E6 Monitor (T2)
//! Tracks acknowledgement delay rate per gossip broadcast epoch.
//! HIGH_ACK_DELAY_E6_THRESHOLD = 17: delay_rate_pct > 17 → high_ack_delay_e6

use sha2::{Sha256, Digest};

pub const ACK_DELAY_E6_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_ACK_DELAY_E6_THRESHOLD: u32 = 17;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipAckDelayE6Entry {
    pub epoch_end:         u64,
    pub delayed_acks:      u32,
    pub total_acks:        u32,
    pub delay_rate_pct:    u32,
    pub high_ack_delay_e6: bool,
    pub entry_hash:        [u8; 32],
    pub prev_hash:         [u8; 32],
}

fn compute_hash(prev: &[u8; 32], epoch_end: u64, delayed_acks: u32, total_acks: u32, rate_pct: u32, high_ack_delay_e6: bool) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev); h.update(epoch_end.to_be_bytes());
    h.update(delayed_acks.to_be_bytes()); h.update(total_acks.to_be_bytes());
    h.update(rate_pct.to_be_bytes()); h.update([high_ack_delay_e6 as u8]);
    h.finalize().into()
}

pub struct GossipAckDelayE6Log { pub entries: Vec<GossipAckDelayE6Entry> }

impl GossipAckDelayE6Log {
    pub fn new() -> Self { Self { entries: Vec::new() } }
    pub fn record(&mut self, epoch_end: u64, delayed_acks: u32, total_acks: u32) -> &GossipAckDelayE6Entry {
        let denom = total_acks.max(1) as u64;
        let delay_rate_pct = ((delayed_acks as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_ack_delay_e6 = delay_rate_pct > HIGH_ACK_DELAY_E6_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(ACK_DELAY_E6_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, delayed_acks, total_acks, delay_rate_pct, high_ack_delay_e6);
        self.entries.push(GossipAckDelayE6Entry { epoch_end, delayed_acks, total_acks, delay_rate_pct, high_ack_delay_e6, entry_hash, prev_hash: prev });
        self.entries.last().unwrap()
    }
    pub fn high_ack_delay_e6_count(&self) -> usize { self.entries.iter().filter(|e| e.high_ack_delay_e6).count() }
    pub fn total_delayed_acks(&self) -> u64 { self.entries.iter().map(|e| e.delayed_acks as u64).sum() }
    pub fn mean_delay_rate_pct(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        (self.entries.iter().map(|e| e.delay_rate_pct as u64).sum::<u64>() / self.entries.len() as u64) as u32
    }
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = ACK_DELAY_E6_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev { return (false, Some(i)); }
            if e.entry_hash != compute_hash(&prev, e.epoch_end, e.delayed_acks, e.total_acks, e.delay_rate_pct, e.high_ack_delay_e6) { return (false, Some(i)); }
            prev = e.entry_hash;
        }
        (true, None)
    }
}
impl Default for GossipAckDelayE6Log { fn default() -> Self { Self::new() } }

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipAckDelayE6Log::new();
        let e = log.record(1000, 22, 100);
        assert_eq!(e.epoch_end, 1000); assert_eq!(e.delayed_acks, 22);
        assert_eq!(e.total_acks, 100); assert_eq!(e.delay_rate_pct, 22);
        assert!(e.high_ack_delay_e6);
    }
    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipAckDelayE6Log::new();
        let e = log.record(2000, 17, 100);
        assert_eq!(e.delay_rate_pct, 17); assert!(!e.high_ack_delay_e6);
    }
    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipAckDelayE6Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.delay_rate_pct, 100); assert!(e.high_ack_delay_e6);
    }
    #[test]
    fn total_acks_zero_no_div_by_zero() {
        let mut log = GossipAckDelayE6Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.delay_rate_pct, 0); assert!(!e.high_ack_delay_e6);
    }
    #[test]
    fn threshold_constant_value_is_17() { assert_eq!(HIGH_ACK_DELAY_E6_THRESHOLD, 17); }
    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipAckDelayE6Log::new();
        assert_ne!(log.record(5000, 20, 80).entry_hash, [0u8; 32]);
    }
    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipAckDelayE6Log::new();
        assert_eq!(log.record(6000, 14, 80).prev_hash, ACK_DELAY_E6_GENESIS_HASH);
    }
    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipAckDelayE6Log::new();
        log.record(7000, 14, 80);
        let h = log.entries[0].entry_hash;
        log.record(8000, 22, 100);
        assert_eq!(log.entries[1].prev_hash, h);
    }
    #[test]
    fn verify_chain_empty_returns_true_none() { assert_eq!(GossipAckDelayE6Log::new().verify_chain(), (true, None)); }
    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipAckDelayE6Log::new();
        log.record(9000, 18, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }
    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipAckDelayE6Log::new();
        log.record(10000, 10, 60); log.record(11000, 18, 80); log.record(12000, 25, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }
    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipAckDelayE6Log::new();
        log.record(13000, 14, 80); log.record(14000, 22, 100);
        log.entries[0].delayed_acks = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }
    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipAckDelayE6Log::new();
        log.record(15000, 14, 80); log.record(16000, 22, 100);
        log.entries[1].delayed_acks = 99;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }
    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut l1 = GossipAckDelayE6Log::new(); let mut l2 = GossipAckDelayE6Log::new(); let mut l3 = GossipAckDelayE6Log::new();
        let e1 = l1.record(17000, 20, 90).entry_hash; let e2 = l2.record(17000, 20, 90).entry_hash; let e3 = l3.record(17000, 20, 90).entry_hash;
        assert_eq!(e1, e2); assert_eq!(e2, e3);
    }
    #[test]
    fn high_ack_delay_e6_count_mixed_log() {
        let mut log = GossipAckDelayE6Log::new();
        log.record(18000, 14, 100); log.record(19000, 22, 100); log.record(20000, 17, 100); log.record(21000, 18, 100);
        assert_eq!(log.high_ack_delay_e6_count(), 2);
    }
    #[test]
    fn total_delayed_acks_sums_correctly() {
        let mut log = GossipAckDelayE6Log::new();
        log.record(22000, 10, 100); log.record(23000, 25, 100); log.record(24000, 7, 100);
        assert_eq!(log.total_delayed_acks(), 42);
    }
    #[test]
    fn mean_delay_rate_pct_empty_returns_zero() { assert_eq!(GossipAckDelayE6Log::new().mean_delay_rate_pct(), 0); }
    #[test]
    fn mean_delay_rate_pct_multi_entry_correct() {
        let mut log = GossipAckDelayE6Log::new();
        log.record(25000, 10, 100); log.record(26000, 20, 100); log.record(27000, 30, 100);
        assert_eq!(log.mean_delay_rate_pct(), 20);
    }
    #[test]
    fn default_produces_zero_entries() { assert_eq!(GossipAckDelayE6Log::default().entries.len(), 0); }
}
