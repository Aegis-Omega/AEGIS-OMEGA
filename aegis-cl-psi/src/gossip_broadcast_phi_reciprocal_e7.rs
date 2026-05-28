// EPISTEMIC TIER: T2 (engineering hypothesis)
// Gate 603 — Gossip Broadcast Phi Reciprocal E7 Log
// Per-epoch measurement of the 1/φ=φ−1 identity in the gossip layer.
// reciprocal_aligned_epochs: epochs where the ratio of smaller to larger partition ≈ φ−1 (≈0.618).
// total_epochs: denominator for rate.
// reciprocal_rate_pct = (reciprocal_aligned_epochs*100)/max(total_epochs,1) capped 100.
// phi_reciprocal_e7: reciprocal_rate_pct > PHI_RECIPROCAL_E7_THRESHOLD (61).
// Threshold 61 ≈ φ×100: the reciprocal identity 1/φ=φ−1 is the complementary face of φ²=φ+1.
// Together Gates 602+603 certify that the topology satisfies both directions of φ's self-definition:
// growth (φ²=φ+1) and proportion (1/φ=φ−1). A system that satisfies both is constitutionally φ-stable.
// entry_hash = SHA-256(prev[32]‖epoch_end_be8‖reciprocal_aligned_epochs_be4‖total_epochs_be4‖reciprocal_rate_pct_be4‖phi_reciprocal_byte).
// GossipPhiReciprocalE7Log: record(), phi_reciprocal_e7_count(), total_reciprocal_aligned_epochs(),
//   mean_reciprocal_rate_pct(), verify_chain().

use sha2::{Digest, Sha256};

pub const GOSSIP_PHI_RECIPROCAL_E7_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const PHI_RECIPROCAL_E7_THRESHOLD: u32 = 61;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPhiReciprocalE7Entry {
    pub epoch_end: u64,
    pub reciprocal_aligned_epochs: u32,
    pub total_epochs: u32,
    pub reciprocal_rate_pct: u32,
    pub phi_reciprocal_e7: bool,
    pub entry_hash: [u8; 32],
    pub prev_hash: [u8; 32],
}

pub struct GossipPhiReciprocalE7Log {
    entries: Vec<GossipPhiReciprocalE7Entry>,
}

fn compute_phi_reciprocal_e7_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    reciprocal_aligned_epochs: u32,
    total_epochs: u32,
    reciprocal_rate_pct: u32,
    phi_reciprocal_e7: bool,
) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(prev);
    hasher.update(epoch_end.to_be_bytes());
    hasher.update(reciprocal_aligned_epochs.to_be_bytes());
    hasher.update(total_epochs.to_be_bytes());
    hasher.update(reciprocal_rate_pct.to_be_bytes());
    hasher.update([phi_reciprocal_e7 as u8]);
    hasher.finalize().into()
}

impl GossipPhiReciprocalE7Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn entry_count(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    pub fn entries(&self) -> &[GossipPhiReciprocalE7Entry] {
        &self.entries
    }

    pub fn latest(&self) -> Option<&GossipPhiReciprocalE7Entry> {
        self.entries.last()
    }

    pub fn record(&mut self, epoch_end: u64, reciprocal_aligned_epochs: u32, total_epochs: u32) -> &GossipPhiReciprocalE7Entry {
        let rate = ((reciprocal_aligned_epochs as u64).saturating_mul(100)
            / (total_epochs.max(1) as u64))
            .min(100) as u32;
        let flag = rate > PHI_RECIPROCAL_E7_THRESHOLD;
        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_PHI_RECIPROCAL_E7_GENESIS_HASH);
        let hash = compute_phi_reciprocal_e7_hash(&prev, epoch_end, reciprocal_aligned_epochs, total_epochs, rate, flag);
        self.entries.push(GossipPhiReciprocalE7Entry {
            epoch_end,
            reciprocal_aligned_epochs,
            total_epochs,
            reciprocal_rate_pct: rate,
            phi_reciprocal_e7: flag,
            entry_hash: hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn phi_reciprocal_e7_count(&self) -> usize {
        self.entries.iter().filter(|e| e.phi_reciprocal_e7).count()
    }

    pub fn total_reciprocal_aligned_epochs(&self) -> u64 {
        self.entries.iter().map(|e| e.reciprocal_aligned_epochs as u64).fold(0u64, |a, v| a.saturating_add(v))
    }

    pub fn mean_reciprocal_rate_pct(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        let sum: u64 = self.entries.iter().map(|e| e.reciprocal_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_PHI_RECIPROCAL_E7_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev { return (false, Some(i)); }
            let expected = compute_phi_reciprocal_e7_hash(
                &prev, e.epoch_end, e.reciprocal_aligned_epochs, e.total_epochs,
                e.reciprocal_rate_pct, e.phi_reciprocal_e7,
            );
            if e.entry_hash != expected { return (false, Some(i)); }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPhiReciprocalE7Log {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields (1) ─────────────────────────────────────────────────────
    #[test]
    fn record_fields_stored() {
        let mut log = GossipPhiReciprocalE7Log::new();
        let e = log.record(5000, 65, 100);
        assert_eq!(e.epoch_end, 5000);
        assert_eq!(e.reciprocal_aligned_epochs, 65);
        assert_eq!(e.total_epochs, 100);
        assert_eq!(e.reciprocal_rate_pct, 65);
        assert!(e.phi_reciprocal_e7);
    }

    // ── threshold (6) ─────────────────────────────────────────────────────────
    #[test]
    fn zero_input_not_flagged() {
        let mut log = GossipPhiReciprocalE7Log::new();
        let e = log.record(1, 0, 0);
        assert_eq!(e.reciprocal_rate_pct, 0);
        assert!(!e.phi_reciprocal_e7);
    }

    #[test]
    fn well_below_threshold_not_flagged() {
        let mut log = GossipPhiReciprocalE7Log::new();
        let e = log.record(1, 15, 100);
        assert!(!e.phi_reciprocal_e7);
    }

    #[test]
    fn just_below_threshold_not_flagged() {
        let mut log = GossipPhiReciprocalE7Log::new();
        let e = log.record(1, 60, 100);
        assert_eq!(e.reciprocal_rate_pct, 60);
        assert!(!e.phi_reciprocal_e7);
    }

    #[test]
    fn at_threshold_strict_greater_not_flagged() {
        let mut log = GossipPhiReciprocalE7Log::new();
        let e = log.record(1, 61, 100);
        assert_eq!(e.reciprocal_rate_pct, 61);
        assert!(!e.phi_reciprocal_e7); // strict >
    }

    #[test]
    fn just_above_threshold_flagged() {
        let mut log = GossipPhiReciprocalE7Log::new();
        let e = log.record(1, 62, 100);
        assert_eq!(e.reciprocal_rate_pct, 62);
        assert!(e.phi_reciprocal_e7);
    }

    #[test]
    fn rate_capped_at_100() {
        let mut log = GossipPhiReciprocalE7Log::new();
        let e = log.record(1, 400, 100);
        assert_eq!(e.reciprocal_rate_pct, 100);
        assert!(e.phi_reciprocal_e7);
    }

    // ── aggregates (2) ────────────────────────────────────────────────────────
    #[test]
    fn phi_reciprocal_count_correct() {
        let mut log = GossipPhiReciprocalE7Log::new();
        log.record(1, 45, 100); // 45% — not flagged
        log.record(2, 68, 100); // 68% — flagged
        log.record(3, 72, 100); // 72% — flagged
        assert_eq!(log.phi_reciprocal_e7_count(), 2);
    }

    #[test]
    fn total_reciprocal_aligned_correct() {
        let mut log = GossipPhiReciprocalE7Log::new();
        log.record(1, 33, 100);
        log.record(2, 47, 100);
        assert_eq!(log.total_reciprocal_aligned_epochs(), 80);
    }

    // ── hash chain (3) ────────────────────────────────────────────────────────
    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipPhiReciprocalE7Log::new();
        let e = log.record(1, 65, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_is_genesis() {
        let mut log = GossipPhiReciprocalE7Log::new();
        let e = log.record(1, 65, 100);
        assert_eq!(e.prev_hash, GOSSIP_PHI_RECIPROCAL_E7_GENESIS_HASH);
    }

    #[test]
    fn chain_links_correctly() {
        let mut log = GossipPhiReciprocalE7Log::new();
        log.record(1, 65, 100);
        log.record(2, 70, 100);
        let entries = log.entries();
        assert_eq!(entries[1].prev_hash, entries[0].entry_hash);
    }

    // ── verify_chain (6) ─────────────────────────────────────────────────────
    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipPhiReciprocalE7Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_single_ok() {
        let mut log = GossipPhiReciprocalE7Log::new();
        log.record(1, 65, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipPhiReciprocalE7Log::new();
        log.record(1, 65, 100);
        log.record(2, 70, 100);
        log.record(3, 80, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_detects_tamper_at_first() {
        let mut log = GossipPhiReciprocalE7Log::new();
        log.record(1, 65, 100);
        log.record(2, 70, 100);
        log.entries.first_mut().unwrap().reciprocal_aligned_epochs ^= 1;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn verify_chain_detects_tamper_at_last() {
        let mut log = GossipPhiReciprocalE7Log::new();
        log.record(1, 65, 100);
        log.record(2, 70, 100);
        log.record(3, 80, 100);
        log.entries.last_mut().unwrap().reciprocal_aligned_epochs ^= 1;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(2));
    }

    #[test]
    fn verify_chain_detects_tamper_in_middle() {
        let mut log = GossipPhiReciprocalE7Log::new();
        log.record(1, 65, 100);
        log.record(2, 70, 100);
        log.record(3, 80, 100);
        log.entries[1].reciprocal_aligned_epochs ^= 1;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    // ── determinism (1) ──────────────────────────────────────────────────────
    #[test]
    fn entry_hash_deterministic() {
        let mut log_a = GossipPhiReciprocalE7Log::new();
        let mut log_b = GossipPhiReciprocalE7Log::new();
        log_a.record(999, 62, 100);
        log_b.record(999, 62, 100);
        assert_eq!(log_a.entries()[0].entry_hash, log_b.entries()[0].entry_hash);
    }
}
