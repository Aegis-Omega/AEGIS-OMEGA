//! Gate 233: Constitutional Replay — Deterministic State Reconstruction
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Implements the core replay invariant at the Rust layer:
//!   State_t = Replay(Lineage_{0→t})
//!
//! Given a sequence of AutonodeTick inputs (the "lineage"), ReplayChain
//! reconstructs the complete ConstitutionalAutonode state deterministically.
//! The terminal_hash of any replay is a content-addressed proof of the entire
//! governance history — same ticks → same terminal_hash on any platform.
//!
//! A stored ReplayProof captures:
//!   tick_count, constitutional_hash, system_version, terminal_hash, consensus_hash
//! Verification replays the exact tick sequence and compares both hashes.
//!
//! Constitutional invariant enforced:
//!   AdaptivePower(T) ≤ ReplayVerifiability(T)
//! The replay record is the verifiability; the tick sequence is the adaptive power.
//! A replay mismatch = the system evolved beyond what can be reconstructed = T0_ABORT.

use sha2::{Sha256, Digest};
use crate::constitutional_autonode::{ConstitutionalAutonode, AutonodeTick, AutonodeCycleRecord};

// ─── Replay error ─────────────────────────────────────────────────────────

#[derive(Debug)]
pub struct ReplayError(pub &'static str);

// ─── Replay proof ─────────────────────────────────────────────────────────

/// A tamper-evident proof of a replay sequence's terminal state.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ReplayProof {
    /// Number of ticks in the original sequence.
    pub tick_count: usize,
    /// Constitutional hash used during replay (bound into every SelfCertificate).
    pub constitutional_hash: [u8; 32],
    /// Terminal chain hash of the autonode after all ticks (Gates 229+231).
    pub terminal_hash: [u8; 32],
    /// SHA-256 of all cycle record chain_entry_hashes in epoch order (replay fingerprint).
    pub replay_fingerprint: [u8; 32],
    /// Coherent tick count (how many ticks produced global_section_exists=true).
    pub coherent_count: usize,
    /// True iff every tick was fully coherent (is_continuously_coherent at end).
    pub continuously_coherent: bool,
}

// ─── Replay chain ─────────────────────────────────────────────────────────

/// A replay-certifiable constitutional chain.
///
/// Wraps a ConstitutionalAutonode and accumulates tick records for fingerprinting.
pub struct ReplayChain {
    node:             ConstitutionalAutonode,
    cycle_records:    Vec<AutonodeCycleRecord>,
    constitutional_hash: [u8; 32],
    system_version:   &'static str,
}

impl ReplayChain {
    /// Create a new replay chain (empty — no ticks yet).
    pub fn new(constitutional_hash: [u8; 32], system_version: &'static str) -> Self {
        Self {
            node: ConstitutionalAutonode::new(constitutional_hash, system_version),
            cycle_records: Vec::new(),
            constitutional_hash,
            system_version,
        }
    }

    /// Number of ticks processed.
    pub fn tick_count(&self) -> usize { self.cycle_records.len() }

    /// Current terminal hash of the epoch chain.
    pub fn terminal_hash(&self) -> [u8; 32] { self.node.terminal_hash() }

    /// True iff all ticks so far have been continuously coherent.
    pub fn is_continuously_coherent(&self) -> bool { self.node.is_continuously_coherent() }

    /// All accumulated cycle records.
    pub fn cycle_records(&self) -> &[AutonodeCycleRecord] { &self.cycle_records }

    /// Process one tick and accumulate its record.
    pub fn tick(&mut self, input: AutonodeTick) -> Result<&AutonodeCycleRecord, ReplayError> {
        let rec = self.node.tick(input).map_err(|e| ReplayError(e.0))?;
        self.cycle_records.push(rec);
        Ok(self.cycle_records.last().unwrap())
    }

    /// Process a full sequence of ticks (the "lineage").
    pub fn replay_sequence(&mut self, ticks: Vec<AutonodeTick>) -> Result<(), ReplayError> {
        for tick in ticks {
            self.tick(tick)?;
        }
        Ok(())
    }

    /// Build a ReplayProof from the current chain state.
    ///
    /// The replay_fingerprint is SHA-256 of all chain_entry_hashes in epoch order.
    pub fn build_proof(&self) -> ReplayProof {
        let mut hasher = Sha256::new();
        for rec in &self.cycle_records {
            hasher.update(rec.chain_entry_hash);
        }
        let replay_fingerprint: [u8; 32] = hasher.finalize().into();

        let coherent_count = self.cycle_records.iter().filter(|r| r.is_fully_coherent).count();

        ReplayProof {
            tick_count: self.cycle_records.len(),
            constitutional_hash: self.constitutional_hash,
            terminal_hash: self.terminal_hash(),
            replay_fingerprint,
            coherent_count,
            continuously_coherent: self.is_continuously_coherent(),
        }
    }

    /// Verify: replay a fresh chain with the given ticks and compare proof.
    /// Returns Ok(true) if terminal_hash and replay_fingerprint both match.
    /// Returns Ok(false) if they don't match (tamper detected).
    /// Returns Err if replay itself fails (e.g. epoch monotonicity violated).
    pub fn verify_against_proof(
        ticks: Vec<AutonodeTick>,
        expected: &ReplayProof,
        system_version: &'static str,
    ) -> Result<bool, ReplayError> {
        if ticks.len() != expected.tick_count {
            return Ok(false);
        }
        let mut fresh = ReplayChain::new(expected.constitutional_hash, system_version);
        fresh.replay_sequence(ticks)?;
        let actual = fresh.build_proof();
        Ok(actual.terminal_hash == expected.terminal_hash
            && actual.replay_fingerprint == expected.replay_fingerprint)
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::chord_network::NetworkVerdict;
    use crate::self_certification::NetworkSnapshot;

    fn ch(v: u8) -> [u8; 32] { let mut h = [0u8; 32]; h[0] = v; h }

    fn ring5(s: u8) -> Vec<[u8; 32]> {
        vec![ch(s), ch(s+1), ch(s+2), ch(s+1), ch(s)]
    }

    fn net() -> NetworkSnapshot {
        NetworkSnapshot { verdict: NetworkVerdict::Unified, peer_count: 3, above_phi_count: 0, quorum_triadic: true }
    }

    fn good_tick(epoch: u64, seq: u64) -> AutonodeTick {
        AutonodeTick {
            epoch, sequence_id: seq, divergence_risk: 0.12,
            start_rank: 3, end_rank: 9, ring_hashes: ring5(1),
            network: net(), mutation_authority_active: true,
        }
    }

    fn make_ticks(n: usize) -> Vec<AutonodeTick> {
        (0..n).map(|i| good_tick((i + 1) as u64, (100 + i) as u64)).collect()
    }

    #[test]
    fn new_chain_empty() {
        let chain = ReplayChain::new(ch(1), "1.0.0");
        assert_eq!(chain.tick_count(), 0);
    }

    #[test]
    fn single_tick_chain_length_one() {
        let mut chain = ReplayChain::new(ch(1), "1.0.0");
        chain.tick(good_tick(1, 100)).unwrap();
        assert_eq!(chain.tick_count(), 1);
    }

    #[test]
    fn replay_sequence_all_ticks_processed() {
        let mut chain = ReplayChain::new(ch(1), "1.0.0");
        chain.replay_sequence(make_ticks(5)).unwrap();
        assert_eq!(chain.tick_count(), 5);
    }

    #[test]
    fn terminal_hash_nonzero_after_ticks() {
        let mut chain = ReplayChain::new(ch(1), "1.0.0");
        chain.replay_sequence(make_ticks(3)).unwrap();
        assert_ne!(chain.terminal_hash(), [0u8; 32]);
    }

    #[test]
    fn build_proof_tick_count_matches() {
        let mut chain = ReplayChain::new(ch(1), "1.0.0");
        chain.replay_sequence(make_ticks(4)).unwrap();
        let proof = chain.build_proof();
        assert_eq!(proof.tick_count, 4);
    }

    #[test]
    fn build_proof_replay_fingerprint_nonzero() {
        let mut chain = ReplayChain::new(ch(1), "1.0.0");
        chain.replay_sequence(make_ticks(3)).unwrap();
        let proof = chain.build_proof();
        assert_ne!(proof.replay_fingerprint, [0u8; 32]);
    }

    #[test]
    fn build_proof_coherent_count_correct() {
        let mut chain = ReplayChain::new(ch(1), "1.0.0");
        chain.replay_sequence(make_ticks(5)).unwrap(); // all good inputs → all coherent
        let proof = chain.build_proof();
        assert_eq!(proof.coherent_count, 5);
    }

    #[test]
    fn build_proof_continuously_coherent_true_on_good_sequence() {
        let mut chain = ReplayChain::new(ch(1), "1.0.0");
        chain.replay_sequence(make_ticks(5)).unwrap();
        let proof = chain.build_proof();
        assert!(proof.continuously_coherent);
    }

    #[test]
    fn verify_against_proof_matching_sequence() {
        let ticks = make_ticks(5);
        let mut chain = ReplayChain::new(ch(1), "1.0.0");
        chain.replay_sequence(ticks.clone()).unwrap();
        let proof = chain.build_proof();
        let ok = ReplayChain::verify_against_proof(ticks, &proof, "1.0.0").unwrap();
        assert!(ok);
    }

    #[test]
    fn verify_against_proof_wrong_tick_count() {
        let ticks = make_ticks(5);
        let mut chain = ReplayChain::new(ch(1), "1.0.0");
        chain.replay_sequence(ticks).unwrap();
        let proof = chain.build_proof();
        let ok = ReplayChain::verify_against_proof(make_ticks(4), &proof, "1.0.0").unwrap();
        assert!(!ok);
    }

    #[test]
    fn verify_against_proof_tampered_divergence_fails() {
        let ticks = make_ticks(5);
        let mut chain = ReplayChain::new(ch(1), "1.0.0");
        chain.replay_sequence(ticks).unwrap();
        let proof = chain.build_proof();
        // Replay with different divergence risk on tick 3
        let mut altered = make_ticks(5);
        altered[2].divergence_risk = 0.99; // tamper tick index 2
        let ok = ReplayChain::verify_against_proof(altered, &proof, "1.0.0").unwrap();
        assert!(!ok);
    }

    #[test]
    fn determinism_same_ticks_same_proof() {
        let build = || {
            let mut c = ReplayChain::new(ch(42), "1.0.0");
            c.replay_sequence(make_ticks(5)).unwrap();
            c.build_proof()
        };
        let p1 = build();
        let p2 = build();
        let p3 = build();
        assert_eq!(p1, p2);
        assert_eq!(p2, p3);
    }

    #[test]
    fn different_constitutional_hash_different_proof() {
        let build = |seed: u8| {
            let mut c = ReplayChain::new(ch(seed), "1.0.0");
            c.replay_sequence(make_ticks(3)).unwrap();
            c.build_proof()
        };
        assert_ne!(build(1), build(2));
    }

    #[test]
    fn proof_fingerprint_changes_with_additional_ticks() {
        let mut c1 = ReplayChain::new(ch(1), "1.0.0");
        c1.replay_sequence(make_ticks(3)).unwrap();
        let p1 = c1.build_proof();

        let mut c2 = ReplayChain::new(ch(1), "1.0.0");
        c2.replay_sequence(make_ticks(4)).unwrap();
        let p2 = c2.build_proof();

        assert_ne!(p1.replay_fingerprint, p2.replay_fingerprint);
        assert_ne!(p1.terminal_hash, p2.terminal_hash);
    }

    #[test]
    fn replay_error_wraps_str() {
        let e = ReplayError("bad epoch");
        assert_eq!(e.0, "bad epoch");
    }
}
