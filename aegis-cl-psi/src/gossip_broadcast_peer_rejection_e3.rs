//! Gate 484 — Gossip Broadcast Peer Rejection E3 Monitor (T2)
//! Tracks peer rejection e3 rate per gossip broadcast epoch.
//! HIGH_REJECTION_E3_THRESHOLD = 10: rate_pct > 10 → high_rejection_e3

use sha2::{Sha256, Digest};

pub const PEER_REJECTION_E3_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_REJECTION_E3_THRESHOLD: u32 = 10;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPeerRejectionE3Entry {
    pub epoch_end:          u64,
    pub rejected_peers:     u32,
    pub total_peers:        u32,
    pub rejected_rate_pct:  u32,
    pub high_rejection_e3:  bool,
    pub entry_hash:         [u8; 32],
    pub prev_hash:          [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    rejected_peers: u32,
    total_peers: u32,
    rate_pct: u32,
    high_rejection_e3: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(rejected_peers.to_be_bytes());
    h.update(total_peers.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_rejection_e3 as u8]);
    h.finalize().into()
}

pub struct GossipPeerRejectionE3Log {
    pub entries: Vec<GossipPeerRejectionE3Entry>,
}

impl GossipPeerRejectionE3Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        rejected_peers: u32,
        total_peers: u32,
    ) -> &GossipPeerRejectionE3Entry {
        let denom = total_peers.max(1) as u64;
        let rejected_rate_pct = ((rejected_peers as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_rejection_e3 = rejected_rate_pct > HIGH_REJECTION_E3_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(PEER_REJECTION_E3_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, rejected_peers, total_peers, rejected_rate_pct, high_rejection_e3);
        self.entries.push(GossipPeerRejectionE3Entry {
            epoch_end,
            rejected_peers,
            total_peers,
            rejected_rate_pct,
            high_rejection_e3,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_rejection_e3_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_rejection_e3).count()
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
        let mut prev = PEER_REJECTION_E3_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(&prev, e.epoch_end, e.rejected_peers, e.total_peers, e.rejected_rate_pct, e.high_rejection_e3);
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPeerRejectionE3Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_flag_true() {
        let mut log = GossipPeerRejectionE3Log::new();
        let e = log.record(1000, 50, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.rejected_peers, 50);
        assert_eq!(e.total_peers, 100);
        assert_eq!(e.rejected_rate_pct, 50);
        assert!(e.high_rejection_e3);
    }

    #[test]
    fn test_flag_false_when_exactly_at_threshold() {
        let mut log = GossipPeerRejectionE3Log::new();
        // rate_pct == 10 → NOT > 10 → false
        let e = log.record(2000, 10, 100);
        assert_eq!(e.rejected_rate_pct, 10);
        assert!(!e.high_rejection_e3);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipPeerRejectionE3Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.rejected_rate_pct, 100);
    }

    #[test]
    fn test_total_peers_zero_no_div_by_zero() {
        let mut log = GossipPeerRejectionE3Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.rejected_rate_pct, 0);
        assert!(!e.high_rejection_e3);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(HIGH_REJECTION_E3_THRESHOLD, 10);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipPeerRejectionE3Log::new();
        let e = log.record(5000, 5, 10);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipPeerRejectionE3Log::new();
        let e = log.record(6000, 1, 10);
        assert_eq!(e.prev_hash, PEER_REJECTION_E3_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipPeerRejectionE3Log::new();
        log.record(7000, 1, 10);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 2, 10);
        let second = &log.entries[1];
        assert_eq!(second.prev_hash, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipPeerRejectionE3Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_single_entry() {
        let mut log = GossipPeerRejectionE3Log::new();
        log.record(9000, 3, 30);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipPeerRejectionE3Log::new();
        log.record(10000, 5, 50);
        log.record(11000, 10, 100);
        log.record(12000, 2, 20);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipPeerRejectionE3Log::new();
        log.record(13000, 5, 50);
        log.record(14000, 10, 100);
        log.entries[0].rejected_peers = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipPeerRejectionE3Log::new();
        log.record(15000, 5, 50);
        log.record(16000, 10, 100);
        log.entries[1].rejected_peers = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipPeerRejectionE3Log::new();
        let mut log2 = GossipPeerRejectionE3Log::new();
        let mut log3 = GossipPeerRejectionE3Log::new();
        log1.record(17000, 7, 70);
        log2.record(17000, 7, 70);
        log3.record(17000, 7, 70);
        assert_eq!(log1.entries[0].entry_hash, log2.entries[0].entry_hash);
        assert_eq!(log2.entries[0].entry_hash, log3.entries[0].entry_hash);
    }

    #[test]
    fn test_high_rejection_e3_count_mixed() {
        let mut log = GossipPeerRejectionE3Log::new();
        log.record(18000, 1, 100);  // rate=1, flag=false
        log.record(19000, 50, 100); // rate=50, flag=true
        log.record(20000, 10, 100); // rate=10, flag=false (exactly at threshold)
        log.record(21000, 11, 100); // rate=11, flag=true
        assert_eq!(log.high_rejection_e3_count(), 2);
    }

    #[test]
    fn test_total_rejected_peers_sums_correctly() {
        let mut log = GossipPeerRejectionE3Log::new();
        log.record(22000, 5, 50);
        log.record(23000, 15, 100);
        log.record(24000, 3, 30);
        assert_eq!(log.total_rejected_peers(), 23);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipPeerRejectionE3Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry() {
        let mut log = GossipPeerRejectionE3Log::new();
        log.record(25000, 20, 100); // rate=20
        log.record(26000, 40, 100); // rate=40
        log.record(27000, 60, 100); // rate=60
        // mean = (20+40+60)/3 = 40
        assert_eq!(log.mean_rate_pct(), 40);
    }

    #[test]
    fn test_default_has_zero_entries() {
        let log = GossipPeerRejectionE3Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}