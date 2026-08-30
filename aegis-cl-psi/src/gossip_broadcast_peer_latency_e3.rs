//! Gate 460 — Gossip Broadcast Peer Latency E3 Monitor (T2)
//! Tracks peer latency e3 rate per gossip broadcast epoch.
//! EXCESSIVE_LATENCY_E3_THRESHOLD = 20: rate_pct > 20 → excessive_latency_e3

use sha2::{Sha256, Digest};

pub const PEER_LATENCY_E3_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const EXCESSIVE_LATENCY_E3_THRESHOLD: u32 = 20;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPeerLatencyE3Entry {
    pub epoch_end:             u64,
    pub high_latency_peers:    u32,
    pub total_peers:           u32,
    pub high_latency_rate_pct: u32,
    pub excessive_latency_e3:  bool,
    pub entry_hash:            [u8; 32],
    pub prev_hash:             [u8; 32],
}

fn compute_hash(
    prev:               &[u8; 32],
    epoch_end:          u64,
    high_latency_peers: u32,
    total_peers:        u32,
    rate_pct:           u32,
    excessive:          bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(high_latency_peers.to_be_bytes());
    h.update(total_peers.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([excessive as u8]);
    h.finalize().into()
}

pub struct GossipPeerLatencyE3Log {
    pub entries: Vec<GossipPeerLatencyE3Entry>,
}

impl GossipPeerLatencyE3Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end:          u64,
        high_latency_peers: u32,
        total_peers:        u32,
    ) -> &GossipPeerLatencyE3Entry {
        let denom = total_peers.max(1) as u64;
        let rate_pct = ((high_latency_peers as u64).saturating_mul(100) / denom)
            .min(100) as u32;
        let excessive_latency_e3 = rate_pct > EXCESSIVE_LATENCY_E3_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(PEER_LATENCY_E3_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, high_latency_peers, total_peers, rate_pct, excessive_latency_e3);
        self.entries.push(GossipPeerLatencyE3Entry {
            epoch_end,
            high_latency_peers,
            total_peers,
            high_latency_rate_pct: rate_pct,
            excessive_latency_e3,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn excessive_latency_e3_count(&self) -> usize {
        self.entries.iter().filter(|e| e.excessive_latency_e3).count()
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
        let mut prev = PEER_LATENCY_E3_GENESIS_HASH;
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
                e.excessive_latency_e3,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPeerLatencyE3Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_flag_true() {
        let mut log = GossipPeerLatencyE3Log::new();
        let e = log.record(1000, 30, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.high_latency_peers, 30);
        assert_eq!(e.total_peers, 100);
        assert_eq!(e.high_latency_rate_pct, 30);
        assert!(e.excessive_latency_e3);
    }

    #[test]
    fn test_flag_false_when_exactly_at_threshold() {
        let mut log = GossipPeerLatencyE3Log::new();
        // rate_pct == 20, which is NOT > 20
        let e = log.record(2000, 20, 100);
        assert_eq!(e.high_latency_rate_pct, 20);
        assert!(!e.excessive_latency_e3);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipPeerLatencyE3Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.high_latency_rate_pct, 100);
    }

    #[test]
    fn test_total_peers_zero_no_div_by_zero() {
        let mut log = GossipPeerLatencyE3Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.high_latency_rate_pct, 0);
        assert!(!e.excessive_latency_e3);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(EXCESSIVE_LATENCY_E3_THRESHOLD, 20);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipPeerLatencyE3Log::new();
        let e = log.record(5000, 50, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipPeerLatencyE3Log::new();
        let e = log.record(6000, 10, 100);
        assert_eq!(e.prev_hash, PEER_LATENCY_E3_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipPeerLatencyE3Log::new();
        log.record(7000, 10, 100);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 15, 100);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipPeerLatencyE3Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_one_entry() {
        let mut log = GossipPeerLatencyE3Log::new();
        log.record(9000, 5, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipPeerLatencyE3Log::new();
        log.record(10000, 5, 100);
        log.record(11000, 10, 100);
        log.record(12000, 25, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipPeerLatencyE3Log::new();
        log.record(13000, 5, 100);
        log.record(14000, 10, 100);
        log.entries[0].high_latency_peers = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipPeerLatencyE3Log::new();
        log.record(15000, 5, 100);
        log.record(16000, 10, 100);
        log.record(17000, 25, 100);
        log.entries[1].high_latency_peers = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipPeerLatencyE3Log::new();
        let mut log2 = GossipPeerLatencyE3Log::new();
        let mut log3 = GossipPeerLatencyE3Log::new();
        log1.record(18000, 30, 100);
        log2.record(18000, 30, 100);
        log3.record(18000, 30, 100);
        assert_eq!(log1.entries[0].entry_hash, log2.entries[0].entry_hash);
        assert_eq!(log2.entries[0].entry_hash, log3.entries[0].entry_hash);
    }

    #[test]
    fn test_excessive_latency_e3_count_mixed() {
        let mut log = GossipPeerLatencyE3Log::new();
        log.record(19000, 5, 100);   // 5%  → false
        log.record(20000, 21, 100);  // 21% → true
        log.record(21000, 20, 100);  // 20% → false
        log.record(22000, 50, 100);  // 50% → true
        assert_eq!(log.excessive_latency_e3_count(), 2);
    }

    #[test]
    fn test_total_high_latency_peers_sums_correctly() {
        let mut log = GossipPeerLatencyE3Log::new();
        log.record(23000, 10, 100);
        log.record(24000, 20, 100);
        log.record(25000, 30, 100);
        assert_eq!(log.total_high_latency_peers(), 60);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipPeerLatencyE3Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry_correct() {
        let mut log = GossipPeerLatencyE3Log::new();
        log.record(26000, 10, 100); // 10%
        log.record(27000, 30, 100); // 30%
        log.record(28000, 50, 100); // 50%
        // mean = (10 + 30 + 50) / 3 = 30
        assert_eq!(log.mean_rate_pct(), 30);
    }

    #[test]
    fn test_default_zero_entries() {
        let log = GossipPeerLatencyE3Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}