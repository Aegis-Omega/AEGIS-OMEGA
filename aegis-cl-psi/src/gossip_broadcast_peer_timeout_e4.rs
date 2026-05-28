//! Gate 527 — Gossip Broadcast Peer Timeout E4 Monitor (T2)
//! Tracks peer timeout rate per gossip broadcast epoch.
//! HIGH_PEER_TIMEOUT_E4_THRESHOLD = 8: timeout_rate_pct > 8 → high_peer_timeout_e4

use sha2::{Sha256, Digest};

pub const PEER_TIMEOUT_E4_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_PEER_TIMEOUT_E4_THRESHOLD: u32 = 8;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPeerTimeoutE4Entry {
    pub epoch_end:          u64,
    pub timed_out_peers:    u32,
    pub total_peers:        u32,
    pub timeout_rate_pct:   u32,
    pub high_peer_timeout_e4: bool,
    pub entry_hash:         [u8; 32],
    pub prev_hash:          [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    timed_out_peers: u32,
    total_peers: u32,
    rate_pct: u32,
    high_peer_timeout_e4: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(timed_out_peers.to_be_bytes());
    h.update(total_peers.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_peer_timeout_e4 as u8]);
    h.finalize().into()
}

pub struct GossipPeerTimeoutE4Log {
    pub entries: Vec<GossipPeerTimeoutE4Entry>,
}

impl GossipPeerTimeoutE4Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        timed_out_peers: u32,
        total_peers: u32,
    ) -> &GossipPeerTimeoutE4Entry {
        let denom = total_peers.max(1) as u64;
        let timeout_rate_pct =
            ((timed_out_peers as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_peer_timeout_e4 = timeout_rate_pct > HIGH_PEER_TIMEOUT_E4_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(PEER_TIMEOUT_E4_GENESIS_HASH);
        let entry_hash = compute_hash(
            &prev,
            epoch_end,
            timed_out_peers,
            total_peers,
            timeout_rate_pct,
            high_peer_timeout_e4,
        );
        self.entries.push(GossipPeerTimeoutE4Entry {
            epoch_end,
            timed_out_peers,
            total_peers,
            timeout_rate_pct,
            high_peer_timeout_e4,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_peer_timeout_e4_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_peer_timeout_e4).count()
    }

    pub fn total_timed_out_peers(&self) -> u64 {
        self.entries.iter().map(|e| e.timed_out_peers as u64).sum()
    }

    pub fn mean_timeout_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.timeout_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = PEER_TIMEOUT_E4_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.timed_out_peers,
                e.total_peers,
                e.timeout_rate_pct,
                e.high_peer_timeout_e4,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPeerTimeoutE4Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipPeerTimeoutE4Log::new();
        let e = log.record(1000, 12, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.timed_out_peers, 12);
        assert_eq!(e.total_peers, 100);
        assert_eq!(e.timeout_rate_pct, 12);
        assert!(e.high_peer_timeout_e4);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipPeerTimeoutE4Log::new();
        // rate = (8 * 100) / 100 = 8, not > 8
        let e = log.record(2000, 8, 100);
        assert_eq!(e.timeout_rate_pct, 8);
        assert!(!e.high_peer_timeout_e4);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipPeerTimeoutE4Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.timeout_rate_pct, 100);
        assert!(e.high_peer_timeout_e4);
    }

    #[test]
    fn total_peers_zero_no_div_by_zero() {
        let mut log = GossipPeerTimeoutE4Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.timeout_rate_pct, 0);
        assert!(!e.high_peer_timeout_e4);
    }

    #[test]
    fn threshold_constant_value_is_8() {
        assert_eq!(HIGH_PEER_TIMEOUT_E4_THRESHOLD, 8);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipPeerTimeoutE4Log::new();
        let e = log.record(5000, 10, 80);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipPeerTimeoutE4Log::new();
        let e = log.record(6000, 5, 80);
        assert_eq!(e.prev_hash, PEER_TIMEOUT_E4_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipPeerTimeoutE4Log::new();
        log.record(7000, 5, 80);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 12, 100);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipPeerTimeoutE4Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipPeerTimeoutE4Log::new();
        log.record(9000, 9, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipPeerTimeoutE4Log::new();
        log.record(10000, 5, 60);
        log.record(11000, 9, 80);
        log.record(12000, 14, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipPeerTimeoutE4Log::new();
        log.record(13000, 5, 80);
        log.record(14000, 12, 100);
        log.entries[0].timed_out_peers = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipPeerTimeoutE4Log::new();
        log.record(15000, 5, 80);
        log.record(16000, 12, 100);
        log.entries[1].timed_out_peers = 99;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut log1 = GossipPeerTimeoutE4Log::new();
        let mut log2 = GossipPeerTimeoutE4Log::new();
        let mut log3 = GossipPeerTimeoutE4Log::new();
        let e1 = log1.record(17000, 10, 90).entry_hash;
        let e2 = log2.record(17000, 10, 90).entry_hash;
        let e3 = log3.record(17000, 10, 90).entry_hash;
        assert_eq!(e1, e2);
        assert_eq!(e2, e3);
    }

    #[test]
    fn high_peer_timeout_e4_count_mixed_log() {
        let mut log = GossipPeerTimeoutE4Log::new();
        log.record(18000, 6, 100);  // rate=6,  false
        log.record(19000, 20, 100); // rate=20, true
        log.record(20000, 8, 100);  // rate=8,  false (boundary)
        log.record(21000, 9, 100);  // rate=9,  true
        assert_eq!(log.high_peer_timeout_e4_count(), 2);
    }

    #[test]
    fn total_timed_out_peers_sums_correctly() {
        let mut log = GossipPeerTimeoutE4Log::new();
        log.record(22000, 10, 100);
        log.record(23000, 25, 100);
        log.record(24000, 7, 100);
        assert_eq!(log.total_timed_out_peers(), 42);
    }

    #[test]
    fn mean_timeout_rate_pct_empty_returns_zero() {
        let log = GossipPeerTimeoutE4Log::new();
        assert_eq!(log.mean_timeout_rate_pct(), 0);
    }

    #[test]
    fn mean_timeout_rate_pct_multi_entry_correct() {
        let mut log = GossipPeerTimeoutE4Log::new();
        log.record(25000, 10, 100); // rate=10
        log.record(26000, 20, 100); // rate=20
        log.record(27000, 30, 100); // rate=30
        assert_eq!(log.mean_timeout_rate_pct(), 20);
    }

    #[test]
    fn default_produces_zero_entries() {
        let log = GossipPeerTimeoutE4Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}
