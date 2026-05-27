//! Gate 454 — Gossip Broadcast Flood Rate Monitor (T2)
//! Tracks flood rate rate per gossip broadcast epoch.
//! HIGH_FLOOD_THRESHOLD = 15: rate_pct > 15 → high_flood

use sha2::{Sha256, Digest};

pub const FLOOD_RATE_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_FLOOD_THRESHOLD: u32 = 15;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipFloodRateEntry {
    pub epoch_end:        u64,
    pub flooded_msgs:     u32,
    pub total_sent:       u32,
    pub flooded_rate_pct: u32,
    pub high_flood:       bool,
    pub entry_hash:       [u8; 32],
    pub prev_hash:        [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    flooded_msgs: u32,
    total_sent: u32,
    rate_pct: u32,
    high_flood: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(flooded_msgs.to_be_bytes());
    h.update(total_sent.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_flood as u8]);
    h.finalize().into()
}

pub struct GossipFloodRateLog {
    pub entries: Vec<GossipFloodRateEntry>,
}

impl GossipFloodRateLog {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(&mut self, epoch_end: u64, flooded_msgs: u32, total_sent: u32) -> &GossipFloodRateEntry {
        let denom = total_sent.max(1) as u64;
        let flooded_rate_pct = ((flooded_msgs as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_flood = flooded_rate_pct > HIGH_FLOOD_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(FLOOD_RATE_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, flooded_msgs, total_sent, flooded_rate_pct, high_flood);
        self.entries.push(GossipFloodRateEntry {
            epoch_end,
            flooded_msgs,
            total_sent,
            flooded_rate_pct,
            high_flood,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_flood_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_flood).count()
    }

    pub fn total_flooded_msgs(&self) -> u64 {
        self.entries.iter().map(|e| e.flooded_msgs as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.flooded_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = FLOOD_RATE_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(&prev, e.epoch_end, e.flooded_msgs, e.total_sent, e.flooded_rate_pct, e.high_flood);
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipFloodRateLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_high_flood_true() {
        let mut log = GossipFloodRateLog::new();
        let e = log.record(1000, 20, 50);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.flooded_msgs, 20);
        assert_eq!(e.total_sent, 50);
        assert_eq!(e.flooded_rate_pct, 40);
        assert!(e.high_flood);
    }

    #[test]
    fn test_flag_false_when_exactly_at_threshold() {
        let mut log = GossipFloodRateLog::new();
        // rate_pct = (15 * 100) / 100 = 15, not > 15
        let e = log.record(2000, 15, 100);
        assert_eq!(e.flooded_rate_pct, 15);
        assert!(!e.high_flood);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipFloodRateLog::new();
        // flooded_msgs > total_sent
        let e = log.record(3000, 200, 50);
        assert_eq!(e.flooded_rate_pct, 100);
        assert!(e.high_flood);
    }

    #[test]
    fn test_total_sent_zero_no_div_by_zero() {
        let mut log = GossipFloodRateLog::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.flooded_rate_pct, 0);
        assert!(!e.high_flood);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(HIGH_FLOOD_THRESHOLD, 15u32);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipFloodRateLog::new();
        let e = log.record(5000, 10, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipFloodRateLog::new();
        let e = log.record(6000, 5, 100);
        assert_eq!(e.prev_hash, FLOOD_RATE_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipFloodRateLog::new();
        log.record(7000, 5, 100);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 10, 100);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipFloodRateLog::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_one_entry() {
        let mut log = GossipFloodRateLog::new();
        log.record(9000, 5, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipFloodRateLog::new();
        log.record(10000, 5, 100);
        log.record(11000, 10, 100);
        log.record(12000, 20, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipFloodRateLog::new();
        log.record(13000, 5, 100);
        log.record(14000, 10, 100);
        log.entries[0].flooded_msgs = 99;
        let (valid, idx) = log.verify_chain();
        assert!(!valid);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipFloodRateLog::new();
        log.record(15000, 5, 100);
        log.record(16000, 10, 100);
        log.entries[1].flooded_msgs = 99;
        let (valid, idx) = log.verify_chain();
        assert!(!valid);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipFloodRateLog::new();
        let e1 = log1.record(17000, 8, 100).entry_hash;

        let mut log2 = GossipFloodRateLog::new();
        let e2 = log2.record(17000, 8, 100).entry_hash;

        let mut log3 = GossipFloodRateLog::new();
        let e3 = log3.record(17000, 8, 100).entry_hash;

        assert_eq!(e1, e2);
        assert_eq!(e2, e3);
    }

    #[test]
    fn test_high_flood_count_mixed_log() {
        let mut log = GossipFloodRateLog::new();
        log.record(18000, 5, 100);   // rate=5, not high
        log.record(19000, 20, 100);  // rate=20, high
        log.record(20000, 15, 100);  // rate=15, not high (boundary)
        log.record(21000, 16, 100);  // rate=16, high
        assert_eq!(log.high_flood_count(), 2);
    }

    #[test]
    fn test_total_flooded_msgs_sums_correctly() {
        let mut log = GossipFloodRateLog::new();
        log.record(22000, 10, 100);
        log.record(23000, 25, 100);
        log.record(24000, 5, 100);
        assert_eq!(log.total_flooded_msgs(), 40u64);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipFloodRateLog::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry_correct() {
        let mut log = GossipFloodRateLog::new();
        log.record(25000, 10, 100);  // rate=10
        log.record(26000, 30, 100);  // rate=30
        log.record(27000, 20, 100);  // rate=20
        // mean = (10 + 30 + 20) / 3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn test_default_zero_entries() {
        let log = GossipFloodRateLog::default();
        assert_eq!(log.entries.len(), 0);
    }
}