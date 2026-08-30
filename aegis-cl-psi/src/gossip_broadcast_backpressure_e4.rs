//! Gate 505 — Gossip Broadcast Backpressure E4 Monitor (T2)
//! Tracks backpressure e4 rate per gossip broadcast epoch.
//! UNDER_BACKPRESSURE_E4_THRESHOLD = 20: rate_pct > 20 → under_backpressure_e4

use sha2::{Sha256, Digest};

pub const BACKPRESSURE_E4_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const UNDER_BACKPRESSURE_E4_THRESHOLD: u32 = 20;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipBackpressureE4Entry {
    pub epoch_end:              u64,
    pub backpressured_peers:    u32,
    pub total_peers:            u32,
    pub backpressured_rate_pct: u32,
    pub under_backpressure_e4:  bool,
    pub entry_hash:             [u8; 32],
    pub prev_hash:              [u8; 32],
}

fn compute_hash(
    prev:                &[u8; 32],
    epoch_end:           u64,
    backpressured_peers: u32,
    total_peers:         u32,
    rate_pct:            u32,
    under_backpressure:  bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(backpressured_peers.to_be_bytes());
    h.update(total_peers.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([under_backpressure as u8]);
    h.finalize().into()
}

pub struct GossipBackpressureE4Log {
    pub entries: Vec<GossipBackpressureE4Entry>,
}

impl GossipBackpressureE4Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end:           u64,
        backpressured_peers: u32,
        total_peers:         u32,
    ) -> &GossipBackpressureE4Entry {
        let denom = total_peers.max(1) as u64;
        let rate_pct = ((backpressured_peers as u64).saturating_mul(100) / denom).min(100) as u32;
        let under_backpressure_e4 = rate_pct > UNDER_BACKPRESSURE_E4_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(BACKPRESSURE_E4_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, backpressured_peers, total_peers, rate_pct, under_backpressure_e4);
        self.entries.push(GossipBackpressureE4Entry {
            epoch_end,
            backpressured_peers,
            total_peers,
            backpressured_rate_pct: rate_pct,
            under_backpressure_e4,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn under_backpressure_e4_count(&self) -> usize {
        self.entries.iter().filter(|e| e.under_backpressure_e4).count()
    }

    pub fn total_backpressured_peers(&self) -> u64 {
        self.entries.iter().map(|e| e.backpressured_peers as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.backpressured_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = BACKPRESSURE_E4_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.backpressured_peers,
                e.total_peers,
                e.backpressured_rate_pct,
                e.under_backpressure_e4,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipBackpressureE4Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipBackpressureE4Log::new();
        let e = log.record(1000, 30, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.backpressured_peers, 30);
        assert_eq!(e.total_peers, 100);
        assert_eq!(e.backpressured_rate_pct, 30);
        assert!(e.under_backpressure_e4);
    }

    #[test]
    fn test_flag_false_when_exactly_at_threshold() {
        let mut log = GossipBackpressureE4Log::new();
        // rate_pct = 20, threshold is > 20, so flag should be false
        let e = log.record(2000, 20, 100);
        assert_eq!(e.backpressured_rate_pct, 20);
        assert!(!e.under_backpressure_e4);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipBackpressureE4Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.backpressured_rate_pct, 100);
        assert!(e.under_backpressure_e4);
    }

    #[test]
    fn test_total_peers_zero_no_div_by_zero() {
        let mut log = GossipBackpressureE4Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.backpressured_rate_pct, 0);
        assert!(!e.under_backpressure_e4);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(UNDER_BACKPRESSURE_E4_THRESHOLD, 20u32);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipBackpressureE4Log::new();
        let e = log.record(5000, 25, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_equals_genesis() {
        let mut log = GossipBackpressureE4Log::new();
        log.record(6000, 10, 100);
        assert_eq!(log.entries[0].prev_hash, BACKPRESSURE_E4_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipBackpressureE4Log::new();
        log.record(7000, 10, 100);
        log.record(8000, 15, 100);
        assert_eq!(log.entries[1].prev_hash, log.entries[0].entry_hash);
    }

    #[test]
    fn test_verify_chain_empty_returns_true_none() {
        let log = GossipBackpressureE4Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_one_entry_returns_true_none() {
        let mut log = GossipBackpressureE4Log::new();
        log.record(9000, 5, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries_returns_true_none() {
        let mut log = GossipBackpressureE4Log::new();
        log.record(10000, 5, 100);
        log.record(11000, 15, 100);
        log.record(12000, 25, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipBackpressureE4Log::new();
        log.record(13000, 10, 100);
        log.record(14000, 20, 100);
        log.entries[0].backpressured_peers = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipBackpressureE4Log::new();
        log.record(15000, 10, 100);
        log.record(16000, 20, 100);
        log.entries[1].backpressured_peers = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipBackpressureE4Log::new();
        let h1 = log1.record(17000, 22, 100).entry_hash;

        let mut log2 = GossipBackpressureE4Log::new();
        let h2 = log2.record(17000, 22, 100).entry_hash;

        let mut log3 = GossipBackpressureE4Log::new();
        let h3 = log3.record(17000, 22, 100).entry_hash;

        assert_eq!(h1, h2);
        assert_eq!(h2, h3);
    }

    #[test]
    fn test_under_backpressure_e4_count_mixed_log() {
        let mut log = GossipBackpressureE4Log::new();
        log.record(18000, 5, 100);   // rate=5, flag=false
        log.record(19000, 25, 100);  // rate=25, flag=true
        log.record(20000, 20, 100);  // rate=20, flag=false (boundary)
        log.record(21000, 21, 100);  // rate=21, flag=true
        assert_eq!(log.under_backpressure_e4_count(), 2);
    }

    #[test]
    fn test_total_backpressured_peers_sums_correctly() {
        let mut log = GossipBackpressureE4Log::new();
        log.record(22000, 10, 100);
        log.record(23000, 20, 100);
        log.record(24000, 30, 100);
        assert_eq!(log.total_backpressured_peers(), 60u64);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipBackpressureE4Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry_correct() {
        let mut log = GossipBackpressureE4Log::new();
        log.record(25000, 10, 100);  // rate=10
        log.record(26000, 20, 100);  // rate=20
        log.record(27000, 30, 100);  // rate=30
        // mean = (10+20+30)/3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn test_default_creates_empty_log() {
        let log = GossipBackpressureE4Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}