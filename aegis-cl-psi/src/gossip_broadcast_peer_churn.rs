//! Gate 439 — Gossip Broadcast Peer Churn Monitor (T2)
//! Tracks peer churn rate per gossip broadcast epoch.
//! HIGH_CHURN_THRESHOLD = 25: rate_pct > 25 → high_churn

use sha2::{Sha256, Digest};

pub const PEER_CHURN_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_CHURN_THRESHOLD: u32 = 25;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPeerChurnEntry {
    pub epoch_end:        u64,
    pub churned_peers:    u32,
    pub total_peers:      u32,
    pub churned_rate_pct: u32,
    pub high_churn:       bool,
    pub entry_hash:       [u8; 32],
    pub prev_hash:        [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    churned_peers: u32,
    total_peers: u32,
    rate_pct: u32,
    high_churn: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(churned_peers.to_be_bytes());
    h.update(total_peers.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_churn as u8]);
    h.finalize().into()
}

pub struct GossipPeerChurnLog {
    pub entries: Vec<GossipPeerChurnEntry>,
}

impl GossipPeerChurnLog {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        churned_peers: u32,
        total_peers: u32,
    ) -> &GossipPeerChurnEntry {
        let denom = total_peers.max(1) as u64;
        let churned_rate_pct = ((churned_peers as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_churn = churned_rate_pct > HIGH_CHURN_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(PEER_CHURN_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, churned_peers, total_peers, churned_rate_pct, high_churn);
        self.entries.push(GossipPeerChurnEntry {
            epoch_end,
            churned_peers,
            total_peers,
            churned_rate_pct,
            high_churn,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_churn_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_churn).count()
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
        let mut prev = PEER_CHURN_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.churned_peers,
                e.total_peers,
                e.churned_rate_pct,
                e.high_churn,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPeerChurnLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_high_churn_true() {
        let mut log = GossipPeerChurnLog::new();
        let entry = log.record(1000, 30, 100);
        assert_eq!(entry.epoch_end, 1000);
        assert_eq!(entry.churned_peers, 30);
        assert_eq!(entry.total_peers, 100);
        assert_eq!(entry.churned_rate_pct, 30);
        assert_eq!(entry.high_churn, true);
    }

    #[test]
    fn test_flag_false_when_exactly_at_threshold() {
        let mut log = GossipPeerChurnLog::new();
        // 25 churned out of 100 → rate = 25, which is NOT > 25
        let entry = log.record(2000, 25, 100);
        assert_eq!(entry.churned_rate_pct, 25);
        assert_eq!(entry.high_churn, false);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipPeerChurnLog::new();
        // 200 churned out of 100 → raw rate = 200, capped at 100
        let entry = log.record(3000, 200, 100);
        assert_eq!(entry.churned_rate_pct, 100);
        assert_eq!(entry.high_churn, true);
    }

    #[test]
    fn test_total_peers_zero_no_div_by_zero() {
        let mut log = GossipPeerChurnLog::new();
        let entry = log.record(4000, 5, 0);
        // denom = max(0, 1) = 1, rate = 500 capped at 100
        assert_eq!(entry.churned_rate_pct, 100);
        assert_eq!(entry.high_churn, true);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(HIGH_CHURN_THRESHOLD, 25);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipPeerChurnLog::new();
        let entry = log.record(5000, 10, 100);
        assert_ne!(entry.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_equals_genesis() {
        let mut log = GossipPeerChurnLog::new();
        let entry = log.record(6000, 5, 50);
        assert_eq!(entry.prev_hash, PEER_CHURN_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipPeerChurnLog::new();
        log.record(7000, 5, 50);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 10, 50);
        let second = &log.entries[1];
        assert_eq!(second.prev_hash, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipPeerChurnLog::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_one_entry() {
        let mut log = GossipPeerChurnLog::new();
        log.record(9000, 5, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipPeerChurnLog::new();
        log.record(10000, 5, 100);
        log.record(11000, 10, 100);
        log.record(12000, 30, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipPeerChurnLog::new();
        log.record(13000, 5, 100);
        log.record(14000, 10, 100);
        // Tamper entry 0's churned_peers
        log.entries[0].churned_peers = 99;
        let (ok, idx) = log.verify_chain();
        assert_eq!(ok, false);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipPeerChurnLog::new();
        log.record(15000, 5, 100);
        log.record(16000, 10, 100);
        log.record(17000, 20, 100);
        // Tamper entry 1's churned_rate_pct
        log.entries[1].churned_rate_pct = 99;
        let (ok, idx) = log.verify_chain();
        assert_eq!(ok, false);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipPeerChurnLog::new();
        let mut log2 = GossipPeerChurnLog::new();
        let mut log3 = GossipPeerChurnLog::new();
        log1.record(18000, 15, 100);
        log2.record(18000, 15, 100);
        log3.record(18000, 15, 100);
        assert_eq!(log1.entries[0].entry_hash, log2.entries[0].entry_hash);
        assert_eq!(log2.entries[0].entry_hash, log3.entries[0].entry_hash);
    }

    #[test]
    fn test_high_churn_count_mixed_log() {
        let mut log = GossipPeerChurnLog::new();
        log.record(19000, 5, 100);   // 5% → false
        log.record(20000, 26, 100);  // 26% → true
        log.record(21000, 25, 100);  // 25% → false (boundary)
        log.record(22000, 50, 100);  // 50% → true
        assert_eq!(log.high_churn_count(), 2);
    }

    #[test]
    fn test_total_churned_peers_sums_correctly() {
        let mut log = GossipPeerChurnLog::new();
        log.record(23000, 10, 100);
        log.record(24000, 20, 100);
        log.record(25000, 30, 100);
        assert_eq!(log.total_churned_peers(), 60u64);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipPeerChurnLog::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry_correct() {
        let mut log = GossipPeerChurnLog::new();
        log.record(26000, 10, 100); // rate = 10
        log.record(27000, 20, 100); // rate = 20
        log.record(28000, 30, 100); // rate = 30
        // mean = (10 + 20 + 30) / 3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn test_default_zero_entries() {
        let log = GossipPeerChurnLog::default();
        assert_eq!(log.entries.len(), 0);
    }
}