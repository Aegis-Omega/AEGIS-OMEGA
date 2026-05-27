//! Gate 457 — Gossip Broadcast Peer Timeout Monitor (T2)
//! Tracks peer timeout rate per gossip broadcast epoch.
//! HIGH_PEER_TIMEOUT_THRESHOLD = 10: rate_pct > 10 → high_peer_timeout

use sha2::{Sha256, Digest};

pub const PEER_TIMEOUT_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_PEER_TIMEOUT_THRESHOLD: u32 = 10;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPeerTimeoutEntry {
    pub epoch_end:          u64,
    pub timed_out_peers:    u32,
    pub total_peers:        u32,
    pub timed_out_rate_pct: u32,
    pub high_peer_timeout:  bool,
    pub entry_hash:         [u8; 32],
    pub prev_hash:          [u8; 32],
}

fn compute_hash(
    prev:               &[u8; 32],
    epoch_end:          u64,
    timed_out_peers:    u32,
    total_peers:        u32,
    rate_pct:           u32,
    high_peer_timeout:  bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(timed_out_peers.to_be_bytes());
    h.update(total_peers.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_peer_timeout as u8]);
    h.finalize().into()
}

pub struct GossipPeerTimeoutLog {
    pub entries: Vec<GossipPeerTimeoutEntry>,
}

impl GossipPeerTimeoutLog {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end:       u64,
        timed_out_peers: u32,
        total_peers:     u32,
    ) -> &GossipPeerTimeoutEntry {
        let denom = total_peers.max(1) as u64;
        let timed_out_rate_pct = ((timed_out_peers as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_peer_timeout = timed_out_rate_pct > HIGH_PEER_TIMEOUT_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(PEER_TIMEOUT_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, timed_out_peers, total_peers, timed_out_rate_pct, high_peer_timeout);
        self.entries.push(GossipPeerTimeoutEntry {
            epoch_end,
            timed_out_peers,
            total_peers,
            timed_out_rate_pct,
            high_peer_timeout,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_peer_timeout_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_peer_timeout).count()
    }

    pub fn total_timed_out_peers(&self) -> u64 {
        self.entries.iter().map(|e| e.timed_out_peers as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.timed_out_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = PEER_TIMEOUT_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(&prev, e.epoch_end, e.timed_out_peers, e.total_peers, e.timed_out_rate_pct, e.high_peer_timeout);
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPeerTimeoutLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_flag_true() {
        let mut log = GossipPeerTimeoutLog::new();
        let e = log.record(1000, 15, 50);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.timed_out_peers, 15);
        assert_eq!(e.total_peers, 50);
        assert_eq!(e.timed_out_rate_pct, 30);
        assert!(e.high_peer_timeout);
    }

    #[test]
    fn test_flag_false_exactly_at_threshold() {
        let mut log = GossipPeerTimeoutLog::new();
        // 10 out of 100 = 10%, not > 10, so false
        let e = log.record(2000, 10, 100);
        assert_eq!(e.timed_out_rate_pct, 10);
        assert!(!e.high_peer_timeout);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipPeerTimeoutLog::new();
        let e = log.record(3000, 200, 50);
        assert_eq!(e.timed_out_rate_pct, 100);
        assert!(e.high_peer_timeout);
    }

    #[test]
    fn test_total_peers_zero_no_div_by_zero() {
        let mut log = GossipPeerTimeoutLog::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.timed_out_rate_pct, 0);
        assert!(!e.high_peer_timeout);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(HIGH_PEER_TIMEOUT_THRESHOLD, 10u32);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipPeerTimeoutLog::new();
        let e = log.record(5000, 5, 20);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipPeerTimeoutLog::new();
        let e = log.record(6000, 3, 30);
        assert_eq!(e.prev_hash, PEER_TIMEOUT_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipPeerTimeoutLog::new();
        log.record(7000, 2, 20);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 4, 40);
        let second_prev = log.entries[1].prev_hash;
        assert_eq!(second_prev, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipPeerTimeoutLog::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_one_entry() {
        let mut log = GossipPeerTimeoutLog::new();
        log.record(9000, 1, 10);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipPeerTimeoutLog::new();
        log.record(10000, 2, 20);
        log.record(11000, 3, 30);
        log.record(12000, 4, 40);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipPeerTimeoutLog::new();
        log.record(13000, 5, 50);
        log.record(14000, 6, 60);
        log.entries[0].timed_out_peers = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipPeerTimeoutLog::new();
        log.record(15000, 7, 70);
        log.record(16000, 8, 80);
        log.entries[1].timed_out_peers = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn test_determinism_same_hash() {
        let mut log1 = GossipPeerTimeoutLog::new();
        let e1 = log1.record(17000, 11, 100).entry_hash;

        let mut log2 = GossipPeerTimeoutLog::new();
        let e2 = log2.record(17000, 11, 100).entry_hash;

        let mut log3 = GossipPeerTimeoutLog::new();
        let e3 = log3.record(17000, 11, 100).entry_hash;

        assert_eq!(e1, e2);
        assert_eq!(e2, e3);
    }

    #[test]
    fn test_high_peer_timeout_count_mixed() {
        let mut log = GossipPeerTimeoutLog::new();
        // 0% → false
        log.record(18000, 0, 100);
        // 10% → false (exactly at threshold, not > threshold)
        log.record(19000, 10, 100);
        // 11% → true
        log.record(20000, 11, 100);
        // 50% → true
        log.record(21000, 50, 100);
        assert_eq!(log.high_peer_timeout_count(), 2);
    }

    #[test]
    fn test_total_timed_out_peers_sums_correctly() {
        let mut log = GossipPeerTimeoutLog::new();
        log.record(22000, 5, 50);
        log.record(23000, 10, 100);
        log.record(24000, 3, 30);
        assert_eq!(log.total_timed_out_peers(), 18u64);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipPeerTimeoutLog::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry() {
        let mut log = GossipPeerTimeoutLog::new();
        // 20 out of 100 = 20%
        log.record(25000, 20, 100);
        // 40 out of 100 = 40%
        log.record(26000, 40, 100);
        // 60 out of 100 = 60%
        log.record(27000, 60, 100);
        // mean = (20 + 40 + 60) / 3 = 40
        assert_eq!(log.mean_rate_pct(), 40);
    }

    #[test]
    fn test_default_zero_entries() {
        let log = GossipPeerTimeoutLog::default();
        assert_eq!(log.entries.len(), 0);
    }
}