//! Gate 487 — Gossip Broadcast Peer Isolation E3 Monitor (T2)
//! Tracks peer isolation e3 rate per gossip broadcast epoch.
//! PEER_ISOLATED_E3_THRESHOLD = 10: rate_pct > 10 → peer_isolated_e3

use sha2::{Sha256, Digest};

pub const PEER_ISOLATION_E3_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const PEER_ISOLATED_E3_THRESHOLD: u32 = 10;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPeerIsolationE3Entry {
    pub epoch_end:        u64,
    pub isolated_peers:   u32,
    pub total_peers:      u32,
    pub isolated_rate_pct: u32,
    pub peer_isolated_e3: bool,
    pub entry_hash:       [u8; 32],
    pub prev_hash:        [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    isolated_peers: u32,
    total_peers: u32,
    rate_pct: u32,
    peer_isolated_e3: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(isolated_peers.to_be_bytes());
    h.update(total_peers.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([peer_isolated_e3 as u8]);
    h.finalize().into()
}

pub struct GossipPeerIsolationE3Log {
    pub entries: Vec<GossipPeerIsolationE3Entry>,
}

impl GossipPeerIsolationE3Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        isolated_peers: u32,
        total_peers: u32,
    ) -> &GossipPeerIsolationE3Entry {
        let denom = total_peers.max(1) as u64;
        let isolated_rate_pct = ((isolated_peers as u64).saturating_mul(100) / denom)
            .min(100) as u32;
        let peer_isolated_e3 = isolated_rate_pct > PEER_ISOLATED_E3_THRESHOLD;
        let prev = self
            .entries
            .last()
            .map(|e| e.entry_hash)
            .unwrap_or(PEER_ISOLATION_E3_GENESIS_HASH);
        let entry_hash = compute_hash(
            &prev,
            epoch_end,
            isolated_peers,
            total_peers,
            isolated_rate_pct,
            peer_isolated_e3,
        );
        self.entries.push(GossipPeerIsolationE3Entry {
            epoch_end,
            isolated_peers,
            total_peers,
            isolated_rate_pct,
            peer_isolated_e3,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn peer_isolated_e3_count(&self) -> usize {
        self.entries.iter().filter(|e| e.peer_isolated_e3).count()
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
        let mut prev = PEER_ISOLATION_E3_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.isolated_peers,
                e.total_peers,
                e.isolated_rate_pct,
                e.peer_isolated_e3,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPeerIsolationE3Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipPeerIsolationE3Log::new();
        let e = log.record(1000, 20, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.isolated_peers, 20);
        assert_eq!(e.total_peers, 100);
        assert_eq!(e.isolated_rate_pct, 20);
        assert_eq!(e.peer_isolated_e3, true);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipPeerIsolationE3Log::new();
        // rate = (10 * 100) / 100 = 10, not > 10, so false
        let e = log.record(2000, 10, 100);
        assert_eq!(e.isolated_rate_pct, 10);
        assert_eq!(e.peer_isolated_e3, false);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipPeerIsolationE3Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.isolated_rate_pct, 100);
        assert_eq!(e.peer_isolated_e3, true);
    }

    #[test]
    fn total_peers_zero_no_div_by_zero() {
        let mut log = GossipPeerIsolationE3Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.isolated_rate_pct, 0);
        assert_eq!(e.peer_isolated_e3, false);
    }

    #[test]
    fn threshold_constant_value_is_10() {
        assert_eq!(PEER_ISOLATED_E3_THRESHOLD, 10);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipPeerIsolationE3Log::new();
        let e = log.record(5000, 5, 50);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipPeerIsolationE3Log::new();
        let e = log.record(6000, 3, 30);
        assert_eq!(e.prev_hash, PEER_ISOLATION_E3_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipPeerIsolationE3Log::new();
        log.record(7000, 3, 30);
        let first_hash = log.entries[0].entry_hash;
        let e2 = log.record(8000, 4, 40);
        assert_eq!(e2.prev_hash, first_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipPeerIsolationE3Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_single_entry_returns_true_none() {
        let mut log = GossipPeerIsolationE3Log::new();
        log.record(9000, 2, 20);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipPeerIsolationE3Log::new();
        log.record(10000, 1, 10);
        log.record(11000, 2, 20);
        log.record(12000, 3, 30);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipPeerIsolationE3Log::new();
        log.record(13000, 5, 50);
        log.record(14000, 6, 60);
        log.entries[0].isolated_peers = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipPeerIsolationE3Log::new();
        log.record(15000, 5, 50);
        log.record(16000, 6, 60);
        log.entries[1].isolated_peers = 88;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut log1 = GossipPeerIsolationE3Log::new();
        let h1 = log1.record(17000, 7, 70).entry_hash;
        let mut log2 = GossipPeerIsolationE3Log::new();
        let h2 = log2.record(17000, 7, 70).entry_hash;
        let mut log3 = GossipPeerIsolationE3Log::new();
        let h3 = log3.record(17000, 7, 70).entry_hash;
        assert_eq!(h1, h2);
        assert_eq!(h2, h3);
    }

    #[test]
    fn peer_isolated_e3_count_mixed_log() {
        let mut log = GossipPeerIsolationE3Log::new();
        log.record(18000, 1, 100);  // 1% → false
        log.record(19000, 15, 100); // 15% → true
        log.record(20000, 10, 100); // 10% → false (exactly at threshold)
        log.record(21000, 11, 100); // 11% → true
        assert_eq!(log.peer_isolated_e3_count(), 2);
    }

    #[test]
    fn total_isolated_peers_sums_correctly() {
        let mut log = GossipPeerIsolationE3Log::new();
        log.record(22000, 5, 100);
        log.record(23000, 10, 100);
        log.record(24000, 15, 100);
        assert_eq!(log.total_isolated_peers(), 30u64);
    }

    #[test]
    fn mean_rate_pct_empty_returns_zero() {
        let log = GossipPeerIsolationE3Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn mean_rate_pct_multi_entry_correct() {
        let mut log = GossipPeerIsolationE3Log::new();
        log.record(25000, 10, 100); // 10%
        log.record(26000, 20, 100); // 20%
        log.record(27000, 30, 100); // 30%
        // mean = (10 + 20 + 30) / 3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn default_returns_zero_entries() {
        let log = GossipPeerIsolationE3Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}