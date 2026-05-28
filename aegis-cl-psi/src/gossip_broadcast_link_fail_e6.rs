//! Gate 582 — Gossip Broadcast Link Fail E6 Monitor (T2)
//! Tracks link failure rate per gossip broadcast epoch.
//! HIGH_LINK_FAIL_E6_THRESHOLD = 9: fail_rate_pct > 9 → high_link_fail_e6

use sha2::{Sha256, Digest};

pub const LINK_FAIL_E6_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_LINK_FAIL_E6_THRESHOLD: u32 = 9;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipLinkFailE6Entry {
    pub epoch_end:          u64,
    pub failed_links:       u32,
    pub total_links:        u32,
    pub fail_rate_pct:      u32,
    pub high_link_fail_e6:  bool,
    pub entry_hash:         [u8; 32],
    pub prev_hash:          [u8; 32],
}

fn compute_hash(prev: &[u8; 32], epoch_end: u64, failed_links: u32, total_links: u32, rate_pct: u32, high_link_fail_e6: bool) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev); h.update(epoch_end.to_be_bytes());
    h.update(failed_links.to_be_bytes()); h.update(total_links.to_be_bytes());
    h.update(rate_pct.to_be_bytes()); h.update([high_link_fail_e6 as u8]);
    h.finalize().into()
}

pub struct GossipLinkFailE6Log { pub entries: Vec<GossipLinkFailE6Entry> }

impl GossipLinkFailE6Log {
    pub fn new() -> Self { Self { entries: Vec::new() } }
    pub fn record(&mut self, epoch_end: u64, failed_links: u32, total_links: u32) -> &GossipLinkFailE6Entry {
        let denom = total_links.max(1) as u64;
        let fail_rate_pct = ((failed_links as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_link_fail_e6 = fail_rate_pct > HIGH_LINK_FAIL_E6_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(LINK_FAIL_E6_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, failed_links, total_links, fail_rate_pct, high_link_fail_e6);
        self.entries.push(GossipLinkFailE6Entry { epoch_end, failed_links, total_links, fail_rate_pct, high_link_fail_e6, entry_hash, prev_hash: prev });
        self.entries.last().unwrap()
    }
    pub fn high_link_fail_e6_count(&self) -> usize { self.entries.iter().filter(|e| e.high_link_fail_e6).count() }
    pub fn total_failed_links(&self) -> u64 { self.entries.iter().map(|e| e.failed_links as u64).sum() }
    pub fn mean_fail_rate_pct(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        (self.entries.iter().map(|e| e.fail_rate_pct as u64).sum::<u64>() / self.entries.len() as u64) as u32
    }
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = LINK_FAIL_E6_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev { return (false, Some(i)); }
            if e.entry_hash != compute_hash(&prev, e.epoch_end, e.failed_links, e.total_links, e.fail_rate_pct, e.high_link_fail_e6) { return (false, Some(i)); }
            prev = e.entry_hash;
        }
        (true, None)
    }
}
impl Default for GossipLinkFailE6Log { fn default() -> Self { Self::new() } }

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipLinkFailE6Log::new();
        let e = log.record(1000, 14, 100);
        assert_eq!(e.epoch_end, 1000); assert_eq!(e.failed_links, 14);
        assert_eq!(e.total_links, 100); assert_eq!(e.fail_rate_pct, 14);
        assert!(e.high_link_fail_e6);
    }
    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipLinkFailE6Log::new();
        let e = log.record(2000, 9, 100);
        assert_eq!(e.fail_rate_pct, 9); assert!(!e.high_link_fail_e6);
    }
    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipLinkFailE6Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.fail_rate_pct, 100); assert!(e.high_link_fail_e6);
    }
    #[test]
    fn total_links_zero_no_div_by_zero() {
        let mut log = GossipLinkFailE6Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.fail_rate_pct, 0); assert!(!e.high_link_fail_e6);
    }
    #[test]
    fn threshold_constant_value_is_9() { assert_eq!(HIGH_LINK_FAIL_E6_THRESHOLD, 9); }
    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipLinkFailE6Log::new();
        assert_ne!(log.record(5000, 11, 80).entry_hash, [0u8; 32]);
    }
    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipLinkFailE6Log::new();
        assert_eq!(log.record(6000, 7, 80).prev_hash, LINK_FAIL_E6_GENESIS_HASH);
    }
    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipLinkFailE6Log::new();
        log.record(7000, 7, 80);
        let h = log.entries[0].entry_hash;
        log.record(8000, 14, 100);
        assert_eq!(log.entries[1].prev_hash, h);
    }
    #[test]
    fn verify_chain_empty_returns_true_none() { assert_eq!(GossipLinkFailE6Log::new().verify_chain(), (true, None)); }
    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipLinkFailE6Log::new();
        log.record(9000, 10, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }
    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipLinkFailE6Log::new();
        log.record(10000, 5, 60); log.record(11000, 10, 80); log.record(12000, 16, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }
    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipLinkFailE6Log::new();
        log.record(13000, 7, 80); log.record(14000, 14, 100);
        log.entries[0].failed_links = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }
    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipLinkFailE6Log::new();
        log.record(15000, 7, 80); log.record(16000, 14, 100);
        log.entries[1].failed_links = 99;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }
    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut l1 = GossipLinkFailE6Log::new(); let mut l2 = GossipLinkFailE6Log::new(); let mut l3 = GossipLinkFailE6Log::new();
        let e1 = l1.record(17000, 11, 90).entry_hash; let e2 = l2.record(17000, 11, 90).entry_hash; let e3 = l3.record(17000, 11, 90).entry_hash;
        assert_eq!(e1, e2); assert_eq!(e2, e3);
    }
    #[test]
    fn high_link_fail_e6_count_mixed_log() {
        let mut log = GossipLinkFailE6Log::new();
        log.record(18000, 7, 100); log.record(19000, 14, 100); log.record(20000, 9, 100); log.record(21000, 10, 100);
        assert_eq!(log.high_link_fail_e6_count(), 2);
    }
    #[test]
    fn total_failed_links_sums_correctly() {
        let mut log = GossipLinkFailE6Log::new();
        log.record(22000, 10, 100); log.record(23000, 25, 100); log.record(24000, 7, 100);
        assert_eq!(log.total_failed_links(), 42);
    }
    #[test]
    fn mean_fail_rate_pct_empty_returns_zero() { assert_eq!(GossipLinkFailE6Log::new().mean_fail_rate_pct(), 0); }
    #[test]
    fn mean_fail_rate_pct_multi_entry_correct() {
        let mut log = GossipLinkFailE6Log::new();
        log.record(25000, 10, 100); log.record(26000, 20, 100); log.record(27000, 30, 100);
        assert_eq!(log.mean_fail_rate_pct(), 20);
    }
    #[test]
    fn default_produces_zero_entries() { assert_eq!(GossipLinkFailE6Log::default().entries.len(), 0); }
}
