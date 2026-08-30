//! Gate 471 — Gossip Broadcast Window Miss E3 Monitor (T2)
//! Tracks window miss e3 rate per gossip broadcast epoch.
//! HIGH_MISS_RATE_E3_THRESHOLD = 10: rate_pct > 10 → high_miss_rate_e3

use sha2::{Sha256, Digest};

pub const WINDOW_MISS_E3_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_MISS_RATE_E3_THRESHOLD: u32 = 10;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipWindowMissE3Entry {
    pub epoch_end:            u64,
    pub missed_windows:       u32,
    pub total_windows:        u32,
    pub missed_windows_rate_pct: u32,
    pub high_miss_rate_e3:    bool,
    pub entry_hash:           [u8; 32],
    pub prev_hash:            [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    missed_windows: u32,
    total_windows: u32,
    rate_pct: u32,
    high_miss_rate_e3: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(missed_windows.to_be_bytes());
    h.update(total_windows.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_miss_rate_e3 as u8]);
    h.finalize().into()
}

pub struct GossipWindowMissE3Log {
    pub entries: Vec<GossipWindowMissE3Entry>,
}

impl GossipWindowMissE3Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        missed_windows: u32,
        total_windows: u32,
    ) -> &GossipWindowMissE3Entry {
        let denom = total_windows.max(1) as u64;
        let missed_windows_rate_pct = ((missed_windows as u64).saturating_mul(100) / denom)
            .min(100) as u32;
        let high_miss_rate_e3 = missed_windows_rate_pct > HIGH_MISS_RATE_E3_THRESHOLD;
        let prev = self
            .entries
            .last()
            .map(|e| e.entry_hash)
            .unwrap_or(WINDOW_MISS_E3_GENESIS_HASH);
        let entry_hash = compute_hash(
            &prev,
            epoch_end,
            missed_windows,
            total_windows,
            missed_windows_rate_pct,
            high_miss_rate_e3,
        );
        self.entries.push(GossipWindowMissE3Entry {
            epoch_end,
            missed_windows,
            total_windows,
            missed_windows_rate_pct,
            high_miss_rate_e3,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_miss_rate_e3_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_miss_rate_e3).count()
    }

    pub fn total_missed_windows(&self) -> u64 {
        self.entries.iter().map(|e| e.missed_windows as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.missed_windows_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = WINDOW_MISS_E3_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.missed_windows,
                e.total_windows,
                e.missed_windows_rate_pct,
                e.high_miss_rate_e3,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipWindowMissE3Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_flag_true() {
        let mut log = GossipWindowMissE3Log::new();
        let e = log.record(1000, 50, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.missed_windows, 50);
        assert_eq!(e.total_windows, 100);
        assert_eq!(e.missed_windows_rate_pct, 50);
        assert!(e.high_miss_rate_e3);
    }

    #[test]
    fn test_flag_false_at_threshold_boundary() {
        let mut log = GossipWindowMissE3Log::new();
        // rate = (10 * 100) / 100 = 10, which is NOT > 10
        let e = log.record(2000, 10, 100);
        assert_eq!(e.missed_windows_rate_pct, 10);
        assert!(!e.high_miss_rate_e3);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipWindowMissE3Log::new();
        // missed > total
        let e = log.record(3000, 200, 100);
        assert_eq!(e.missed_windows_rate_pct, 100);
        assert!(e.high_miss_rate_e3);
    }

    #[test]
    fn test_total_windows_zero_no_div_by_zero() {
        let mut log = GossipWindowMissE3Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.missed_windows_rate_pct, 0);
        assert!(!e.high_miss_rate_e3);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(HIGH_MISS_RATE_E3_THRESHOLD, 10u32);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipWindowMissE3Log::new();
        let e = log.record(5000, 20, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_equals_genesis() {
        let mut log = GossipWindowMissE3Log::new();
        let e = log.record(6000, 5, 100);
        assert_eq!(e.prev_hash, WINDOW_MISS_E3_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipWindowMissE3Log::new();
        log.record(7000, 5, 100);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 15, 100);
        let second = &log.entries[1];
        assert_eq!(second.prev_hash, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipWindowMissE3Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_single_entry() {
        let mut log = GossipWindowMissE3Log::new();
        log.record(9000, 5, 50);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipWindowMissE3Log::new();
        log.record(10000, 5, 50);
        log.record(11000, 10, 80);
        log.record(12000, 20, 90);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipWindowMissE3Log::new();
        log.record(13000, 5, 50);
        log.record(14000, 10, 80);
        // Tamper first entry's hash
        log.entries[0].entry_hash = [0xabu8; 32];
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        // Either entry 0 fails (hash mismatch) or entry 1 fails (prev_hash mismatch)
        assert!(idx == Some(0) || idx == Some(1));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipWindowMissE3Log::new();
        log.record(15000, 5, 50);
        log.record(16000, 10, 80);
        log.record(17000, 20, 90);
        // Tamper second entry's missed_windows
        log.entries[1].missed_windows = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipWindowMissE3Log::new();
        log1.record(18000, 15, 100);
        let mut log2 = GossipWindowMissE3Log::new();
        log2.record(18000, 15, 100);
        let mut log3 = GossipWindowMissE3Log::new();
        log3.record(18000, 15, 100);
        assert_eq!(log1.entries[0].entry_hash, log2.entries[0].entry_hash);
        assert_eq!(log2.entries[0].entry_hash, log3.entries[0].entry_hash);
    }

    #[test]
    fn test_high_miss_rate_e3_count_mixed_log() {
        let mut log = GossipWindowMissE3Log::new();
        // rate = 5, not high
        log.record(19000, 5, 100);
        // rate = 50, high
        log.record(20000, 50, 100);
        // rate = 10, not high (boundary)
        log.record(21000, 10, 100);
        // rate = 11, high
        log.record(22000, 11, 100);
        assert_eq!(log.high_miss_rate_e3_count(), 2);
    }

    #[test]
    fn test_total_missed_windows_sums_correctly() {
        let mut log = GossipWindowMissE3Log::new();
        log.record(23000, 7, 100);
        log.record(24000, 13, 100);
        log.record(25000, 20, 100);
        assert_eq!(log.total_missed_windows(), 40u64);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipWindowMissE3Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry_correct() {
        let mut log = GossipWindowMissE3Log::new();
        // rate = 20
        log.record(26000, 20, 100);
        // rate = 40
        log.record(27000, 40, 100);
        // rate = 60
        log.record(28000, 60, 100);
        // mean = (20 + 40 + 60) / 3 = 40
        assert_eq!(log.mean_rate_pct(), 40);
    }

    #[test]
    fn test_default_zero_entries() {
        let log = GossipWindowMissE3Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}