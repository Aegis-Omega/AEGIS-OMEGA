//! Gate 513 — Gossip Broadcast Nack Rate E4 Monitor (T2)
//! Tracks nack rate e4 rate per gossip broadcast epoch.
//! HIGH_NACK_RATE_E4_THRESHOLD = 6: rate_pct > 6 → high_nack_rate_e4

use sha2::{Sha256, Digest};

pub const NACK_RATE_E4_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_NACK_RATE_E4_THRESHOLD: u32 = 6;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipNackRateE4Entry {
    pub epoch_end:         u64,
    pub nack_count:        u32,
    pub total_received:    u32,
    pub nack_rate_pct:     u32,
    pub high_nack_rate_e4: bool,
    pub entry_hash:        [u8; 32],
    pub prev_hash:         [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    nack_count: u32,
    total_received: u32,
    nack_rate_pct: u32,
    high_nack_rate_e4: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(nack_count.to_be_bytes());
    h.update(total_received.to_be_bytes());
    h.update(nack_rate_pct.to_be_bytes());
    h.update([high_nack_rate_e4 as u8]);
    h.finalize().into()
}

pub struct GossipNackRateE4Log {
    pub entries: Vec<GossipNackRateE4Entry>,
}

impl GossipNackRateE4Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        nack_count: u32,
        total_received: u32,
    ) -> &GossipNackRateE4Entry {
        let denom = total_received.max(1) as u64;
        let nack_rate_pct = ((nack_count as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_nack_rate_e4 = nack_rate_pct > HIGH_NACK_RATE_E4_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(NACK_RATE_E4_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, nack_count, total_received, nack_rate_pct, high_nack_rate_e4);
        self.entries.push(GossipNackRateE4Entry {
            epoch_end,
            nack_count,
            total_received,
            nack_rate_pct,
            high_nack_rate_e4,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_nack_rate_e4_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_nack_rate_e4).count()
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
        let mut prev = NACK_RATE_E4_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(&prev, e.epoch_end, e.nack_count, e.total_received, e.nack_rate_pct, e.high_nack_rate_e4);
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipNackRateE4Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_flag_true() {
        let mut log = GossipNackRateE4Log::new();
        // nack_count=10, total_received=100 → rate=10 > 6 → true
        let e = log.record(1000, 10, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.nack_count, 10);
        assert_eq!(e.total_received, 100);
        assert_eq!(e.nack_rate_pct, 10);
        assert_eq!(e.high_nack_rate_e4, true);
    }

    #[test]
    fn test_flag_false_when_exactly_at_threshold() {
        let mut log = GossipNackRateE4Log::new();
        // nack_count=6, total_received=100 → rate=6 == threshold → false (not >)
        let e = log.record(2000, 6, 100);
        assert_eq!(e.nack_rate_pct, 6);
        assert_eq!(e.high_nack_rate_e4, false);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipNackRateE4Log::new();
        // nack_count > total_received → would exceed 100
        let e = log.record(3000, 200, 100);
        assert_eq!(e.nack_rate_pct, 100);
        assert_eq!(e.high_nack_rate_e4, true);
    }

    #[test]
    fn test_total_received_zero_no_div_by_zero() {
        let mut log = GossipNackRateE4Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.nack_rate_pct, 0);
        assert_eq!(e.high_nack_rate_e4, false);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(HIGH_NACK_RATE_E4_THRESHOLD, 6u32);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipNackRateE4Log::new();
        let e = log.record(5000, 10, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipNackRateE4Log::new();
        let e = log.record(6000, 5, 100);
        assert_eq!(e.prev_hash, NACK_RATE_E4_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipNackRateE4Log::new();
        let first_hash = log.record(7000, 5, 100).entry_hash;
        let second = log.record(8000, 10, 100);
        assert_eq!(second.prev_hash, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipNackRateE4Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_one_entry() {
        let mut log = GossipNackRateE4Log::new();
        log.record(9000, 5, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipNackRateE4Log::new();
        log.record(10000, 5, 100);
        log.record(11000, 10, 100);
        log.record(12000, 15, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipNackRateE4Log::new();
        log.record(13000, 5, 100);
        log.record(14000, 10, 100);
        // Tamper entry 0 field
        log.entries[0].nack_count = 99;
        let result = log.verify_chain();
        assert_eq!(result, (false, Some(0)));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipNackRateE4Log::new();
        log.record(15000, 5, 100);
        log.record(16000, 10, 100);
        log.record(17000, 15, 100);
        // Tamper entry 1 field
        log.entries[1].nack_count = 42;
        let result = log.verify_chain();
        assert_eq!(result, (false, Some(1)));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipNackRateE4Log::new();
        let h1 = log1.record(18000, 7, 100).entry_hash;

        let mut log2 = GossipNackRateE4Log::new();
        let h2 = log2.record(18000, 7, 100).entry_hash;

        let mut log3 = GossipNackRateE4Log::new();
        let h3 = log3.record(18000, 7, 100).entry_hash;

        assert_eq!(h1, h2);
        assert_eq!(h2, h3);
    }

    #[test]
    fn test_high_nack_rate_e4_count_mixed() {
        let mut log = GossipNackRateE4Log::new();
        log.record(19000, 6, 100);  // rate=6 → false
        log.record(20000, 7, 100);  // rate=7 → true
        log.record(21000, 8, 100);  // rate=8 → true
        log.record(22000, 3, 100);  // rate=3 → false
        assert_eq!(log.high_nack_rate_e4_count(), 2);
    }

    #[test]
    fn test_total_nack_count_sums_correctly() {
        let mut log = GossipNackRateE4Log::new();
        log.record(23000, 10, 100);
        log.record(24000, 20, 100);
        log.record(25000, 30, 100);
        assert_eq!(log.total_nack_count(), 60u64);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipNackRateE4Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry_correct() {
        let mut log = GossipNackRateE4Log::new();
        // rates: 10, 20, 30 → mean = 20
        log.record(26000, 10, 100);
        log.record(27000, 20, 100);
        log.record(28000, 30, 100);
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn test_default_has_zero_entries() {
        let log = GossipNackRateE4Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}