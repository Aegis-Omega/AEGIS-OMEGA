// EPISTEMIC TIER: T2 (engineering hypothesis)
// Gate 602 — Gossip Broadcast Phi Squared E7 Log
// Per-epoch measurement of the φ²=φ+1 self-similarity property in the gossip layer.
// squared_aligned_epochs: epochs where the ratio of secondary to primary metric ≈ φ+1 (within tolerance).
// total_epochs: denominator for rate.
// squared_rate_pct = (squared_aligned_epochs*100)/max(total_epochs,1) capped 100.
// phi_squared_e7: squared_rate_pct > PHI_SQUARED_E7_THRESHOLD (61).
// Threshold 61 ≈ φ×100: a topology satisfies the φ²=φ+1 identity constitutionally when
// ≥φ of its epochs exhibit the growth-factor self-similarity. The identity states the system
// grows by the same ratio it already is — non-destructive scaling at every level.
// entry_hash = SHA-256(prev[32]‖epoch_end_be8‖squared_aligned_epochs_be4‖total_epochs_be4‖squared_rate_pct_be4‖phi_squared_byte).
// GossipPhiSquaredE7Log: record(), phi_squared_e7_count(), total_squared_aligned_epochs(),
//   mean_squared_rate_pct(), verify_chain().

use sha2::{Digest, Sha256};

pub const GOSSIP_PHI_SQUARED_E7_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const PHI_SQUARED_E7_THRESHOLD: u32 = 61;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPhiSquaredE7Entry {
    pub epoch_end: u64,
    pub squared_aligned_epochs: u32,
    pub total_epochs: u32,
    pub squared_rate_pct: u32,
    pub phi_squared_e7: bool,
    pub entry_hash: [u8; 32],
    pub prev_hash: [u8; 32],
}

pub struct GossipPhiSquaredE7Log {
    entries: Vec<GossipPhiSquaredE7Entry>,
}

fn compute_phi_squared_e7_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    squared_aligned_epochs: u32,
    total_epochs: u32,
    squared_rate_pct: u32,
    phi_squared_e7: bool,
) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(prev);
    hasher.update(epoch_end.to_be_bytes());
    hasher.update(squared_aligned_epochs.to_be_bytes());
    hasher.update(total_epochs.to_be_bytes());
    hasher.update(squared_rate_pct.to_be_bytes());
    hasher.update([phi_squared_e7 as u8]);
    hasher.finalize().into()
}

impl GossipPhiSquaredE7Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn entry_count(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    pub fn entries(&self) -> &[GossipPhiSquaredE7Entry] {
        &self.entries
    }

    pub fn latest(&self) -> Option<&GossipPhiSquaredE7Entry> {
        self.entries.last()
    }

    pub fn record(&mut self, epoch_end: u64, squared_aligned_epochs: u32, total_epochs: u32) -> &GossipPhiSquaredE7Entry {
        let rate = ((squared_aligned_epochs as u64).saturating_mul(100)
            / (total_epochs.max(1) as u64))
            .min(100) as u32;
        let flag = rate > PHI_SQUARED_E7_THRESHOLD;
        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_PHI_SQUARED_E7_GENESIS_HASH);
        let hash = compute_phi_squared_e7_hash(&prev, epoch_end, squared_aligned_epochs, total_epochs, rate, flag);
        self.entries.push(GossipPhiSquaredE7Entry {
            epoch_end,
            squared_aligned_epochs,
            total_epochs,
            squared_rate_pct: rate,
            phi_squared_e7: flag,
            entry_hash: hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn phi_squared_e7_count(&self) -> usize {
        self.entries.iter().filter(|e| e.phi_squared_e7).count()
    }

    pub fn total_squared_aligned_epochs(&self) -> u64 {
        self.entries.iter().map(|e| e.squared_aligned_epochs as u64).fold(0u64, |a, v| a.saturating_add(v))
    }

    pub fn mean_squared_rate_pct(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        let sum: u64 = self.entries.iter().map(|e| e.squared_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_PHI_SQUARED_E7_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev { return (false, Some(i)); }
            let expected = compute_phi_squared_e7_hash(
                &prev, e.epoch_end, e.squared_aligned_epochs, e.total_epochs,
                e.squared_rate_pct, e.phi_squared_e7,
            );
            if e.entry_hash != expected { return (false, Some(i)); }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPhiSquaredE7Log {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields (1) ─────────────────────────────────────────────────────
    #[test]
    fn record_fields_stored() {
        let mut log = GossipPhiSquaredE7Log::new();
        let e = log.record(4000, 70, 100);
        assert_eq!(e.epoch_end, 4000);
        assert_eq!(e.squared_aligned_epochs, 70);
        assert_eq!(e.total_epochs, 100);
        assert_eq!(e.squared_rate_pct, 70);
        assert!(e.phi_squared_e7);
    }

    // ── threshold (6) ─────────────────────────────────────────────────────────
    #[test]
    fn zero_input_not_flagged() {
        let mut log = GossipPhiSquaredE7Log::new();
        let e = log.record(1, 0, 0);
        assert_eq!(e.squared_rate_pct, 0);
        assert!(!e.phi_squared_e7);
    }

    #[test]
    fn well_below_threshold_not_flagged() {
        let mut log = GossipPhiSquaredE7Log::new();
        let e = log.record(1, 20, 100);
        assert!(!e.phi_squared_e7);
    }

    #[test]
    fn just_below_threshold_not_flagged() {
        let mut log = GossipPhiSquaredE7Log::new();
        let e = log.record(1, 60, 100);
        assert_eq!(e.squared_rate_pct, 60);
        assert!(!e.phi_squared_e7);
    }

    #[test]
    fn at_threshold_strict_greater_not_flagged() {
        let mut log = GossipPhiSquaredE7Log::new();
        let e = log.record(1, 61, 100);
        assert_eq!(e.squared_rate_pct, 61);
        assert!(!e.phi_squared_e7); // strict >
    }

    #[test]
    fn just_above_threshold_flagged() {
        let mut log = GossipPhiSquaredE7Log::new();
        let e = log.record(1, 62, 100);
        assert_eq!(e.squared_rate_pct, 62);
        assert!(e.phi_squared_e7);
    }

    #[test]
    fn rate_capped_at_100() {
        let mut log = GossipPhiSquaredE7Log::new();
        let e = log.record(1, 500, 100);
        assert_eq!(e.squared_rate_pct, 100);
        assert!(e.phi_squared_e7);
    }

    // ── aggregates (2) ────────────────────────────────────────────────────────
    #[test]
    fn phi_squared_count_correct() {
        let mut log = GossipPhiSquaredE7Log::new();
        log.record(1, 50, 100); // 50% — not flagged
        log.record(2, 65, 100); // 65% — flagged
        log.record(3, 75, 100); // 75% — flagged
        assert_eq!(log.phi_squared_e7_count(), 2);
    }

    #[test]
    fn total_squared_aligned_correct() {
        let mut log = GossipPhiSquaredE7Log::new();
        log.record(1, 40, 100);
        log.record(2, 55, 100);
        assert_eq!(log.total_squared_aligned_epochs(), 95);
    }

    // ── hash chain (3) ────────────────────────────────────────────────────────
    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipPhiSquaredE7Log::new();
        let e = log.record(1, 65, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_is_genesis() {
        let mut log = GossipPhiSquaredE7Log::new();
        let e = log.record(1, 65, 100);
        assert_eq!(e.prev_hash, GOSSIP_PHI_SQUARED_E7_GENESIS_HASH);
    }

    #[test]
    fn chain_links_correctly() {
        let mut log = GossipPhiSquaredE7Log::new();
        log.record(1, 65, 100);
        log.record(2, 70, 100);
        let entries = log.entries();
        assert_eq!(entries[1].prev_hash, entries[0].entry_hash);
    }

    // ── verify_chain (6) ─────────────────────────────────────────────────────
    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipPhiSquaredE7Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_single_ok() {
        let mut log = GossipPhiSquaredE7Log::new();
        log.record(1, 65, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipPhiSquaredE7Log::new();
        log.record(1, 65, 100);
        log.record(2, 70, 100);
        log.record(3, 80, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_detects_tamper_at_first() {
        let mut log = GossipPhiSquaredE7Log::new();
        log.record(1, 65, 100);
        log.record(2, 70, 100);
        log.entries.first_mut().unwrap().squared_aligned_epochs ^= 1;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn verify_chain_detects_tamper_at_last() {
        let mut log = GossipPhiSquaredE7Log::new();
        log.record(1, 65, 100);
        log.record(2, 70, 100);
        log.record(3, 80, 100);
        log.entries.last_mut().unwrap().squared_aligned_epochs ^= 1;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(2));
    }

    #[test]
    fn verify_chain_detects_tamper_in_middle() {
        let mut log = GossipPhiSquaredE7Log::new();
        log.record(1, 65, 100);
        log.record(2, 70, 100);
        log.record(3, 80, 100);
        log.entries[1].squared_aligned_epochs ^= 1;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    // ── determinism (1) ──────────────────────────────────────────────────────
    #[test]
    fn entry_hash_deterministic() {
        let mut log_a = GossipPhiSquaredE7Log::new();
        let mut log_b = GossipPhiSquaredE7Log::new();
        log_a.record(999, 62, 100);
        log_b.record(999, 62, 100);
        assert_eq!(log_a.entries()[0].entry_hash, log_b.entries()[0].entry_hash);
    }
}
