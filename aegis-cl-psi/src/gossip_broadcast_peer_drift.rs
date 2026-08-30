//! Gate 445 — Gossip Broadcast Peer Drift Monitor (T2)
//! Tracks peer drift rate per gossip broadcast epoch.
//! HIGH_PEER_DRIFT_THRESHOLD = 15: rate_pct > 15 → high_peer_drift

use sha2::{Sha256, Digest};

pub const PEER_DRIFT_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_PEER_DRIFT_THRESHOLD: u32 = 15;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPeerDriftEntry {
    pub epoch_end:        u64,
    pub drifted_peers:    u32,
    pub total_peers:      u32,
    pub drifted_rate_pct: u32,
    pub high_peer_drift:  bool,
    pub entry_hash:       [u8; 32],
    pub prev_hash:        [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    drifted_peers: u32,
    total_peers: u32,
    rate_pct: u32,
    high_peer_drift: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(drifted_peers.to_be_bytes());
    h.update(total_peers.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_peer_drift as u8]);
    h.finalize().into()
}

pub struct GossipPeerDriftLog {
    pub entries: Vec<GossipPeerDriftEntry>,
}

impl GossipPeerDriftLog {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        drifted_peers: u32,
        total_peers: u32,
    ) -> &GossipPeerDriftEntry {
        let denom = total_peers.max(1) as u64;
        let drifted_rate_pct = ((drifted_peers as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_peer_drift = drifted_rate_pct > HIGH_PEER_DRIFT_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(PEER_DRIFT_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, drifted_peers, total_peers, drifted_rate_pct, high_peer_drift);
        self.entries.push(GossipPeerDriftEntry {
            epoch_end,
            drifted_peers,
            total_peers,
            drifted_rate_pct,
            high_peer_drift,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_peer_drift_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_peer_drift).count()
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
        let mut prev = PEER_DRIFT_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.drifted_peers,
                e.total_peers,
                e.drifted_rate_pct,
                e.high_peer_drift,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPeerDriftLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_flag_true() {
        let mut log = GossipPeerDriftLog::new();
        // 20/100 = 20% > 15 → high_peer_drift = true
        let e = log.record(1000, 20, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.drifted_peers, 20);
        assert_eq!(e.total_peers, 100);
        assert_eq!(e.drifted_rate_pct, 20);
        assert!(e.high_peer_drift);
    }

    #[test]
    fn test_flag_false_when_exactly_at_threshold() {
        let mut log = GossipPeerDriftLog::new();
        // 15/100 = 15% == 15, not > 15 → false
        let e = log.record(2000, 15, 100);
        assert_eq!(e.drifted_rate_pct, 15);
        assert!(!e.high_peer_drift);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipPeerDriftLog::new();
        // 200/100 = 200% → capped at 100
        let e = log.record(3000, 200, 100);
        assert_eq!(e.drifted_rate_pct, 100);
        assert!(e.high_peer_drift);
    }

    #[test]
    fn test_total_peers_zero_no_div_by_zero() {
        let mut log = GossipPeerDriftLog::new();
        // denom = max(0,1) = 1, so rate = 5*100/1 = 500 → capped at 100
        let e = log.record(4000, 5, 0);
        assert_eq!(e.drifted_rate_pct, 100);
        assert!(e.high_peer_drift);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(HIGH_PEER_DRIFT_THRESHOLD, 15);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipPeerDriftLog::new();
        let e = log.record(5000, 10, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipPeerDriftLog::new();
        let e = log.record(6000, 5, 100);
        assert_eq!(e.prev_hash, PEER_DRIFT_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipPeerDriftLog::new();
        log.record(7000, 5, 100);
        let first_hash = log.entries[0].entry_hash;
        log.record(7001, 10, 100);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipPeerDriftLog::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_one_entry() {
        let mut log = GossipPeerDriftLog::new();
        log.record(8000, 3, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipPeerDriftLog::new();
        log.record(9000, 5, 100);
        log.record(9001, 10, 100);
        log.record(9002, 20, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipPeerDriftLog::new();
        log.record(10000, 5, 100);
        log.record(10001, 10, 100);
        log.entries[0].drifted_peers = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipPeerDriftLog::new();
        log.record(11000, 5, 100);
        log.record(11001, 10, 100);
        log.record(11002, 20, 100);
        log.entries[1].drifted_peers = 77;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipPeerDriftLog::new();
        let mut log2 = GossipPeerDriftLog::new();
        let mut log3 = GossipPeerDriftLog::new();
        let e1 = log1.record(12000, 8, 50).entry_hash;
        let e2 = log2.record(12000, 8, 50).entry_hash;
        let e3 = log3.record(12000, 8, 50).entry_hash;
        assert_eq!(e1, e2);
        assert_eq!(e2, e3);
    }

    #[test]
    fn test_high_peer_drift_count_mixed() {
        let mut log = GossipPeerDriftLog::new();
        log.record(13000, 5, 100);   // 5% → false
        log.record(13001, 16, 100);  // 16% → true
        log.record(13002, 15, 100);  // 15% → false
        log.record(13003, 50, 100);  // 50% → true
        assert_eq!(log.high_peer_drift_count(), 2);
    }

    #[test]
    fn test_total_drifted_peers_sums_correctly() {
        let mut log = GossipPeerDriftLog::new();
        log.record(14000, 10, 100);
        log.record(14001, 20, 100);
        log.record(14002, 30, 100);
        assert_eq!(log.total_drifted_peers(), 60);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipPeerDriftLog::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry_correct() {
        let mut log = GossipPeerDriftLog::new();
        log.record(15000, 10, 100); // 10%
        log.record(15001, 20, 100); // 20%
        log.record(15002, 30, 100); // 30%
        // mean = (10+20+30)/3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn test_default_zero_entries() {
        let log = GossipPeerDriftLog::default();
        assert_eq!(log.entries.len(), 0);
    }
}