//! Gate 443 — Gossip Broadcast Nack Rate Monitor (T2)
//! Tracks nack rate rate per gossip broadcast epoch.
//! HIGH_NACK_RATE_THRESHOLD = 6: rate_pct > 6 → high_nack_rate

use sha2::{Sha256, Digest};

pub const NACK_RATE_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_NACK_RATE_THRESHOLD: u32 = 6;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipNackRateEntry {
    pub epoch_end:      u64,
    pub nack_count:     u32,
    pub total_received: u32,
    pub nack_rate_pct:  u32,
    pub high_nack_rate: bool,
    pub entry_hash:     [u8; 32],
    pub prev_hash:      [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    nack_count: u32,
    total_received: u32,
    nack_rate_pct: u32,
    high_nack_rate: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(nack_count.to_be_bytes());
    h.update(total_received.to_be_bytes());
    h.update(nack_rate_pct.to_be_bytes());
    h.update([high_nack_rate as u8]);
    h.finalize().into()
}

pub struct GossipNackRateLog {
    pub entries: Vec<GossipNackRateEntry>,
}

impl GossipNackRateLog {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        nack_count: u32,
        total_received: u32,
    ) -> &GossipNackRateEntry {
        let denom = total_received.max(1) as u64;
        let nack_rate_pct = ((nack_count as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_nack_rate = nack_rate_pct > HIGH_NACK_RATE_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(NACK_RATE_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, nack_count, total_received, nack_rate_pct, high_nack_rate);
        self.entries.push(GossipNackRateEntry {
            epoch_end,
            nack_count,
            total_received,
            nack_rate_pct,
            high_nack_rate,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_nack_rate_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_nack_rate).count()
    }

    pub fn total_nack_count(&self) -> u64 {
        self.entries.iter().map(|e| e.nack_count as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.nack_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = NACK_RATE_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(&prev, e.epoch_end, e.nack_count, e.total_received, e.nack_rate_pct, e.high_nack_rate);
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipNackRateLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_high_flag_true() {
        let mut log = GossipNackRateLog::new();
        let e = log.record(1000, 10, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.nack_count, 10);
        assert_eq!(e.total_received, 100);
        assert_eq!(e.nack_rate_pct, 10);
        assert!(e.high_nack_rate);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipNackRateLog::new();
        // rate = (6 * 100) / 100 = 6, which is == threshold, not > threshold
        let e = log.record(2000, 6, 100);
        assert_eq!(e.nack_rate_pct, 6);
        assert!(!e.high_nack_rate);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipNackRateLog::new();
        // nack_count > total_received
        let e = log.record(3000, 200, 100);
        assert_eq!(e.nack_rate_pct, 100);
        assert!(e.high_nack_rate);
    }

    #[test]
    fn total_received_zero_no_div_by_zero() {
        let mut log = GossipNackRateLog::new();
        let e = log.record(4000, 5, 0);
        // denom = max(0, 1) = 1, rate = 5 * 100 / 1 = 500 capped at 100
        assert_eq!(e.nack_rate_pct, 100);
        assert!(e.high_nack_rate);
    }

    #[test]
    fn threshold_constant_value_is_6() {
        assert_eq!(HIGH_NACK_RATE_THRESHOLD, 6);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipNackRateLog::new();
        let e = log.record(5000, 3, 50);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_is_genesis() {
        let mut log = GossipNackRateLog::new();
        let e = log.record(6000, 1, 10);
        assert_eq!(e.prev_hash, NACK_RATE_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipNackRateLog::new();
        log.record(7000, 1, 10);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 2, 20);
        let second_prev = log.entries[1].prev_hash;
        assert_eq!(second_prev, first_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipNackRateLog::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipNackRateLog::new();
        log.record(9000, 1, 10);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipNackRateLog::new();
        log.record(10000, 1, 10);
        log.record(11000, 2, 20);
        log.record(12000, 3, 30);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipNackRateLog::new();
        log.record(13000, 1, 10);
        log.record(14000, 2, 20);
        // Tamper entry 0's entry_hash
        log.entries[0].entry_hash = [0xABu8; 32];
        let result = log.verify_chain();
        assert_eq!(result, (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipNackRateLog::new();
        log.record(15000, 1, 10);
        log.record(16000, 2, 20);
        log.record(17000, 3, 30);
        // Tamper entry 1's nack_count so its hash won't match
        log.entries[1].nack_count = 99;
        let result = log.verify_chain();
        assert_eq!(result, (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut log1 = GossipNackRateLog::new();
        let e1 = log1.record(18000, 7, 100).entry_hash;

        let mut log2 = GossipNackRateLog::new();
        let e2 = log2.record(18000, 7, 100).entry_hash;

        let mut log3 = GossipNackRateLog::new();
        let e3 = log3.record(18000, 7, 100).entry_hash;

        assert_eq!(e1, e2);
        assert_eq!(e2, e3);
    }

    #[test]
    fn high_nack_rate_count_mixed_log() {
        let mut log = GossipNackRateLog::new();
        // rate = 6 (not high)
        log.record(19000, 6, 100);
        // rate = 7 (high)
        log.record(20000, 7, 100);
        // rate = 10 (high)
        log.record(21000, 10, 100);
        // rate = 0 (not high)
        log.record(22000, 0, 100);
        assert_eq!(log.high_nack_rate_count(), 2);
    }

    #[test]
    fn total_nack_count_sums_correctly() {
        let mut log = GossipNackRateLog::new();
        log.record(23000, 5, 100);
        log.record(24000, 10, 200);
        log.record(25000, 3, 50);
        assert_eq!(log.total_nack_count(), 18u64);
    }

    #[test]
    fn mean_rate_pct_empty_returns_zero() {
        let log = GossipNackRateLog::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn mean_rate_pct_multi_entry_correct() {
        let mut log = GossipNackRateLog::new();
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
    fn default_has_zero_entries() {
        let log = GossipNackRateLog::default();
        assert_eq!(log.entries.len(), 0);
    }
}