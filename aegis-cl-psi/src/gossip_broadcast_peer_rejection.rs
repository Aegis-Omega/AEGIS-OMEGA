//! Gate 449 — Gossip Broadcast Peer Rejection Monitor (T2)
//! Tracks peer rejection rate per gossip broadcast epoch.
//! HIGH_REJECTION_THRESHOLD = 10: rate_pct > 10 → high_rejection

use sha2::{Sha256, Digest};

pub const PEER_REJECTION_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_REJECTION_THRESHOLD: u32 = 10;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPeerRejectionEntry {
    pub epoch_end:        u64,
    pub rejected_peers:   u32,
    pub total_peers:      u32,
    pub rejected_rate_pct: u32,
    pub high_rejection:   bool,
    pub entry_hash:       [u8; 32],
    pub prev_hash:        [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    rejected_peers: u32,
    total_peers: u32,
    rate_pct: u32,
    high_rejection: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(rejected_peers.to_be_bytes());
    h.update(total_peers.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_rejection as u8]);
    h.finalize().into()
}

pub struct GossipPeerRejectionLog {
    pub entries: Vec<GossipPeerRejectionEntry>,
}

impl GossipPeerRejectionLog {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        rejected_peers: u32,
        total_peers: u32,
    ) -> &GossipPeerRejectionEntry {
        let denom = total_peers.max(1) as u64;
        let rejected_rate_pct = ((rejected_peers as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_rejection = rejected_rate_pct > HIGH_REJECTION_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(PEER_REJECTION_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, rejected_peers, total_peers, rejected_rate_pct, high_rejection);
        self.entries.push(GossipPeerRejectionEntry {
            epoch_end,
            rejected_peers,
            total_peers,
            rejected_rate_pct,
            high_rejection,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_rejection_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_rejection).count()
    }

    pub fn total_rejected_peers(&self) -> u64 {
        self.entries.iter().map(|e| e.rejected_peers as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.rejected_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = PEER_REJECTION_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(&prev, e.epoch_end, e.rejected_peers, e.total_peers, e.rejected_rate_pct, e.high_rejection);
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPeerRejectionLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_high_rejection_true() {
        let mut log = GossipPeerRejectionLog::new();
        let e = log.record(1000, 50, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.rejected_peers, 50);
        assert_eq!(e.total_peers, 100);
        assert_eq!(e.rejected_rate_pct, 50);
        assert!(e.high_rejection);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipPeerRejectionLog::new();
        // rate_pct == 10 → NOT > 10, so high_rejection = false
        let e = log.record(2000, 10, 100);
        assert_eq!(e.rejected_rate_pct, 10);
        assert!(!e.high_rejection);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipPeerRejectionLog::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.rejected_rate_pct, 100);
        assert!(e.high_rejection);
    }

    #[test]
    fn total_peers_zero_no_div_by_zero() {
        let mut log = GossipPeerRejectionLog::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.rejected_rate_pct, 0);
        assert!(!e.high_rejection);
    }

    #[test]
    fn threshold_constant_value_is_10() {
        assert_eq!(HIGH_REJECTION_THRESHOLD, 10);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipPeerRejectionLog::new();
        let e = log.record(5000, 5, 50);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipPeerRejectionLog::new();
        log.record(6000, 3, 30);
        assert_eq!(log.entries[0].prev_hash, PEER_REJECTION_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipPeerRejectionLog::new();
        log.record(7000, 3, 30);
        log.record(8000, 4, 40);
        assert_eq!(log.entries[1].prev_hash, log.entries[0].entry_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipPeerRejectionLog::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipPeerRejectionLog::new();
        log.record(9000, 2, 20);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipPeerRejectionLog::new();
        log.record(10000, 1, 10);
        log.record(11000, 2, 20);
        log.record(12000, 3, 30);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipPeerRejectionLog::new();
        log.record(13000, 5, 50);
        log.record(14000, 6, 60);
        log.entries[0].rejected_peers = 99;
        let result = log.verify_chain();
        assert_eq!(result, (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipPeerRejectionLog::new();
        log.record(15000, 5, 50);
        log.record(16000, 6, 60);
        log.entries[1].rejected_peers = 99;
        let result = log.verify_chain();
        assert_eq!(result, (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut log1 = GossipPeerRejectionLog::new();
        let e1 = log1.record(17000, 7, 70).entry_hash;

        let mut log2 = GossipPeerRejectionLog::new();
        let e2 = log2.record(17000, 7, 70).entry_hash;

        let mut log3 = GossipPeerRejectionLog::new();
        let e3 = log3.record(17000, 7, 70).entry_hash;

        assert_eq!(e1, e2);
        assert_eq!(e2, e3);
    }

    #[test]
    fn high_rejection_count_mixed_log() {
        let mut log = GossipPeerRejectionLog::new();
        log.record(18000, 1, 100);  // 1% → false
        log.record(19000, 50, 100); // 50% → true
        log.record(20000, 10, 100); // 10% → false (not > 10)
        log.record(21000, 11, 100); // 11% → true
        assert_eq!(log.high_rejection_count(), 2);
    }

    #[test]
    fn total_rejected_peers_sums_correctly() {
        let mut log = GossipPeerRejectionLog::new();
        log.record(22000, 10, 100);
        log.record(23000, 20, 200);
        log.record(24000, 30, 300);
        assert_eq!(log.total_rejected_peers(), 60);
    }

    #[test]
    fn mean_rate_pct_empty_returns_0() {
        let log = GossipPeerRejectionLog::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn mean_rate_pct_multi_entry_correct() {
        let mut log = GossipPeerRejectionLog::new();
        log.record(25000, 20, 100); // 20%
        log.record(26000, 40, 100); // 40%
        log.record(27000, 60, 100); // 60%
        // mean = (20 + 40 + 60) / 3 = 40
        assert_eq!(log.mean_rate_pct(), 40);
    }

    #[test]
    fn default_produces_zero_entries() {
        let log = GossipPeerRejectionLog::default();
        assert_eq!(log.entries.len(), 0);
    }
}