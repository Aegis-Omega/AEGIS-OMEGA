// EPISTEMIC TIER: T2 (engineering hypothesis)
// Gate 601 — Gossip Broadcast Phi Deviation E7 Log
// Per-epoch deviation from the golden ratio φ: drifted_epochs, total_epochs,
// deviation_rate_pct = (drifted_epochs*100)/max(total_epochs,1) capped 100.
// phi_drifted_e7: deviation_rate_pct > PHI_DEVIATION_E7_THRESHOLD (38).
// Threshold 38 ≈ (1-φ)×100 — when more than 38% of epochs drift away from φ,
// the system's structural coupling is breaking down. Complement of Gate 600:
// together they form the full φ-stability envelope (convergence high, deviation low).
// entry_hash = SHA-256(prev[32]‖epoch_end_be8‖drifted_epochs_be4‖total_epochs_be4‖deviation_rate_pct_be4‖phi_drifted_byte).
// GossipPhiDeviationE7Log: record(), phi_drifted_e7_count(), total_drifted_epochs(),
//   mean_deviation_rate_pct(), verify_chain().

use sha2::{Digest, Sha256};

pub const GOSSIP_PHI_DEVIATION_E7_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const PHI_DEVIATION_E7_THRESHOLD: u32 = 38;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPhiDeviationE7Entry {
    pub epoch_end: u64,
    pub drifted_epochs: u32,
    pub total_epochs: u32,
    pub deviation_rate_pct: u32,
    pub phi_drifted_e7: bool,
    pub entry_hash: [u8; 32],
    pub prev_hash: [u8; 32],
}

pub struct GossipPhiDeviationE7Log {
    entries: Vec<GossipPhiDeviationE7Entry>,
}

fn compute_phi_deviation_e7_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    drifted_epochs: u32,
    total_epochs: u32,
    deviation_rate_pct: u32,
    phi_drifted_e7: bool,
) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(prev);
    hasher.update(epoch_end.to_be_bytes());
    hasher.update(drifted_epochs.to_be_bytes());
    hasher.update(total_epochs.to_be_bytes());
    hasher.update(deviation_rate_pct.to_be_bytes());
    hasher.update([phi_drifted_e7 as u8]);
    hasher.finalize().into()
}

impl GossipPhiDeviationE7Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn entry_count(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    pub fn entries(&self) -> &[GossipPhiDeviationE7Entry] {
        &self.entries
    }

    pub fn latest(&self) -> Option<&GossipPhiDeviationE7Entry> {
        self.entries.last()
    }

    pub fn record(&mut self, epoch_end: u64, drifted_epochs: u32, total_epochs: u32) -> &GossipPhiDeviationE7Entry {
        let rate = ((drifted_epochs as u64).saturating_mul(100)
            / (total_epochs.max(1) as u64))
            .min(100) as u32;
        let flag = rate > PHI_DEVIATION_E7_THRESHOLD;
        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_PHI_DEVIATION_E7_GENESIS_HASH);
        let hash = compute_phi_deviation_e7_hash(&prev, epoch_end, drifted_epochs, total_epochs, rate, flag);
        self.entries.push(GossipPhiDeviationE7Entry {
            epoch_end,
            drifted_epochs,
            total_epochs,
            deviation_rate_pct: rate,
            phi_drifted_e7: flag,
            entry_hash: hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn phi_drifted_e7_count(&self) -> usize {
        self.entries.iter().filter(|e| e.phi_drifted_e7).count()
    }

    pub fn total_drifted_epochs(&self) -> u64 {
        self.entries.iter().map(|e| e.drifted_epochs as u64).fold(0u64, |a, v| a.saturating_add(v))
    }

    pub fn mean_deviation_rate_pct(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        let sum: u64 = self.entries.iter().map(|e| e.deviation_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_PHI_DEVIATION_E7_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev { return (false, Some(i)); }
            let expected = compute_phi_deviation_e7_hash(
                &prev, e.epoch_end, e.drifted_epochs, e.total_epochs,
                e.deviation_rate_pct, e.phi_drifted_e7,
            );
            if e.entry_hash != expected { return (false, Some(i)); }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPhiDeviationE7Log {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields (1) ─────────────────────────────────────────────────────
    #[test]
    fn record_fields_stored() {
        let mut log = GossipPhiDeviationE7Log::new();
        let e = log.record(3000, 40, 100);
        assert_eq!(e.epoch_end, 3000);
        assert_eq!(e.drifted_epochs, 40);
        assert_eq!(e.total_epochs, 100);
        assert_eq!(e.deviation_rate_pct, 40);
        assert!(e.phi_drifted_e7);
    }

    // ── threshold (6) ────────────────────────────────────────────────────────
    #[test]
    fn zero_input_not_flagged() {
        let mut log = GossipPhiDeviationE7Log::new();
        let e = log.record(1, 0, 0);
        assert_eq!(e.deviation_rate_pct, 0);
        assert!(!e.phi_drifted_e7);
    }

    #[test]
    fn well_below_threshold_not_flagged() {
        let mut log = GossipPhiDeviationE7Log::new();
        let e = log.record(1, 10, 100);
        assert!(!e.phi_drifted_e7);
    }

    #[test]
    fn just_below_threshold_not_flagged() {
        let mut log = GossipPhiDeviationE7Log::new();
        let e = log.record(1, 37, 100);
        assert_eq!(e.deviation_rate_pct, 37);
        assert!(!e.phi_drifted_e7);
    }

    #[test]
    fn at_threshold_strict_greater_not_flagged() {
        let mut log = GossipPhiDeviationE7Log::new();
        let e = log.record(1, 38, 100);
        assert_eq!(e.deviation_rate_pct, 38);
        assert!(!e.phi_drifted_e7); // strict >
    }

    #[test]
    fn just_above_threshold_flagged() {
        let mut log = GossipPhiDeviationE7Log::new();
        let e = log.record(1, 39, 100);
        assert_eq!(e.deviation_rate_pct, 39);
        assert!(e.phi_drifted_e7);
    }

    #[test]
    fn rate_capped_at_100() {
        let mut log = GossipPhiDeviationE7Log::new();
        let e = log.record(1, 300, 100);
        assert_eq!(e.deviation_rate_pct, 100);
        assert!(e.phi_drifted_e7);
    }

    // ── aggregates (2) ────────────────────────────────────────────────────────
    #[test]
    fn phi_drifted_count_correct() {
        let mut log = GossipPhiDeviationE7Log::new();
        log.record(1, 20, 100); // 20% — not flagged
        log.record(2, 50, 100); // 50% — flagged
        log.record(3, 60, 100); // 60% — flagged
        assert_eq!(log.phi_drifted_e7_count(), 2);
    }

    #[test]
    fn total_drifted_epochs_correct() {
        let mut log = GossipPhiDeviationE7Log::new();
        log.record(1, 25, 100);
        log.record(2, 35, 100);
        assert_eq!(log.total_drifted_epochs(), 60);
    }

    // ── hash chain (3) ────────────────────────────────────────────────────────
    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipPhiDeviationE7Log::new();
        let e = log.record(1, 40, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_is_genesis() {
        let mut log = GossipPhiDeviationE7Log::new();
        let e = log.record(1, 40, 100);
        assert_eq!(e.prev_hash, GOSSIP_PHI_DEVIATION_E7_GENESIS_HASH);
    }

    #[test]
    fn chain_links_correctly() {
        let mut log = GossipPhiDeviationE7Log::new();
        log.record(1, 40, 100);
        log.record(2, 50, 100);
        let entries = log.entries();
        assert_eq!(entries[1].prev_hash, entries[0].entry_hash);
    }

    // ── verify_chain (6) ─────────────────────────────────────────────────────
    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipPhiDeviationE7Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_single_ok() {
        let mut log = GossipPhiDeviationE7Log::new();
        log.record(1, 40, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipPhiDeviationE7Log::new();
        log.record(1, 40, 100);
        log.record(2, 50, 100);
        log.record(3, 60, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_detects_tamper_at_first() {
        let mut log = GossipPhiDeviationE7Log::new();
        log.record(1, 40, 100);
        log.record(2, 50, 100);
        log.entries.first_mut().unwrap().drifted_epochs ^= 1;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn verify_chain_detects_tamper_at_last() {
        let mut log = GossipPhiDeviationE7Log::new();
        log.record(1, 40, 100);
        log.record(2, 50, 100);
        log.record(3, 60, 100);
        log.entries.last_mut().unwrap().drifted_epochs ^= 1;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(2));
    }

    #[test]
    fn verify_chain_detects_tamper_in_middle() {
        let mut log = GossipPhiDeviationE7Log::new();
        log.record(1, 40, 100);
        log.record(2, 50, 100);
        log.record(3, 60, 100);
        log.entries[1].drifted_epochs ^= 1;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    // ── determinism (1) ──────────────────────────────────────────────────────
    #[test]
    fn entry_hash_deterministic() {
        let mut log_a = GossipPhiDeviationE7Log::new();
        let mut log_b = GossipPhiDeviationE7Log::new();
        log_a.record(999, 39, 100);
        log_b.record(999, 39, 100);
        assert_eq!(log_a.entries()[0].entry_hash, log_b.entries()[0].entry_hash);
    }
}
