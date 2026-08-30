//! Gate 477 — Gossip Broadcast Sync Lag E3 Monitor (T2)
//! Tracks sync lag e3 rate per gossip broadcast epoch.
//! HIGH_SYNC_LAG_E3_THRESHOLD = 30: rate_pct > 30 → high_sync_lag_e3

use sha2::{Sha256, Digest};

pub const SYNC_LAG_E3_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_SYNC_LAG_E3_THRESHOLD: u32 = 30;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipSyncLagE3Entry {
    pub epoch_end:        u64,
    pub lagging_peers:    u32,
    pub total_peers:      u32,
    pub lagging_rate_pct: u32,
    pub high_sync_lag_e3: bool,
    pub entry_hash:       [u8; 32],
    pub prev_hash:        [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    lagging_peers: u32,
    total_peers: u32,
    rate_pct: u32,
    high_sync_lag_e3: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(lagging_peers.to_be_bytes());
    h.update(total_peers.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_sync_lag_e3 as u8]);
    h.finalize().into()
}

pub struct GossipSyncLagE3Log {
    pub entries: Vec<GossipSyncLagE3Entry>,
}

impl GossipSyncLagE3Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        lagging_peers: u32,
        total_peers: u32,
    ) -> &GossipSyncLagE3Entry {
        let denom = total_peers.max(1) as u64;
        let lagging_rate_pct = ((lagging_peers as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_sync_lag_e3 = lagging_rate_pct > HIGH_SYNC_LAG_E3_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(SYNC_LAG_E3_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, lagging_peers, total_peers, lagging_rate_pct, high_sync_lag_e3);
        self.entries.push(GossipSyncLagE3Entry {
            epoch_end,
            lagging_peers,
            total_peers,
            lagging_rate_pct,
            high_sync_lag_e3,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_sync_lag_e3_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_sync_lag_e3).count()
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
        let mut prev = SYNC_LAG_E3_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(&prev, e.epoch_end, e.lagging_peers, e.total_peers, e.lagging_rate_pct, e.high_sync_lag_e3);
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipSyncLagE3Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true_above_threshold() {
        let mut log = GossipSyncLagE3Log::new();
        let entry = log.record(1000, 40, 100);
        assert_eq!(entry.epoch_end, 1000);
        assert_eq!(entry.lagging_peers, 40);
        assert_eq!(entry.total_peers, 100);
        assert_eq!(entry.lagging_rate_pct, 40);
        assert!(entry.high_sync_lag_e3);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipSyncLagE3Log::new();
        let entry = log.record(2000, 30, 100);
        assert_eq!(entry.lagging_rate_pct, 30);
        assert!(!entry.high_sync_lag_e3);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipSyncLagE3Log::new();
        let entry = log.record(3000, 200, 100);
        assert_eq!(entry.lagging_rate_pct, 100);
        assert!(entry.high_sync_lag_e3);
    }

    #[test]
    fn total_peers_zero_no_div_by_zero() {
        let mut log = GossipSyncLagE3Log::new();
        let entry = log.record(4000, 0, 0);
        assert_eq!(entry.lagging_rate_pct, 0);
        assert!(!entry.high_sync_lag_e3);
    }

    #[test]
    fn threshold_constant_value_is_30() {
        assert_eq!(HIGH_SYNC_LAG_E3_THRESHOLD, 30);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipSyncLagE3Log::new();
        let entry = log.record(5000, 10, 100);
        assert_ne!(entry.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipSyncLagE3Log::new();
        log.record(6000, 5, 50);
        assert_eq!(log.entries[0].prev_hash, SYNC_LAG_E3_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipSyncLagE3Log::new();
        log.record(7000, 5, 50);
        log.record(8000, 10, 50);
        let first_hash = log.entries[0].entry_hash;
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipSyncLagE3Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipSyncLagE3Log::new();
        log.record(9000, 15, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipSyncLagE3Log::new();
        log.record(10000, 10, 100);
        log.record(11000, 20, 100);
        log.record(12000, 35, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipSyncLagE3Log::new();
        log.record(13000, 10, 100);
        log.record(14000, 20, 100);
        log.entries[0].lagging_peers = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipSyncLagE3Log::new();
        log.record(15000, 10, 100);
        log.record(16000, 20, 100);
        log.entries[1].lagging_peers = 88;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_produce_same_hash() {
        let mut log1 = GossipSyncLagE3Log::new();
        let mut log2 = GossipSyncLagE3Log::new();
        let mut log3 = GossipSyncLagE3Log::new();
        let e1 = log1.record(17000, 25, 80).entry_hash;
        let e2 = log2.record(17000, 25, 80).entry_hash;
        let e3 = log3.record(17000, 25, 80).entry_hash;
        assert_eq!(e1, e2);
        assert_eq!(e2, e3);
    }

    #[test]
    fn high_sync_lag_e3_count_mixed_log() {
        let mut log = GossipSyncLagE3Log::new();
        log.record(18000, 5, 100);   // 5% → false
        log.record(19000, 31, 100);  // 31% → true
        log.record(20000, 30, 100);  // 30% → false (at threshold)
        log.record(21000, 50, 100);  // 50% → true
        assert_eq!(log.high_sync_lag_e3_count(), 2);
    }

    #[test]
    fn total_lagging_peers_sums_correctly() {
        let mut log = GossipSyncLagE3Log::new();
        log.record(22000, 10, 100);
        log.record(23000, 20, 100);
        log.record(24000, 30, 100);
        assert_eq!(log.total_lagging_peers(), 60);
    }

    #[test]
    fn mean_rate_pct_empty_returns_zero() {
        let log = GossipSyncLagE3Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn mean_rate_pct_multi_entry_correct() {
        let mut log = GossipSyncLagE3Log::new();
        log.record(25000, 20, 100); // 20%
        log.record(26000, 40, 100); // 40%
        log.record(27000, 60, 100); // 60%
        // mean = (20 + 40 + 60) / 3 = 40
        assert_eq!(log.mean_rate_pct(), 40);
    }

    #[test]
    fn default_produces_zero_entries() {
        let log = GossipSyncLagE3Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}