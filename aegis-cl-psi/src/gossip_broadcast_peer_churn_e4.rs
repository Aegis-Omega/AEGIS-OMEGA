//! Gate 509 — Gossip Broadcast Peer Churn E4 Monitor (T2)
//! Tracks peer churn e4 rate per gossip broadcast epoch.
//! HIGH_CHURN_E4_THRESHOLD = 25: rate_pct > 25 → high_churn_e4

use sha2::{Sha256, Digest};

pub const PEER_CHURN_E4_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_CHURN_E4_THRESHOLD: u32 = 25;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPeerChurnE4Entry {
    pub epoch_end:       u64,
    pub churned_peers:   u32,
    pub total_peers:     u32,
    pub churned_rate_pct: u32,
    pub high_churn_e4:   bool,
    pub entry_hash:      [u8; 32],
    pub prev_hash:       [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    churned_peers: u32,
    total_peers: u32,
    rate_pct: u32,
    high_churn_e4: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(churned_peers.to_be_bytes());
    h.update(total_peers.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_churn_e4 as u8]);
    h.finalize().into()
}

pub struct GossipPeerChurnE4Log {
    pub entries: Vec<GossipPeerChurnE4Entry>,
}

impl GossipPeerChurnE4Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        churned_peers: u32,
        total_peers: u32,
    ) -> &GossipPeerChurnE4Entry {
        let denom = total_peers.max(1) as u64;
        let churned_rate_pct = ((churned_peers as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_churn_e4 = churned_rate_pct > HIGH_CHURN_E4_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(PEER_CHURN_E4_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, churned_peers, total_peers, churned_rate_pct, high_churn_e4);
        self.entries.push(GossipPeerChurnE4Entry {
            epoch_end,
            churned_peers,
            total_peers,
            churned_rate_pct,
            high_churn_e4,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_churn_e4_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_churn_e4).count()
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
        let mut prev = PEER_CHURN_E4_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(&prev, e.epoch_end, e.churned_peers, e.total_peers, e.churned_rate_pct, e.high_churn_e4);
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPeerChurnE4Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipPeerChurnE4Log::new();
        let e = log.record(1000, 30, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.churned_peers, 30);
        assert_eq!(e.total_peers, 100);
        assert_eq!(e.churned_rate_pct, 30);
        assert_eq!(e.high_churn_e4, true);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipPeerChurnE4Log::new();
        // 25 churned / 100 total = 25% => not > 25, so false
        let e = log.record(2000, 25, 100);
        assert_eq!(e.churned_rate_pct, 25);
        assert_eq!(e.high_churn_e4, false);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipPeerChurnE4Log::new();
        // churned > total
        let e = log.record(3000, 200, 100);
        assert_eq!(e.churned_rate_pct, 100);
        assert_eq!(e.high_churn_e4, true);
    }

    #[test]
    fn total_peers_zero_no_div_by_zero() {
        let mut log = GossipPeerChurnE4Log::new();
        let e = log.record(4000, 0, 0);
        // (0 * 100) / max(0, 1) = 0
        assert_eq!(e.churned_rate_pct, 0);
        assert_eq!(e.high_churn_e4, false);
    }

    #[test]
    fn threshold_constant_value_is_25() {
        assert_eq!(HIGH_CHURN_E4_THRESHOLD, 25);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipPeerChurnE4Log::new();
        let e = log.record(5000, 10, 40);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipPeerChurnE4Log::new();
        let e = log.record(6000, 5, 20);
        assert_eq!(e.prev_hash, PEER_CHURN_E4_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipPeerChurnE4Log::new();
        log.record(7000, 5, 20);
        let first_hash = log.entries[0].entry_hash;
        log.record(7001, 6, 20);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipPeerChurnE4Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipPeerChurnE4Log::new();
        log.record(8000, 10, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipPeerChurnE4Log::new();
        log.record(9000, 10, 100);
        log.record(9001, 20, 100);
        log.record(9002, 5, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipPeerChurnE4Log::new();
        log.record(10000, 10, 100);
        log.record(10001, 20, 100);
        log.entries[0].churned_peers = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipPeerChurnE4Log::new();
        log.record(11000, 10, 100);
        log.record(11001, 20, 100);
        log.entries[1].churned_peers = 99;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut log1 = GossipPeerChurnE4Log::new();
        let mut log2 = GossipPeerChurnE4Log::new();
        let mut log3 = GossipPeerChurnE4Log::new();
        let e1 = log1.record(12000, 15, 60);
        let e2 = log2.record(12000, 15, 60);
        let e3 = log3.record(12000, 15, 60);
        assert_eq!(e1.entry_hash, e2.entry_hash);
        assert_eq!(e2.entry_hash, e3.entry_hash);
    }

    #[test]
    fn high_churn_e4_count_mixed_log() {
        let mut log = GossipPeerChurnE4Log::new();
        log.record(13000, 10, 100); // 10% → false
        log.record(13001, 30, 100); // 30% → true
        log.record(13002, 25, 100); // 25% → false (boundary)
        log.record(13003, 26, 100); // 26% → true
        assert_eq!(log.high_churn_e4_count(), 2);
    }

    #[test]
    fn total_churned_peers_sums_correctly() {
        let mut log = GossipPeerChurnE4Log::new();
        log.record(14000, 10, 100);
        log.record(14001, 20, 100);
        log.record(14002, 30, 100);
        assert_eq!(log.total_churned_peers(), 60u64);
    }

    #[test]
    fn mean_rate_pct_empty_returns_zero() {
        let log = GossipPeerChurnE4Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn mean_rate_pct_multi_entry_correct() {
        let mut log = GossipPeerChurnE4Log::new();
        log.record(15000, 10, 100); // 10%
        log.record(15001, 20, 100); // 20%
        log.record(15002, 30, 100); // 30%
        // mean = (10 + 20 + 30) / 3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn default_produces_zero_entries() {
        let log = GossipPeerChurnE4Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}