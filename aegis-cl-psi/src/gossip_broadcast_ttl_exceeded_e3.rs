//! Gate 488 — Gossip Broadcast Ttl Exceeded E3 Monitor (T2)
//! Tracks ttl exceeded e3 rate per gossip broadcast epoch.
//! HIGH_TTL_EXCEED_E3_THRESHOLD = 4: rate_pct > 4 → high_ttl_exceed_e3

use sha2::{Sha256, Digest};

pub const TTL_EXCEEDED_E3_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_TTL_EXCEED_E3_THRESHOLD: u32 = 4;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipTtlExceededE3Entry {
    pub epoch_end:           u64,
    pub ttl_exceeded_msgs:   u32,
    pub total_sent:          u32,
    pub ttl_exceeded_rate_pct: u32,
    pub high_ttl_exceed_e3:  bool,
    pub entry_hash:          [u8; 32],
    pub prev_hash:           [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    ttl_exceeded_msgs: u32,
    total_sent: u32,
    rate_pct: u32,
    high_ttl_exceed_e3: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(ttl_exceeded_msgs.to_be_bytes());
    h.update(total_sent.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_ttl_exceed_e3 as u8]);
    h.finalize().into()
}

pub struct GossipTtlExceededE3Log {
    pub entries: Vec<GossipTtlExceededE3Entry>,
}

impl GossipTtlExceededE3Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        ttl_exceeded_msgs: u32,
        total_sent: u32,
    ) -> &GossipTtlExceededE3Entry {
        let denom = total_sent.max(1) as u64;
        let ttl_exceeded_rate_pct =
            ((ttl_exceeded_msgs as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_ttl_exceed_e3 = ttl_exceeded_rate_pct > HIGH_TTL_EXCEED_E3_THRESHOLD;
        let prev = self
            .entries
            .last()
            .map(|e| e.entry_hash)
            .unwrap_or(TTL_EXCEEDED_E3_GENESIS_HASH);
        let entry_hash = compute_hash(
            &prev,
            epoch_end,
            ttl_exceeded_msgs,
            total_sent,
            ttl_exceeded_rate_pct,
            high_ttl_exceed_e3,
        );
        self.entries.push(GossipTtlExceededE3Entry {
            epoch_end,
            ttl_exceeded_msgs,
            total_sent,
            ttl_exceeded_rate_pct,
            high_ttl_exceed_e3,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_ttl_exceed_e3_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_ttl_exceed_e3).count()
    }

    pub fn total_ttl_exceeded_msgs(&self) -> u64 {
        self.entries.iter().map(|e| e.ttl_exceeded_msgs as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.ttl_exceeded_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = TTL_EXCEEDED_E3_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.ttl_exceeded_msgs,
                e.total_sent,
                e.ttl_exceeded_rate_pct,
                e.high_ttl_exceed_e3,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipTtlExceededE3Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_flag_true() {
        let mut log = GossipTtlExceededE3Log::new();
        // rate = (10 * 100) / 100 = 10 > 4 → high_ttl_exceed_e3 = true
        let e = log.record(1000, 10, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.ttl_exceeded_msgs, 10);
        assert_eq!(e.total_sent, 100);
        assert_eq!(e.ttl_exceeded_rate_pct, 10);
        assert!(e.high_ttl_exceed_e3);
    }

    #[test]
    fn test_flag_false_when_exactly_at_threshold() {
        let mut log = GossipTtlExceededE3Log::new();
        // rate = (4 * 100) / 100 = 4, not > 4 → false
        let e = log.record(2000, 4, 100);
        assert_eq!(e.ttl_exceeded_rate_pct, 4);
        assert!(!e.high_ttl_exceed_e3);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipTtlExceededE3Log::new();
        // ttl_exceeded_msgs > total_sent → would exceed 100
        let e = log.record(3000, 200, 50);
        assert_eq!(e.ttl_exceeded_rate_pct, 100);
        assert!(e.high_ttl_exceed_e3);
    }

    #[test]
    fn test_total_sent_zero_no_div_by_zero() {
        let mut log = GossipTtlExceededE3Log::new();
        // total_sent = 0, denom = max(0,1) = 1 → rate = (5*100)/1 capped at 100
        let e = log.record(4000, 5, 0);
        assert_eq!(e.ttl_exceeded_rate_pct, 100);
        assert!(e.high_ttl_exceed_e3);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(HIGH_TTL_EXCEED_E3_THRESHOLD, 4);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipTtlExceededE3Log::new();
        let e = log.record(5000, 1, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipTtlExceededE3Log::new();
        let e = log.record(6000, 1, 100);
        assert_eq!(e.prev_hash, TTL_EXCEEDED_E3_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_is_first_entry_hash() {
        let mut log = GossipTtlExceededE3Log::new();
        let e1_hash = log.record(7000, 1, 100).entry_hash;
        let e2 = log.record(8000, 2, 100);
        assert_eq!(e2.prev_hash, e1_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipTtlExceededE3Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_single_entry() {
        let mut log = GossipTtlExceededE3Log::new();
        log.record(9000, 3, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipTtlExceededE3Log::new();
        log.record(10000, 1, 100);
        log.record(11000, 2, 100);
        log.record(12000, 3, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipTtlExceededE3Log::new();
        log.record(13000, 1, 100);
        log.record(14000, 2, 100);
        // Tamper the first entry's ttl_exceeded_msgs
        log.entries[0].ttl_exceeded_msgs = 99;
        let (valid, idx) = log.verify_chain();
        assert!(!valid);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipTtlExceededE3Log::new();
        log.record(15000, 1, 100);
        log.record(16000, 2, 100);
        log.record(17000, 3, 100);
        // Tamper the second entry's ttl_exceeded_msgs
        log.entries[1].ttl_exceeded_msgs = 99;
        let (valid, idx) = log.verify_chain();
        assert!(!valid);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let inputs = [(18000u64, 5u32, 100u32)];
        let mut hashes = Vec::new();
        for _ in 0..3 {
            let mut log = GossipTtlExceededE3Log::new();
            let (ep, tm, ts) = inputs[0];
            let e = log.record(ep, tm, ts);
            hashes.push(e.entry_hash);
        }
        assert_eq!(hashes[0], hashes[1]);
        assert_eq!(hashes[1], hashes[2]);
    }

    #[test]
    fn test_high_ttl_exceed_e3_count_mixed() {
        let mut log = GossipTtlExceededE3Log::new();
        // rate=4 → false
        log.record(19000, 4, 100);
        // rate=5 → true
        log.record(20000, 5, 100);
        // rate=0 → false
        log.record(21000, 0, 100);
        // rate=10 → true
        log.record(22000, 10, 100);
        assert_eq!(log.high_ttl_exceed_e3_count(), 2);
    }

    #[test]
    fn test_total_ttl_exceeded_msgs_sums_correctly() {
        let mut log = GossipTtlExceededE3Log::new();
        log.record(23000, 7, 100);
        log.record(24000, 13, 100);
        log.record(25000, 5, 100);
        assert_eq!(log.total_ttl_exceeded_msgs(), 25);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipTtlExceededE3Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry() {
        let mut log = GossipTtlExceededE3Log::new();
        // rate = 10
        log.record(26000, 10, 100);
        // rate = 20
        log.record(27000, 20, 100);
        // rate = 30
        log.record(28000, 30, 100);
        // mean = (10 + 20 + 30) / 3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn test_default_has_zero_entries() {
        let log = GossipTtlExceededE3Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}