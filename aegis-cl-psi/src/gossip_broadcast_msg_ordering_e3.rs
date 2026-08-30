//! Gate 485 — Gossip Broadcast Msg Ordering E3 Monitor (T2)
//! Tracks msg ordering e3 rate per gossip broadcast epoch.
//! HIGH_DISORDER_E3_THRESHOLD = 5: rate_pct > 5 → high_disorder_e3

use sha2::{Sha256, Digest};

pub const MSG_ORDERING_E3_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_DISORDER_E3_THRESHOLD: u32 = 5;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipMsgOrderingE3Entry {
    pub epoch_end:            u64,
    pub out_of_order_msgs:    u32,
    pub total_received:       u32,
    pub out_of_order_rate_pct: u32,
    pub high_disorder_e3:     bool,
    pub entry_hash:           [u8; 32],
    pub prev_hash:            [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    out_of_order_msgs: u32,
    total_received: u32,
    rate_pct: u32,
    high_disorder_e3: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(out_of_order_msgs.to_be_bytes());
    h.update(total_received.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_disorder_e3 as u8]);
    h.finalize().into()
}

pub struct GossipMsgOrderingE3Log {
    pub entries: Vec<GossipMsgOrderingE3Entry>,
}

impl GossipMsgOrderingE3Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        out_of_order_msgs: u32,
        total_received: u32,
    ) -> &GossipMsgOrderingE3Entry {
        let denom = total_received.max(1) as u64;
        let rate_pct = ((out_of_order_msgs as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_disorder_e3 = rate_pct > HIGH_DISORDER_E3_THRESHOLD;
        let prev = self
            .entries
            .last()
            .map(|e| e.entry_hash)
            .unwrap_or(MSG_ORDERING_E3_GENESIS_HASH);
        let entry_hash = compute_hash(
            &prev,
            epoch_end,
            out_of_order_msgs,
            total_received,
            rate_pct,
            high_disorder_e3,
        );
        self.entries.push(GossipMsgOrderingE3Entry {
            epoch_end,
            out_of_order_msgs,
            total_received,
            out_of_order_rate_pct: rate_pct,
            high_disorder_e3,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_disorder_e3_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_disorder_e3).count()
    }

    pub fn total_out_of_order_msgs(&self) -> u64 {
        self.entries
            .iter()
            .map(|e| e.out_of_order_msgs as u64)
            .fold(0u64, |acc, v| acc.saturating_add(v))
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self
            .entries
            .iter()
            .map(|e| e.out_of_order_rate_pct as u64)
            .fold(0u64, |acc, v| acc.saturating_add(v));
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = MSG_ORDERING_E3_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.out_of_order_msgs,
                e.total_received,
                e.out_of_order_rate_pct,
                e.high_disorder_e3,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipMsgOrderingE3Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_flag_true() {
        let mut log = GossipMsgOrderingE3Log::new();
        let e = log.record(1000, 10, 50);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.out_of_order_msgs, 10);
        assert_eq!(e.total_received, 50);
        // rate = (10 * 100) / 50 = 20
        assert_eq!(e.out_of_order_rate_pct, 20);
        // 20 > 5 → true
        assert!(e.high_disorder_e3);
    }

    #[test]
    fn test_flag_false_at_threshold_boundary() {
        let mut log = GossipMsgOrderingE3Log::new();
        // rate = (5 * 100) / 100 = 5; 5 > 5 is false
        let e = log.record(2000, 5, 100);
        assert_eq!(e.out_of_order_rate_pct, 5);
        assert!(!e.high_disorder_e3);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipMsgOrderingE3Log::new();
        // out_of_order_msgs > total_received
        let e = log.record(3000, 200, 50);
        assert_eq!(e.out_of_order_rate_pct, 100);
    }

    #[test]
    fn test_total_received_zero_no_div_by_zero() {
        let mut log = GossipMsgOrderingE3Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.out_of_order_rate_pct, 0);
        assert!(!e.high_disorder_e3);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(HIGH_DISORDER_E3_THRESHOLD, 5);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipMsgOrderingE3Log::new();
        let e = log.record(5000, 10, 50);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipMsgOrderingE3Log::new();
        let e = log.record(6000, 1, 10);
        assert_eq!(e.prev_hash, MSG_ORDERING_E3_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipMsgOrderingE3Log::new();
        log.record(7000, 1, 10);
        let first_hash = log.entries[0].entry_hash;
        log.record(7001, 2, 20);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipMsgOrderingE3Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_one_entry() {
        let mut log = GossipMsgOrderingE3Log::new();
        log.record(8000, 3, 30);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipMsgOrderingE3Log::new();
        log.record(9000, 1, 10);
        log.record(9001, 2, 20);
        log.record(9002, 3, 30);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipMsgOrderingE3Log::new();
        log.record(10000, 1, 10);
        log.record(10001, 2, 20);
        // Tamper entry 0's out_of_order_msgs
        log.entries[0].out_of_order_msgs = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipMsgOrderingE3Log::new();
        log.record(11000, 1, 10);
        log.record(11001, 2, 20);
        log.record(11002, 3, 30);
        // Tamper entry 1's total_received
        log.entries[1].total_received = 999;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipMsgOrderingE3Log::new();
        let mut log2 = GossipMsgOrderingE3Log::new();
        let mut log3 = GossipMsgOrderingE3Log::new();
        log1.record(12000, 5, 50);
        log2.record(12000, 5, 50);
        log3.record(12000, 5, 50);
        assert_eq!(log1.entries[0].entry_hash, log2.entries[0].entry_hash);
        assert_eq!(log2.entries[0].entry_hash, log3.entries[0].entry_hash);
    }

    #[test]
    fn test_high_disorder_e3_count_mixed_log() {
        let mut log = GossipMsgOrderingE3Log::new();
        // rate = 5 → not high
        log.record(13000, 5, 100);
        // rate = 6 → high
        log.record(13001, 6, 100);
        // rate = 0 → not high
        log.record(13002, 0, 100);
        // rate = 20 → high
        log.record(13003, 20, 100);
        assert_eq!(log.high_disorder_e3_count(), 2);
    }

    #[test]
    fn test_total_out_of_order_msgs_sums_correctly() {
        let mut log = GossipMsgOrderingE3Log::new();
        log.record(14000, 10, 100);
        log.record(14001, 20, 200);
        log.record(14002, 30, 300);
        assert_eq!(log.total_out_of_order_msgs(), 60);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipMsgOrderingE3Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry_correct() {
        let mut log = GossipMsgOrderingE3Log::new();
        // rate = 10
        log.record(15000, 10, 100);
        // rate = 20
        log.record(15001, 20, 100);
        // rate = 30
        log.record(15002, 30, 100);
        // mean = (10 + 20 + 30) / 3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn test_default_zero_entries() {
        let log = GossipMsgOrderingE3Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}