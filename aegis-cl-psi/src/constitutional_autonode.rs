//! Gate 231: Constitutional Autonode — Unified Constitutional State Machine
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Assembles the full constitutional stack into one self-certifying, hash-chained node:
//!   Gate 222 — ResonanceReport  (phi + ring + sequence + vortex invariants)
//!   Gate 225 — SelfCertificate  (autopoietic closure verdict)
//!   Gate 227 — CoherenceReport  (moduli tower global section checker)
//!   Gate 228 — CoherenceFrame   (16-byte gossip broadcast encoding)
//!   Gate 229 — EpochCoherenceChain (temporal coherence history)
//!
//! One tick() call = one complete constitutional cycle:
//!   1. Compute ResonanceReport from inputs
//!   2. Certify self → SelfCertificate
//!   3. Check moduli tower → CoherenceReport
//!   4. Encode 16-byte gossip frame → CoherenceFrame
//!   5. Append to epoch coherence chain
//!   6. Return AutonodeCycleRecord (all outputs, hash-linkable)
//!
//! The autonode is the concrete instantiation of AdaptivePower(T) ≤ ReplayVerifiability(T):
//! every adaptive tick produces a verifiable, hash-linked cycle record.
//! No clock, no randomness — same inputs → same record across all platforms.

use crate::resonance_monitor::{check_resonance, ResonanceReport};
use crate::self_certification::{certify_self, NetworkSnapshot, SelfCertificate};
use crate::lattice_coherence::{check_coherence, CoherenceReport, TowerSnapshot};
use crate::coherence_broadcaster::{encode_coherence_frame, CoherenceFrame};
use crate::epoch_coherence_chain::EpochCoherenceChain;

// ─── Error type ───────────────────────────────────────────────────────────

#[derive(Debug)]
pub struct AutonodeError(pub &'static str);

// ─── Tick input ───────────────────────────────────────────────────────────

/// All inputs required for one constitutional cycle tick.
#[derive(Debug, Clone)]
pub struct AutonodeTick {
    /// Epoch number — must be strictly greater than the previous tick's epoch.
    pub epoch: u64,
    /// Sequence ID for this cycle (used in resonance monotonicity check).
    pub sequence_id: u64,
    /// Cumulative Lawvere divergence risk of the current path.
    pub divergence_risk: f64,
    /// Rank of the path start node (for vortex classification).
    pub start_rank: usize,
    /// Rank of the path end node (must exceed start_rank for Triadic classification).
    pub end_rank: usize,
    /// Hash sequence for A-B-C-B'-A' ring composition check (≥ 3 elements).
    pub ring_hashes: Vec<[u8; 32]>,
    /// Network state snapshot (verdict, peers, above-phi count, quorum).
    pub network: NetworkSnapshot,
    /// Whether mutation authority is currently active (no D2+ divergence).
    pub mutation_authority_active: bool,
}

// ─── Cycle record ─────────────────────────────────────────────────────────

/// The output of one constitutional cycle tick — all reports hash-linked via epoch chain.
#[derive(Debug)]
pub struct AutonodeCycleRecord {
    /// Epoch this cycle covers.
    pub epoch: u64,
    /// Sequence ID used in this cycle.
    pub sequence_id: u64,

    /// Gate 222 — resonance report for this cycle.
    pub resonance: ResonanceReport,
    /// Gate 225 — self-certificate for this cycle.
    pub certificate: SelfCertificate,
    /// Gate 227 — coherence report for this cycle.
    pub coherence: CoherenceReport,
    /// Gate 228 — 16-byte gossip frame for broadcast.
    pub frame: CoherenceFrame,

    /// SHA-256 of this epoch's chain entry (Gate 229).
    pub chain_entry_hash: [u8; 32],
    /// Total entries in chain after this tick.
    pub chain_length: usize,

    /// True iff the moduli tower global section exists for this cycle.
    pub is_fully_coherent: bool,
    /// True iff ALL epochs in the chain so far have global_section_exists=true.
    pub is_continuously_coherent: bool,
}

// ─── Autonode ─────────────────────────────────────────────────────────────

/// Constitutional Autonode — unified, self-certifying, hash-chained constitutional node.
///
/// Maintains an `EpochCoherenceChain` across ticks, providing both per-cycle snapshots
/// and temporal coherence history (martingale proof surface).
pub struct ConstitutionalAutonode {
    chain:                EpochCoherenceChain,
    constitutional_hash:  [u8; 32],
    last_sequence:        Option<u64>,
    system_version:       &'static str,
}

impl ConstitutionalAutonode {
    /// Create a new autonode with the given constitutional hash and system version.
    ///
    /// The constitutional hash is bound into every SelfCertificate produced.
    pub fn new(constitutional_hash: [u8; 32], system_version: &'static str) -> Self {
        Self {
            chain: EpochCoherenceChain::new(),
            constitutional_hash,
            last_sequence: None,
            system_version,
        }
    }

    /// Number of completed epochs in the chain.
    pub fn chain_length(&self) -> usize {
        self.chain.len()
    }

    /// True iff every epoch in the chain has global_section_exists=true.
    pub fn is_continuously_coherent(&self) -> bool {
        self.chain.is_continuously_coherent()
    }

    /// The first epoch where global_section_exists=false, or None if never breached.
    pub fn first_breach_epoch(&self) -> Option<u64> {
        self.chain.first_breach_epoch()
    }

    /// SHA-256 of the last chain entry (or GENESIS if empty) — for external certifiers.
    pub fn terminal_hash(&self) -> [u8; 32] {
        self.chain.terminal_hash()
    }

    /// Run one complete constitutional cycle.
    ///
    /// Steps: resonance → self-certification → coherence → gossip frame → epoch chain.
    /// Returns Err if:
    ///   - epoch is not strictly greater than the previous epoch (monotonicity violated)
    ///   - ring_hashes has fewer than 3 elements (ring check would be TooShort)
    ///   - gossip frame encoding fails (score out of range)
    pub fn tick(&mut self, input: AutonodeTick) -> Result<AutonodeCycleRecord, AutonodeError> {
        if input.ring_hashes.len() < 3 {
            return Err(AutonodeError("ring_hashes must have at least 3 elements"));
        }

        // ── 1. Resonance (Gate 222) ───────────────────────────────────────
        let resonance: ResonanceReport = check_resonance(
            input.divergence_risk,
            input.start_rank,
            input.end_rank,
            &input.ring_hashes,
            input.sequence_id,
            self.last_sequence,
        );

        // ── 2. Self-certification (Gate 225) ──────────────────────────────
        let certificate: SelfCertificate = certify_self(
            &self.constitutional_hash,
            &resonance,
            &input.network,
            self.system_version,
        );

        // ── 3. Lattice coherence (Gate 227) ───────────────────────────────
        let snap = TowerSnapshot {
            sequence_monotone:        resonance.sequence_monotone,
            mutation_authority_active: input.mutation_authority_active,
            resonance:                &resonance,
            network_verdict:          input.network.verdict,
            all_below_phi:            input.network.above_phi_count == 0,
            certification:            &certificate,
        };
        let coherence: CoherenceReport = check_coherence(&snap);
        let is_fully_coherent = coherence.global_section_exists;

        // ── 4. Gossip frame (Gate 228) ────────────────────────────────────
        let frame: CoherenceFrame = encode_coherence_frame(
            &coherence,
            &self.constitutional_hash,
        ).map_err(|e| AutonodeError(e.0))?;

        // ── 5. Epoch chain (Gate 229) ─────────────────────────────────────
        let entry = self.chain.append(input.epoch, frame.clone())
            .map_err(|e| AutonodeError(e.0))?;
        let chain_entry_hash = entry.entry_hash;
        let chain_length = self.chain.len();
        let is_continuously_coherent = self.chain.is_continuously_coherent();

        // Update last sequence for next tick's monotonicity check
        self.last_sequence = Some(input.sequence_id);

        Ok(AutonodeCycleRecord {
            epoch: input.epoch,
            sequence_id: input.sequence_id,
            resonance,
            certificate,
            coherence,
            frame,
            chain_entry_hash,
            chain_length,
            is_fully_coherent,
            is_continuously_coherent,
        })
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::chord_network::NetworkVerdict;
    use crate::self_certification::NetworkSnapshot;

    fn const_hash(v: u8) -> [u8; 32] {
        let mut h = [0u8; 32]; h[0] = v; h
    }

    fn ring3(a: u8, b: u8, c: u8) -> Vec<[u8; 32]> {
        vec![const_hash(a), const_hash(b), const_hash(c), const_hash(b), const_hash(a)]
    }

    fn unified_net() -> NetworkSnapshot {
        NetworkSnapshot {
            verdict: NetworkVerdict::Unified,
            peer_count: 3,
            above_phi_count: 0,
            quorum_triadic: true,
        }
    }

    fn good_tick(epoch: u64, seq: u64) -> AutonodeTick {
        AutonodeTick {
            epoch,
            sequence_id: seq,
            divergence_risk: 0.12,   // below 1/φ ≈ 0.618
            start_rank: 3,
            end_rank: 9,             // span=6, digital_root(6)=6 → Triadic
            ring_hashes: ring3(1, 2, 3),
            network: unified_net(),
            mutation_authority_active: true,
        }
    }

    #[test]
    fn new_has_empty_chain() {
        let node = ConstitutionalAutonode::new(const_hash(1), "1.0.0");
        assert_eq!(node.chain_length(), 0);
    }

    #[test]
    fn new_is_vacuously_coherent() {
        let node = ConstitutionalAutonode::new(const_hash(1), "1.0.0");
        assert!(node.is_continuously_coherent());
        assert!(node.first_breach_epoch().is_none());
    }

    #[test]
    fn first_tick_chain_length_one() {
        let mut node = ConstitutionalAutonode::new(const_hash(1), "1.0.0");
        let rec = node.tick(good_tick(1, 100)).unwrap();
        assert_eq!(rec.chain_length, 1);
        assert_eq!(node.chain_length(), 1);
    }

    #[test]
    fn good_inputs_fully_coherent() {
        let mut node = ConstitutionalAutonode::new(const_hash(1), "1.0.0");
        let rec = node.tick(good_tick(1, 100)).unwrap();
        assert!(rec.is_fully_coherent);
        assert!(rec.is_continuously_coherent);
    }

    #[test]
    fn resonance_propagated_correctly() {
        let mut node = ConstitutionalAutonode::new(const_hash(1), "1.0.0");
        let rec = node.tick(good_tick(1, 100)).unwrap();
        assert!(rec.resonance.phi_convergent);
        assert!(rec.resonance.ring_valid);
        assert!(rec.resonance.sequence_monotone);
    }

    #[test]
    fn certificate_verdict_certified_on_good_inputs() {
        use crate::self_certification::CertificationVerdict;
        let mut node = ConstitutionalAutonode::new(const_hash(1), "1.0.0");
        let rec = node.tick(good_tick(1, 100)).unwrap();
        assert_eq!(rec.certificate.verdict, CertificationVerdict::Certified);
    }

    #[test]
    fn gossip_frame_is_16_bytes() {
        let mut node = ConstitutionalAutonode::new(const_hash(1), "1.0.0");
        let rec = node.tick(good_tick(1, 100)).unwrap();
        assert_eq!(rec.frame.bytes.len(), 16);
    }

    #[test]
    fn chain_entry_hash_nonzero() {
        let mut node = ConstitutionalAutonode::new(const_hash(1), "1.0.0");
        let rec = node.tick(good_tick(1, 100)).unwrap();
        assert_ne!(rec.chain_entry_hash, [0u8; 32]);
    }

    #[test]
    fn multiple_ticks_grow_chain() {
        let mut node = ConstitutionalAutonode::new(const_hash(1), "1.0.0");
        node.tick(good_tick(1, 100)).unwrap();
        node.tick(good_tick(2, 101)).unwrap();
        node.tick(good_tick(3, 102)).unwrap();
        assert_eq!(node.chain_length(), 3);
    }

    #[test]
    fn duplicate_epoch_rejected() {
        let mut node = ConstitutionalAutonode::new(const_hash(1), "1.0.0");
        node.tick(good_tick(5, 100)).unwrap();
        let err = node.tick(good_tick(5, 101));
        assert!(err.is_err());
    }

    #[test]
    fn terminal_hash_changes_with_ticks() {
        let mut node = ConstitutionalAutonode::new(const_hash(1), "1.0.0");
        let h0 = node.terminal_hash();
        node.tick(good_tick(1, 100)).unwrap();
        let h1 = node.terminal_hash();
        node.tick(good_tick(2, 101)).unwrap();
        let h2 = node.terminal_hash();
        assert_ne!(h0, h1);
        assert_ne!(h1, h2);
    }

    #[test]
    fn above_phi_divergence_uncertified() {
        use crate::self_certification::CertificationVerdict;
        let mut node = ConstitutionalAutonode::new(const_hash(1), "1.0.0");
        let mut t = good_tick(1, 100);
        t.divergence_risk = 0.99; // above 1/φ
        let rec = node.tick(t).unwrap();
        assert_eq!(rec.certificate.verdict, CertificationVerdict::Uncertified);
        assert!(!rec.is_fully_coherent);
    }

    #[test]
    fn breach_epoch_tracked() {
        let mut node = ConstitutionalAutonode::new(const_hash(1), "1.0.0");
        node.tick(good_tick(1, 100)).unwrap(); // coherent
        // Force a breach: above-phi → coherence fails L4
        let mut t2 = good_tick(2, 101);
        t2.divergence_risk = 0.99;
        let rec2 = node.tick(t2).unwrap();
        assert!(!rec2.is_fully_coherent);
        assert!(!node.is_continuously_coherent());
        assert_eq!(node.first_breach_epoch(), Some(2));
    }

    #[test]
    fn sequence_monotonicity_enforced_in_resonance() {
        let mut node = ConstitutionalAutonode::new(const_hash(1), "1.0.0");
        node.tick(good_tick(1, 200)).unwrap(); // last_sequence = 200
        let mut t2 = good_tick(2, 100); // sequence_id=100 < 200 → not monotone
        t2.ring_hashes = ring3(1, 2, 3);
        let rec = node.tick(t2).unwrap();
        assert!(!rec.resonance.sequence_monotone);
    }

    #[test]
    fn ring_hashes_too_short_is_err() {
        let mut node = ConstitutionalAutonode::new(const_hash(1), "1.0.0");
        let mut t = good_tick(1, 100);
        t.ring_hashes = vec![const_hash(1), const_hash(2)]; // only 2 elements
        assert!(node.tick(t).is_err());
    }

    #[test]
    fn determinism_same_inputs_same_hashes() {
        let build = || {
            let mut n = ConstitutionalAutonode::new(const_hash(42), "1.0.0");
            let r1 = n.tick(good_tick(1, 100)).unwrap();
            let r2 = n.tick(good_tick(2, 101)).unwrap();
            (r1.chain_entry_hash, r2.chain_entry_hash, n.terminal_hash())
        };
        let (a1, a2, at) = build();
        let (b1, b2, bt) = build();
        let (c1, c2, ct) = build();
        assert_eq!(a1, b1); assert_eq!(b1, c1);
        assert_eq!(a2, b2); assert_eq!(b2, c2);
        assert_eq!(at, bt); assert_eq!(bt, ct);
    }

    #[test]
    fn autonode_error_wraps_str() {
        let e = AutonodeError("test message");
        assert_eq!(e.0, "test message");
    }
}
