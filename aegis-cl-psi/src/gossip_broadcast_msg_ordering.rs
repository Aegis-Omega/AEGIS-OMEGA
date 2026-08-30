//! Gate 450 — Gossip Broadcast Msg Ordering Monitor (T2)
//! Tracks msg ordering rate per gossip broadcast epoch.
//! HIGH_DISORDER_THRESHOLD = 5: rate_pct > 5 → high_disorder

use sha2::{Sha256, Digest};

pub const MSG_ORDERING_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_DISORDER_THRESHOLD: u32 = 5;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipMsgOrderingEntry {
    pub epoch_end:          u64,
    pub out_of_order_msgs:  u32,
    pub total_received:     u32,
    pub out_of_order_rate_pct: u32,
    pub high_disorder:      bool,
    pub entry_hash:         [u8; 32],
    pub prev_hash:          [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    out_of_order_msgs: u32,
    total_received: u32,
    rate_pct: u32,
    high_disorder: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(out_of_order_msgs.to_be_bytes());
    h.update(total_received.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_disorder as u8]);
    h.finalize().into()
}

pub struct GossipMsgOrderingLog {
    pub entries: Vec<GossipMsgOrderingEntry>,
}

impl GossipMsgOrderingLog {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        out_of_order_msgs: u32,
        total_received: u32,
    ) -> &GossipMsgOrderingEntry {
        let denom = total_received.max(1) as u64;
        let rate_pct = ((out_of_order_msgs as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_disorder = rate_pct > HIGH_DISORDER_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(MSG_ORDERING_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, out_of_order_msgs, total_received, rate_pct, high_disorder);
        self.entries.push(GossipMsgOrderingEntry {
            epoch_end,
            out_of_order_msgs,
            total_received,
            out_of_order_rate_pct: rate_pct,
            high_disorder,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_disorder_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_disorder).count()
    }

    pub fn total_out_of_order_msgs(&self) -> u64 {
        self.entries.iter().map(|e| e.out_of_order_msgs as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.out_of_order_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = MSG_ORDERING_GENESIS_HASH;
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
                e.high_disorder,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipMsgOrderingLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_set_correctly() {
        let mut log = GossipMsgOrderingLog::new();
        let e = log.record(1000, 10, 50);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.out_of_order_msgs, 10);
        assert_eq!(e.total_received, 50);
        assert_eq!(e.out_of_order_rate_pct, 20);
        assert!(e.high_disorder);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipMsgOrderingLog::new();
        // rate_pct == 5, not > 5, so high_disorder = false
        let e = log.record(2000, 5, 100);
        assert_eq!(e.out_of_order_rate_pct, 5);
        assert!(!e.high_disorder);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipMsgOrderingLog::new();
        let e = log.record(3000, 200, 50);
        assert_eq!(e.out_of_order_rate_pct, 100);
        assert!(e.high_disorder);
    }

    #[test]
    fn total_received_zero_no_div_by_zero() {
        let mut log = GossipMsgOrderingLog::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.out_of_order_rate_pct, 0);
        assert!(!e.high_disorder);
    }

    #[test]
    fn threshold_constant_value_is_5() {
        assert_eq!(HIGH_DISORDER_THRESHOLD, 5);
    }

    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipMsgOrderingLog::new();
        let e = log.record(5000, 3, 30);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_is_genesis() {
        let mut log = GossipMsgOrderingLog::new();
        let e = log.record(6000, 1, 10);
        assert_eq!(e.prev_hash, MSG_ORDERING_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipMsgOrderingLog::new();
        log.record(7000, 1, 10);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 2, 20);
        let second_prev = log.entries[1].prev_hash;
        assert_eq!(second_prev, first_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipMsgOrderingLog::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipMsgOrderingLog::new();
        log.record(9000, 1, 10);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipMsgOrderingLog::new();
        log.record(10000, 1, 10);
        log.record(11000, 2, 20);
        log.record(12000, 3, 30);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipMsgOrderingLog::new();
        log.record(13000, 1, 10);
        log.record(14000, 2, 20);
        log.entries[0].out_of_order_msgs = 99;
        let result = log.verify_chain();
        assert_eq!(result, (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipMsgOrderingLog::new();
        log.record(15000, 1, 10);
        log.record(16000, 2, 20);
        log.entries[1].out_of_order_msgs = 99;
        let result = log.verify_chain();
        assert_eq!(result, (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut log1 = GossipMsgOrderingLog::new();
        let mut log2 = GossipMsgOrderingLog::new();
        let mut log3 = GossipMsgOrderingLog::new();
        log1.record(17000, 5, 50);
        log2.record(17000, 5, 50);
        log3.record(17000, 5, 50);
        assert_eq!(log1.entries[0].entry_hash, log2.entries[0].entry_hash);
        assert_eq!(log2.entries[0].entry_hash, log3.entries[0].entry_hash);
    }

    #[test]
    fn high_disorder_count_mixed_log() {
        let mut log = GossipMsgOrderingLog::new();
        // rate = 0 → false
        log.record(18000, 0, 100);
        // rate = 5 → false (not > 5)
        log.record(18001, 5, 100);
        // rate = 6 → true
        log.record(18002, 6, 100);
        // rate = 50 → true
        log.record(18003, 50, 100);
        assert_eq!(log.high_disorder_count(), 2);
    }

    #[test]
    fn total_out_of_order_msgs_sums_correctly() {
        let mut log = GossipMsgOrderingLog::new();
        log.record(19000, 10, 100);
        log.record(19001, 20, 200);
        log.record(19002, 30, 300);
        assert_eq!(log.total_out_of_order_msgs(), 60);
    }

    #[test]
    fn mean_rate_pct_empty_returns_zero() {
        let log = GossipMsgOrderingLog::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn mean_rate_pct_multi_entry_correct() {
        let mut log = GossipMsgOrderingLog::new();
        // rate = 10
        log.record(20000, 10, 100);
        // rate = 20
        log.record(20001, 20, 100);
        // rate = 30
        log.record(20002, 30, 100);
        // mean = (10+20+30)/3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn default_produces_zero_entries() {
        let log = GossipMsgOrderingLog::default();
        assert_eq!(log.entries.len(), 0);
    }
}