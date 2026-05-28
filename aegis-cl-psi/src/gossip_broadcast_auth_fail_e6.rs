//! Gate 593 — Gossip Broadcast Auth Fail E6 Monitor (T2)
//! Tracks authentication failure rate per gossip broadcast epoch.
//! HIGH_AUTH_FAIL_E6_THRESHOLD = 9: auth_fail_rate_pct > 9 → high_auth_fail_e6

use sha2::{Sha256, Digest};

pub const AUTH_FAIL_E6_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_AUTH_FAIL_E6_THRESHOLD: u32 = 9;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipAuthFailE6Entry {
    pub epoch_end:          u64,
    pub auth_failures:      u32,
    pub total_msgs:         u32,
    pub auth_fail_rate_pct: u32,
    pub high_auth_fail_e6:  bool,
    pub entry_hash:         [u8; 32],
    pub prev_hash:          [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    auth_failures: u32,
    total_msgs: u32,
    rate_pct: u32,
    high_auth_fail_e6: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(auth_failures.to_be_bytes());
    h.update(total_msgs.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_auth_fail_e6 as u8]);
    h.finalize().into()
}

pub struct GossipAuthFailE6Log {
    pub entries: Vec<GossipAuthFailE6Entry>,
}

impl GossipAuthFailE6Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        auth_failures: u32,
        total_msgs: u32,
    ) -> &GossipAuthFailE6Entry {
        let denom = total_msgs.max(1) as u64;
        let auth_fail_rate_pct =
            ((auth_failures as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_auth_fail_e6 = auth_fail_rate_pct > HIGH_AUTH_FAIL_E6_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(AUTH_FAIL_E6_GENESIS_HASH);
        let entry_hash = compute_hash(
            &prev,
            epoch_end,
            auth_failures,
            total_msgs,
            auth_fail_rate_pct,
            high_auth_fail_e6,
        );
        self.entries.push(GossipAuthFailE6Entry {
            epoch_end,
            auth_failures,
            total_msgs,
            auth_fail_rate_pct,
            high_auth_fail_e6,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_auth_fail_e6_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_auth_fail_e6).count()
    }

    pub fn total_auth_failures(&self) -> u64 {
        self.entries.iter().map(|e| e.auth_failures as u64).sum()
    }

    pub fn mean_auth_fail_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.auth_fail_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = AUTH_FAIL_E6_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.auth_failures,
                e.total_msgs,
                e.auth_fail_rate_pct,
                e.high_auth_fail_e6,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipAuthFailE6Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipAuthFailE6Log::new();
        let e = log.record(1000, 13, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.auth_failures, 13);
        assert_eq!(e.total_msgs, 100);
        assert_eq!(e.auth_fail_rate_pct, 13);
        assert!(e.high_auth_fail_e6);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipAuthFailE6Log::new();
        let e = log.record(2000, 9, 100);
        assert_eq!(e.auth_fail_rate_pct, 9);
        assert!(!e.high_auth_fail_e6);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipAuthFailE6Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.auth_fail_rate_pct, 100);
        assert!(e.high_auth_fail_e6);
    }

    #[test]
    fn total_msgs_zero_no_div_by_zero() {
        let mut log = GossipAuthFailE6Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.auth_fail_rate_pct, 0);
        assert!(!e.high_auth_fail_e6);
    }

    #[test]
    fn threshold_constant_value_is_9() {
        assert_eq!(HIGH_AUTH_FAIL_E6_THRESHOLD, 9);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipAuthFailE6Log::new();
        let e = log.record(5000, 13, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipAuthFailE6Log::new();
        let e = log.record(6000, 4, 80);
        assert_eq!(e.prev_hash, AUTH_FAIL_E6_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipAuthFailE6Log::new();
        log.record(7000, 4, 80);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 13, 100);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipAuthFailE6Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipAuthFailE6Log::new();
        log.record(9000, 7, 80);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipAuthFailE6Log::new();
        log.record(10000, 4, 60);
        log.record(11000, 10, 80);
        log.record(12000, 14, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipAuthFailE6Log::new();
        log.record(13000, 4, 80);
        log.record(14000, 13, 100);
        log.entries[0].auth_failures = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipAuthFailE6Log::new();
        log.record(15000, 4, 80);
        log.record(16000, 13, 100);
        log.entries[1].auth_failures = 99;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut log1 = GossipAuthFailE6Log::new();
        let mut log2 = GossipAuthFailE6Log::new();
        let mut log3 = GossipAuthFailE6Log::new();
        let e1 = log1.record(17000, 11, 90).entry_hash;
        let e2 = log2.record(17000, 11, 90).entry_hash;
        let e3 = log3.record(17000, 11, 90).entry_hash;
        assert_eq!(e1, e2);
        assert_eq!(e2, e3);
    }

    #[test]
    fn high_auth_fail_e6_count_mixed_log() {
        let mut log = GossipAuthFailE6Log::new();
        log.record(18000, 6, 100);  // rate=6,  false
        log.record(19000, 13, 100); // rate=13, true
        log.record(20000, 9, 100);  // rate=9,  false (boundary)
        log.record(21000, 10, 100); // rate=10, true
        assert_eq!(log.high_auth_fail_e6_count(), 2);
    }

    #[test]
    fn total_auth_failures_sums_correctly() {
        let mut log = GossipAuthFailE6Log::new();
        log.record(22000, 10, 100);
        log.record(23000, 25, 100);
        log.record(24000, 7, 100);
        assert_eq!(log.total_auth_failures(), 42);
    }

    #[test]
    fn mean_auth_fail_rate_pct_empty_returns_zero() {
        let log = GossipAuthFailE6Log::new();
        assert_eq!(log.mean_auth_fail_rate_pct(), 0);
    }

    #[test]
    fn mean_auth_fail_rate_pct_multi_entry_correct() {
        let mut log = GossipAuthFailE6Log::new();
        log.record(25000, 10, 100); // rate=10
        log.record(26000, 20, 100); // rate=20
        log.record(27000, 30, 100); // rate=30
        assert_eq!(log.mean_auth_fail_rate_pct(), 20);
    }

    #[test]
    fn default_produces_zero_entries() {
        let log = GossipAuthFailE6Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}
