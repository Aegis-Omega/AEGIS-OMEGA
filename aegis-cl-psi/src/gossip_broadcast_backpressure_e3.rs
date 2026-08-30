//! Gate 470 — Gossip Broadcast Backpressure E3 Monitor (T2)
//! Tracks backpressure e3 rate per gossip broadcast epoch.
//! UNDER_BACKPRESSURE_E3_THRESHOLD = 20: rate_pct > 20 → under_backpressure_e3

use sha2::{Sha256, Digest};

pub const BACKPRESSURE_E3_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const UNDER_BACKPRESSURE_E3_THRESHOLD: u32 = 20;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipBackpressureE3Entry {
    pub epoch_end:             u64,
    pub backpressured_peers:   u32,
    pub total_peers:           u32,
    pub backpressured_rate_pct: u32,
    pub under_backpressure_e3: bool,
    pub entry_hash:            [u8; 32],
    pub prev_hash:             [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    backpressured_peers: u32,
    total_peers: u32,
    rate_pct: u32,
    under_backpressure_e3: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(backpressured_peers.to_be_bytes());
    h.update(total_peers.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([under_backpressure_e3 as u8]);
    h.finalize().into()
}

pub struct GossipBackpressureE3Log {
    pub entries: Vec<GossipBackpressureE3Entry>,
}

impl GossipBackpressureE3Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        backpressured_peers: u32,
        total_peers: u32,
    ) -> &GossipBackpressureE3Entry {
        let denom = total_peers.max(1) as u64;
        let rate_pct = ((backpressured_peers as u64).saturating_mul(100) / denom).min(100) as u32;
        let under_backpressure_e3 = rate_pct > UNDER_BACKPRESSURE_E3_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(BACKPRESSURE_E3_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, backpressured_peers, total_peers, rate_pct, under_backpressure_e3);
        self.entries.push(GossipBackpressureE3Entry {
            epoch_end,
            backpressured_peers,
            total_peers,
            backpressured_rate_pct: rate_pct,
            under_backpressure_e3,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn under_backpressure_e3_count(&self) -> usize {
        self.entries.iter().filter(|e| e.under_backpressure_e3).count()
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
        let mut prev = BACKPRESSURE_E3_GENESIS_HASH;
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
                e.under_backpressure_e3,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipBackpressureE3Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipBackpressureE3Log::new();
        let e = log.record(1000, 30, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.backpressured_peers, 30);
        assert_eq!(e.total_peers, 100);
        assert_eq!(e.backpressured_rate_pct, 30);
        assert!(e.under_backpressure_e3);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipBackpressureE3Log::new();
        // rate_pct = (20 * 100) / 100 = 20, which is NOT > 20
        let e = log.record(2000, 20, 100);
        assert_eq!(e.backpressured_rate_pct, 20);
        assert!(!e.under_backpressure_e3);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipBackpressureE3Log::new();
        // backpressured_peers > total_peers
        let e = log.record(3000, 200, 100);
        assert_eq!(e.backpressured_rate_pct, 100);
        assert!(e.under_backpressure_e3);
    }

    #[test]
    fn total_peers_zero_no_div_by_zero() {
        let mut log = GossipBackpressureE3Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.backpressured_rate_pct, 0);
        assert!(!e.under_backpressure_e3);
    }

    #[test]
    fn threshold_constant_value_is_20() {
        assert_eq!(UNDER_BACKPRESSURE_E3_THRESHOLD, 20);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipBackpressureE3Log::new();
        let e = log.record(5000, 50, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipBackpressureE3Log::new();
        log.record(6000, 10, 100);
        assert_eq!(log.entries[0].prev_hash, BACKPRESSURE_E3_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipBackpressureE3Log::new();
        log.record(7000, 10, 100);
        log.record(8000, 20, 100);
        assert_eq!(log.entries[1].prev_hash, log.entries[0].entry_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipBackpressureE3Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipBackpressureE3Log::new();
        log.record(9000, 5, 50);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipBackpressureE3Log::new();
        log.record(10000, 5, 50);
        log.record(11000, 10, 50);
        log.record(12000, 25, 50);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipBackpressureE3Log::new();
        log.record(13000, 5, 50);
        log.record(14000, 10, 50);
        log.entries[0].backpressured_peers = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipBackpressureE3Log::new();
        log.record(15000, 5, 50);
        log.record(16000, 10, 50);
        log.entries[1].backpressured_peers = 99;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_produce_same_hash() {
        let mut log1 = GossipBackpressureE3Log::new();
        let e1 = log1.record(17000, 15, 60).entry_hash;

        let mut log2 = GossipBackpressureE3Log::new();
        let e2 = log2.record(17000, 15, 60).entry_hash;

        let mut log3 = GossipBackpressureE3Log::new();
        let e3 = log3.record(17000, 15, 60).entry_hash;

        assert_eq!(e1, e2);
        assert_eq!(e2, e3);
    }

    #[test]
    fn under_backpressure_e3_count_mixed_log() {
        let mut log = GossipBackpressureE3Log::new();
        log.record(18000, 5, 100);   // rate=5, flag=false
        log.record(19000, 25, 100);  // rate=25, flag=true
        log.record(20000, 10, 100);  // rate=10, flag=false
        log.record(21000, 50, 100);  // rate=50, flag=true
        assert_eq!(log.under_backpressure_e3_count(), 2);
    }

    #[test]
    fn total_backpressured_peers_sums_correctly() {
        let mut log = GossipBackpressureE3Log::new();
        log.record(22000, 10, 100);
        log.record(23000, 20, 100);
        log.record(24000, 30, 100);
        assert_eq!(log.total_backpressured_peers(), 60);
    }

    #[test]
    fn mean_rate_pct_empty_returns_zero() {
        let log = GossipBackpressureE3Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn mean_rate_pct_multi_entry_correct() {
        let mut log = GossipBackpressureE3Log::new();
        log.record(25000, 10, 100);  // rate=10
        log.record(26000, 20, 100);  // rate=20
        log.record(27000, 30, 100);  // rate=30
        // mean = (10 + 20 + 30) / 3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn default_produces_zero_entries() {
        let log = GossipBackpressureE3Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}