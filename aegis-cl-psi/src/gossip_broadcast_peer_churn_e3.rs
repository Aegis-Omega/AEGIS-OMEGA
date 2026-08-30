//! Gate 474 — Gossip Broadcast Peer Churn E3 Monitor (T2)
//! Tracks peer churn e3 rate per gossip broadcast epoch.
//! HIGH_CHURN_E3_THRESHOLD = 25: rate_pct > 25 → high_churn_e3

use sha2::{Sha256, Digest};

pub const PEER_CHURN_E3_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_CHURN_E3_THRESHOLD: u32 = 25;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPeerChurnE3Entry {
    pub epoch_end:       u64,
    pub churned_peers:   u32,
    pub total_peers:     u32,
    pub churned_rate_pct: u32,
    pub high_churn_e3:   bool,
    pub entry_hash:      [u8; 32],
    pub prev_hash:       [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    churned_peers: u32,
    total_peers: u32,
    rate_pct: u32,
    high_churn_e3: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(churned_peers.to_be_bytes());
    h.update(total_peers.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_churn_e3 as u8]);
    h.finalize().into()
}

pub struct GossipPeerChurnE3Log {
    pub entries: Vec<GossipPeerChurnE3Entry>,
}

impl GossipPeerChurnE3Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        churned_peers: u32,
        total_peers: u32,
    ) -> &GossipPeerChurnE3Entry {
        let denom = total_peers.max(1) as u64;
        let churned_rate_pct = ((churned_peers as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_churn_e3 = churned_rate_pct > HIGH_CHURN_E3_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(PEER_CHURN_E3_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, churned_peers, total_peers, churned_rate_pct, high_churn_e3);
        self.entries.push(GossipPeerChurnE3Entry {
            epoch_end,
            churned_peers,
            total_peers,
            churned_rate_pct,
            high_churn_e3,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_churn_e3_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_churn_e3).count()
    }

    pub fn total_churned_peers(&self) -> u64 {
        self.entries.iter().map(|e| e.churned_peers as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.churned_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = PEER_CHURN_E3_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(&prev, e.epoch_end, e.churned_peers, e.total_peers, e.churned_rate_pct, e.high_churn_e3);
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPeerChurnE3Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipPeerChurnE3Log::new();
        // churned=30, total=100 => rate=30 > 25 => high_churn_e3=true
        let e = log.record(1000, 30, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.churned_peers, 30);
        assert_eq!(e.total_peers, 100);
        assert_eq!(e.churned_rate_pct, 30);
        assert!(e.high_churn_e3);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipPeerChurnE3Log::new();
        // churned=25, total=100 => rate=25, not > 25 => false
        let e = log.record(2000, 25, 100);
        assert_eq!(e.churned_rate_pct, 25);
        assert!(!e.high_churn_e3);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipPeerChurnE3Log::new();
        // churned=200, total=100 => raw=200, capped=100
        let e = log.record(3000, 200, 100);
        assert_eq!(e.churned_rate_pct, 100);
        assert!(e.high_churn_e3);
    }

    #[test]
    fn total_peers_zero_no_div_by_zero() {
        let mut log = GossipPeerChurnE3Log::new();
        // total_peers=0, denom=max(0,1)=1, churned=5 => rate=500 capped=100
        let e = log.record(4000, 5, 0);
        assert_eq!(e.total_peers, 0);
        assert_eq!(e.churned_rate_pct, 100);
        assert!(e.high_churn_e3);
    }

    #[test]
    fn threshold_constant_value_is_25() {
        assert_eq!(HIGH_CHURN_E3_THRESHOLD, 25);
    }

    #[test]
    fn entry_hash_is_non_zero() {
        let mut log = GossipPeerChurnE3Log::new();
        let e = log.record(5000, 10, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipPeerChurnE3Log::new();
        let e = log.record(6000, 10, 100);
        assert_eq!(e.prev_hash, PEER_CHURN_E3_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipPeerChurnE3Log::new();
        log.record(7000, 10, 100);
        let first_hash = log.entries[0].entry_hash;
        log.record(7001, 20, 100);
        let second = &log.entries[1];
        assert_eq!(second.prev_hash, first_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipPeerChurnE3Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_single_entry_returns_true_none() {
        let mut log = GossipPeerChurnE3Log::new();
        log.record(8000, 10, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipPeerChurnE3Log::new();
        log.record(9000, 5, 100);
        log.record(9001, 15, 100);
        log.record(9002, 30, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipPeerChurnE3Log::new();
        log.record(10000, 10, 100);
        log.record(10001, 20, 100);
        // Tamper entry 0's churned_peers
        log.entries[0].churned_peers = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipPeerChurnE3Log::new();
        log.record(11000, 10, 100);
        log.record(11001, 20, 100);
        // Tamper entry 1's churned_peers
        log.entries[1].churned_peers = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut log1 = GossipPeerChurnE3Log::new();
        log1.record(12000, 10, 100);
        let mut log2 = GossipPeerChurnE3Log::new();
        log2.record(12000, 10, 100);
        let mut log3 = GossipPeerChurnE3Log::new();
        log3.record(12000, 10, 100);
        assert_eq!(log1.entries[0].entry_hash, log2.entries[0].entry_hash);
        assert_eq!(log2.entries[0].entry_hash, log3.entries[0].entry_hash);
    }

    #[test]
    fn high_churn_e3_count_mixed_log() {
        let mut log = GossipPeerChurnE3Log::new();
        // rate=10 => false
        log.record(13000, 10, 100);
        // rate=30 => true
        log.record(13001, 30, 100);
        // rate=25 => false (not > 25)
        log.record(13002, 25, 100);
        // rate=26 => true
        log.record(13003, 26, 100);
        assert_eq!(log.high_churn_e3_count(), 2);
    }

    #[test]
    fn total_churned_peers_sums_correctly() {
        let mut log = GossipPeerChurnE3Log::new();
        log.record(14000, 5, 100);
        log.record(14001, 15, 100);
        log.record(14002, 25, 100);
        assert_eq!(log.total_churned_peers(), 45u64);
    }

    #[test]
    fn mean_rate_pct_empty_returns_zero() {
        let log = GossipPeerChurnE3Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn mean_rate_pct_multi_entry_correct() {
        let mut log = GossipPeerChurnE3Log::new();
        // rate=10
        log.record(15000, 10, 100);
        // rate=30
        log.record(15001, 30, 100);
        // rate=20
        log.record(15002, 20, 100);
        // mean = (10+30+20)/3 = 60/3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn default_produces_zero_entries() {
        let log = GossipPeerChurnE3Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}