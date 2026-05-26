//! Gate 335 — Compaction Epoch Seal (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Closes each epoch with a tamper-evident seal binding the Unified Compaction
//! Manager output (Gate 334) to an epoch sequence. Mirrors the pattern from
//! Gate 270 (EpochSealer) for the compaction subsystem.
//!
//! CompactionEpochSeal per epoch:
//!   epoch:               u64
//!   unified_hash:        [u8;32]  — UnifiedCompactionLog terminal hash at epoch close
//!   spsf_total_pruned:   u64      — running total from UnifiedCompactionLog
//!   health_total_pruned: u64
//!   resonance_total_pruned: u64
//!   total_pruned:        u64      — sum of all three
//!   seal_hash:           [u8;32]
//!   prev_hash:           [u8;32]
//!
//! seal_hash = SHA-256(prev[32] ‖ epoch_be8 ‖ unified_hash[32]
//!                      ‖ spsf_pruned_be8 ‖ health_pruned_be8 ‖ resonance_pruned_be8
//!                      ‖ total_pruned_be8)
//!
//! CompactionSealChain: append(), terminal_hash(), seal_count(), verify_chain().
//!   terminal_hash() = last seal_hash, or GENESIS if empty.
//!   verify_chain() → (bool, Option<usize>) — index of first invalid seal.

use sha2::{Sha256, Digest};

pub const COMPACTION_SEAL_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── CompactionEpochSeal ──────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct CompactionEpochSeal {
    pub epoch:                  u64,
    pub unified_hash:           [u8; 32],
    pub spsf_total_pruned:      u64,
    pub health_total_pruned:    u64,
    pub resonance_total_pruned: u64,
    pub total_pruned:           u64,
    pub seal_hash:              [u8; 32],
    pub prev_hash:              [u8; 32],
}

fn compute_seal_hash(
    prev:                   &[u8; 32],
    epoch:                  u64,
    unified_hash:           &[u8; 32],
    spsf_pruned:            u64,
    health_pruned:          u64,
    resonance_pruned:       u64,
    total_pruned:           u64,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update(unified_hash);
    h.update(spsf_pruned.to_be_bytes());
    h.update(health_pruned.to_be_bytes());
    h.update(resonance_pruned.to_be_bytes());
    h.update(total_pruned.to_be_bytes());
    h.finalize().into()
}

// ─── CompactionSealChain ──────────────────────────────────────────────────────

pub struct CompactionSealChain {
    seals: Vec<CompactionEpochSeal>,
}

impl CompactionSealChain {
    pub fn new() -> Self { Self { seals: Vec::new() } }

    pub fn seal_count(&self) -> usize { self.seals.len() }

    pub fn seals(&self) -> &[CompactionEpochSeal] { &self.seals }
    pub fn seals_mut(&mut self) -> &mut [CompactionEpochSeal] { &mut self.seals }

    pub fn latest(&self) -> Option<&CompactionEpochSeal> { self.seals.last() }

    pub fn terminal_hash(&self) -> [u8; 32] {
        self.seals.last()
            .map(|s| s.seal_hash)
            .unwrap_or(COMPACTION_SEAL_GENESIS_HASH)
    }

    /// Append a new epoch seal.
    ///
    /// `unified_hash`: terminal hash of the UnifiedCompactionLog at epoch close.
    /// `spsf_total`, `health_total`, `resonance_total`: running totals from the log.
    pub fn append(
        &mut self,
        epoch:           u64,
        unified_hash:    [u8; 32],
        spsf_total:      u64,
        health_total:    u64,
        resonance_total: u64,
    ) -> &CompactionEpochSeal {
        let prev = self.terminal_hash();
        let total_pruned = spsf_total.saturating_add(health_total).saturating_add(resonance_total);
        let seal_hash = compute_seal_hash(
            &prev, epoch, &unified_hash,
            spsf_total, health_total, resonance_total, total_pruned,
        );

        self.seals.push(CompactionEpochSeal {
            epoch,
            unified_hash,
            spsf_total_pruned:      spsf_total,
            health_total_pruned:    health_total,
            resonance_total_pruned: resonance_total,
            total_pruned,
            seal_hash,
            prev_hash:              prev,
        });
        self.seals.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = COMPACTION_SEAL_GENESIS_HASH;
        for (i, s) in self.seals.iter().enumerate() {
            if s.prev_hash != prev {
                return (false, Some(i));
            }
            let total = s.spsf_total_pruned
                .saturating_add(s.health_total_pruned)
                .saturating_add(s.resonance_total_pruned);
            if s.total_pruned != total {
                return (false, Some(i));
            }
            let expected = compute_seal_hash(
                &prev, s.epoch, &s.unified_hash,
                s.spsf_total_pruned, s.health_total_pruned,
                s.resonance_total_pruned, s.total_pruned,
            );
            if s.seal_hash != expected {
                return (false, Some(i));
            }
            prev = s.seal_hash;
        }
        (true, None)
    }
}

impl Default for CompactionSealChain {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_unified_hash(n: u8) -> [u8; 32] {
        let mut h = [0u8; 32];
        h[0] = n;
        h[31] = n.wrapping_mul(7);
        h
    }

    // ── CompactionSealChain basics ────────────────────────────────────────────

    #[test]
    fn new_chain_has_zero_seals() {
        let c = CompactionSealChain::new();
        assert_eq!(c.seal_count(), 0);
        assert_eq!(c.terminal_hash(), COMPACTION_SEAL_GENESIS_HASH);
        assert!(c.latest().is_none());
    }

    #[test]
    fn append_single_seal() {
        let mut c = CompactionSealChain::new();
        let s = c.append(1, sample_unified_hash(1), 10, 5, 3);
        assert_eq!(s.epoch, 1);
        assert_eq!(s.spsf_total_pruned, 10);
        assert_eq!(s.health_total_pruned, 5);
        assert_eq!(s.resonance_total_pruned, 3);
        assert_eq!(s.total_pruned, 18);
        assert_eq!(c.seal_count(), 1);
    }

    #[test]
    fn total_pruned_is_sum() {
        let mut c = CompactionSealChain::new();
        let s = c.append(1, sample_unified_hash(1), 7, 3, 5);
        assert_eq!(s.total_pruned, 15);
    }

    #[test]
    fn terminal_hash_updates_after_append() {
        let mut c = CompactionSealChain::new();
        assert_eq!(c.terminal_hash(), COMPACTION_SEAL_GENESIS_HASH);
        c.append(1, sample_unified_hash(1), 0, 0, 0);
        let t1 = c.terminal_hash();
        assert_ne!(t1, COMPACTION_SEAL_GENESIS_HASH);
        c.append(2, sample_unified_hash(2), 0, 0, 0);
        let t2 = c.terminal_hash();
        assert_ne!(t1, t2);
    }

    #[test]
    fn prev_hash_links_correctly() {
        let mut c = CompactionSealChain::new();
        c.append(1, sample_unified_hash(1), 5, 3, 2);
        let s1_hash = c.latest().unwrap().seal_hash;
        c.append(2, sample_unified_hash(2), 1, 1, 0);
        assert_eq!(c.latest().unwrap().prev_hash, s1_hash);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let c = CompactionSealChain::new();
        let (ok, idx) = c.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_single_seal_ok() {
        let mut c = CompactionSealChain::new();
        c.append(1, sample_unified_hash(1), 3, 2, 1);
        let (ok, idx) = c.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_five_seals_ok() {
        let mut c = CompactionSealChain::new();
        for i in 1u64..=5 {
            c.append(i, sample_unified_hash(i as u8), i * 3, i * 2, i);
        }
        let (ok, idx) = c.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tampered_seal_hash() {
        let mut c = CompactionSealChain::new();
        c.append(1, sample_unified_hash(1), 5, 3, 2);
        c.append(2, sample_unified_hash(2), 1, 1, 0);
        c.seals[0].seal_hash[0] ^= 0xFF;
        let (ok, idx) = c.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn verify_chain_detects_tampered_prev_hash() {
        let mut c = CompactionSealChain::new();
        c.append(1, sample_unified_hash(1), 5, 3, 2);
        c.append(2, sample_unified_hash(2), 1, 1, 0);
        c.seals[1].prev_hash[0] ^= 0xFF;
        let (ok, idx) = c.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn verify_chain_detects_tampered_spsf_total() {
        let mut c = CompactionSealChain::new();
        c.append(1, sample_unified_hash(1), 5, 3, 2);
        c.seals[0].spsf_total_pruned = 999;
        let (ok, idx) = c.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn verify_chain_detects_tampered_total_pruned() {
        let mut c = CompactionSealChain::new();
        c.append(1, sample_unified_hash(1), 5, 3, 2);
        c.seals[0].total_pruned = 0; // was 10, mismatch
        let (ok, idx) = c.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn verify_chain_detects_tampered_unified_hash() {
        let mut c = CompactionSealChain::new();
        c.append(1, sample_unified_hash(1), 5, 3, 2);
        c.seals[0].unified_hash[0] ^= 0xFF;
        let (ok, idx) = c.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── Determinism ───────────────────────────────────────────────────────────

    #[test]
    fn seal_hash_deterministic() {
        let mut c1 = CompactionSealChain::new();
        let mut c2 = CompactionSealChain::new();
        c1.append(3, sample_unified_hash(3), 10, 7, 4);
        c2.append(3, sample_unified_hash(3), 10, 7, 4);
        assert_eq!(c1.terminal_hash(), c2.terminal_hash());
    }

    #[test]
    fn different_epochs_different_hashes() {
        let mut c1 = CompactionSealChain::new();
        let mut c2 = CompactionSealChain::new();
        c1.append(1, sample_unified_hash(5), 0, 0, 0);
        c2.append(2, sample_unified_hash(5), 0, 0, 0);
        assert_ne!(c1.terminal_hash(), c2.terminal_hash());
    }

    #[test]
    fn different_unified_hash_different_seal() {
        let mut c1 = CompactionSealChain::new();
        let mut c2 = CompactionSealChain::new();
        c1.append(1, sample_unified_hash(1), 5, 3, 2);
        c2.append(1, sample_unified_hash(2), 5, 3, 2);
        assert_ne!(c1.terminal_hash(), c2.terminal_hash());
    }

    #[test]
    fn ten_epoch_chain_verify_ok() {
        let mut c = CompactionSealChain::new();
        for i in 1u64..=10 {
            c.append(i, sample_unified_hash(i as u8), i * 5, i * 2, i * 3);
        }
        assert_eq!(c.seal_count(), 10);
        let (ok, _) = c.verify_chain();
        assert!(ok);
    }
}
