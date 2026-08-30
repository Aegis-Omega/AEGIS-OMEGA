// EPISTEMIC TIER: T2 (engineering hypothesis)
// Gate 605 — Gossip Broadcast Phi Holographic E7 Log
// Per-epoch holographic fragment property: every node's local state contains
// reconstructible information about the whole topology.
// coherent_nodes: nodes whose local state is sufficient to reconstruct the epoch boundary.
// total_nodes: denominator for rate.
// holographic_rate_pct = (coherent_nodes*100)/max(total_nodes,1) capped 100.
// phi_holographic_e7: holographic_rate_pct > PHI_HOLOGRAPHIC_E7_THRESHOLD (61).
// The holographic property: if you smash the system into fragments, every fragment
// still renders the whole at reduced resolution. A system satisfies this when ≥φ
// of its nodes carry sufficient boundary data to reconstruct the bulk state.
// This is the formal gossip-layer encoding of: boundary (hash chain) projects bulk
// (distributed runtime). Each node is a fragment of the hologram.
// entry_hash = SHA-256(prev[32]‖epoch_end_be8‖coherent_nodes_be4‖total_nodes_be4‖holographic_rate_pct_be4‖phi_holographic_byte).
// GossipPhiHolographicE7Log: record(), phi_holographic_e7_count(), total_coherent_nodes(),
//   mean_holographic_rate_pct(), verify_chain().

use sha2::{Digest, Sha256};

pub const GOSSIP_PHI_HOLOGRAPHIC_E7_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const PHI_HOLOGRAPHIC_E7_THRESHOLD: u32 = 61;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPhiHolographicE7Entry {
    pub epoch_end: u64,
    pub coherent_nodes: u32,
    pub total_nodes: u32,
    pub holographic_rate_pct: u32,
    pub phi_holographic_e7: bool,
    pub entry_hash: [u8; 32],
    pub prev_hash: [u8; 32],
}

pub struct GossipPhiHolographicE7Log {
    entries: Vec<GossipPhiHolographicE7Entry>,
}

fn compute_phi_holographic_e7_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    coherent_nodes: u32,
    total_nodes: u32,
    holographic_rate_pct: u32,
    phi_holographic_e7: bool,
) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(prev);
    hasher.update(epoch_end.to_be_bytes());
    hasher.update(coherent_nodes.to_be_bytes());
    hasher.update(total_nodes.to_be_bytes());
    hasher.update(holographic_rate_pct.to_be_bytes());
    hasher.update([phi_holographic_e7 as u8]);
    hasher.finalize().into()
}

impl GossipPhiHolographicE7Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn entry_count(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    pub fn entries(&self) -> &[GossipPhiHolographicE7Entry] {
        &self.entries
    }

    pub fn latest(&self) -> Option<&GossipPhiHolographicE7Entry> {
        self.entries.last()
    }

    pub fn record(&mut self, epoch_end: u64, coherent_nodes: u32, total_nodes: u32) -> &GossipPhiHolographicE7Entry {
        let rate = ((coherent_nodes as u64).saturating_mul(100)
            / (total_nodes.max(1) as u64))
            .min(100) as u32;
        let flag = rate > PHI_HOLOGRAPHIC_E7_THRESHOLD;
        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_PHI_HOLOGRAPHIC_E7_GENESIS_HASH);
        let hash = compute_phi_holographic_e7_hash(&prev, epoch_end, coherent_nodes, total_nodes, rate, flag);
        self.entries.push(GossipPhiHolographicE7Entry {
            epoch_end,
            coherent_nodes,
            total_nodes,
            holographic_rate_pct: rate,
            phi_holographic_e7: flag,
            entry_hash: hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn phi_holographic_e7_count(&self) -> usize {
        self.entries.iter().filter(|e| e.phi_holographic_e7).count()
    }

    pub fn total_coherent_nodes(&self) -> u64 {
        self.entries.iter().map(|e| e.coherent_nodes as u64).fold(0u64, |a, v| a.saturating_add(v))
    }

    pub fn mean_holographic_rate_pct(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        let sum: u64 = self.entries.iter().map(|e| e.holographic_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_PHI_HOLOGRAPHIC_E7_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev { return (false, Some(i)); }
            let expected = compute_phi_holographic_e7_hash(
                &prev, e.epoch_end, e.coherent_nodes, e.total_nodes,
                e.holographic_rate_pct, e.phi_holographic_e7,
            );
            if e.entry_hash != expected { return (false, Some(i)); }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPhiHolographicE7Log {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields (1) ─────────────────────────────────────────────────────
    #[test]
    fn record_fields_stored() {
        let mut log = GossipPhiHolographicE7Log::new();
        let e = log.record(7000, 75, 100);
        assert_eq!(e.epoch_end, 7000);
        assert_eq!(e.coherent_nodes, 75);
        assert_eq!(e.total_nodes, 100);
        assert_eq!(e.holographic_rate_pct, 75);
        assert!(e.phi_holographic_e7);
    }

    // ── threshold (6) ─────────────────────────────────────────────────────────
    #[test]
    fn zero_input_not_flagged() {
        let mut log = GossipPhiHolographicE7Log::new();
        let e = log.record(1, 0, 0);
        assert_eq!(e.holographic_rate_pct, 0);
        assert!(!e.phi_holographic_e7);
    }

    #[test]
    fn well_below_threshold_not_flagged() {
        let mut log = GossipPhiHolographicE7Log::new();
        let e = log.record(1, 30, 100);
        assert!(!e.phi_holographic_e7);
    }

    #[test]
    fn just_below_threshold_not_flagged() {
        let mut log = GossipPhiHolographicE7Log::new();
        let e = log.record(1, 60, 100);
        assert_eq!(e.holographic_rate_pct, 60);
        assert!(!e.phi_holographic_e7);
    }

    #[test]
    fn at_threshold_strict_greater_not_flagged() {
        let mut log = GossipPhiHolographicE7Log::new();
        let e = log.record(1, 61, 100);
        assert_eq!(e.holographic_rate_pct, 61);
        assert!(!e.phi_holographic_e7); // strict >
    }

    #[test]
    fn just_above_threshold_flagged() {
        let mut log = GossipPhiHolographicE7Log::new();
        let e = log.record(1, 62, 100);
        assert_eq!(e.holographic_rate_pct, 62);
        assert!(e.phi_holographic_e7);
    }

    #[test]
    fn rate_capped_at_100() {
        let mut log = GossipPhiHolographicE7Log::new();
        let e = log.record(1, 400, 100);
        assert_eq!(e.holographic_rate_pct, 100);
        assert!(e.phi_holographic_e7);
    }

    // ── aggregates (2) ────────────────────────────────────────────────────────
    #[test]
    fn phi_holographic_count_correct() {
        let mut log = GossipPhiHolographicE7Log::new();
        log.record(1, 50, 100); // 50% — not flagged
        log.record(2, 64, 100); // 64% — flagged
        log.record(3, 78, 100); // 78% — flagged
        assert_eq!(log.phi_holographic_e7_count(), 2);
    }

    #[test]
    fn total_coherent_nodes_correct() {
        let mut log = GossipPhiHolographicE7Log::new();
        log.record(1, 38, 100);
        log.record(2, 52, 100);
        assert_eq!(log.total_coherent_nodes(), 90);
    }

    // ── hash chain (3) ────────────────────────────────────────────────────────
    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipPhiHolographicE7Log::new();
        let e = log.record(1, 65, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_is_genesis() {
        let mut log = GossipPhiHolographicE7Log::new();
        let e = log.record(1, 65, 100);
        assert_eq!(e.prev_hash, GOSSIP_PHI_HOLOGRAPHIC_E7_GENESIS_HASH);
    }

    #[test]
    fn chain_links_correctly() {
        let mut log = GossipPhiHolographicE7Log::new();
        log.record(1, 65, 100);
        log.record(2, 74, 100);
        let entries = log.entries();
        assert_eq!(entries[1].prev_hash, entries[0].entry_hash);
    }

    // ── verify_chain (6) ─────────────────────────────────────────────────────
    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipPhiHolographicE7Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_single_ok() {
        let mut log = GossipPhiHolographicE7Log::new();
        log.record(1, 65, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipPhiHolographicE7Log::new();
        log.record(1, 65, 100);
        log.record(2, 74, 100);
        log.record(3, 82, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_detects_tamper_at_first() {
        let mut log = GossipPhiHolographicE7Log::new();
        log.record(1, 65, 100);
        log.record(2, 74, 100);
        log.entries.first_mut().unwrap().coherent_nodes ^= 1;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn verify_chain_detects_tamper_at_last() {
        let mut log = GossipPhiHolographicE7Log::new();
        log.record(1, 65, 100);
        log.record(2, 74, 100);
        log.record(3, 82, 100);
        log.entries.last_mut().unwrap().coherent_nodes ^= 1;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(2));
    }

    #[test]
    fn verify_chain_detects_tamper_in_middle() {
        let mut log = GossipPhiHolographicE7Log::new();
        log.record(1, 65, 100);
        log.record(2, 74, 100);
        log.record(3, 82, 100);
        log.entries[1].coherent_nodes ^= 1;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    // ── determinism (1) ──────────────────────────────────────────────────────
    #[test]
    fn entry_hash_deterministic() {
        let mut log_a = GossipPhiHolographicE7Log::new();
        let mut log_b = GossipPhiHolographicE7Log::new();
        log_a.record(999, 62, 100);
        log_b.record(999, 62, 100);
        assert_eq!(log_a.entries()[0].entry_hash, log_b.entries()[0].entry_hash);
    }
}
