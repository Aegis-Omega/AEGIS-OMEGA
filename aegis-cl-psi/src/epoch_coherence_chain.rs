//! Gate 229: Epoch Coherence Chain — Hash-linked CoherenceFrame history
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Records one CoherenceFrame per epoch in a hash-linked chain, making the
//! system's coherence history replay-certifiable.
//!
//! The central question of lattice_coherence.rs is STATIC: "does the global
//! section exist right now?" This module adds the TEMPORAL dimension:
//! "has the global section been continuously maintained across all epochs?"
//!
//! Each EpochCoherenceEntry chains: entry_hash = SHA-256(epoch ‖ frame ‖ prev_hash)
//! A chain with all entries having global_section_exists=true is CONTINUOUSLY COHERENT.
//!
//! Constitutional grounding:
//!   E[S_{n+1}|F_n] = S_n — the martingale holds IFF the chain is continuously coherent.
//!   A single epoch where global_section_exists=false is a martingale breach point.
//!
//! Uses SHA-256 from the sha2 crate (already in Cargo.toml).

use crate::coherence_broadcaster::CoherenceFrame;
use sha2::{Sha256, Digest};

/// One entry in the epoch coherence chain.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EpochCoherenceEntry {
    /// Epoch number (monotonically increasing).
    pub epoch: u64,
    /// The 16-byte coherence frame for this epoch.
    pub frame: CoherenceFrame,
    /// SHA-256(epoch_be ‖ frame.bytes ‖ prev_entry_hash).
    /// For the first entry, prev_entry_hash = [0u8; 32].
    pub entry_hash: [u8; 32],
    /// Hash of the previous entry (genesis = [0u8; 32]).
    pub prev_entry_hash: [u8; 32],
}

impl EpochCoherenceEntry {
    /// True iff the embedded frame declares a global section.
    pub fn is_globally_coherent(&self) -> bool {
        self.frame.global_section_exists()
    }
}

/// The genesis hash — predecessor of the first entry.
pub const GENESIS_COHERENCE_HASH: [u8; 32] = [0u8; 32];

/// A hash-linked chain of epoch coherence frames.
#[derive(Debug, Clone)]
pub struct EpochCoherenceChain {
    entries: Vec<EpochCoherenceEntry>,
}

#[derive(Debug)]
pub struct ChainError(pub &'static str);

impl EpochCoherenceChain {
    /// Create an empty chain.
    pub fn new() -> Self { Self { entries: Vec::new() } }

    /// Number of entries in the chain.
    pub fn len(&self) -> usize { self.entries.len() }

    /// True iff the chain has no entries.
    pub fn is_empty(&self) -> bool { self.entries.is_empty() }

    /// The hash of the last entry, or GENESIS_COHERENCE_HASH if empty.
    pub fn last_hash(&self) -> [u8; 32] {
        self.entries.last().map(|e| e.entry_hash).unwrap_or(GENESIS_COHERENCE_HASH)
    }

    /// The epoch of the last entry, or None if empty.
    pub fn last_epoch(&self) -> Option<u64> {
        self.entries.last().map(|e| e.epoch)
    }

    /// Append a new coherence frame for the given epoch.
    /// Returns Err if epoch <= last_epoch (monotonicity violated).
    pub fn append(
        &mut self,
        epoch: u64,
        frame: CoherenceFrame,
    ) -> Result<&EpochCoherenceEntry, ChainError> {
        if let Some(last) = self.last_epoch() {
            if epoch <= last {
                return Err(ChainError("epoch must be strictly greater than last epoch"));
            }
        }
        let prev_hash = self.last_hash();
        let entry_hash = compute_entry_hash(epoch, &frame, &prev_hash);
        self.entries.push(EpochCoherenceEntry {
            epoch,
            frame,
            entry_hash,
            prev_entry_hash: prev_hash,
        });
        Ok(self.entries.last().unwrap())
    }

    /// All entries in chain order.
    pub fn entries(&self) -> &[EpochCoherenceEntry] {
        &self.entries
    }

    /// True iff every entry in the chain declares global_section_exists=true.
    /// Empty chain returns true (vacuously coherent).
    pub fn is_continuously_coherent(&self) -> bool {
        self.entries.iter().all(|e| e.is_globally_coherent())
    }

    /// Index of the first entry where global_section_exists=false, or None.
    pub fn first_breach_epoch(&self) -> Option<u64> {
        self.entries.iter().find(|e| !e.is_globally_coherent()).map(|e| e.epoch)
    }

    /// Verify the full hash chain integrity.
    /// Returns (is_valid, first_broken_epoch) where first_broken_epoch is None iff valid.
    pub fn verify_chain(&self) -> (bool, Option<u64>) {
        let mut prev_hash = GENESIS_COHERENCE_HASH;
        for entry in &self.entries {
            if entry.prev_entry_hash != prev_hash {
                return (false, Some(entry.epoch));
            }
            let expected = compute_entry_hash(entry.epoch, &entry.frame, &prev_hash);
            if expected != entry.entry_hash {
                return (false, Some(entry.epoch));
            }
            prev_hash = entry.entry_hash;
        }
        (true, None)
    }

    /// Terminal hash of the chain (last entry_hash, or GENESIS if empty).
    /// Used as input to external certifiers.
    pub fn terminal_hash(&self) -> [u8; 32] {
        self.last_hash()
    }
}

impl Default for EpochCoherenceChain {
    fn default() -> Self { Self::new() }
}

/// Compute SHA-256(epoch_be8 ‖ frame.bytes[0..16] ‖ prev_hash[0..32]).
fn compute_entry_hash(epoch: u64, frame: &CoherenceFrame, prev_hash: &[u8; 32]) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(epoch.to_be_bytes());
    hasher.update(frame.bytes);
    hasher.update(prev_hash);
    hasher.finalize().into()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::coherence_broadcaster::{encode_coherence_frame};
    use crate::lattice_coherence::{CoherenceReport, ObstructionLevels};

    fn full_frame() -> CoherenceFrame {
        let report = CoherenceReport {
            global_section_exists: true,
            levels: ObstructionLevels {
                l0_ralph_frame: true, l1_mutation_authority: true,
                l2_resonance: true, l3_chord_unity: true, l4_autopoietic: true,
            },
            coherence_score: 1.0,
            satisfied_count: 5,
            first_obstruction: None,
        };
        encode_coherence_frame(&report, &[0u8; 32]).unwrap()
    }

    fn partial_frame() -> CoherenceFrame {
        let report = CoherenceReport {
            global_section_exists: false,
            levels: ObstructionLevels {
                l0_ralph_frame: true, l1_mutation_authority: true,
                l2_resonance: true, l3_chord_unity: false, l4_autopoietic: false,
            },
            coherence_score: 4.0 / 12.0,
            satisfied_count: 3,
            first_obstruction: Some(3),
        };
        encode_coherence_frame(&report, &[0u8; 32]).unwrap()
    }

    #[test]
    fn empty_chain_is_vacuously_coherent() {
        let chain = EpochCoherenceChain::new();
        assert!(chain.is_continuously_coherent());
        assert!(chain.first_breach_epoch().is_none());
    }

    #[test]
    fn empty_chain_last_hash_is_genesis() {
        let chain = EpochCoherenceChain::new();
        assert_eq!(chain.last_hash(), GENESIS_COHERENCE_HASH);
        assert!(chain.last_epoch().is_none());
    }

    #[test]
    fn append_first_entry() {
        let mut chain = EpochCoherenceChain::new();
        let entry = chain.append(1, full_frame()).unwrap();
        assert_eq!(entry.epoch, 1);
        assert_eq!(entry.prev_entry_hash, GENESIS_COHERENCE_HASH);
        assert_eq!(chain.len(), 1);
    }

    #[test]
    fn entry_hash_is_32_bytes() {
        let mut chain = EpochCoherenceChain::new();
        let entry = chain.append(1, full_frame()).unwrap();
        assert_ne!(entry.entry_hash, [0u8; 32]);
    }

    #[test]
    fn monotone_epoch_enforced() {
        let mut chain = EpochCoherenceChain::new();
        chain.append(5, full_frame()).unwrap();
        assert!(chain.append(5, full_frame()).is_err());
        assert!(chain.append(3, full_frame()).is_err());
        assert!(chain.append(6, full_frame()).is_ok());
    }

    #[test]
    fn hash_links_chain_correctly() {
        let mut chain = EpochCoherenceChain::new();
        chain.append(1, full_frame()).unwrap();
        chain.append(2, full_frame()).unwrap();
        let entries = chain.entries();
        assert_eq!(entries[1].prev_entry_hash, entries[0].entry_hash);
    }

    #[test]
    fn verify_clean_chain() {
        let mut chain = EpochCoherenceChain::new();
        for epoch in 1..=5 { chain.append(epoch, full_frame()).unwrap(); }
        let (valid, broken) = chain.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    #[test]
    fn continuously_coherent_all_full() {
        let mut chain = EpochCoherenceChain::new();
        for epoch in 1..=5 { chain.append(epoch, full_frame()).unwrap(); }
        assert!(chain.is_continuously_coherent());
        assert!(chain.first_breach_epoch().is_none());
    }

    #[test]
    fn breach_detected_on_partial_frame() {
        let mut chain = EpochCoherenceChain::new();
        chain.append(1, full_frame()).unwrap();
        chain.append(2, full_frame()).unwrap();
        chain.append(3, partial_frame()).unwrap();
        chain.append(4, full_frame()).unwrap();
        assert!(!chain.is_continuously_coherent());
        assert_eq!(chain.first_breach_epoch(), Some(3));
    }

    #[test]
    fn terminal_hash_changes_with_entries() {
        let mut chain = EpochCoherenceChain::new();
        let h0 = chain.terminal_hash();
        chain.append(1, full_frame()).unwrap();
        let h1 = chain.terminal_hash();
        chain.append(2, full_frame()).unwrap();
        let h2 = chain.terminal_hash();
        assert_ne!(h0, h1);
        assert_ne!(h1, h2);
    }

    #[test]
    fn determinism_same_inputs_same_chain() {
        let mut c1 = EpochCoherenceChain::new();
        let mut c2 = EpochCoherenceChain::new();
        for epoch in 1..=3 {
            c1.append(epoch, full_frame()).unwrap();
            c2.append(epoch, full_frame()).unwrap();
        }
        assert_eq!(c1.terminal_hash(), c2.terminal_hash());
        assert_eq!(c1.entries()[2].entry_hash, c2.entries()[2].entry_hash);
    }

    #[test]
    fn different_frames_different_hashes() {
        let mut c1 = EpochCoherenceChain::new();
        let mut c2 = EpochCoherenceChain::new();
        c1.append(1, full_frame()).unwrap();
        c2.append(1, partial_frame()).unwrap();
        assert_ne!(c1.terminal_hash(), c2.terminal_hash());
    }

    #[test]
    fn verify_empty_chain() {
        let chain = EpochCoherenceChain::new();
        let (valid, broken) = chain.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    #[test]
    fn chain_error_type() {
        let e = ChainError("test");
        assert_eq!(e.0, "test");
    }

    #[test]
    fn genesis_coherence_hash_is_zero() {
        assert_eq!(GENESIS_COHERENCE_HASH, [0u8; 32]);
    }
}
