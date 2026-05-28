//! Gate 517 — Gossip Broadcast Rebroadcast E4 Monitor (T2)
//! Tracks rebroadcast e4 rate per gossip broadcast epoch.
//! HIGH_REBROADCAST_E4_THRESHOLD = 12: rate_pct > 12 → high_rebroadcast_e4

use sha2::{Sha256, Digest};

pub const REBROADCAST_E4_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_REBROADCAST_E4_THRESHOLD: u32 = 12;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipRebroadcastE4Entry {
    pub epoch_end:            u64,
    pub rebroadcast_count:    u32,
    pub total_sent:           u32,
    pub rebroadcast_rate_pct: u32,
    pub high_rebroadcast_e4:  bool,
    pub entry_hash:           [u8; 32],
    pub prev_hash:            [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    rebroadcast_count: u32,
    total_sent: u32,
    rebroadcast_rate_pct: u32,
    high_rebroadcast_e4: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(rebroadcast_count.to_be_bytes());
    h.update(total_sent.to_be_bytes());
    h.update(rebroadcast_rate_pct.to_be_bytes());
    h.update([high_rebroadcast_e4 as u8]);
    h.finalize().into()
}

pub struct GossipRebroadcastE4Log {
    pub entries: Vec<GossipRebroadcastE4Entry>,
}

impl GossipRebroadcastE4Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        rebroadcast_count: u32,
        total_sent: u32,
    ) -> &GossipRebroadcastE4Entry {
        let denom = total_sent.max(1) as u64;
        let rebroadcast_rate_pct =
            ((rebroadcast_count as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_rebroadcast_e4 = rebroadcast_rate_pct > HIGH_REBROADCAST_E4_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(REBROADCAST_E4_GENESIS_HASH);
        let entry_hash = compute_hash(
            &prev,
            epoch_end,
            rebroadcast_count,
            total_sent,
            rebroadcast_rate_pct,
            high_rebroadcast_e4,
        );
        self.entries.push(GossipRebroadcastE4Entry {
            epoch_end,
            rebroadcast_count,
            total_sent,
            rebroadcast_rate_pct,
            high_rebroadcast_e4,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_rebroadcast_e4_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_rebroadcast_e4).count()
    }

    pub fn total_rebroadcast_count(&self) -> u64 {
        self.entries.iter().map(|e| e.rebroadcast_count as u64).sum()
    }

    pub fn mean_rate_pct(&self) -> u32 {
        if self.entries.is_empty() {
            return 0;
        }
        let sum: u64 = self.entries.iter().map(|e| e.rebroadcast_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = REBROADCAST_E4_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_hash(
                &prev,
                e.epoch_end,
                e.rebroadcast_count,
                e.total_sent,
                e.rebroadcast_rate_pct,
                e.high_rebroadcast_e4,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipRebroadcastE4Log {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipRebroadcastE4Log::new();
        let e = log.record(1000, 20, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.rebroadcast_count, 20);
        assert_eq!(e.total_sent, 100);
        assert_eq!(e.rebroadcast_rate_pct, 20);
        assert!(e.high_rebroadcast_e4);
    }

    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipRebroadcastE4Log::new();
        // rebroadcast_count=12, total_sent=100 => rate=12, not > 12 => false
        let e = log.record(2000, 12, 100);
        assert_eq!(e.rebroadcast_rate_pct, 12);
        assert!(!e.high_rebroadcast_e4);
    }

    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipRebroadcastE4Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.rebroadcast_rate_pct, 100);
        assert!(e.high_rebroadcast_e4);
    }

    #[test]
    fn total_sent_zero_no_div_by_zero() {
        let mut log = GossipRebroadcastE4Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.rebroadcast_rate_pct, 0);
        assert!(!e.high_rebroadcast_e4);
    }

    #[test]
    fn threshold_constant_value_is_12() {
        assert_eq!(HIGH_REBROADCAST_E4_THRESHOLD, 12);
    }

    #[test]
    fn entry_hash_is_non_zero() {
        let mut log = GossipRebroadcastE4Log::new();
        let e = log.record(5000, 10, 50);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipRebroadcastE4Log::new();
        let e = log.record(6000, 5, 50);
        assert_eq!(e.prev_hash, REBROADCAST_E4_GENESIS_HASH);
    }

    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipRebroadcastE4Log::new();
        log.record(7000, 5, 50);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 10, 50);
        assert_eq!(log.entries[1].prev_hash, first_hash);
    }

    #[test]
    fn verify_chain_empty_returns_true_none() {
        let log = GossipRebroadcastE4Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipRebroadcastE4Log::new();
        log.record(9000, 5, 50);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipRebroadcastE4Log::new();
        log.record(10000, 5, 50);
        log.record(11000, 8, 60);
        log.record(12000, 15, 70);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipRebroadcastE4Log::new();
        log.record(13000, 5, 50);
        log.record(14000, 8, 60);
        log.entries[0].rebroadcast_count = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }

    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipRebroadcastE4Log::new();
        log.record(15000, 5, 50);
        log.record(16000, 8, 60);
        log.entries[1].rebroadcast_count = 99;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }

    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut log1 = GossipRebroadcastE4Log::new();
        let mut log2 = GossipRebroadcastE4Log::new();
        let mut log3 = GossipRebroadcastE4Log::new();
        let e1 = log1.record(17000, 10, 80).entry_hash;
        let e2 = log2.record(17000, 10, 80).entry_hash;
        let e3 = log3.record(17000, 10, 80).entry_hash;
        assert_eq!(e1, e2);
        assert_eq!(e2, e3);
    }

    #[test]
    fn high_rebroadcast_e4_count_mixed_log() {
        let mut log = GossipRebroadcastE4Log::new();
        log.record(18000, 5, 100);  // rate=5, false
        log.record(19000, 20, 100); // rate=20, true
        log.record(20000, 12, 100); // rate=12, false (boundary)
        log.record(21000, 13, 100); // rate=13, true
        assert_eq!(log.high_rebroadcast_e4_count(), 2);
    }

    #[test]
    fn total_rebroadcast_count_sums_correctly() {
        let mut log = GossipRebroadcastE4Log::new();
        log.record(22000, 10, 100);
        log.record(23000, 25, 100);
        log.record(24000, 7, 100);
        assert_eq!(log.total_rebroadcast_count(), 42);
    }

    #[test]
    fn mean_rate_pct_empty_returns_zero() {
        let log = GossipRebroadcastE4Log::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn mean_rate_pct_multi_entry_correct() {
        let mut log = GossipRebroadcastE4Log::new();
        log.record(25000, 10, 100); // rate=10
        log.record(26000, 20, 100); // rate=20
        log.record(27000, 30, 100); // rate=30
        // mean = (10+20+30)/3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn default_produces_zero_entries() {
        let log = GossipRebroadcastE4Log::default();
        assert_eq!(log.entries.len(), 0);
    }
}
