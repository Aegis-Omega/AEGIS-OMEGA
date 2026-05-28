//! Gate 591 — Gossip Broadcast Version Mismatch E6 Monitor (T2)
//! Tracks version mismatch rate per gossip broadcast epoch.
//! HIGH_VERSION_MISMATCH_E6_THRESHOLD = 11: mismatch_rate_pct > 11 → high_version_mismatch_e6

use sha2::{Sha256, Digest};

pub const VERSION_MISMATCH_E6_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_VERSION_MISMATCH_E6_THRESHOLD: u32 = 11;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipVersionMismatchE6Entry {
    pub epoch_end:                u64,
    pub mismatched_versions:      u32,
    pub total_msgs:               u32,
    pub mismatch_rate_pct:        u32,
    pub high_version_mismatch_e6: bool,
    pub entry_hash:               [u8; 32],
    pub prev_hash:                [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    mismatched_versions: u32,
    total_msgs: u32,
    rate_pct: u32,
    high_version_mismatch_e6: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(mismatched_versions.to_be_bytes());
    h.update(total_msgs.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_version_mismatch_e6 as u8]);
    h.finalize().into()
}

pub struct GossipVersionMismatchE6Log {
    pub entries: Vec<GossipVersionMismatchE6Entry>,
}

impl GossipVersionMismatchE6Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        mismatched_versions: u32,
        total_msgs: u32,
    ) -> &GossipVersionMismatchE6Entry {
        let denom = total_msgs.max(1) as u64;
        let mismatch_rate_pct =
            ((mismatched_versions as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_version_mismatch_e6 = mismatch_rate_pct > HIGH_VERSION_MISMATCH_E6_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(VERSION_MISMATCH_E6_GENESIS_HASH);
        let entry_hash = compute_hash(
            &prev,
            epoch_end,
            mismatched_versions,
            total_msgs,
            mismatch_rate_pct,
            high_version_mismatch_e6,
        );
        self.entries.push(GossipVersionMismatchE6Entry {
            epoch_end,
            mismatched_versions,
            total_msgs,
            mismatch_rate_pct,
            high_version_mismatch_e6,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_version_mismatch_e6_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_version_mismatch_e6).count()
    }

    pub fn total_mismatched_versions(&self) -> u64 {
        self.entries.iter().map(|e| e.mismatched_versions as u64).sum()
    }

    pub fn mean_mismatch_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.mismatch_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = VERSION_MISMATCH_E6_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.mismatched_versions,
                e.total_msgs,
                e.mismatch_rate_pct,
                e.high_version_mismatch_e6,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipVersionMismatchE6Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipVersionMismatchE6Log::new();
        let e = log.record(1000, 15, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.mismatched_versions, 15);
        assert_eq!(e.total_msgs, 100);
        assert_eq!(e.mismatch_rate_pct, 15);
        assert!(e.high_version_mismatch_e6);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipVersionMismatchE6Log::new();
        let e = log.record(2000, 11, 100);
        assert_eq!(e.mismatch_rate_pct, 11);
        assert!(!e.high_version_mismatch_e6);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipVersionMismatchE6Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.mismatch_rate_pct, 100);
        assert!(e.high_version_mismatch_e6);
    }

    #[test]
    fn total_msgs_zero_no_div_by_zero() {
        let mut log = GossipVersionMismatchE6Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.mismatch_rate_pct, 0);
        assert!(!e.high_version_mismatch_e6);
    }

    #[test]
    fn threshold_constant_value_is_11() {
        assert_eq!(HIGH_VERSION_MISMATCH_E6_THRESHOLD, 11);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipVersionMismatchE6Log::new();
        let e = log.record(5000, 15, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipVersionMismatchE6Log::new();
        let e = log.record(6000, 5, 80);
        assert_eq!(e.prev_hash, VERSION_MISMATCH_E6_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipVersionMismatchE6Log::new();
        log.record(7000, 5, 80);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 15, 100);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipVersionMismatchE6Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipVersionMismatchE6Log::new();
        log.record(9000, 8, 80);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipVersionMismatchE6Log::new();
        log.record(10000, 5, 60);
        log.record(11000, 12, 80);
        log.record(12000, 18, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipVersionMismatchE6Log::new();
        log.record(13000, 5, 80);
        log.record(14000, 15, 100);
        log.entries[0].mismatched_versions = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipVersionMismatchE6Log::new();
        log.record(15000, 5, 80);
        log.record(16000, 15, 100);
        log.entries[1].mismatched_versions = 99;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut log1 = GossipVersionMismatchE6Log::new();
        let mut log2 = GossipVersionMismatchE6Log::new();
        let mut log3 = GossipVersionMismatchE6Log::new();
        let e1 = log1.record(17000, 13, 90).entry_hash;
        let e2 = log2.record(17000, 13, 90).entry_hash;
        let e3 = log3.record(17000, 13, 90).entry_hash;
        assert_eq!(e1, e2);
        assert_eq!(e2, e3);
    }

    #[test]
    fn high_version_mismatch_e6_count_mixed_log() {
        let mut log = GossipVersionMismatchE6Log::new();
        log.record(18000, 8, 100);  // rate=8,  false
        log.record(19000, 20, 100); // rate=20, true
        log.record(20000, 11, 100); // rate=11, false (boundary)
        log.record(21000, 12, 100); // rate=12, true
        assert_eq!(log.high_version_mismatch_e6_count(), 2);
    }

    #[test]
    fn total_mismatched_versions_sums_correctly() {
        let mut log = GossipVersionMismatchE6Log::new();
        log.record(22000, 10, 100);
        log.record(23000, 25, 100);
        log.record(24000, 7, 100);
        assert_eq!(log.total_mismatched_versions(), 42);
    }

    #[test]
    fn mean_mismatch_rate_pct_empty_returns_zero() {
        let log = GossipVersionMismatchE6Log::new();
        assert_eq!(log.mean_mismatch_rate_pct(), 0);
    }

    #[test]
    fn mean_mismatch_rate_pct_multi_entry_correct() {
        let mut log = GossipVersionMismatchE6Log::new();
        log.record(25000, 10, 100); // rate=10
        log.record(26000, 20, 100); // rate=20
        log.record(27000, 30, 100); // rate=30
        assert_eq!(log.mean_mismatch_rate_pct(), 20);
    }

    #[test]
    fn default_produces_zero_entries() {
        let log = GossipVersionMismatchE6Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}
