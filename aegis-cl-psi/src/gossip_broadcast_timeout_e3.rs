//! Gate 468 — Gossip Broadcast Timeout E3 Monitor (T2)
//! Tracks timeout e3 rate per gossip broadcast epoch.
//! HIGH_TIMEOUT_RATE_E3_THRESHOLD = 4: rate_pct > 4 → high_timeout_rate_e3

use sha2::{Sha256, Digest};

pub const TIMEOUT_E3_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_TIMEOUT_RATE_E3_THRESHOLD: u32 = 4;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipTimeoutE3Entry {
    pub epoch_end:            u64,
    pub timed_out_msgs:       u32,
    pub total_sent:           u32,
    pub timed_out_rate_pct:   u32,
    pub high_timeout_rate_e3: bool,
    pub entry_hash:           [u8; 32],
    pub prev_hash:            [u8; 32],
}

fn compute_hash(
    prev:               &[u8; 32],
    epoch_end:          u64,
    timed_out_msgs:     u32,
    total_sent:         u32,
    rate_pct:           u32,
    high_timeout_rate_e3: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(timed_out_msgs.to_be_bytes());
    h.update(total_sent.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_timeout_rate_e3 as u8]);
    h.finalize().into()
}

pub struct GossipTimeoutE3Log {
    pub entries: Vec<GossipTimeoutE3Entry>,
}

impl GossipTimeoutE3Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end:      u64,
        timed_out_msgs: u32,
        total_sent:     u32,
    ) -> &GossipTimeoutE3Entry {
        let denom = total_sent.max(1) as u64;
        let timed_out_rate_pct =
            ((timed_out_msgs as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_timeout_rate_e3 = timed_out_rate_pct > HIGH_TIMEOUT_RATE_E3_THRESHOLD;
        let prev = self
            .entries
            .last()
            .map(|e| e.entry_hash)
            .unwrap_or(TIMEOUT_E3_GENESIS_HASH);
        let entry_hash = compute_hash(
            &prev,
            epoch_end,
            timed_out_msgs,
            total_sent,
            timed_out_rate_pct,
            high_timeout_rate_e3,
        );
        self.entries.push(GossipTimeoutE3Entry {
            epoch_end,
            timed_out_msgs,
            total_sent,
            timed_out_rate_pct,
            high_timeout_rate_e3,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_timeout_rate_e3_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_timeout_rate_e3).count()
    }

    pub fn total_timed_out_msgs(&self) -> u64 {
        self.entries.iter().map(|e| e.timed_out_msgs as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.timed_out_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = TIMEOUT_E3_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.timed_out_msgs,
                e.total_sent,
                e.timed_out_rate_pct,
                e.high_timeout_rate_e3,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipTimeoutE3Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true() {
        let mut log = GossipTimeoutE3Log::new();
        let e = log.record(1000, 10, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.timed_out_msgs, 10);
        assert_eq!(e.total_sent, 100);
        assert_eq!(e.timed_out_rate_pct, 10);
        assert!(e.high_timeout_rate_e3);
    }

    #[test]
    fn flag_false_at_exact_threshold() {
        let mut log = GossipTimeoutE3Log::new();
        // rate = (4 * 100) / 100 = 4, which is NOT > 4
        let e = log.record(2000, 4, 100);
        assert_eq!(e.timed_out_rate_pct, 4);
        assert!(!e.high_timeout_rate_e3);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipTimeoutE3Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.timed_out_rate_pct, 100);
        assert!(e.high_timeout_rate_e3);
    }

    #[test]
    fn total_sent_zero_no_div_by_zero() {
        let mut log = GossipTimeoutE3Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.timed_out_rate_pct, 0);
        assert!(!e.high_timeout_rate_e3);
    }

    #[test]
    fn threshold_constant_value() {
        assert_eq!(HIGH_TIMEOUT_RATE_E3_THRESHOLD, 4);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipTimeoutE3Log::new();
        let e = log.record(5000, 5, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_is_genesis() {
        let mut log = GossipTimeoutE3Log::new();
        log.record(6000, 1, 100);
        assert_eq!(log.entries[0].prev_hash, TIMEOUT_E3_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_is_first_entry_hash() {
        let mut log = GossipTimeoutE3Log::new();
        log.record(7000, 1, 100);
        log.record(8000, 2, 100);
        assert_eq!(log.entries[1].prev_hash, log.entries[0].entry_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipTimeoutE3Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_one_entry_valid() {
        let mut log = GossipTimeoutE3Log::new();
        log.record(9000, 3, 60);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_valid() {
        let mut log = GossipTimeoutE3Log::new();
        log.record(10000, 1, 20);
        log.record(11000, 2, 40);
        log.record(12000, 3, 60);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0() {
        let mut log = GossipTimeoutE3Log::new();
        log.record(13000, 5, 100);
        log.record(14000, 6, 100);
        log.entries[0].timed_out_msgs = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1() {
        let mut log = GossipTimeoutE3Log::new();
        log.record(15000, 5, 100);
        log.record(16000, 6, 100);
        log.entries[1].timed_out_msgs = 77;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut log1 = GossipTimeoutE3Log::new();
        let mut log2 = GossipTimeoutE3Log::new();
        let mut log3 = GossipTimeoutE3Log::new();
        let e1 = log1.record(17000, 7, 100);
        let h1 = e1.entry_hash;
        let e2 = log2.record(17000, 7, 100);
        let h2 = e2.entry_hash;
        let e3 = log3.record(17000, 7, 100);
        let h3 = e3.entry_hash;
        assert_eq!(h1, h2);
        assert_eq!(h2, h3);
    }

    #[test]
    fn high_timeout_rate_e3_count_mixed() {
        let mut log = GossipTimeoutE3Log::new();
        // rate = 4 → not high
        log.record(18000, 4, 100);
        // rate = 5 → high
        log.record(19000, 5, 100);
        // rate = 0 → not high
        log.record(20000, 0, 100);
        // rate = 10 → high
        log.record(21000, 10, 100);
        assert_eq!(log.high_timeout_rate_e3_count(), 2);
    }

    #[test]
    fn total_timed_out_msgs_sums_correctly() {
        let mut log = GossipTimeoutE3Log::new();
        log.record(22000, 3, 100);
        log.record(23000, 7, 100);
        log.record(24000, 15, 100);
        assert_eq!(log.total_timed_out_msgs(), 25);
    }

    #[test]
    fn mean_rate_pct_empty_returns_zero() {
        let log = GossipTimeoutE3Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn mean_rate_pct_multi_entry_correct() {
        let mut log = GossipTimeoutE3Log::new();
        // rate = 10
        log.record(25000, 10, 100);
        // rate = 20
        log.record(26000, 20, 100);
        // rate = 30
        log.record(27000, 30, 100);
        // mean = (10 + 20 + 30) / 3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn default_has_zero_entries() {
        let log = GossipTimeoutE3Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}