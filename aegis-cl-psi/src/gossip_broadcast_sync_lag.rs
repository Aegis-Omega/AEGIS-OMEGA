//! Gate 442 — Gossip Broadcast Sync Lag Monitor (T2)
//! Tracks sync lag rate per gossip broadcast epoch.
//! HIGH_SYNC_LAG_THRESHOLD = 30: rate_pct > 30 → high_sync_lag

use sha2::{Sha256, Digest};

pub const SYNC_LAG_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_SYNC_LAG_THRESHOLD: u32 = 30;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipSyncLagEntry {
    pub epoch_end:      u64,
    pub lagging_peers:  u32,
    pub total_peers:    u32,
    pub lagging_rate_pct: u32,
    pub high_sync_lag:  bool,
    pub entry_hash:     [u8; 32],
    pub prev_hash:      [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    lagging_peers: u32,
    total_peers: u32,
    rate_pct: u32,
    high_sync_lag: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(lagging_peers.to_be_bytes());
    h.update(total_peers.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_sync_lag as u8]);
    h.finalize().into()
}

pub struct GossipSyncLagLog {
    pub entries: Vec<GossipSyncLagEntry>,
}

impl GossipSyncLagLog {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(&mut self, epoch_end: u64, lagging_peers: u32, total_peers: u32) -> &GossipSyncLagEntry {
        let denom = total_peers.max(1) as u64;
        let lagging_rate_pct = ((lagging_peers as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_sync_lag = lagging_rate_pct > HIGH_SYNC_LAG_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(SYNC_LAG_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, lagging_peers, total_peers, lagging_rate_pct, high_sync_lag);
        self.entries.push(GossipSyncLagEntry {
            epoch_end,
            lagging_peers,
            total_peers,
            lagging_rate_pct,
            high_sync_lag,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_sync_lag_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_sync_lag).count()
    }

    pub fn total_lagging_peers(&self) -> u64 {
        self.entries.iter().map(|e| e.lagging_peers as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.lagging_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = SYNC_LAG_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(&prev, e.epoch_end, e.lagging_peers, e.total_peers, e.lagging_rate_pct, e.high_sync_lag);
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipSyncLagLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_rate_and_flag_true() {
        let mut log = GossipSyncLagLog::new();
        let e = log.record(1000, 40, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.lagging_peers, 40);
        assert_eq!(e.total_peers, 100);
        assert_eq!(e.lagging_rate_pct, 40);
        assert!(e.high_sync_lag);
    }

    #[test]
    fn test_flag_false_when_exactly_at_threshold() {
        let mut log = GossipSyncLagLog::new();
        // rate_pct = (30 * 100) / 100 = 30, which is NOT > 30, so high_sync_lag = false
        let e = log.record(2000, 30, 100);
        assert_eq!(e.lagging_rate_pct, 30);
        assert!(!e.high_sync_lag);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipSyncLagLog::new();
        // lagging_peers > total_peers
        let e = log.record(3000, 200, 100);
        assert_eq!(e.lagging_rate_pct, 100);
        assert!(e.high_sync_lag);
    }

    #[test]
    fn test_total_peers_zero_no_div_by_zero() {
        let mut log = GossipSyncLagLog::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.lagging_rate_pct, 0);
        assert!(!e.high_sync_lag);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(HIGH_SYNC_LAG_THRESHOLD, 30);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipSyncLagLog::new();
        let e = log.record(5000, 10, 50);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipSyncLagLog::new();
        let e = log.record(6000, 5, 20);
        assert_eq!(e.prev_hash, SYNC_LAG_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipSyncLagLog::new();
        log.record(7000, 5, 20);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 8, 20);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipSyncLagLog::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_one_entry() {
        let mut log = GossipSyncLagLog::new();
        log.record(9000, 10, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipSyncLagLog::new();
        log.record(10000, 10, 100);
        log.record(11000, 20, 100);
        log.record(12000, 35, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipSyncLagLog::new();
        log.record(13000, 10, 100);
        log.record(14000, 20, 100);
        // Tamper entry 0's lagging_peers
        log.entries[0].lagging_peers = 99;
        let (valid, idx) = log.verify_chain();
        assert!(!valid);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipSyncLagLog::new();
        log.record(15000, 10, 100);
        log.record(16000, 20, 100);
        log.record(17000, 30, 100);
        // Tamper entry 1's lagging_peers
        log.entries[1].lagging_peers = 99;
        let (valid, idx) = log.verify_chain();
        assert!(!valid);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipSyncLagLog::new();
        let e1 = log1.record(18000, 15, 50).entry_hash;

        let mut log2 = GossipSyncLagLog::new();
        let e2 = log2.record(18000, 15, 50).entry_hash;

        let mut log3 = GossipSyncLagLog::new();
        let e3 = log3.record(18000, 15, 50).entry_hash;

        assert_eq!(e1, e2);
        assert_eq!(e2, e3);
    }

    #[test]
    fn test_high_sync_lag_count_mixed() {
        let mut log = GossipSyncLagLog::new();
        log.record(19000, 10, 100); // 10% — false
        log.record(20000, 31, 100); // 31% — true
        log.record(21000, 50, 100); // 50% — true
        log.record(22000, 30, 100); // 30% — false
        assert_eq!(log.high_sync_lag_count(), 2);
    }

    #[test]
    fn test_total_lagging_peers_sums_correctly() {
        let mut log = GossipSyncLagLog::new();
        log.record(23000, 5, 100);
        log.record(24000, 15, 100);
        log.record(25000, 25, 100);
        assert_eq!(log.total_lagging_peers(), 45u64);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipSyncLagLog::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry_correct() {
        let mut log = GossipSyncLagLog::new();
        log.record(26000, 20, 100); // 20%
        log.record(27000, 40, 100); // 40%
        log.record(28000, 60, 100); // 60%
        // mean = (20 + 40 + 60) / 3 = 40
        assert_eq!(log.mean_rate_pct(), 40);
    }

    #[test]
    fn test_default_has_zero_entries() {
        let log = GossipSyncLagLog::default();
        assert_eq!(log.entries.len(), 0);
    }
}