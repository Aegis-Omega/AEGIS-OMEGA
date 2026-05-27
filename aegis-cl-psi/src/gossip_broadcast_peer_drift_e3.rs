//! Gate 480 — Gossip Broadcast Peer Drift E3 Monitor (T2)
//! Tracks peer drift e3 rate per gossip broadcast epoch.
//! HIGH_PEER_DRIFT_E3_THRESHOLD = 15: rate_pct > 15 → high_peer_drift_e3

use sha2::{Sha256, Digest};

pub const PEER_DRIFT_E3_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_PEER_DRIFT_E3_THRESHOLD: u32 = 15;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPeerDriftE3Entry {
    pub epoch_end:          u64,
    pub drifted_peers:      u32,
    pub total_peers:        u32,
    pub drifted_rate_pct:   u32,
    pub high_peer_drift_e3: bool,
    pub entry_hash:         [u8; 32],
    pub prev_hash:          [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    drifted_peers: u32,
    total_peers: u32,
    rate_pct: u32,
    high_peer_drift_e3: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(drifted_peers.to_be_bytes());
    h.update(total_peers.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_peer_drift_e3 as u8]);
    h.finalize().into()
}

pub struct GossipPeerDriftE3Log {
    pub entries: Vec<GossipPeerDriftE3Entry>,
}

impl GossipPeerDriftE3Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(&mut self, epoch_end: u64, drifted_peers: u32, total_peers: u32) -> &GossipPeerDriftE3Entry {
        let denom = total_peers.max(1) as u64;
        let drifted_rate_pct = ((drifted_peers as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_peer_drift_e3 = drifted_rate_pct > HIGH_PEER_DRIFT_E3_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(PEER_DRIFT_E3_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, drifted_peers, total_peers, drifted_rate_pct, high_peer_drift_e3);
        self.entries.push(GossipPeerDriftE3Entry {
            epoch_end,
            drifted_peers,
            total_peers,
            drifted_rate_pct,
            high_peer_drift_e3,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_peer_drift_e3_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_peer_drift_e3).count()
    }

    pub fn total_drifted_peers(&self) -> u64 {
        self.entries.iter().map(|e| e.drifted_peers as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.drifted_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = PEER_DRIFT_E3_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(&prev, e.epoch_end, e.drifted_peers, e.total_peers, e.drifted_rate_pct, e.high_peer_drift_e3);
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPeerDriftE3Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipPeerDriftE3Log::new();
        let e = log.record(1000, 20, 50);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.drifted_peers, 20);
        assert_eq!(e.total_peers, 50);
        assert_eq!(e.drifted_rate_pct, 40);
        assert!(e.high_peer_drift_e3);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipPeerDriftE3Log::new();
        // 15 out of 100 => rate = 15, not > 15
        let e = log.record(2000, 15, 100);
        assert_eq!(e.drifted_rate_pct, 15);
        assert!(!e.high_peer_drift_e3);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipPeerDriftE3Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.drifted_rate_pct, 100);
        assert!(e.high_peer_drift_e3);
    }

    #[test]
    fn total_peers_zero_no_div_by_zero() {
        let mut log = GossipPeerDriftE3Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.drifted_rate_pct, 0);
        assert!(!e.high_peer_drift_e3);
    }

    #[test]
    fn threshold_constant_value_is_15() {
        assert_eq!(HIGH_PEER_DRIFT_E3_THRESHOLD, 15);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipPeerDriftE3Log::new();
        let e = log.record(5000, 10, 50);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipPeerDriftE3Log::new();
        let e = log.record(6000, 5, 30);
        assert_eq!(e.prev_hash, PEER_DRIFT_E3_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipPeerDriftE3Log::new();
        log.record(7000, 5, 30);
        let first_hash = log.entries[0].entry_hash;
        log.record(7001, 6, 30);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipPeerDriftE3Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipPeerDriftE3Log::new();
        log.record(8000, 3, 20);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipPeerDriftE3Log::new();
        log.record(9000, 2, 10);
        log.record(9001, 4, 20);
        log.record(9002, 6, 30);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipPeerDriftE3Log::new();
        log.record(10000, 5, 25);
        log.record(10001, 6, 25);
        log.entries[0].drifted_peers = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipPeerDriftE3Log::new();
        log.record(11000, 5, 25);
        log.record(11001, 6, 25);
        log.entries[1].drifted_peers = 99;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_produce_same_hash() {
        let mut log1 = GossipPeerDriftE3Log::new();
        let mut log2 = GossipPeerDriftE3Log::new();
        let mut log3 = GossipPeerDriftE3Log::new();
        let e1 = log1.record(12000, 8, 40);
        let e2 = log2.record(12000, 8, 40);
        let e3 = log3.record(12000, 8, 40);
        assert_eq!(e1.entry_hash, e2.entry_hash);
        assert_eq!(e2.entry_hash, e3.entry_hash);
    }

    #[test]
    fn high_peer_drift_e3_count_mixed_log() {
        let mut log = GossipPeerDriftE3Log::new();
        log.record(13000, 1, 100);  // rate=1, flag=false
        log.record(13001, 20, 100); // rate=20, flag=true
        log.record(13002, 15, 100); // rate=15, flag=false (boundary)
        log.record(13003, 16, 100); // rate=16, flag=true
        assert_eq!(log.high_peer_drift_e3_count(), 2);
    }

    #[test]
    fn total_drifted_peers_sums_correctly() {
        let mut log = GossipPeerDriftE3Log::new();
        log.record(14000, 10, 100);
        log.record(14001, 20, 100);
        log.record(14002, 30, 100);
        assert_eq!(log.total_drifted_peers(), 60);
    }

    #[test]
    fn mean_rate_pct_empty_returns_zero() {
        let log = GossipPeerDriftE3Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn mean_rate_pct_multi_entry_correct() {
        let mut log = GossipPeerDriftE3Log::new();
        log.record(15000, 10, 100); // rate=10
        log.record(15001, 30, 100); // rate=30
        log.record(15002, 50, 100); // rate=50
        // mean = (10+30+50)/3 = 90/3 = 30
        assert_eq!(log.mean_rate_pct(), 30);
    }

    #[test]
    fn default_impl_produces_zero_entries() {
        let log = GossipPeerDriftE3Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}