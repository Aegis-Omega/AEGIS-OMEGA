//! Gate 446 — Gossip Broadcast Epoch Stall Monitor (T2)
//! Tracks epoch stall rate per gossip broadcast epoch.
//! EPOCH_STALLING_THRESHOLD = 5: rate_pct > 5 → epoch_stalling

use sha2::{Sha256, Digest};

pub const EPOCH_STALL_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const EPOCH_STALLING_THRESHOLD: u32 = 5;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipEpochStallEntry {
    pub epoch_end:      u64,
    pub stalled_epochs: u32,
    pub total_epochs:   u32,
    pub stalled_rate_pct: u32,
    pub epoch_stalling: bool,
    pub entry_hash:     [u8; 32],
    pub prev_hash:      [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    stalled_epochs: u32,
    total_epochs: u32,
    rate_pct: u32,
    epoch_stalling: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(stalled_epochs.to_be_bytes());
    h.update(total_epochs.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([epoch_stalling as u8]);
    h.finalize().into()
}

pub struct GossipEpochStallLog {
    pub entries: Vec<GossipEpochStallEntry>,
}

impl GossipEpochStallLog {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        stalled_epochs: u32,
        total_epochs: u32,
    ) -> &GossipEpochStallEntry {
        let denom = total_epochs.max(1) as u64;
        let stalled_rate_pct = ((stalled_epochs as u64).saturating_mul(100) / denom).min(100) as u32;
        let epoch_stalling = stalled_rate_pct > EPOCH_STALLING_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(EPOCH_STALL_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, stalled_epochs, total_epochs, stalled_rate_pct, epoch_stalling);
        self.entries.push(GossipEpochStallEntry {
            epoch_end,
            stalled_epochs,
            total_epochs,
            stalled_rate_pct,
            epoch_stalling,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn epoch_stalling_count(&self) -> usize {
        self.entries.iter().filter(|e| e.epoch_stalling).count()
    }

    pub fn total_stalled_epochs(&self) -> u64 {
        self.entries.iter().map(|e| e.stalled_epochs as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.stalled_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = EPOCH_STALL_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(&prev, e.epoch_end, e.stalled_epochs, e.total_epochs, e.stalled_rate_pct, e.epoch_stalling);
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipEpochStallLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_flag_true() {
        let mut log = GossipEpochStallLog::new();
        let entry = log.record(1000, 10, 50);
        assert_eq!(entry.epoch_end, 1000);
        assert_eq!(entry.stalled_epochs, 10);
        assert_eq!(entry.total_epochs, 50);
        assert_eq!(entry.stalled_rate_pct, 20);
        assert!(entry.epoch_stalling);
    }

    #[test]
    fn test_flag_false_when_at_threshold() {
        // rate_pct == 5 => NOT > 5, so epoch_stalling = false
        let mut log = GossipEpochStallLog::new();
        let entry = log.record(2000, 5, 100);
        assert_eq!(entry.stalled_rate_pct, 5);
        assert!(!entry.epoch_stalling);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipEpochStallLog::new();
        let entry = log.record(3000, 200, 100);
        assert_eq!(entry.stalled_rate_pct, 100);
        assert!(entry.epoch_stalling);
    }

    #[test]
    fn test_total_epochs_zero_no_div_by_zero() {
        let mut log = GossipEpochStallLog::new();
        let entry = log.record(4000, 0, 0);
        assert_eq!(entry.stalled_rate_pct, 0);
        assert!(!entry.epoch_stalling);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(EPOCH_STALLING_THRESHOLD, 5);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipEpochStallLog::new();
        let entry = log.record(5000, 3, 10);
        assert_ne!(entry.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipEpochStallLog::new();
        log.record(6000, 1, 20);
        assert_eq!(log.entries[0].prev_hash, EPOCH_STALL_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipEpochStallLog::new();
        log.record(7000, 1, 20);
        log.record(8000, 2, 20);
        assert_eq!(log.entries[1].prev_hash, log.entries[0].entry_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipEpochStallLog::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_one_entry() {
        let mut log = GossipEpochStallLog::new();
        log.record(9000, 1, 10);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipEpochStallLog::new();
        log.record(10000, 1, 10);
        log.record(11000, 2, 20);
        log.record(12000, 3, 30);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipEpochStallLog::new();
        log.record(13000, 1, 10);
        log.record(14000, 2, 20);
        log.entries[0].stalled_epochs = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipEpochStallLog::new();
        log.record(15000, 1, 10);
        log.record(16000, 2, 20);
        log.record(17000, 3, 30);
        log.entries[1].stalled_epochs = 77;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipEpochStallLog::new();
        let mut log2 = GossipEpochStallLog::new();
        let mut log3 = GossipEpochStallLog::new();
        let h1 = log1.record(18000, 4, 40).entry_hash;
        let h2 = log2.record(18000, 4, 40).entry_hash;
        let h3 = log3.record(18000, 4, 40).entry_hash;
        assert_eq!(h1, h2);
        assert_eq!(h2, h3);
    }

    #[test]
    fn test_epoch_stalling_count_mixed() {
        let mut log = GossipEpochStallLog::new();
        log.record(19000, 1, 100);  // rate=1, not stalling
        log.record(20000, 10, 100); // rate=10, stalling
        log.record(21000, 5, 100);  // rate=5, not stalling (boundary)
        log.record(22000, 6, 100);  // rate=6, stalling
        assert_eq!(log.epoch_stalling_count(), 2);
    }

    #[test]
    fn test_total_stalled_epochs_sums_correctly() {
        let mut log = GossipEpochStallLog::new();
        log.record(23000, 3, 50);
        log.record(24000, 7, 50);
        log.record(25000, 2, 50);
        assert_eq!(log.total_stalled_epochs(), 12);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipEpochStallLog::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry() {
        let mut log = GossipEpochStallLog::new();
        log.record(26000, 10, 100); // rate=10
        log.record(27000, 20, 100); // rate=20
        log.record(28000, 30, 100); // rate=30
        // mean = (10+20+30)/3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn test_default_zero_entries() {
        let log = GossipEpochStallLog::default();
        assert_eq!(log.entries.len(), 0);
    }
}