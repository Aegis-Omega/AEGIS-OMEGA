//! Gate 447 — Gossip Broadcast Rebroadcast Monitor (T2)
//! Tracks rebroadcast rate per gossip broadcast epoch.
//! HIGH_REBROADCAST_THRESHOLD = 12: rate_pct > 12 → high_rebroadcast

use sha2::{Sha256, Digest};

pub const REBROADCAST_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_REBROADCAST_THRESHOLD: u32 = 12;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipRebroadcastEntry {
    pub epoch_end:          u64,
    pub rebroadcast_count:  u32,
    pub total_sent:         u32,
    pub rebroadcast_rate_pct: u32,
    pub high_rebroadcast:   bool,
    pub entry_hash:         [u8; 32],
    pub prev_hash:          [u8; 32],
}

fn compute_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    rebroadcast_count: u32,
    total_sent: u32,
    rate_pct: u32,
    high_rebroadcast: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(rebroadcast_count.to_be_bytes());
    h.update(total_sent.to_be_bytes());
    h.update(rate_pct.to_be_bytes());
    h.update([high_rebroadcast as u8]);
    h.finalize().into()
}

pub struct GossipRebroadcastLog {
    pub entries: Vec<GossipRebroadcastEntry>,
}

impl GossipRebroadcastLog {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn record(
        &mut self,
        epoch_end: u64,
        rebroadcast_count: u32,
        total_sent: u32,
    ) -> &GossipRebroadcastEntry {
        let denom = total_sent.max(1) as u64;
        let rebroadcast_rate_pct = ((rebroadcast_count as u64).saturating_mul(100) / denom)
            .min(100) as u32;
        let high_rebroadcast = rebroadcast_rate_pct > HIGH_REBROADCAST_THRESHOLD;
        let prev = self
            .entries
            .last()
            .map(|e| e.entry_hash)
            .unwrap_or(REBROADCAST_GENESIS_HASH);
        let entry_hash = compute_hash(
            &prev,
            epoch_end,
            rebroadcast_count,
            total_sent,
            rebroadcast_rate_pct,
            high_rebroadcast,
        );
        self.entries.push(GossipRebroadcastEntry {
            epoch_end,
            rebroadcast_count,
            total_sent,
            rebroadcast_rate_pct,
            high_rebroadcast,
            entry_hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn high_rebroadcast_count(&self) -> usize {
        self.entries.iter().filter(|e| e.high_rebroadcast).count()
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
        let mut prev = REBROADCAST_GENESIS_HASH;
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
                e.high_rebroadcast,
            );
            if e.entry_hash != expected {
                return (false, Some(i));
            }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipRebroadcastLog {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_fields_correct_flag_true() {
        let mut log = GossipRebroadcastLog::new();
        // rebroadcast_count=20, total_sent=50 => rate = 2000/50 = 40 > 12 => high=true
        let e = log.record(1000, 20, 50);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.rebroadcast_count, 20);
        assert_eq!(e.total_sent, 50);
        assert_eq!(e.rebroadcast_rate_pct, 40);
        assert!(e.high_rebroadcast);
    }

    #[test]
    fn test_flag_false_when_exactly_at_threshold() {
        let mut log = GossipRebroadcastLog::new();
        // rate = 12 => not > 12 => high=false
        // rebroadcast_count=12, total_sent=100 => rate = 1200/100 = 12
        let e = log.record(2000, 12, 100);
        assert_eq!(e.rebroadcast_rate_pct, 12);
        assert!(!e.high_rebroadcast);
    }

    #[test]
    fn test_rate_pct_capped_at_100() {
        let mut log = GossipRebroadcastLog::new();
        // rebroadcast_count=200, total_sent=100 => raw=200, capped=100
        let e = log.record(3000, 200, 100);
        assert_eq!(e.rebroadcast_rate_pct, 100);
        assert!(e.high_rebroadcast);
    }

    #[test]
    fn test_total_sent_zero_no_div_by_zero() {
        let mut log = GossipRebroadcastLog::new();
        // total_sent=0 => denom=1, rebroadcast_count=5 => rate=500, capped=100
        let e = log.record(4000, 5, 0);
        assert_eq!(e.rebroadcast_rate_pct, 100);
        assert!(e.high_rebroadcast);
    }

    #[test]
    fn test_threshold_constant_value() {
        assert_eq!(HIGH_REBROADCAST_THRESHOLD, 12u32);
    }

    #[test]
    fn test_entry_hash_non_zero() {
        let mut log = GossipRebroadcastLog::new();
        let e = log.record(5000, 10, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn test_first_prev_hash_is_genesis() {
        let mut log = GossipRebroadcastLog::new();
        let e = log.record(6000, 5, 100);
        assert_eq!(e.prev_hash, REBROADCAST_GENESIS_HASH);
    }

    #[test]
    fn test_second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipRebroadcastLog::new();
        log.record(7000, 5, 100);
        let first_hash = log.entries[0].entry_hash;
        log.record(8000, 10, 100);
        let second = &log.entries[1];
        assert_eq!(second.prev_hash, first_hash);
    }

    #[test]
    fn test_verify_chain_empty() {
        let log = GossipRebroadcastLog::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_one_entry() {
        let mut log = GossipRebroadcastLog::new();
        log.record(9000, 5, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_three_entries() {
        let mut log = GossipRebroadcastLog::new();
        log.record(10000, 5, 100);
        log.record(11000, 10, 100);
        log.record(12000, 15, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn test_verify_chain_tamper_entry_0() {
        let mut log = GossipRebroadcastLog::new();
        log.record(13000, 5, 100);
        log.record(14000, 10, 100);
        log.entries[0].rebroadcast_count = 99;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn test_verify_chain_tamper_entry_1() {
        let mut log = GossipRebroadcastLog::new();
        log.record(15000, 5, 100);
        log.record(16000, 10, 100);
        log.entries[1].rebroadcast_count = 77;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn test_determinism_same_inputs_same_hash() {
        let mut log1 = GossipRebroadcastLog::new();
        let mut log2 = GossipRebroadcastLog::new();
        let mut log3 = GossipRebroadcastLog::new();
        log1.record(17000, 8, 100);
        log2.record(17000, 8, 100);
        log3.record(17000, 8, 100);
        assert_eq!(log1.entries[0].entry_hash, log2.entries[0].entry_hash);
        assert_eq!(log2.entries[0].entry_hash, log3.entries[0].entry_hash);
    }

    #[test]
    fn test_high_rebroadcast_count_mixed_log() {
        let mut log = GossipRebroadcastLog::new();
        // rate=5 => not high
        log.record(18000, 5, 100);
        // rate=50 => high
        log.record(19000, 50, 100);
        // rate=12 => not high (exactly at threshold)
        log.record(20000, 12, 100);
        // rate=13 => high
        log.record(21000, 13, 100);
        assert_eq!(log.high_rebroadcast_count(), 2);
    }

    #[test]
    fn test_total_rebroadcast_count_sums_correctly() {
        let mut log = GossipRebroadcastLog::new();
        log.record(22000, 10, 100);
        log.record(23000, 20, 100);
        log.record(24000, 30, 100);
        assert_eq!(log.total_rebroadcast_count(), 60u64);
    }

    #[test]
    fn test_mean_rate_pct_empty_returns_zero() {
        let log = GossipRebroadcastLog::new();
        assert_eq!(log.mean_rate_pct(), 0);
    }

    #[test]
    fn test_mean_rate_pct_multi_entry_correct() {
        let mut log = GossipRebroadcastLog::new();
        // rate=10
        log.record(25000, 10, 100);
        // rate=20
        log.record(26000, 20, 100);
        // rate=30
        log.record(27000, 30, 100);
        // mean = (10+20+30)/3 = 20
        assert_eq!(log.mean_rate_pct(), 20);
    }

    #[test]
    fn test_default_has_zero_entries() {
        let log = GossipRebroadcastLog::default();
        assert_eq!(log.entries.len(), 0);
    }
}