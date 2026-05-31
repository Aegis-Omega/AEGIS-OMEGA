// EPISTEMIC TIER: T2 (engineering hypothesis)
// Gate 605 — Gossip Broadcast Phi Seal E8 Log
// Terminal capstone of the gossip broadcast φ-series.
// Measures whether the cumulative phi_stability_e8 record has reached a sealed state:
// stable_records: entries in the phi_stability_e8 log where phi_stability_e8=true.
// total_records: total entries recorded.
// seal_rate_pct = (stable_records*100)/max(total_records,1) capped 100.
// sealed: seal_rate_pct > PHI_SEAL_E8_THRESHOLD (61).
// When sealed, the gossip topology has demonstrated sustained constitutional φ-stability
// across its entire hash-chained lifetime. Gates 602–605 together form the complete
// φ-certification chain: each direction independently (602, 603), both simultaneously (604),
// and the cumulative lifetime seal (605). A sealed topology has no further φ obligation.
// entry_hash = SHA-256(prev[32]‖epoch_end_be8‖stable_records_be4‖total_records_be4‖seal_rate_pct_be4‖sealed_byte).
// GossipPhiSealE8Log: record(), sealed_count(), total_stable_records(),
//   mean_seal_rate_pct(), verify_chain().

use sha2::{Digest, Sha256};

pub const GOSSIP_PHI_SEAL_E8_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const PHI_SEAL_E8_THRESHOLD: u32 = 61;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPhiSealE8Entry {
    pub epoch_end: u64,
    pub stable_records: u32,
    pub total_records: u32,
    pub seal_rate_pct: u32,
    pub sealed: bool,
    pub entry_hash: [u8; 32],
    pub prev_hash: [u8; 32],
}

pub struct GossipPhiSealE8Log {
    entries: Vec<GossipPhiSealE8Entry>,
}

fn compute_phi_seal_e8_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    stable_records: u32,
    total_records: u32,
    seal_rate_pct: u32,
    sealed: bool,
) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(prev);
    hasher.update(epoch_end.to_be_bytes());
    hasher.update(stable_records.to_be_bytes());
    hasher.update(total_records.to_be_bytes());
    hasher.update(seal_rate_pct.to_be_bytes());
    hasher.update([sealed as u8]);
    hasher.finalize().into()
}

impl GossipPhiSealE8Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn entry_count(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    pub fn entries(&self) -> &[GossipPhiSealE8Entry] {
        &self.entries
    }

    pub fn latest(&self) -> Option<&GossipPhiSealE8Entry> {
        self.entries.last()
    }

    pub fn record(&mut self, epoch_end: u64, stable_records: u32, total_records: u32) -> &GossipPhiSealE8Entry {
        let rate = ((stable_records as u64).saturating_mul(100)
            / (total_records.max(1) as u64))
            .min(100) as u32;
        let flag = rate > PHI_SEAL_E8_THRESHOLD;
        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_PHI_SEAL_E8_GENESIS_HASH);
        let hash = compute_phi_seal_e8_hash(&prev, epoch_end, stable_records, total_records, rate, flag);
        self.entries.push(GossipPhiSealE8Entry {
            epoch_end,
            stable_records,
            total_records,
            seal_rate_pct: rate,
            sealed: flag,
            entry_hash: hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn sealed_count(&self) -> usize {
        self.entries.iter().filter(|e| e.sealed).count()
    }

    pub fn total_stable_records(&self) -> u64 {
        self.entries.iter().map(|e| e.stable_records as u64).fold(0u64, |a, v| a.saturating_add(v))
    }

    pub fn mean_seal_rate_pct(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        let sum: u64 = self.entries.iter().map(|e| e.seal_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_PHI_SEAL_E8_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev { return (false, Some(i)); }
            let expected = compute_phi_seal_e8_hash(
                &prev, e.epoch_end, e.stable_records, e.total_records,
                e.seal_rate_pct, e.sealed,
            );
            if e.entry_hash != expected { return (false, Some(i)); }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPhiSealE8Log {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields (1) ─────────────────────────────────────────────────────
    #[test]
    fn record_fields_stored() {
        let mut log = GossipPhiSealE8Log::new();
        let e = log.record(9000, 70, 100);
        assert_eq!(e.epoch_end, 9000);
        assert_eq!(e.stable_records, 70);
        assert_eq!(e.total_records, 100);
        assert_eq!(e.seal_rate_pct, 70);
        assert!(e.sealed);
    }

    // ── threshold (6) ─────────────────────────────────────────────────────────
    #[test]
    fn zero_input_not_sealed() {
        let mut log = GossipPhiSealE8Log::new();
        let e = log.record(1, 0, 0);
        assert_eq!(e.seal_rate_pct, 0);
        assert!(!e.sealed);
    }

    #[test]
    fn well_below_threshold_not_sealed() {
        let mut log = GossipPhiSealE8Log::new();
        let e = log.record(1, 20, 100);
        assert!(!e.sealed);
    }

    #[test]
    fn just_below_threshold_not_sealed() {
        let mut log = GossipPhiSealE8Log::new();
        let e = log.record(1, 60, 100);
        assert_eq!(e.seal_rate_pct, 60);
        assert!(!e.sealed);
    }

    #[test]
    fn at_threshold_strict_greater_not_sealed() {
        let mut log = GossipPhiSealE8Log::new();
        let e = log.record(1, 61, 100);
        assert_eq!(e.seal_rate_pct, 61);
        assert!(!e.sealed); // strict >
    }

    #[test]
    fn just_above_threshold_sealed() {
        let mut log = GossipPhiSealE8Log::new();
        let e = log.record(1, 62, 100);
        assert_eq!(e.seal_rate_pct, 62);
        assert!(e.sealed);
    }

    #[test]
    fn rate_capped_at_100() {
        let mut log = GossipPhiSealE8Log::new();
        let e = log.record(1, 300, 100);
        assert_eq!(e.seal_rate_pct, 100);
        assert!(e.sealed);
    }

    // ── aggregates (2) ────────────────────────────────────────────────────────
    #[test]
    fn sealed_count_correct() {
        let mut log = GossipPhiSealE8Log::new();
        log.record(1, 30, 100); // 30% — not sealed
        log.record(2, 65, 100); // 65% — sealed
        log.record(3, 80, 100); // 80% — sealed
        assert_eq!(log.sealed_count(), 2);
    }

    #[test]
    fn total_stable_records_correct() {
        let mut log = GossipPhiSealE8Log::new();
        log.record(1, 40, 100);
        log.record(2, 60, 100);
        assert_eq!(log.total_stable_records(), 100);
    }

    // ── hash chain (3) ────────────────────────────────────────────────────────
    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipPhiSealE8Log::new();
        let e = log.record(1, 70, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_is_genesis() {
        let mut log = GossipPhiSealE8Log::new();
        let e = log.record(1, 70, 100);
        assert_eq!(e.prev_hash, GOSSIP_PHI_SEAL_E8_GENESIS_HASH);
    }

    #[test]
    fn chain_links_correctly() {
        let mut log = GossipPhiSealE8Log::new();
        log.record(1, 70, 100);
        log.record(2, 75, 100);
        let entries = log.entries();
        assert_eq!(entries[1].prev_hash, entries[0].entry_hash);
    }

    // ── verify_chain (6) ─────────────────────────────────────────────────────
    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipPhiSealE8Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_single_ok() {
        let mut log = GossipPhiSealE8Log::new();
        log.record(1, 70, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipPhiSealE8Log::new();
        log.record(1, 70, 100);
        log.record(2, 75, 100);
        log.record(3, 80, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_detects_tamper_at_first() {
        let mut log = GossipPhiSealE8Log::new();
        log.record(1, 70, 100);
        log.record(2, 75, 100);
        log.entries.first_mut().unwrap().stable_records ^= 1;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn verify_chain_detects_tamper_at_last() {
        let mut log = GossipPhiSealE8Log::new();
        log.record(1, 70, 100);
        log.record(2, 75, 100);
        log.record(3, 80, 100);
        log.entries.last_mut().unwrap().stable_records ^= 1;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(2));
    }

    #[test]
    fn verify_chain_detects_tamper_in_middle() {
        let mut log = GossipPhiSealE8Log::new();
        log.record(1, 70, 100);
        log.record(2, 75, 100);
        log.record(3, 80, 100);
        log.entries[1].stable_records ^= 1;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    // ── determinism (1) ──────────────────────────────────────────────────────
    #[test]
    fn entry_hash_deterministic() {
        let mut log_a = GossipPhiSealE8Log::new();
        let mut log_b = GossipPhiSealE8Log::new();
        log_a.record(2000, 68, 100);
        log_b.record(2000, 68, 100);
        assert_eq!(log_a.entries()[0].entry_hash, log_b.entries()[0].entry_hash);
    }
}
