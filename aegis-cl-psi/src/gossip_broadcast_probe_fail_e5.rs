//! Gate 561 — Gossip Broadcast Probe Fail E5 Monitor (T2)
//! Tracks probe failure rate per gossip broadcast epoch.
//! HIGH_PROBE_FAIL_E5_THRESHOLD = 14: fail_rate_pct > 14 → high_probe_fail_e5

use sha2::{Sha256, Digest};

pub const PROBE_FAIL_E5_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const HIGH_PROBE_FAIL_E5_THRESHOLD: u32 = 14;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipProbeFailE5Entry {
    pub epoch_end:          u64,
    pub failed_probes:      u32,
    pub total_probes:       u32,
    pub fail_rate_pct:      u32,
    pub high_probe_fail_e5: bool,
    pub entry_hash:         [u8; 32],
    pub prev_hash:          [u8; 32],
}

fn compute_hash(prev: &[u8; 32], epoch_end: u64, failed_probes: u32, total_probes: u32, rate_pct: u32, high_probe_fail_e5: bool) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev); h.update(epoch_end.to_be_bytes());
    h.update(failed_probes.to_be_bytes()); h.update(total_probes.to_be_bytes());
    h.update(rate_pct.to_be_bytes()); h.update([high_probe_fail_e5 as u8]);
    h.finalize().into()
}

pub struct GossipProbeFailE5Log { pub entries: Vec<GossipProbeFailE5Entry> }

impl GossipProbeFailE5Log {
    pub fn new() -> Self { Self { entries: Vec::new() } }
    pub fn record(&mut self, epoch_end: u64, failed_probes: u32, total_probes: u32) -> &GossipProbeFailE5Entry {
        let denom = total_probes.max(1) as u64;
        let fail_rate_pct = ((failed_probes as u64).saturating_mul(100) / denom).min(100) as u32;
        let high_probe_fail_e5 = fail_rate_pct > HIGH_PROBE_FAIL_E5_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(PROBE_FAIL_E5_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, failed_probes, total_probes, fail_rate_pct, high_probe_fail_e5);
        self.entries.push(GossipProbeFailE5Entry { epoch_end, failed_probes, total_probes, fail_rate_pct, high_probe_fail_e5, entry_hash, prev_hash: prev });
        self.entries.last().unwrap()
    }
    pub fn high_probe_fail_e5_count(&self) -> usize { self.entries.iter().filter(|e| e.high_probe_fail_e5).count() }
    pub fn total_failed_probes(&self) -> u64 { self.entries.iter().map(|e| e.failed_probes as u64).sum() }
    pub fn mean_fail_rate_pct(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        (self.entries.iter().map(|e| e.fail_rate_pct as u64).sum::<u64>() / self.entries.len() as u64) as u32
    }
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = PROBE_FAIL_E5_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev { return (false, Some(i)); }
            if e.entry_hash != compute_hash(&prev, e.epoch_end, e.failed_probes, e.total_probes, e.fail_rate_pct, e.high_probe_fail_e5) { return (false, Some(i)); }
            prev = e.entry_hash;
        }
        (true, None)
    }
}
impl Default for GossipProbeFailE5Log { fn default() -> Self { Self::new() } }

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn record_fields_correct_flag_true_when_above_threshold() {
        let mut log = GossipProbeFailE5Log::new();
        let e = log.record(1000, 20, 100);
        assert_eq!(e.epoch_end, 1000); assert_eq!(e.failed_probes, 20);
        assert_eq!(e.total_probes, 100); assert_eq!(e.fail_rate_pct, 20);
        assert!(e.high_probe_fail_e5);
    }
    #[test]
    fn flag_false_when_exactly_at_threshold() {
        let mut log = GossipProbeFailE5Log::new();
        let e = log.record(2000, 14, 100);
        assert_eq!(e.fail_rate_pct, 14); assert!(!e.high_probe_fail_e5);
    }
    #[test]
    fn rate_pct_capped_at_100() {
        let mut log = GossipProbeFailE5Log::new();
        let e = log.record(3000, 200, 100);
        assert_eq!(e.fail_rate_pct, 100); assert!(e.high_probe_fail_e5);
    }
    #[test]
    fn total_probes_zero_no_div_by_zero() {
        let mut log = GossipProbeFailE5Log::new();
        let e = log.record(4000, 0, 0);
        assert_eq!(e.fail_rate_pct, 0); assert!(!e.high_probe_fail_e5);
    }
    #[test]
    fn threshold_constant_value_is_14() { assert_eq!(HIGH_PROBE_FAIL_E5_THRESHOLD, 14); }
    #[test]
    fn entry_hash_non_zero() {
        let mut log = GossipProbeFailE5Log::new();
        assert_ne!(log.record(5000, 16, 80).entry_hash, [0u8; 32]);
    }
    #[test]
    fn first_prev_hash_equals_genesis() {
        let mut log = GossipProbeFailE5Log::new();
        assert_eq!(log.record(6000, 10, 80).prev_hash, PROBE_FAIL_E5_GENESIS_HASH);
    }
    #[test]
    fn second_prev_hash_equals_first_entry_hash() {
        let mut log = GossipProbeFailE5Log::new();
        log.record(7000, 10, 80);
        let h = log.entries[0].entry_hash;
        log.record(8000, 20, 100);
        assert_eq!(log.entries[1].prev_hash, h);
    }
    #[test]
    fn verify_chain_empty_returns_true_none() { assert_eq!(GossipProbeFailE5Log::new().verify_chain(), (true, None)); }
    #[test]
    fn verify_chain_one_entry_returns_true_none() {
        let mut log = GossipProbeFailE5Log::new();
        log.record(9000, 15, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }
    #[test]
    fn verify_chain_three_entries_returns_true_none() {
        let mut log = GossipProbeFailE5Log::new();
        log.record(10000, 8, 60); log.record(11000, 15, 80); log.record(12000, 22, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }
    #[test]
    fn verify_chain_tamper_entry_0_returns_false_some_0() {
        let mut log = GossipProbeFailE5Log::new();
        log.record(13000, 10, 80); log.record(14000, 20, 100);
        log.entries[0].failed_probes = 99;
        assert_eq!(log.verify_chain(), (false, Some(0)));
    }
    #[test]
    fn verify_chain_tamper_entry_1_returns_false_some_1() {
        let mut log = GossipProbeFailE5Log::new();
        log.record(15000, 10, 80); log.record(16000, 20, 100);
        log.entries[1].failed_probes = 99;
        assert_eq!(log.verify_chain(), (false, Some(1)));
    }
    #[test]
    fn determinism_same_inputs_same_hash() {
        let mut l1 = GossipProbeFailE5Log::new(); let mut l2 = GossipProbeFailE5Log::new(); let mut l3 = GossipProbeFailE5Log::new();
        let e1 = l1.record(17000, 16, 90).entry_hash; let e2 = l2.record(17000, 16, 90).entry_hash; let e3 = l3.record(17000, 16, 90).entry_hash;
        assert_eq!(e1, e2); assert_eq!(e2, e3);
    }
    #[test]
    fn high_probe_fail_e5_count_mixed_log() {
        let mut log = GossipProbeFailE5Log::new();
        log.record(18000, 11, 100); log.record(19000, 20, 100); log.record(20000, 14, 100); log.record(21000, 15, 100);
        assert_eq!(log.high_probe_fail_e5_count(), 2);
    }
    #[test]
    fn total_failed_probes_sums_correctly() {
        let mut log = GossipProbeFailE5Log::new();
        log.record(22000, 10, 100); log.record(23000, 25, 100); log.record(24000, 7, 100);
        assert_eq!(log.total_failed_probes(), 42);
    }
    #[test]
    fn mean_fail_rate_pct_empty_returns_zero() { assert_eq!(GossipProbeFailE5Log::new().mean_fail_rate_pct(), 0); }
    #[test]
    fn mean_fail_rate_pct_multi_entry_correct() {
        let mut log = GossipProbeFailE5Log::new();
        log.record(25000, 10, 100); log.record(26000, 20, 100); log.record(27000, 30, 100);
        assert_eq!(log.mean_fail_rate_pct(), 20);
    }
    #[test]
    fn default_produces_zero_entries() { assert_eq!(GossipProbeFailE5Log::default().entries.len(), 0); }
}
