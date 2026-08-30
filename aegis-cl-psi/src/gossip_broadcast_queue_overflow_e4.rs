//! Gate 511 — Gossip Broadcast Queue Overflow E4 Monitor (T2)
//! Tracks queue overflow e4 rate per gossip broadcast epoch.
//! HIGH_OVERFLOW_E4_THRESHOLD = 3: rate_pct > 3 → high_overflow_e4

use sha2::{Sha256, Digest};

pub const QUEUE_OVERFLOW_E4_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_OVERFLOW_E4_THRESHOLD: u32 = 3;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipQueueOverflowE4Entry {
    pub epoch_end: u64,
    pub overflow_events: u32,
    pub total_enqueued: u32,
    pub overflow_events_rate_pct: u32,
    pub high_overflow_e4: bool,
    pub entry_hash: [u8; 32],
    pub prev_hash: [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    overflow_events: u32,
    total_enqueued: u32,
    rate_pct: u32,
    high_overflow_e4: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(overflow_events.to_be_bytes());
    h.update(total_enqueued.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_overflow_e4 as u8]);
    h.finalize().into()
}

pub struct GossipQueueOverflowE4Log {
    pub entries: Vec<GossipQueueOverflowE4Entry>,
}

impl GossipQueueOverflowE4Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        overflow_events: u32,
        total_enqueued: u32,
    ) -> &GossipQueueOverflowE4Entry {
        let denom = total_enqueued.max(1) as u64;
        let overflow_events_rate_pct =
            ((overflow_events as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_overflow_e4 = overflow_events_rate_pct > HIGH_OVERFLOW_E4_THRESHOLD;
        let prev = self
            .entries
            .last()
            .map(|e| e.entry_hash)
            .unwrap_or(QUEUE_OVERFLOW_E4_GENESIS_HASH);
        let entry_hash = compute_hash(
            &prev,
            epoch_end,
            overflow_events,
            total_enqueued,
            overflow_events_rate_pct,
            high_overflow_e4,
        );
        self.entries.push(GossipQueueOverflowE4Entry {
            epoch_end,
            overflow_events,
            total_enqueued,
            overflow_events_rate_pct,
            high_overflow_e4,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_overflow_e4_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_overflow_e4).count()
    }

    pub fn total_overflow_events(&self) -> u64 {
        self.entries
            .iter()
            .map(|e| e.overflow_events as u64)
            .fold(0u64, |acc, x| acc.saturating_add(x))
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self
            .entries
            .iter()
            .map(|e| e.overflow_events_rate_pct as u64)
            .fold(0u64, |acc, x| acc.saturating_add(x));
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = QUEUE_OVERFLOW_E4_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.overflow_events,
                e.total_enqueued,
                e.overflow_events_rate_pct,
                e.high_overflow_e4,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipQueueOverflowE4Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipQueueOverflowE4Log::new();
        // overflow_events=5, total_enqueued=100 → rate=5 > 3 → high=true
        let e = log.record(1000, 5, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.overflow_events, 5);
        assert_eq!(e.total_enqueued, 100);
        assert_eq!(e.overflow_events_rate_pct, 5);
        assert!(e.high_overflow_e4);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipQueueOverflowE4Log::new();
        // overflow_events=3, total_enqueued=100 → rate=3, not > 3 → false
        let e = log.record(2000, 3, 100);
        assert_eq!(e.overflow_events_rate_pct, 3);
        assert!(!e.high_overflow_e4);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipQueueOverflowE4Log::new();
        // overflow_events > total_enqueued → rate should cap at 100
        let e = log.record(3000, 200, 50);
        assert_eq!(e.overflow_events_rate_pct, 100);
        assert!(e.high_overflow_e4);
    }

    #[test]
    fn total_enqueued_zero_no_div_by_zero() {
        let mut log = GossipQueueOverflowE4Log::new();
        // total_enqueued=0 → denom=max(0,1)=1 → rate=(0*100)/1=0
        let e = log.record(4000, 0, 0);
        assert_eq!(e.overflow_events_rate_pct, 0);
        assert!(!e.high_overflow_e4);
    }

    #[test]
    fn threshold_constant_value_is_3() {
        assert_eq!(HIGH_OVERFLOW_E4_THRESHOLD, 3);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipQueueOverflowE4Log::new();
        let e = log.record(5000, 10, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipQueueOverflowE4Log::new();
        let e = log.record(6000, 1, 100);
        assert_eq!(e.prev_hash, QUEUE_OVERFLOW_E4_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipQueueOverflowE4Log::new();
        let e1_hash = log.record(7000, 1, 100).entry_hash;
        let e2_prev = log.record(8000, 2, 100).prev_hash;
        assert_eq!(e2_prev, e1_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipQueueOverflowE4Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipQueueOverflowE4Log::new();
        log.record(9000, 1, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipQueueOverflowE4Log::new();
        log.record(10000, 1, 100);
        log.record(11000, 2, 100);
        log.record(12000, 3, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipQueueOverflowE4Log::new();
        log.record(13000, 1, 100);
        log.record(14000, 2, 100);
        // Tamper entry 0's entry_hash
        log.entries[0].entry_hash = [0xAB; 32];
        let result = log.verify_chain();
        assert_eq!(result, (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipQueueOverflowE4Log::new();
        log.record(15000, 1, 100);
        log.record(16000, 2, 100);
        log.record(17000, 3, 100);
        // Tamper entry 1's overflow_events so hash recompute differs
        log.entries[1].overflow_events = 99;
        let result = log.verify_chain();
        assert_eq!(result, (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_three_times_same_hash() {
        let mut log1 = GossipQueueOverflowE4Log::new();
        let mut log2 = GossipQueueOverflowE4Log::new();
        let mut log3 = GossipQueueOverflowE4Log::new();
        let h1 = log1.record(18000, 5, 100).entry_hash;
        let h2 = log2.record(18000, 5, 100).entry_hash;
        let h3 = log3.record(18000, 5, 100).entry_hash;
        assert_eq!(h1, h2);
        assert_eq!(h2, h3);
    }

    #[test]
    fn high_overflow_e4_count_mixed_log() {
        let mut log = GossipQueueOverflowE4Log::new();
        // rate=0 → false
        log.record(19000, 0, 100);
        // rate=5 → true
        log.record(20000, 5, 100);
        // rate=3 → false (exactly at threshold)
        log.record(21000, 3, 100);
        // rate=50 → true
        log.record(22000, 50, 100);
        assert_eq!(log.high_overflow_e4_count(), 2);
    }

    #[test]
    fn total_overflow_events_sums_correctly() {
        let mut log = GossipQueueOverflowE4Log::new();
        log.record(23000, 10, 100);
        log.record(24000, 20, 100);
        log.record(25000, 30, 100);
        assert_eq!(log.total_overflow_events(), 60u64);
    }

    #[test]
    fn mean_rate_pct_empty_returns_zero() {
        let log = GossipQueueOverflowE4Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn mean_rate_pct_multi_entry_correct() {
        let mut log = GossipQueueOverflowE4Log::new();
        // rate=10
        log.record(26000, 10, 100);
        // rate=20
        log.record(27000, 20, 100);
        // rate=30
        log.record(28000, 30, 100);
        // mean = (10+20+30)/3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn default_log_has_zero_entries() {
        let log = GossipQueueOverflowE4Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}