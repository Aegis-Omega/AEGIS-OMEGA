// EPISTEMIC TIER: T2 (engineering hypothesis)
// Gate 599 — Gossip Broadcast Phi Fibonacci Alignment E7 Log
// Per-epoch Fibonacci alignment of active peer count: fibonacci_epochs, total_epochs,
// fib_align_pct = (fibonacci_epochs*100)/max(total_epochs,1) capped 100.
// phi_fibonacci_aligned_e7: fib_align_pct > PHI_FIBONACCI_ALIGN_E7_THRESHOLD (55).
// The threshold 55 is F(10), a Fibonacci number itself — the target fraction of epochs
// in which the active peer count falls within a Fibonacci number range, indicating
// natural φ-spread topology (T^n scaling where T=[[1,1],[1,0]], eigenvalue φ).
// Epochs where peer count ≈ F(n) for any n exhibit minimum-stress gossip fanout:
// the Fibonacci lattice is the discrete analogue of the golden-angle phyllotaxis.
// entry_hash = SHA-256(prev[32]‖epoch_end_be8‖fibonacci_epochs_be4‖total_epochs_be4‖fib_align_pct_be4‖phi_fibonacci_aligned_byte).
// GossipPhiFibonacciE7Log: record(), phi_fibonacci_aligned_e7_count(), total_fibonacci_epochs(),
//   mean_fib_align_pct(), verify_chain().

use sha2::{Digest, Sha256};

pub const GOSSIP_PHI_FIBONACCI_E7_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const PHI_FIBONACCI_ALIGN_E7_THRESHOLD: u32 = 55;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPhiFibonacciE7Entry {
    pub epoch_end: u64,
    pub fibonacci_epochs: u32,
    pub total_epochs: u32,
    pub fib_align_pct: u32,
    pub phi_fibonacci_aligned_e7: bool,
    pub entry_hash: [u8; 32],
    pub prev_hash: [u8; 32],
}

pub struct GossipPhiFibonacciE7Log {
    entries: Vec<GossipPhiFibonacciE7Entry>,
}

fn compute_phi_fibonacci_e7_hash(
    prev: &[u8; 32],
    epoch_end: u64,
    fibonacci_epochs: u32,
    total_epochs: u32,
    fib_align_pct: u32,
    phi_fibonacci_aligned_e7: bool,
) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(prev);
    hasher.update(epoch_end.to_be_bytes());
    hasher.update(fibonacci_epochs.to_be_bytes());
    hasher.update(total_epochs.to_be_bytes());
    hasher.update(fib_align_pct.to_be_bytes());
    hasher.update([phi_fibonacci_aligned_e7 as u8]);
    hasher.finalize().into()
}

impl GossipPhiFibonacciE7Log {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn entry_count(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    pub fn entries(&self) -> &[GossipPhiFibonacciE7Entry] {
        &self.entries
    }

    pub fn latest(&self) -> Option<&GossipPhiFibonacciE7Entry> {
        self.entries.last()
    }

    pub fn record(&mut self, epoch_end: u64, fibonacci_epochs: u32, total_epochs: u32) -> &GossipPhiFibonacciE7Entry {
        let rate = ((fibonacci_epochs as u64).saturating_mul(100)
            / (total_epochs.max(1) as u64))
            .min(100) as u32;
        let flag = rate > PHI_FIBONACCI_ALIGN_E7_THRESHOLD;
        let prev = self.entries.last()
            .map(|e| e.entry_hash)
            .unwrap_or(GOSSIP_PHI_FIBONACCI_E7_GENESIS_HASH);
        let hash = compute_phi_fibonacci_e7_hash(&prev, epoch_end, fibonacci_epochs, total_epochs, rate, flag);
        self.entries.push(GossipPhiFibonacciE7Entry {
            epoch_end,
            fibonacci_epochs,
            total_epochs,
            fib_align_pct: rate,
            phi_fibonacci_aligned_e7: flag,
            entry_hash: hash,
            prev_hash: prev,
        });
        self.entries.last().unwrap()
    }

    pub fn phi_fibonacci_aligned_e7_count(&self) -> usize {
        self.entries.iter().filter(|e| e.phi_fibonacci_aligned_e7).count()
    }

    pub fn total_fibonacci_epochs(&self) -> u64 {
        self.entries.iter().map(|e| e.fibonacci_epochs as u64).fold(0u64, |a, v| a.saturating_add(v))
    }

    pub fn mean_fib_align_pct(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        let sum: u64 = self.entries.iter().map(|e| e.fib_align_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_PHI_FIBONACCI_E7_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev { return (false, Some(i)); }
            let expected = compute_phi_fibonacci_e7_hash(
                &prev, e.epoch_end, e.fibonacci_epochs, e.total_epochs,
                e.fib_align_pct, e.phi_fibonacci_aligned_e7,
            );
            if e.entry_hash != expected { return (false, Some(i)); }
            prev = e.entry_hash;
        }
        (true, None)
    }
}

impl Default for GossipPhiFibonacciE7Log {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── record fields ─────────────────────────────────────────────────────────
    #[test]
    fn record_fields_stored() {
        let mut log = GossipPhiFibonacciE7Log::new();
        let e = log.record(2000, 60, 100);
        assert_eq!(e.epoch_end, 2000);
        assert_eq!(e.fibonacci_epochs, 60);
        assert_eq!(e.total_epochs, 100);
        assert_eq!(e.fib_align_pct, 60);
        assert!(e.phi_fibonacci_aligned_e7);
    }

    #[test]
    fn zero_input_zero_rate() {
        let mut log = GossipPhiFibonacciE7Log::new();
        let e = log.record(1, 0, 0);
        assert_eq!(e.fib_align_pct, 0);
        assert!(!e.phi_fibonacci_aligned_e7);
    }

    #[test]
    fn denominator_zero_uses_max_one() {
        let mut log = GossipPhiFibonacciE7Log::new();
        let e = log.record(1, 3, 0);
        assert_eq!(e.fib_align_pct, 100);
    }

    #[test]
    fn rate_capped_at_100() {
        let mut log = GossipPhiFibonacciE7Log::new();
        let e = log.record(1, 300, 100);
        assert_eq!(e.fib_align_pct, 100);
    }

    // ── threshold / boolean flag ──────────────────────────────────────────────
    #[test]
    fn below_threshold_not_flagged() {
        let mut log = GossipPhiFibonacciE7Log::new();
        let e = log.record(1, 40, 100);
        assert_eq!(e.fib_align_pct, 40);
        assert!(!e.phi_fibonacci_aligned_e7);
    }

    #[test]
    fn at_threshold_boundary_not_flagged() {
        let mut log = GossipPhiFibonacciE7Log::new();
        let e = log.record(1, 55, 100);
        assert_eq!(e.fib_align_pct, 55);
        assert!(!e.phi_fibonacci_aligned_e7); // strict >
    }

    #[test]
    fn above_threshold_flagged() {
        let mut log = GossipPhiFibonacciE7Log::new();
        let e = log.record(1, 56, 100);
        assert_eq!(e.fib_align_pct, 56);
        assert!(e.phi_fibonacci_aligned_e7);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────
    #[test]
    fn flag_count_correct() {
        let mut log = GossipPhiFibonacciE7Log::new();
        log.record(1, 40, 100);
        log.record(2, 60, 100);
        log.record(3, 70, 100);
        assert_eq!(log.phi_fibonacci_aligned_e7_count(), 2);
    }

    #[test]
    fn total_fibonacci_epochs_correct() {
        let mut log = GossipPhiFibonacciE7Log::new();
        log.record(1, 21, 100);
        log.record(2, 34, 100);
        assert_eq!(log.total_fibonacci_epochs(), 55);
    }

    #[test]
    fn mean_fib_align_correct() {
        let mut log = GossipPhiFibonacciE7Log::new();
        log.record(1, 50, 100);
        log.record(2, 70, 100);
        assert_eq!(log.mean_fib_align_pct(), 60);
    }

    #[test]
    fn mean_rate_empty_zero() {
        let log = GossipPhiFibonacciE7Log::new();
        assert_eq!(log.mean_fib_align_pct(), 0);
    }

    #[test]
    fn total_empty_zero() {
        let log = GossipPhiFibonacciE7Log::new();
        assert_eq!(log.total_fibonacci_epochs(), 0);
    }

    // ── hash chain ────────────────────────────────────────────────────────────
    #[test]
    fn entry_hash_nonzero() {
        let mut log = GossipPhiFibonacciE7Log::new();
        let e = log.record(1, 60, 100);
        assert_ne!(e.entry_hash, [0u8; 32]);
    }

    #[test]
    fn first_entry_prev_hash_is_genesis() {
        let mut log = GossipPhiFibonacciE7Log::new();
        let e = log.record(1, 60, 100);
        assert_eq!(e.prev_hash, GOSSIP_PHI_FIBONACCI_E7_GENESIS_HASH);
    }

    #[test]
    fn chain_prev_links() {
        let mut log = GossipPhiFibonacciE7Log::new();
        log.record(1, 60, 100);
        log.record(2, 70, 100);
        let entries = log.entries();
        assert_eq!(entries[1].prev_hash, entries[0].entry_hash);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────
    #[test]
    fn verify_chain_empty_ok() {
        let log = GossipPhiFibonacciE7Log::new();
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_multiple_ok() {
        let mut log = GossipPhiFibonacciE7Log::new();
        log.record(1, 60, 100);
        log.record(2, 70, 100);
        log.record(3, 80, 100);
        assert_eq!(log.verify_chain(), (true, None));
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut log = GossipPhiFibonacciE7Log::new();
        log.record(1, 60, 100);
        log.record(2, 70, 100);
        log.entries.first_mut().unwrap().fibonacci_epochs ^= 1;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────
    #[test]
    fn entry_hash_deterministic() {
        let mut log_a = GossipPhiFibonacciE7Log::new();
        let mut log_b = GossipPhiFibonacciE7Log::new();
        log_a.record(888, 56, 100);
        log_b.record(888, 56, 100);
        assert_eq!(log_a.entries()[0].entry_hash, log_b.entries()[0].entry_hash);
    }
}
