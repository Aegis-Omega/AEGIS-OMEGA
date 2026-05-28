// EPISTEMIC TIER: T2 (engineering hypothesis)
// Gate 598 — Gossip Broadcast Phi Angular Balance E7 Log
// Per-epoch angular balance of gossip links: balanced_links, total_links,
// balance_rate_pct = (balanced_links*100)/max(total_links,1) capped 100.
// phi_balanced_e7: balance_rate_pct > PHI_ANGULAR_BALANCE_E7_THRESHOLD (61).
// The threshold 61 ≈ φ×100 (golden ratio × 100, truncated) — the minimum
// fraction of links that must exhibit angular balance for the topology to
// approach the Penrose/pentagonal equilibrium (non-destructive scaling regime).
// entry_hash = SHA-256(prev[32]‖epoch_end_be8‖balanced_links_be4‖total_links_be4‖balance_rate_pct_be4‖phi_balanced_byte).
// GossipPhiAngularE7Log: record(), phi_balanced_e7_count(), total_balanced_links(),
//   mean_balance_rate_pct(), verify_chain().

use sha2::{Digest, Sha256};

pub const GOSSIP_PHI_ANGULAR_E7_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const PHI_ANGULAR_BALANCE_E7_THRESHOLD: u32 = 61;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPhiAngularE7Entry {
    pub epoch_end: u64,
    pub balanced_links: u32,
    pub total_links: u32,
    pub balance_rate_pct: u32,
    pub phi_balanced_e7: bool,
    pub entry_hash: [u8; 32],
    pub prev_hash: [u8; 32],
}

pub struct GossipPhiAngularE7Log {
    entries: Vec<GossipPhiAngularE7Entry>,
}

fn compute_phi_angular_e7_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    balanced_links: u32,
    total_links: u32,
    balance_rate_pct: u32,
    phi_balanced_e7: bool,
) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(prev);
    hasher.update(epoch_end.to_be_bytes());
    hasher.update(balanced_links.to_be_bytes());
    hasher.update(total_links.to_be_bytes());
    hasher.update(balance_rate_pct.to_be_bytes());
    hasher.update([phi_balanced_e7 as u8]);
    hasher.finalize().into()
}

impl GossipPhiAngularE7Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn entry_count(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    pub fn entries(&self) -> &[GossipPhiAngularE7Entry] {
        &self.entries
    }

    pub fn latest(&self) -> Option<&GossipPhiAngularE7Entry> {
        self.entries.last()
    }

    pub fn record(&mut self, epoch_end: u64, balanced_links: u32, total_links: u32) -> &GossipPhiAngularE7Entry {
        let rate = ((balanced_links as u64).saturating_mul(100)
            / (total_links.max(1) as u64))
            .min(100) as u32;
        let flag = rate > PHI_ANGULAR_BALANCE_E7_THRESHOLD;
        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_PHI_ANGULAR_E7_GENESIS_HASH);
        let hash = compute_phi_angular_e7_hash(&prev, epoch_end, balanced_links, total_links, rate, flag);
        self.entries.push(GossipPhiAngularE7Entry {
            epoch_end,
            balanced_links,
            total_links,
            balance_rate_pct: rate,
            phi_balanced_e7: flag,
            entry_hash: hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn phi_balanced_e7_count(&self) -> usize {
        self.entries.iter().filter(|e| e.phi_balanced_e7).count()
    }

    pub fn total_balanced_links(&self) -> u64 {
        self.entries.iter().map(|e| e.balanced_links as u64).fold(0u64, |a, v| a.saturating_add(v))
    }

    pub fn mean_balance_rate_pct(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        let sum: u64 = self.entries.iter().map(|e| e.balance_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_PHI_ANGULAR_E7_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev { return (false, Some(i)); }
            let expected = compute_phi_angular_e7_hash(
                &prev, e.epoch_end, e.balanced_links, e.total_links,
                e.balance_rate_pct, e.phi_balanced_e7,
            );
            if e.entry_hash != expected { return (false, Some(i)); }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPhiAngularE7Log {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────
    #[test]
    fn record_fields_stored() {
        let mut log = GossipPhiAngularE7Log::new();
        let e = log.record(1000, 70, 100);
        assert_eq!(e.epoch_end, 1000);
        assert_eq!(e.balanced_links, 70);
        assert_eq!(e.total_links, 100);
        assert_eq!(e.balance_rate_pct, 70);
        assert!(e.phi_balanced_e7);
    }

    #[test]
    fn zero_input_zero_rate() {
        let mut log = GossipPhiAngularE7Log::new();
        let e = log.record(1, 0, 0);
        assert_eq!(e.balance_rate_pct, 0);
        assert!(!e.phi_balanced_e7);
    }

    #[test]
    fn denominator_zero_uses_max_one() {
        let mut log = GossipPhiAngularE7Log::new();
        let e = log.record(1, 5, 0);
        assert_eq!(e.balance_rate_pct, 100);
    }

    #[test]
    fn rate_capped_at_100() {
        let mut log = GossipPhiAngularE7Log::new();
        let e = log.record(1, 200, 100);
        assert_eq!(e.balance_rate_pct, 100);
    }

    // ── threshold / boolean flag ──────────────────────────────────────────────
    #[test]
    fn below_threshold_not_flagged() {
        let mut log = GossipPhiAngularE7Log::new();
        let e = log.record(1, 55, 100);
        assert_eq!(e.balance_rate_pct, 55);
        assert!(!e.phi_balanced_e7);
    }

    #[test]
    fn at_threshold_boundary_not_flagged() {
        let mut log = GossipPhiAngularE7Log::new();
        let e = log.record(1, 61, 100);
        assert_eq!(e.balance_rate_pct, 61);
        assert!(!e.phi_balanced_e7); // strict >
    }

    #[test]
    fn above_threshold_flagged() {
        let mut log = GossipPhiAngularE7Log::new();
        let e = log.record(1, 62, 100);
        assert_eq!(e.balance_rate_pct, 62);
        assert!(e.phi_balanced_e7);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────
    #[test]
    fn flag_count_correct() {
        let mut log = GossipPhiAngularE7Log::new();
        log.record(1, 50, 100);
        log.record(2, 70, 100);
        log.record(3, 80, 100);
        assert_eq!(log.phi_balanced_e7_count(), 2);
    }

    #[test]
    fn total_balanced_links_correct() {
        let mut log = GossipPhiAngularE7Log::new();
        log.record(1, 30, 100);
        log.record(2, 45, 100);
        assert_eq!(log.total_balanced_links(), 75);
    }

    #[test]
    fn mean_balance_rate_correct() {
        let mut log = GossipPhiAngularE7Log::new();
        log.record(1, 40, 100);
        log.record(2, 80, 100);
        assert_eq!(log.mean_balance_rate_pct(), 60);
    }

    #[test]
    fn mean_rate_empty_zero() {
        let log = GossipPhiAngularE7Log::new();
        assert_eq!(log.mean_balance_rate_pct(), 0);
    }

    #[test]
    fn total_empty_zero() {
        let log = GossipPhiAngularE7Log::new();
        assert_eq!(log.total_balanced_links(), 0);
    }

    // ── hash chain ────────────────────────────────────────────────────────────
    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipPhiAngularE7Log::new();
        let e = log.record(1, 70, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipPhiAngularE7Log::new();
        let e = log.record(1, 70, 100);
        assert_eq!(e.prev_hash, GOSSIP_PHI_ANGULAR_E7_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipPhiAngularE7Log::new();
        log.record(1, 70, 100);
        log.record(2, 65, 100);
        let entries = log.entries();
        assert_eq!(entries[1].prev_hash, entries[0].entry_hash);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────
    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipPhiAngularE7Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipPhiAngularE7Log::new();
        log.record(1, 70, 100);
        log.record(2, 65, 100);
        log.record(3, 80, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipPhiAngularE7Log::new();
        log.record(1, 70, 100);
        log.record(2, 65, 100);
        log.entries.first_mut().unwrap().balanced_links ^= 1;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────
    #[test]
    fn entry_hash_deterministic() {
        let mut log_a = GossipPhiAngularE7Log::new();
        let mut log_b = GossipPhiAngularE7Log::new();
        log_a.record(999, 62, 100);
        log_b.record(999, 62, 100);
        assert_eq!(log_a.entries()[0].entry_hash, log_b.entries()[0].entry_hash);
    }
}
