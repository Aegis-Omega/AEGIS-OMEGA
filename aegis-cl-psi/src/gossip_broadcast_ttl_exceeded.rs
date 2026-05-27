//! Gate 453 — Gossip Broadcast Ttl Exceeded Monitor (T2)
//! Tracks ttl exceeded rate per gossip broadcast epoch.
//! HIGH_TTL_EXCEED_THRESHOLD = 4: rate_pct > 4 → high_ttl_exceed

use sha2::{Sha256, Digest};

pub const TTL_EXCEEDED_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_TTL_EXCEED_THRESHOLD: u32 = 4;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipTtlExceededEntry {
    pub epoch_end:           u64,
    pub ttl_exceeded_msgs:   u32,
    pub total_sent:          u32,
    pub ttl_exceeded_rate_pct: u32,
    pub high_ttl_exceed:     bool,
    pub entry_hash:          [u8; 32],
    pub prev_hash:           [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    ttl_exceeded_msgs: u32,
    total_sent: u32,
    rate_pct: u32,
    high_ttl_exceed: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(ttl_exceeded_msgs.to_be_bytes());
    h.update(total_sent.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_ttl_exceed as u8]);
    h.finalize().into()
}

pub struct GossipTtlExceededLog {
    pub entries: Vec<GossipTtlExceededEntry>,
}

impl GossipTtlExceededLog {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        ttl_exceeded_msgs: u32,
        total_sent: u32,
    ) -> &GossipTtlExceededEntry {
        let denom = total_sent.max(1) as u64;
        let ttl_exceeded_rate_pct = ((ttl_exceeded_msgs as u64).saturating_mul(100) / denom)
            .min(100) as u32;
        let high_ttl_exceed = ttl_exceeded_rate_pct > HIGH_TTL_EXCEED_THRESHOLD;
        let prev = self
            .entries
            .last()
            .map(|e| e.entry_hash)
            .unwrap_or(TTL_EXCEEDED_GENESIS_HASH);
        let entry_hash = compute_hash(
            &prev,
            epoch_end,
            ttl_exceeded_msgs,
            total_sent,
            ttl_exceeded_rate_pct,
            high_ttl_exceed,
        );
        self.entries.push(GossipTtlExceededEntry {
            epoch_end,
            ttl_exceeded_msgs,
            total_sent,
            ttl_exceeded_rate_pct,
            high_ttl_exceed,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_ttl_exceed_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_ttl_exceed).count()
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
        let mut prev = TTL_EXCEEDED_GENESIS_HASH;
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
                e.high_ttl_exceed,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipTtlExceededLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_flag_true() {
        let mut log = GossipTtlExceededLog::new();
        // rate = (10 * 100) / 100 = 10 > 4 → high_ttl_exceed = true
        let e = log.record(1000, 10, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.ttl_exceeded_msgs, 10);
        assert_eq!(e.total_sent, 100);
        assert_eq!(e.ttl_exceeded_rate_pct, 10);
        assert!(e.high_ttl_exceed);
    }

    #[test]
    fn test_flag_false_when_at_threshold() {
        let mut log = GossipTtlExceededLog::new();
        // rate = (4 * 100) / 100 = 4, not > 4 → high_ttl_exceed = false
        let e = log.record(2000, 4, 100);
        assert_eq!(e.ttl_exceeded_rate_pct, 4);
        assert!(!e.high_ttl_exceed);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipTtlExceededLog::new();
        // 200 exceeded out of 100 sent → raw rate = 200 → capped at 100
        let e = log.record(3000, 200, 100);
        assert_eq!(e.ttl_exceeded_rate_pct, 100);
    }

    #[test]
    fn test_total_sent_zero_no_div_by_zero() {
        let mut log = GossipTtlExceededLog::new();
        // total_sent = 0 → denom = max(0,1) = 1 → rate = 0 * 100 / 1 = 0
        let e = log.record(4000, 0, 0);
        assert_eq!(e.ttl_exceeded_rate_pct, 0);
        assert!(!e.high_ttl_exceed);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(HIGH_TTL_EXCEED_THRESHOLD, 4);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipTtlExceededLog::new();
        let e = log.record(5000, 5, 50);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipTtlExceededLog::new();
        let e = log.record(6000, 1, 20);
        assert_eq!(e.prev_hash, TTL_EXCEEDED_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipTtlExceededLog::new();
        log.record(7000, 1, 20);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 2, 20);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipTtlExceededLog::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_single_entry() {
        let mut log = GossipTtlExceededLog::new();
        log.record(9000, 3, 60);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipTtlExceededLog::new();
        log.record(10000, 2, 40);
        log.record(10001, 5, 50);
        log.record(10002, 1, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipTtlExceededLog::new();
        log.record(11000, 2, 40);
        log.record(11001, 5, 50);
        // Tamper entry 0's hash
        log.entries[0].entry_hash = [0xAB; 32];
        let (valid, idx) = log.verify_chain();
        assert!(!valid);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipTtlExceededLog::new();
        log.record(12000, 2, 40);
        log.record(12001, 5, 50);
        log.record(12002, 1, 100);
        // Tamper entry 1's ttl_exceeded_msgs to break content hash
        log.entries[1].ttl_exceeded_msgs = 99;
        let (valid, idx) = log.verify_chain();
        assert!(!valid);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipTtlExceededLog::new();
        let mut log2 = GossipTtlExceededLog::new();
        let mut log3 = GossipTtlExceededLog::new();
        log1.record(13000, 7, 70);
        log2.record(13000, 7, 70);
        log3.record(13000, 7, 70);
        assert_eq!(log1.entries[0].entry_hash, log2.entries[0].entry_hash);
        assert_eq!(log2.entries[0].entry_hash, log3.entries[0].entry_hash);
    }

    #[test]
    fn test_high_ttl_exceed_count_mixed() {
        let mut log = GossipTtlExceededLog::new();
        // rate = 0 → false
        log.record(14000, 0, 100);
        // rate = 5 > 4 → true
        log.record(14001, 5, 100);
        // rate = 4 → false
        log.record(14002, 4, 100);
        // rate = 10 > 4 → true
        log.record(14003, 10, 100);
        assert_eq!(log.high_ttl_exceed_count(), 2);
    }

    #[test]
    fn test_total_ttl_exceeded_msgs_sums_correctly() {
        let mut log = GossipTtlExceededLog::new();
        log.record(15000, 3, 100);
        log.record(15001, 7, 100);
        log.record(15002, 11, 100);
        assert_eq!(log.total_ttl_exceeded_msgs(), 21u64);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipTtlExceededLog::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry_correct() {
        let mut log = GossipTtlExceededLog::new();
        // rate = 10
        log.record(16000, 10, 100);
        // rate = 20
        log.record(16001, 20, 100);
        // rate = 30
        log.record(16002, 30, 100);
        // mean = (10 + 20 + 30) / 3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn test_default_has_zero_entries() {
        let log = GossipTtlExceededLog::default();
        assert_eq!(log.entries.len(), 0);
    }
}