// EPISTEMIC TIER: T2 (engineering hypothesis)
// Gate 604 — Gossip Broadcast Phi Stability E8 Log
// Dual-φ synthesis: epochs where BOTH φ²=φ+1 (squared) AND 1/φ=φ−1 (reciprocal) hold simultaneously.
// stability_epochs: epochs satisfying both squared_aligned AND reciprocal_aligned criteria.
// total_epochs: denominator for rate.
// stability_rate_pct = (stability_epochs*100)/max(total_epochs,1) capped 100.
// phi_stability_e8: stability_rate_pct > PHI_STABILITY_E8_THRESHOLD (61).
// Threshold 61 ≈ φ×100: a system where ≥φ of its epochs are dual-φ-aligned has reached the
// highest constitutional φ-stability — both directions of φ's self-definition satisfied together.
// Gates 602+603 certified each direction independently; Gate 604 certifies their simultaneous
// presence as a unified constitutional property of the gossip topology.
// entry_hash = SHA-256(prev[32]‖epoch_end_be8‖stability_epochs_be4‖total_epochs_be4‖stability_rate_pct_be4‖phi_stability_byte).
// GossipPhiStabilityE8Log: record(), phi_stability_e8_count(), total_stability_epochs(),
//   mean_stability_rate_pct(), verify_chain().

use sha2::{Digest, Sha256};

pub const GOSSIP_PHI_STABILITY_E8_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const PHI_STABILITY_E8_THRESHOLD: u32 = 61;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPhiStabilityE8Entry {
    pub epoch_end: u64,
    pub stability_epochs: u32,
    pub total_epochs: u32,
    pub stability_rate_pct: u32,
    pub phi_stability_e8: bool,
    pub entry_hash: [u8; 32],
    pub prev_hash: [u8; 32],
}

pub struct GossipPhiStabilityE8Log {
    entries: Vec<GossipPhiStabilityE8Entry>,
}

fn compute_phi_stability_e8_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    stability_epochs: u32,
    total_epochs: u32,
    stability_rate_pct: u32,
    phi_stability_e8: bool,
) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(prev);
    hasher.update(epoch_end.to_be_bytes());
    hasher.update(stability_epochs.to_be_bytes());
    hasher.update(total_epochs.to_be_bytes());
    hasher.update(stability_rate_pct.to_be_bytes());
    hasher.update([phi_stability_e8 as u8]);
    hasher.finalize().into()
}

impl GossipPhiStabilityE8Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn entry_count(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    pub fn entries(&self) -> &[GossipPhiStabilityE8Entry] {
        &self.entries
    }

    pub fn latest(&self) -> Option<&GossipPhiStabilityE8Entry> {
        self.entries.last()
    }

    pub fn record(&mut self, epoch_end: u64, stability_epochs: u32, total_epochs: u32) -> &GossipPhiStabilityE8Entry {
        let rate = ((stability_epochs as u64).saturating_mul(100)
            / (total_epochs.max(1) as u64))
            .min(100) as u32;
        let flag = rate > PHI_STABILITY_E8_THRESHOLD;
        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_PHI_STABILITY_E8_GENESIS_HASH);
        let hash = compute_phi_stability_e8_hash(&prev, epoch_end, stability_epochs, total_epochs, rate, flag);
        self.entries.push(GossipPhiStabilityE8Entry {
            epoch_end,
            stability_epochs,
            total_epochs,
            stability_rate_pct: rate,
            phi_stability_e8: flag,
            entry_hash: hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn phi_stability_e8_count(&self) -> usize {
        self.entries.iter().filter(|e| e.phi_stability_e8).count()
    }

    pub fn total_stability_epochs(&self) -> u64 {
        self.entries.iter().map(|e| e.stability_epochs as u64).fold(0u64, |a, v| a.saturating_add(v))
    }

    pub fn mean_stability_rate_pct(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        let sum: u64 = self.entries.iter().map(|e| e.stability_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_PHI_STABILITY_E8_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev { return (false, Some(i)); }
            let expected = compute_phi_stability_e8_hash(
                &prev, e.epoch_end, e.stability_epochs, e.total_epochs,
                e.stability_rate_pct, e.phi_stability_e8,
            );
            if e.entry_hash != expected { return (false, Some(i)); }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPhiStabilityE8Log {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields (1) ─────────────────────────────────────────────────────
    #[test]
    fn record_fields_stored() {
        let mut log = GossipPhiStabilityE8Log::new();
        let e = log.record(8000, 65, 100);
        assert_eq!(e.epoch_end, 8000);
        assert_eq!(e.stability_epochs, 65);
        assert_eq!(e.total_epochs, 100);
        assert_eq!(e.stability_rate_pct, 65);
        assert!(e.phi_stability_e8);
    }

    // ── threshold (6) ─────────────────────────────────────────────────────────
    #[test]
    fn zero_input_not_flagged() {
        let mut log = GossipPhiStabilityE8Log::new();
        let e = log.record(1, 0, 0);
        assert_eq!(e.stability_rate_pct, 0);
        assert!(!e.phi_stability_e8);
    }

    #[test]
    fn well_below_threshold_not_flagged() {
        let mut log = GossipPhiStabilityE8Log::new();
        let e = log.record(1, 10, 100);
        assert!(!e.phi_stability_e8);
    }

    #[test]
    fn just_below_threshold_not_flagged() {
        let mut log = GossipPhiStabilityE8Log::new();
        let e = log.record(1, 60, 100);
        assert_eq!(e.stability_rate_pct, 60);
        assert!(!e.phi_stability_e8);
    }

    #[test]
    fn at_threshold_strict_greater_not_flagged() {
        let mut log = GossipPhiStabilityE8Log::new();
        let e = log.record(1, 61, 100);
        assert_eq!(e.stability_rate_pct, 61);
        assert!(!e.phi_stability_e8); // strict >
    }

    #[test]
    fn just_above_threshold_flagged() {
        let mut log = GossipPhiStabilityE8Log::new();
        let e = log.record(1, 62, 100);
        assert_eq!(e.stability_rate_pct, 62);
        assert!(e.phi_stability_e8);
    }

    #[test]
    fn rate_capped_at_100() {
        let mut log = GossipPhiStabilityE8Log::new();
        let e = log.record(1, 500, 100);
        assert_eq!(e.stability_rate_pct, 100);
        assert!(e.phi_stability_e8);
    }

    // ── aggregates (2) ────────────────────────────────────────────────────────
    #[test]
    fn phi_stability_count_correct() {
        let mut log = GossipPhiStabilityE8Log::new();
        log.record(1, 40, 100); // 40% — not flagged
        log.record(2, 70, 100); // 70% — flagged
        log.record(3, 75, 100); // 75% — flagged
        assert_eq!(log.phi_stability_e8_count(), 2);
    }

    #[test]
    fn total_stability_epochs_correct() {
        let mut log = GossipPhiStabilityE8Log::new();
        log.record(1, 30, 100);
        log.record(2, 55, 100);
        assert_eq!(log.total_stability_epochs(), 85);
    }

    // ── hash chain (3) ────────────────────────────────────────────────────────
    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipPhiStabilityE8Log::new();
        let e = log.record(1, 65, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_is_genesis() {
        let mut log = GossipPhiStabilityE8Log::new();
        let e = log.record(1, 65, 100);
        assert_eq!(e.prev_hash, GOSSIP_PHI_STABILITY_E8_GENESIS_HASH);
    }

    #[test]
    fn chain_links_correctly() {
        let mut log = GossipPhiStabilityE8Log::new();
        log.record(1, 65, 100);
        log.record(2, 70, 100);
        let entries = log.entries();
        assert_eq!(entries[1].prev_hash, entries[0].entry_hash);
    }

    // ── verify_chain (6) ─────────────────────────────────────────────────────
    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipPhiStabilityE8Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_single_ok() {
        let mut log = GossipPhiStabilityE8Log::new();
        log.record(1, 65, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipPhiStabilityE8Log::new();
        log.record(1, 65, 100);
        log.record(2, 70, 100);
        log.record(3, 80, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_detects_tamper_at_first() {
        let mut log = GossipPhiStabilityE8Log::new();
        log.record(1, 65, 100);
        log.record(2, 70, 100);
        log.entries.first_mut().unwrap().stability_epochs ^= 1;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn verify_chain_detects_tamper_at_last() {
        let mut log = GossipPhiStabilityE8Log::new();
        log.record(1, 65, 100);
        log.record(2, 70, 100);
        log.record(3, 80, 100);
        log.entries.last_mut().unwrap().stability_epochs ^= 1;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(2));
    }

    #[test]
    fn verify_chain_detects_tamper_in_middle() {
        let mut log = GossipPhiStabilityE8Log::new();
        log.record(1, 65, 100);
        log.record(2, 70, 100);
        log.record(3, 80, 100);
        log.entries[1].stability_epochs ^= 1;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    // ── determinism (1) ──────────────────────────────────────────────────────
    #[test]
    fn entry_hash_deterministic() {
        let mut log_a = GossipPhiStabilityE8Log::new();
        let mut log_b = GossipPhiStabilityE8Log::new();
        log_a.record(1000, 63, 100);
        log_b.record(1000, 63, 100);
        assert_eq!(log_a.entries()[0].entry_hash, log_b.entries()[0].entry_hash);
    }
}
