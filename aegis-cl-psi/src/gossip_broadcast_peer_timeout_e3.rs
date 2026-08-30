//! Gate 492 — Gossip Broadcast Peer Timeout E3 Monitor (T2)
//! Tracks peer timeout e3 rate per gossip broadcast epoch.
//! HIGH_PEER_TIMEOUT_E3_THRESHOLD = 10: rate_pct > 10 → high_peer_timeout_e3

use sha2::{Sha256, Digest};

pub const PEER_TIMEOUT_E3_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_PEER_TIMEOUT_E3_THRESHOLD: u32 = 10;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPeerTimeoutE3Entry {
    pub epoch_end:            u64,
    pub timed_out_peers:      u32,
    pub total_peers:          u32,
    pub timed_out_rate_pct:   u32,
    pub high_peer_timeout_e3: bool,
    pub entry_hash:           [u8; 32],
    pub prev_hash:            [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    timed_out_peers: u32,
    total_peers: u32,
    rate_pct: u32,
    high_peer_timeout_e3: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(timed_out_peers.to_be_bytes());
    h.update(total_peers.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_peer_timeout_e3 as u8]);
    h.finalize().into()
}

pub struct GossipPeerTimeoutE3Log {
    pub entries: Vec<GossipPeerTimeoutE3Entry>,
}

impl GossipPeerTimeoutE3Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        timed_out_peers: u32,
        total_peers: u32,
    ) -> &GossipPeerTimeoutE3Entry {
        let denom = total_peers.max(1) as u64;
        let timed_out_rate_pct = ((timed_out_peers as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_peer_timeout_e3 = timed_out_rate_pct > HIGH_PEER_TIMEOUT_E3_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(PEER_TIMEOUT_E3_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, timed_out_peers, total_peers, timed_out_rate_pct, high_peer_timeout_e3);
        self.entries.push(GossipPeerTimeoutE3Entry {
            epoch_end,
            timed_out_peers,
            total_peers,
            timed_out_rate_pct,
            high_peer_timeout_e3,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_peer_timeout_e3_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_peer_timeout_e3).count()
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
        let mut prev = PEER_TIMEOUT_E3_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.timed_out_peers,
                e.total_peers,
                e.timed_out_rate_pct,
                e.high_peer_timeout_e3,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPeerTimeoutE3Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_flag_true() {
        let mut log = GossipPeerTimeoutE3Log::new();
        let e = log.record(1000, 15, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.timed_out_peers, 15);
        assert_eq!(e.total_peers, 100);
        assert_eq!(e.timed_out_rate_pct, 15);
        assert!(e.high_peer_timeout_e3);
    }

    #[test]
    fn test_flag_false_when_exactly_at_threshold() {
        let mut log = GossipPeerTimeoutE3Log::new();
        // rate_pct = 10, which is NOT > 10, so flag should be false
        let e = log.record(2000, 10, 100);
        assert_eq!(e.timed_out_rate_pct, 10);
        assert!(!e.high_peer_timeout_e3);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipPeerTimeoutE3Log::new();
        // timed_out_peers > total_peers would give > 100 without cap
        let e = log.record(3000, 200, 100);
        assert_eq!(e.timed_out_rate_pct, 100);
        assert!(e.high_peer_timeout_e3);
    }

    #[test]
    fn test_total_peers_zero_no_div_by_zero() {
        let mut log = GossipPeerTimeoutE3Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.timed_out_rate_pct, 0);
        assert!(!e.high_peer_timeout_e3);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(HIGH_PEER_TIMEOUT_E3_THRESHOLD, 10);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipPeerTimeoutE3Log::new();
        let e = log.record(5000, 5, 50);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipPeerTimeoutE3Log::new();
        let e = log.record(6000, 3, 30);
        assert_eq!(e.prev_hash, PEER_TIMEOUT_E3_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipPeerTimeoutE3Log::new();
        log.record(7000, 3, 30);
        let first_hash = log.entries[0].entry_hash;
        log.record(7001, 5, 50);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipPeerTimeoutE3Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_one_entry() {
        let mut log = GossipPeerTimeoutE3Log::new();
        log.record(8000, 2, 20);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipPeerTimeoutE3Log::new();
        log.record(9000, 1, 10);
        log.record(9001, 2, 20);
        log.record(9002, 3, 30);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipPeerTimeoutE3Log::new();
        log.record(10000, 5, 50);
        log.record(10001, 6, 60);
        log.entries[0].timed_out_peers = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipPeerTimeoutE3Log::new();
        log.record(11000, 5, 50);
        log.record(11001, 6, 60);
        log.entries[1].timed_out_peers = 99;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipPeerTimeoutE3Log::new();
        let h1 = log1.record(12000, 7, 70).entry_hash;

        let mut log2 = GossipPeerTimeoutE3Log::new();
        let h2 = log2.record(12000, 7, 70).entry_hash;

        let mut log3 = GossipPeerTimeoutE3Log::new();
        let h3 = log3.record(12000, 7, 70).entry_hash;

        assert_eq!(h1, h2);
        assert_eq!(h2, h3);
    }

    #[test]
    fn test_high_peer_timeout_e3_count_mixed() {
        let mut log = GossipPeerTimeoutE3Log::new();
        log.record(13000, 1, 100);  // rate = 1, flag false
        log.record(13001, 20, 100); // rate = 20, flag true
        log.record(13002, 10, 100); // rate = 10, flag false (boundary)
        log.record(13003, 11, 100); // rate = 11, flag true
        assert_eq!(log.high_peer_timeout_e3_count(), 2);
    }

    #[test]
    fn test_total_timed_out_peers_sums_correctly() {
        let mut log = GossipPeerTimeoutE3Log::new();
        log.record(14000, 5, 100);
        log.record(14001, 10, 100);
        log.record(14002, 3, 100);
        assert_eq!(log.total_timed_out_peers(), 18);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipPeerTimeoutE3Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry_correct() {
        let mut log = GossipPeerTimeoutE3Log::new();
        log.record(15000, 20, 100); // rate = 20
        log.record(15001, 40, 100); // rate = 40
        log.record(15002, 60, 100); // rate = 60
        // mean = (20 + 40 + 60) / 3 = 40
        assert_eq!(log.mean_rate_pct(), 40);
    }

    #[test]
    fn test_default_has_zero_entries() {
        let log = GossipPeerTimeoutE3Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}