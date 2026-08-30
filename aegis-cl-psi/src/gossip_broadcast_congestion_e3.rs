//! Gate 464 — Gossip Broadcast Congestion E3 Monitor (T2)
//! Tracks congestion e3 rate per gossip broadcast epoch.
//! CONGESTED_E3_THRESHOLD = 30: rate_pct > 30 → congested_e3

use sha2::{Sha256, Digest};

pub const CONGESTION_E3_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const CONGESTED_E3_THRESHOLD: u32 = 30;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipCongestionE3Entry {
    pub epoch_end:         u64,
    pub congested_epochs:  u32,
    pub total_epochs:      u32,
    pub congested_rate_pct: u32,
    pub congested_e3:      bool,
    pub entry_hash:        [u8; 32],
    pub prev_hash:         [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    congested_epochs: u32,
    total_epochs: u32,
    rate_pct: u32,
    congested_e3: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(congested_epochs.to_be_bytes());
    h.update(total_epochs.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([congested_e3 as u8]);
    h.finalize().into()
}

pub struct GossipCongestionE3Log {
    pub entries: Vec<GossipCongestionE3Entry>,
}

impl GossipCongestionE3Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        congested_epochs: u32,
        total_epochs: u32,
    ) -> &GossipCongestionE3Entry {
        let denom = total_epochs.max(1) as u64;
        let rate_pct = ((congested_epochs as u64).saturating_mul(100) / denom).min(100) as u32;
        let congested_e3 = rate_pct > CONGESTED_E3_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(CONGESTION_E3_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, congested_epochs, total_epochs, rate_pct, congested_e3);
        self.entries.push(GossipCongestionE3Entry {
            epoch_end,
            congested_epochs,
            total_epochs,
            congested_rate_pct: rate_pct,
            congested_e3,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn congested_e3_count(&self) -> usize {
        self.entries.iter().filter(|e| e.congested_e3).count()
    }

    pub fn total_congested_epochs(&self) -> u64 {
        self.entries.iter().map(|e| e.congested_epochs as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.congested_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = CONGESTION_E3_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.congested_epochs,
                e.total_epochs,
                e.congested_rate_pct,
                e.congested_e3,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipCongestionE3Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_flag_true() {
        let mut log = GossipCongestionE3Log::new();
        let e = log.record(1000, 40, 80);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.congested_epochs, 40);
        assert_eq!(e.total_epochs, 80);
        assert_eq!(e.congested_rate_pct, 50);
        assert!(e.congested_e3);
    }

    #[test]
    fn test_flag_false_when_exactly_at_threshold() {
        let mut log = GossipCongestionE3Log::new();
        // rate = (30 * 100) / 100 = 30, which is NOT > 30
        let e = log.record(2000, 30, 100);
        assert_eq!(e.congested_rate_pct, 30);
        assert!(!e.congested_e3);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipCongestionE3Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.congested_rate_pct, 100);
        assert!(e.congested_e3);
    }

    #[test]
    fn test_total_epochs_zero_no_div_by_zero() {
        let mut log = GossipCongestionE3Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.congested_rate_pct, 0);
        assert!(!e.congested_e3);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(CONGESTED_E3_THRESHOLD, 30);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipCongestionE3Log::new();
        let e = log.record(5000, 50, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipCongestionE3Log::new();
        let e = log.record(6000, 10, 100);
        assert_eq!(e.prev_hash, CONGESTION_E3_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipCongestionE3Log::new();
        log.record(7000, 10, 100);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 20, 100);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipCongestionE3Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_one_entry() {
        let mut log = GossipCongestionE3Log::new();
        log.record(9000, 15, 50);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipCongestionE3Log::new();
        log.record(10000, 10, 100);
        log.record(11000, 35, 100);
        log.record(12000, 50, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipCongestionE3Log::new();
        log.record(13000, 10, 100);
        log.record(14000, 20, 100);
        log.entries[0].congested_epochs = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipCongestionE3Log::new();
        log.record(15000, 10, 100);
        log.record(16000, 20, 100);
        log.entries[1].congested_epochs = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn test_determinism_same_inputs() {
        let mut log1 = GossipCongestionE3Log::new();
        let mut log2 = GossipCongestionE3Log::new();
        let mut log3 = GossipCongestionE3Log::new();
        log1.record(17000, 40, 100);
        log2.record(17000, 40, 100);
        log3.record(17000, 40, 100);
        assert_eq!(log1.entries[0].entry_hash, log2.entries[0].entry_hash);
        assert_eq!(log2.entries[0].entry_hash, log3.entries[0].entry_hash);
    }

    #[test]
    fn test_congested_e3_count_mixed() {
        let mut log = GossipCongestionE3Log::new();
        log.record(18000, 10, 100); // 10% - not congested
        log.record(19000, 35, 100); // 35% - congested
        log.record(20000, 50, 100); // 50% - congested
        log.record(21000, 30, 100); // 30% - not congested (boundary)
        assert_eq!(log.congested_e3_count(), 2);
    }

    #[test]
    fn test_total_congested_epochs_sums_correctly() {
        let mut log = GossipCongestionE3Log::new();
        log.record(22000, 10, 100);
        log.record(23000, 25, 100);
        log.record(24000, 40, 100);
        assert_eq!(log.total_congested_epochs(), 75u64);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipCongestionE3Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry() {
        let mut log = GossipCongestionE3Log::new();
        log.record(25000, 20, 100); // 20%
        log.record(26000, 40, 100); // 40%
        log.record(27000, 60, 100); // 60%
        // mean = (20 + 40 + 60) / 3 = 40
        assert_eq!(log.mean_rate_pct(), 40);
    }

    #[test]
    fn test_default_zero_entries() {
        let log = GossipCongestionE3Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}