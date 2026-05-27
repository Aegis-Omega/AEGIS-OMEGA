//! Gate 452 — Gossip Broadcast Peer Isolation Monitor (T2)
//! Tracks peer isolation rate per gossip broadcast epoch.
//! PEER_ISOLATED_THRESHOLD = 10: rate_pct > 10 → peer_isolated

use sha2::{Sha256, Digest};

pub const PEER_ISOLATION_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const PEER_ISOLATED_THRESHOLD: u32 = 10;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPeerIsolationEntry {
    pub epoch_end:        u64,
    pub isolated_peers:   u32,
    pub total_peers:      u32,
    pub isolated_rate_pct: u32,
    pub peer_isolated:    bool,
    pub entry_hash:       [u8; 32],
    pub prev_hash:        [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    isolated_peers: u32,
    total_peers: u32,
    isolated_rate_pct: u32,
    peer_isolated: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(isolated_peers.to_be_bytes());
    h.update(total_peers.to_be_bytes());
    h.update(isolated_rate_pct.to_be_bytes());
    h.update([peer_isolated as u8]);
    h.finalize().into()
}

pub struct GossipPeerIsolationLog {
    pub entries: Vec<GossipPeerIsolationEntry>,
}

impl GossipPeerIsolationLog {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(&mut self, epoch_end: u64, isolated_peers: u32, total_peers: u32) -> &GossipPeerIsolationEntry {
        let denom = total_peers.max(1) as u64;
        let isolated_rate_pct = ((isolated_peers as u64).saturating_mul(100) / denom).min(100) as u32;
        let peer_isolated = isolated_rate_pct > PEER_ISOLATED_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(PEER_ISOLATION_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, isolated_peers, total_peers, isolated_rate_pct, peer_isolated);
        self.entries.push(GossipPeerIsolationEntry {
            epoch_end,
            isolated_peers,
            total_peers,
            isolated_rate_pct,
            peer_isolated,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn peer_isolated_count(&self) -> usize {
        self.entries.iter().filter(|e| e.peer_isolated).count()
    }

    pub fn total_isolated_peers(&self) -> u64 {
        self.entries.iter().map(|e| e.isolated_peers as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.isolated_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = PEER_ISOLATION_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(&prev, e.epoch_end, e.isolated_peers, e.total_peers, e.isolated_rate_pct, e.peer_isolated);
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPeerIsolationLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_flag_true() {
        let mut log = GossipPeerIsolationLog::new();
        let e = log.record(1000, 20, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.isolated_peers, 20);
        assert_eq!(e.total_peers, 100);
        assert_eq!(e.isolated_rate_pct, 20);
        assert!(e.peer_isolated);
    }

    #[test]
    fn test_flag_false_when_exactly_at_threshold() {
        let mut log = GossipPeerIsolationLog::new();
        // rate = (10 * 100) / 100 = 10, which is NOT > 10, so peer_isolated = false
        let e = log.record(2000, 10, 100);
        assert_eq!(e.isolated_rate_pct, 10);
        assert!(!e.peer_isolated);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipPeerIsolationLog::new();
        // isolated_peers > total_peers => rate > 100 => capped at 100
        let e = log.record(3000, 200, 100);
        assert_eq!(e.isolated_rate_pct, 100);
    }

    #[test]
    fn test_total_peers_zero_no_div_by_zero() {
        let mut log = GossipPeerIsolationLog::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.isolated_rate_pct, 0);
        assert!(!e.peer_isolated);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(PEER_ISOLATED_THRESHOLD, 10);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipPeerIsolationLog::new();
        let e = log.record(5000, 5, 50);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipPeerIsolationLog::new();
        let e = log.record(6000, 3, 30);
        assert_eq!(e.prev_hash, PEER_ISOLATION_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipPeerIsolationLog::new();
        log.record(7000, 1, 10);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 2, 10);
        let second = &log.entries[1];
        assert_eq!(second.prev_hash, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipPeerIsolationLog::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_one_entry() {
        let mut log = GossipPeerIsolationLog::new();
        log.record(9000, 5, 50);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipPeerIsolationLog::new();
        log.record(10000, 5, 50);
        log.record(11000, 10, 50);
        log.record(12000, 15, 50);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipPeerIsolationLog::new();
        log.record(13000, 5, 50);
        log.record(14000, 10, 50);
        log.entries[0].isolated_peers = 99;
        let (valid, idx) = log.verify_chain();
        assert!(!valid);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipPeerIsolationLog::new();
        log.record(15000, 5, 50);
        log.record(16000, 10, 50);
        log.entries[1].isolated_peers = 99;
        let (valid, idx) = log.verify_chain();
        assert!(!valid);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipPeerIsolationLog::new();
        let e1 = log1.record(17000, 7, 70).clone();

        let mut log2 = GossipPeerIsolationLog::new();
        let e2 = log2.record(17000, 7, 70).clone();

        let mut log3 = GossipPeerIsolationLog::new();
        let e3 = log3.record(17000, 7, 70).clone();

        assert_eq!(e1.entry_hash, e2.entry_hash);
        assert_eq!(e2.entry_hash, e3.entry_hash);
    }

    #[test]
    fn test_peer_isolated_count_mixed_log() {
        let mut log = GossipPeerIsolationLog::new();
        // rate = 0, flag false
        log.record(18000, 0, 100);
        // rate = 50, flag true
        log.record(19000, 50, 100);
        // rate = 10, flag false (exactly at threshold)
        log.record(20000, 10, 100);
        // rate = 11, flag true
        log.record(21000, 11, 100);
        assert_eq!(log.peer_isolated_count(), 2);
    }

    #[test]
    fn test_total_isolated_peers_sums_correctly() {
        let mut log = GossipPeerIsolationLog::new();
        log.record(22000, 5, 100);
        log.record(23000, 15, 100);
        log.record(24000, 25, 100);
        assert_eq!(log.total_isolated_peers(), 45u64);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipPeerIsolationLog::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry_correct() {
        let mut log = GossipPeerIsolationLog::new();
        // rate = 10
        log.record(25000, 10, 100);
        // rate = 20
        log.record(26000, 20, 100);
        // rate = 30
        log.record(27000, 30, 100);
        // mean = (10 + 20 + 30) / 3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn test_default_has_zero_entries() {
        let log = GossipPeerIsolationLog::default();
        assert_eq!(log.entries.len(), 0);
    }
}