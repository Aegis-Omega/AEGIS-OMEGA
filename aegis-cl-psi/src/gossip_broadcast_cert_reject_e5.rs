//! Gate 560 — Gossip Broadcast Cert Reject E5 Monitor (T2)
//! Tracks certificate rejection rate per gossip broadcast epoch.
//! HIGH_CERT_REJECT_E5_THRESHOLD = 4: reject_rate_pct > 4 → high_cert_reject_e5

use sha2::{Sha256, Digest};

pub const CERT_REJECT_E5_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_CERT_REJECT_E5_THRESHOLD: u32 = 4;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipCertRejectE5Entry {
    pub epoch_end:          u64,
    pub rejected_certs:     u32,
    pub total_certs:        u32,
    pub reject_rate_pct:    u32,
    pub high_cert_reject_e5: bool,
    pub entry_hash:         [u8; 32],
    pub prev_hash:          [u8; 32],
}

fn compute_hash(prev: &[u8; 32], epoch_end: u64, rejected_certs: u32, total_certs: u32, rate_pct: u32, high_cert_reject_e5: bool) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev); h.update(epoch_end.to_be_bytes());
    h.update(rejected_certs.to_be_bytes()); h.update(total_certs.to_be_bytes());
    h.update(rate_pct.to_be_bytes()); h.update([high_cert_reject_e5 as u8]);
    h.finalize().into()
}

pub struct GossipCertRejectE5Log { pub entries: Vec<GossipCertRejectE5Entry> }

impl GossipCertRejectE5Log {
    pub fn new() -> Self { Self { entries: Vec::new() } }
    pub fn record(&mut self, epoch_end: u64, rejected_certs: u32, total_certs: u32) -> &GossipCertRejectE5Entry {
        let denom = total_certs.max(1) as u64;
        let reject_rate_pct = ((rejected_certs as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_cert_reject_e5 = reject_rate_pct > HIGH_CERT_REJECT_E5_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(CERT_REJECT_E5_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, rejected_certs, total_certs, reject_rate_pct, high_cert_reject_e5);
        self.entries.push(GossipCertRejectE5Entry { epoch_end, rejected_certs, total_certs, reject_rate_pct, high_cert_reject_e5, entry_hash, prev_hash: prev });
        self.entries.last().unwrap()
    }
    pub fn high_cert_reject_e5_count(&self) -> usize { self.entries.iter().filter(|e| e.high_cert_reject_e5).count() }
    pub fn total_rejected_certs(&self) -> u64 { self.entries.iter().map(|e| e.rejected_certs as u64).sum() }
    pub fn mean_reject_rate_pct(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        (self.entries.iter().map(|e| e.reject_rate_pct as u64).sum::<u64>() / self.entries.len() as u64) as u32
    }
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = CERT_REJECT_E5_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev { return (false, Some(i)); }
            if e.entry_hash != compute_hash(&prev, e.epoch_end, e.rejected_certs, e.total_certs, e.reject_rate_pct, e.high_cert_reject_e5) { return (false, Some(i)); }
            prev = e.entry_hash;
        }
        (true, None)
    }
}
impl Default for GossipCertRejectE5Log { fn default() -> Self { Self::new() } }

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipCertRejectE5Log::new();
        let e = log.record(1000, 8, 100);
        assert_eq!(e.epoch_end, 1000); assert_eq!(e.rejected_certs, 8);
        assert_eq!(e.total_certs, 100); assert_eq!(e.reject_rate_pct, 8);
        assert!(e.high_cert_reject_e5);
    }
    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipCertRejectE5Log::new();
        let e = log.record(2000, 4, 100);
        assert_eq!(e.reject_rate_pct, 4); assert!(!e.high_cert_reject_e5);
    }
    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipCertRejectE5Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.reject_rate_pct, 100); assert!(e.high_cert_reject_e5);
    }
    #[test]
    fn total_certs_zero_no_div_by_zero() {
        let mut log = GossipCertRejectE5Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.reject_rate_pct, 0); assert!(!e.high_cert_reject_e5);
    }
    #[test]
    fn threshold_constant_value_is_4() { assert_eq!(HIGH_CERT_REJECT_E5_THRESHOLD, 4); }
    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipCertRejectE5Log::new();
        assert_ne!(log.record(5000, 6, 80).entry_hash, [0u8; 32]);
    }
    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipCertRejectE5Log::new();
        assert_eq!(log.record(6000, 3, 80).prev_hash, CERT_REJECT_E5_GENESIS_HASH);
    }
    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipCertRejectE5Log::new();
        log.record(7000, 3, 80);
        let h = log.entries[0].entry_hash;
        log.record(8000, 8, 100);
        assert_eq!(log.entries[1].prev_hash, h);
    }
    #[test]
    fn verify_chain_empty_returns_true_none() { assert_eq!(GossipCertRejectE5Log::new().verify_chain(), (true, None)); }
    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipCertRejectE5Log::new();
        log.record(9000, 5, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }
    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipCertRejectE5Log::new();
        log.record(10000, 2, 60); log.record(11000, 5, 80); log.record(12000, 8, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }
    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipCertRejectE5Log::new();
        log.record(13000, 3, 80); log.record(14000, 8, 100);
        log.entries[0].rejected_certs = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }
    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipCertRejectE5Log::new();
        log.record(15000, 3, 80); log.record(16000, 8, 100);
        log.entries[1].rejected_certs = 99;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }
    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut l1 = GossipCertRejectE5Log::new(); let mut l2 = GossipCertRejectE5Log::new(); let mut l3 = GossipCertRejectE5Log::new();
        let e1 = l1.record(17000, 6, 90).entry_hash; let e2 = l2.record(17000, 6, 90).entry_hash; let e3 = l3.record(17000, 6, 90).entry_hash;
        assert_eq!(e1, e2); assert_eq!(e2, e3);
    }
    #[test]
    fn high_cert_reject_e5_count_mixed_log() {
        let mut log = GossipCertRejectE5Log::new();
        log.record(18000, 3, 100); log.record(19000, 8, 100); log.record(20000, 4, 100); log.record(21000, 5, 100);
        assert_eq!(log.high_cert_reject_e5_count(), 2);
    }
    #[test]
    fn total_rejected_certs_sums_correctly() {
        let mut log = GossipCertRejectE5Log::new();
        log.record(22000, 10, 100); log.record(23000, 25, 100); log.record(24000, 7, 100);
        assert_eq!(log.total_rejected_certs(), 42);
    }
    #[test]
    fn mean_reject_rate_pct_empty_returns_zero() { assert_eq!(GossipCertRejectE5Log::new().mean_reject_rate_pct(), 0); }
    #[test]
    fn mean_reject_rate_pct_multi_entry_correct() {
        let mut log = GossipCertRejectE5Log::new();
        log.record(25000, 10, 100); log.record(26000, 20, 100); log.record(27000, 30, 100);
        assert_eq!(log.mean_reject_rate_pct(), 20);
    }
    #[test]
    fn default_produces_zero_entries() { assert_eq!(GossipCertRejectE5Log::default().entries.len(), 0); }
}
