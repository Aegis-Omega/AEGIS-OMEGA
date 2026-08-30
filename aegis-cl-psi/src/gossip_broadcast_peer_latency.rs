//! Gate 431 — Gossip Broadcast Peer Latency Monitor (T2)
//! Tracks peer latency rate per gossip broadcast epoch.
//! EXCESSIVE_LATENCY_THRESHOLD = 20: rate_pct > 20 → excessive_latency

use sha2::{Sha256, Digest};

pub const PEER_LATENCY_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const EXCESSIVE_LATENCY_THRESHOLD: u32 = 20;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPeerLatencyEntry {
    pub epoch_end:           u64,
    pub high_latency_peers:  u32,
    pub total_peers:         u32,
    pub high_latency_rate_pct: u32,
    pub excessive_latency:   bool,
    pub entry_hash:          [u8; 32],
    pub prev_hash:           [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    high_latency_peers: u32,
    total_peers: u32,
    rate_pct: u32,
    excessive_latency: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(high_latency_peers.to_be_bytes());
    h.update(total_peers.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([excessive_latency as u8]);
    h.finalize().into()
}

pub struct GossipPeerLatencyLog {
    pub entries: Vec<GossipPeerLatencyEntry>,
}

impl GossipPeerLatencyLog {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        high_latency_peers: u32,
        total_peers: u32,
    ) -> &GossipPeerLatencyEntry {
        let denom = total_peers.max(1) as u64;
        let high_latency_rate_pct = ((high_latency_peers as u64).saturating_mul(100) / denom)
            .min(100) as u32;
        let excessive_latency = high_latency_rate_pct > EXCESSIVE_LATENCY_THRESHOLD;
        let prev = self
            .entries
            .last()
            .map(|e| e.entry_hash)
            .unwrap_or(PEER_LATENCY_GENESIS_HASH);
        let entry_hash = compute_hash(
            &prev,
            epoch_end,
            high_latency_peers,
            total_peers,
            high_latency_rate_pct,
            excessive_latency,
        );
        self.entries.push(GossipPeerLatencyEntry {
            epoch_end,
            high_latency_peers,
            total_peers,
            high_latency_rate_pct,
            excessive_latency,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn excessive_latency_count(&self) -> usize {
        self.entries.iter().filter(|e| e.excessive_latency).count()
    }

    pub fn total_high_latency_peers(&self) -> u64 {
        self.entries.iter().map(|e| e.high_latency_peers as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.high_latency_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = PEER_LATENCY_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.high_latency_peers,
                e.total_peers,
                e.high_latency_rate_pct,
                e.excessive_latency,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPeerLatencyLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipPeerLatencyLog::new();
        // 30 out of 100 => rate_pct = 30 > 20 => excessive_latency = true
        let e = log.record(1000, 30, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.high_latency_peers, 30);
        assert_eq!(e.total_peers, 100);
        assert_eq!(e.high_latency_rate_pct, 30);
        assert!(e.excessive_latency);
    }

    #[test]
    fn test_flag_false_when_exactly_at_threshold() {
        let mut log = GossipPeerLatencyLog::new();
        // 20 out of 100 => rate_pct = 20, not > 20 => excessive_latency = false
        let e = log.record(2000, 20, 100);
        assert_eq!(e.high_latency_rate_pct, 20);
        assert!(!e.excessive_latency);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipPeerLatencyLog::new();
        // 200 out of 100 => would be 200 but capped at 100
        let e = log.record(3000, 200, 100);
        assert_eq!(e.high_latency_rate_pct, 100);
        assert!(e.excessive_latency);
    }

    #[test]
    fn test_total_peers_zero_no_div_by_zero() {
        let mut log = GossipPeerLatencyLog::new();
        // total_peers = 0 => denom = max(0,1) = 1 => rate = 0
        let e = log.record(4000, 0, 0);
        assert_eq!(e.high_latency_rate_pct, 0);
        assert!(!e.excessive_latency);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(EXCESSIVE_LATENCY_THRESHOLD, 20);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipPeerLatencyLog::new();
        let e = log.record(5000, 10, 50);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_equals_genesis() {
        let mut log = GossipPeerLatencyLog::new();
        let e = log.record(6000, 5, 25);
        assert_eq!(e.prev_hash, PEER_LATENCY_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipPeerLatencyLog::new();
        log.record(7000, 5, 25);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 10, 50);
        let second_prev = log.entries[1].prev_hash;
        assert_eq!(second_prev, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipPeerLatencyLog::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_one_entry() {
        let mut log = GossipPeerLatencyLog::new();
        log.record(9000, 3, 15);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipPeerLatencyLog::new();
        log.record(10000, 5, 20);
        log.record(11000, 8, 40);
        log.record(12000, 12, 60);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipPeerLatencyLog::new();
        log.record(13000, 5, 20);
        log.record(14000, 8, 40);
        // Tamper entry 0's hash
        log.entries[0].entry_hash = [0xABu8; 32];
        let result = log.verify_chain();
        assert_eq!(result, (false, Some(0)));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipPeerLatencyLog::new();
        log.record(15000, 5, 20);
        log.record(16000, 8, 40);
        log.record(17000, 12, 60);
        // Tamper entry 1's high_latency_peers to break content hash
        log.entries[1].high_latency_peers = 99;
        let result = log.verify_chain();
        assert_eq!(result, (false, Some(1)));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipPeerLatencyLog::new();
        let e1 = log1.record(18000, 7, 35).clone();

        let mut log2 = GossipPeerLatencyLog::new();
        let e2 = log2.record(18000, 7, 35).clone();

        let mut log3 = GossipPeerLatencyLog::new();
        let e3 = log3.record(18000, 7, 35).clone();

        assert_eq!(e1.entry_hash, e2.entry_hash);
        assert_eq!(e2.entry_hash, e3.entry_hash);
    }

    #[test]
    fn test_excessive_latency_count_mixed_log() {
        let mut log = GossipPeerLatencyLog::new();
        // rate = 10 => not excessive
        log.record(19000, 10, 100);
        // rate = 21 => excessive
        log.record(20000, 21, 100);
        // rate = 30 => excessive
        log.record(21000, 30, 100);
        // rate = 20 => not excessive (boundary)
        log.record(22000, 20, 100);
        assert_eq!(log.excessive_latency_count(), 2);
    }

    #[test]
    fn test_total_high_latency_peers_sums_correctly() {
        let mut log = GossipPeerLatencyLog::new();
        log.record(23000, 5, 50);
        log.record(24000, 10, 50);
        log.record(25000, 15, 50);
        assert_eq!(log.total_high_latency_peers(), 30u64);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipPeerLatencyLog::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry_correct() {
        let mut log = GossipPeerLatencyLog::new();
        // rate = 10
        log.record(26000, 10, 100);
        // rate = 20
        log.record(27000, 20, 100);
        // rate = 30
        log.record(28000, 30, 100);
        // mean = (10 + 20 + 30) / 3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn test_default_zero_entries() {
        let log = GossipPeerLatencyLog::default();
        assert_eq!(log.entries.len(), 0);
    }
}