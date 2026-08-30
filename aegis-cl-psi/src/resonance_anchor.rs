//! Gate 321 — Resonance Anchor: hash-chained constitutional resonance ledger (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Wraps Gate 222 `check_resonance` to add:
//!   • report_hash        — SHA-256(prev_hash[32] ‖ encoded fields) for audit replay
//!   • vortex_is_triadic  — explicit bool derived from VortexFamily
//!   • ring_depth         — chiastic ring depth (center_index from ring_composition)
//!   • certified_constitutional — resonance_coefficient > RESONANCE_CERTIFICATION_THRESHOLD
//!
//! Hash input layout:
//!   prev_hash[32]
//!   ‖ is_resonant_byte
//!   ‖ phi_convergent_byte
//!   ‖ ring_valid_byte
//!   ‖ sequence_monotone_byte
//!   ‖ vortex_is_triadic_byte
//!   ‖ certified_constitutional_byte
//!   ‖ resonance_depth_byte
//!   ‖ ring_depth_be8
//!   ‖ coefficient_bits_be8   (f64 → to_bits() → big-endian)
//!   ‖ phi_headroom_bits_be8
//!   ‖ sequence_id_be8
//!
//! ResonanceChain: record(), latest(), verify_chain() → (bool, Option<usize>)
//! Genesis hash: RESONANCE_ANCHOR_GENESIS_HASH = [0u8; 32]

use sha2::{Sha256, Digest};

use crate::resonance_monitor::{
    check_resonance, RESONANCE_CERTIFICATION_THRESHOLD,
};
use crate::ring_composition::{verify_ring, RingVerdict};
use crate::vortex_classifier::VortexFamily;

pub const RESONANCE_ANCHOR_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── Anchored report ──────────────────────────────────────────────────────────

/// A single hash-chained resonance record with augmented fields.
#[derive(Debug, Clone, PartialEq)]
pub struct AnchoredResonanceReport {
    // ── Provenance ──────────────────────────────────────────────────────────
    pub sequence_id:    u64,
    pub prev_hash:      [u8; 32],
    pub report_hash:    [u8; 32],

    // ── Core invariants (mirrored from ResonanceReport) ─────────────────────
    pub is_resonant:            bool,
    pub phi_convergent:         bool,
    pub ring_valid:             bool,
    pub sequence_monotone:      bool,
    pub resonance_depth:        u8,
    pub resonance_coefficient:  f64,
    pub phi_headroom:           f64,

    // ── Augmented fields ────────────────────────────────────────────────────
    /// True when VortexFamily is Triadic (digital root ∈ {3,6,9}).
    pub vortex_is_triadic:          bool,
    /// Center index from ring_composition::verify_ring — 0 when ring is invalid or too short.
    pub ring_depth:                 usize,
    /// resonance_coefficient > RESONANCE_CERTIFICATION_THRESHOLD (5.0).
    pub certified_constitutional:   bool,
}

// ─── Input ────────────────────────────────────────────────────────────────────

/// Input parameters for a single anchor record.
#[derive(Debug, Clone, Copy)]
pub struct ResonanceAnchorInput {
    pub divergence_risk: f64,
    pub start_rank:      usize,
    pub end_rank:        usize,
    pub sequence_id:     u64,
    pub max_committed:   Option<u64>,
}

// ─── Hash computation ─────────────────────────────────────────────────────────

fn compute_anchor_hash_with_seq(
    prev:    &[u8; 32],
    rec:     &AnchoredResonanceReport,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update([rec.is_resonant           as u8]);
    h.update([rec.phi_convergent        as u8]);
    h.update([rec.ring_valid            as u8]);
    h.update([rec.sequence_monotone     as u8]);
    h.update([rec.vortex_is_triadic     as u8]);
    h.update([rec.certified_constitutional as u8]);
    h.update([rec.resonance_depth]);
    h.update((rec.ring_depth as u64).to_be_bytes());
    h.update(rec.resonance_coefficient.to_bits().to_be_bytes());
    h.update(rec.phi_headroom.to_bits().to_be_bytes());
    h.update(rec.sequence_id.to_be_bytes());
    h.finalize().into()
}

// ─── Build one anchored report ────────────────────────────────────────────────

/// Build an `AnchoredResonanceReport` from raw inputs plus a hash-chain predecessor.
///
/// `ring_hashes` is forwarded to `check_resonance` and also used to extract `ring_depth`.
pub fn anchor_resonance(
    prev:       &[u8; 32],
    inp:        ResonanceAnchorInput,
    ring_hashes: &[[u8; 32]],
) -> AnchoredResonanceReport {
    // ── Run Gate 222 core computation ──────────────────────────────────────
    let report = check_resonance(
        inp.divergence_risk,
        inp.start_rank,
        inp.end_rank,
        ring_hashes,
        inp.sequence_id,
        inp.max_committed,
    );

    // ── Augmented fields ──────────────────────────────────────────────────
    let vortex_is_triadic = matches!(report.vortex_family, VortexFamily::Triadic);

    // Ring depth = center_index of the ring verification result.
    let ring_depth = if ring_hashes.len() >= 3 {
        let result = verify_ring(ring_hashes);
        match result.verdict {
            RingVerdict::Valid => result.center_index,
            _                 => 0,
        }
    } else {
        0
    };

    let certified = report.resonance_coefficient > RESONANCE_CERTIFICATION_THRESHOLD;

    // ── Hash including sequence_id ────────────────────────────────────────
    let mut h = Sha256::new();
    h.update(prev);
    h.update([report.is_resonant           as u8]);
    h.update([report.phi_convergent        as u8]);
    h.update([report.ring_valid            as u8]);
    h.update([report.sequence_monotone     as u8]);
    h.update([vortex_is_triadic            as u8]);
    h.update([certified                    as u8]);
    h.update([report.resonance_depth]);
    h.update((ring_depth as u64).to_be_bytes());
    h.update(report.resonance_coefficient.to_bits().to_be_bytes());
    h.update(report.phi_headroom.to_bits().to_be_bytes());
    h.update(inp.sequence_id.to_be_bytes());
    let report_hash: [u8; 32] = h.finalize().into();

    AnchoredResonanceReport {
        sequence_id:           inp.sequence_id,
        prev_hash:             *prev,
        report_hash,
        is_resonant:           report.is_resonant,
        phi_convergent:        report.phi_convergent,
        ring_valid:            report.ring_valid,
        sequence_monotone:     report.sequence_monotone,
        resonance_depth:       report.resonance_depth,
        resonance_coefficient: report.resonance_coefficient,
        phi_headroom:          report.phi_headroom,
        vortex_is_triadic,
        ring_depth,
        certified_constitutional: certified,
    }
}

// ─── Chain monitor ────────────────────────────────────────────────────────────

/// Append-only hash-chained ledger of resonance assessments.
///
/// Each record's `prev_hash` links to the `report_hash` of its predecessor,
/// beginning at `RESONANCE_ANCHOR_GENESIS_HASH`.
pub struct ResonanceChain {
    records: Vec<AnchoredResonanceReport>,
}

impl ResonanceChain {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[AnchoredResonanceReport] { &self.records }

    /// Record a new assessment, chaining from the last report (or genesis).
    pub fn record(
        &mut self,
        inp:         ResonanceAnchorInput,
        ring_hashes: &[[u8; 32]],
    ) -> AnchoredResonanceReport {
        let prev = self.records.last()
            .map(|r| r.report_hash)
            .unwrap_or(RESONANCE_ANCHOR_GENESIS_HASH);
        let rec = anchor_resonance(&prev, inp, ring_hashes);
        self.records.push(rec.clone());
        rec
    }

    /// Most recently recorded report, or `None` if empty.
    pub fn latest(&self) -> Option<&AnchoredResonanceReport> {
        self.records.last()
    }

    /// True if the most recent record is a certified constitutional path.
    pub fn is_chain_certified(&self) -> Option<bool> {
        self.latest().map(|r| r.certified_constitutional)
    }

    /// Verify hash-chain integrity.
    ///
    /// Returns `(true, None)` when all links are valid.
    /// Returns `(false, Some(idx))` where `idx` is the first broken record.
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = RESONANCE_ANCHOR_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_anchor_hash_with_seq(&prev, r);
            if r.report_hash != expected {
                return (false, Some(i));
            }
            prev = r.report_hash;
        }
        (true, None)
    }
}

impl Default for ResonanceChain {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── Helpers ──────────────────────────────────────────────────────────────

    fn ideal_input(seq: u64) -> ResonanceAnchorInput {
        ResonanceAnchorInput {
            divergence_risk: 0.1,   // well below PHI_THRESHOLD ≈ 0.618
            start_rank: 3,
            end_rank:   9,          // span 6 → digital root 6 → Triadic
            sequence_id: seq,
            max_committed: if seq > 1 { Some(seq - 1) } else { None },
        }
    }

    /// Minimal valid ring: [A, B, A]
    fn ring3() -> Vec<[u8; 32]> {
        let a = [0xAAu8; 32];
        let b = [0xBBu8; 32];
        vec![a, b, a]
    }

    /// Longer valid ring: [A, B, C, B, A]
    fn ring5() -> Vec<[u8; 32]> {
        let a = [0x11u8; 32];
        let b = [0x22u8; 32];
        let c = [0x33u8; 32];
        vec![a, b, c, b, a]
    }

    /// Empty ring (→ ring_valid=false, ring_depth=0)
    fn ring_empty() -> Vec<[u8; 32]> { vec![] }

    // ── Genesis ───────────────────────────────────────────────────────────────

    #[test]
    fn genesis_hash_is_zero() {
        assert_eq!(RESONANCE_ANCHOR_GENESIS_HASH, [0u8; 32]);
    }

    #[test]
    fn fresh_chain_empty() {
        let c = ResonanceChain::new();
        assert!(c.is_empty());
        assert!(c.latest().is_none());
        assert!(c.is_chain_certified().is_none());
    }

    // ── Single record ─────────────────────────────────────────────────────────

    #[test]
    fn first_record_prev_is_genesis() {
        let mut c = ResonanceChain::new();
        let r = c.record(ideal_input(1), &ring3());
        assert_eq!(r.prev_hash, RESONANCE_ANCHOR_GENESIS_HASH);
    }

    #[test]
    fn report_hash_is_32_bytes() {
        let mut c = ResonanceChain::new();
        let r = c.record(ideal_input(1), &ring3());
        // Non-zero (astronomically unlikely to be zero)
        assert_ne!(r.report_hash, [0u8; 32]);
    }

    #[test]
    fn ideal_path_is_resonant() {
        let mut c = ResonanceChain::new();
        let r = c.record(ideal_input(1), &ring3());
        assert!(r.is_resonant);
        assert!(r.phi_convergent);
        assert!(r.ring_valid);
        assert!(r.sequence_monotone);
    }

    #[test]
    fn ideal_path_vortex_is_triadic() {
        let mut c = ResonanceChain::new();
        // span = end_rank - start_rank = 9 - 3 = 6; digital_root(6) = 6 → Triadic
        let r = c.record(ideal_input(1), &ring3());
        assert!(r.vortex_is_triadic);
    }

    #[test]
    fn ideal_path_certified_constitutional() {
        let mut c = ResonanceChain::new();
        // Triadic + all 4 invariants → depth=4, coeff = 4 × 3.0 × phi_headroom > 5.0
        let r = c.record(ideal_input(1), &ring3());
        assert!(r.certified_constitutional);
    }

    // ── Ring depth ────────────────────────────────────────────────────────────

    #[test]
    fn ring_depth_ring3_is_1() {
        let mut c = ResonanceChain::new();
        let r = c.record(ideal_input(1), &ring3());
        // ring3 = [A, B, A] — center_index = 1
        assert_eq!(r.ring_depth, 1);
    }

    #[test]
    fn ring_depth_ring5_is_2() {
        let mut c = ResonanceChain::new();
        let r = c.record(ideal_input(1), &ring5());
        // ring5 = [A, B, C, B, A] — center_index = 2
        assert_eq!(r.ring_depth, 2);
    }

    #[test]
    fn ring_depth_empty_is_0() {
        let mut c = ResonanceChain::new();
        let r = c.record(ideal_input(1), &ring_empty());
        assert_eq!(r.ring_depth, 0);
    }

    // ── Non-certified path ────────────────────────────────────────────────────

    #[test]
    fn above_phi_not_certified() {
        let mut c = ResonanceChain::new();
        let inp = ResonanceAnchorInput {
            divergence_risk: 0.99,  // above PHI_THRESHOLD ≈ 0.618
            start_rank: 3,
            end_rank:   9,
            sequence_id: 1,
            max_committed: None,
        };
        let r = c.record(inp, &ring3());
        assert!(!r.phi_convergent);
        assert!(!r.is_resonant);
        assert!(!r.certified_constitutional);
    }

    #[test]
    fn hexadic_span_not_triadic() {
        let mut c = ResonanceChain::new();
        let inp = ResonanceAnchorInput {
            divergence_risk: 0.1,
            start_rank: 0,
            end_rank:   1, // span=1, digital_root(1)=1 → Hexadic
            sequence_id: 1,
            max_committed: None,
        };
        let r = c.record(inp, &ring3());
        assert!(!r.vortex_is_triadic);
    }

    // ── Hash-chain linking ────────────────────────────────────────────────────

    #[test]
    fn second_record_links_to_first() {
        let mut c = ResonanceChain::new();
        let r1 = c.record(ideal_input(1), &ring3());
        let r2 = c.record(ideal_input(2), &ring3());
        assert_eq!(r2.prev_hash, r1.report_hash);
    }

    #[test]
    fn chain_links_three_records() {
        let mut c = ResonanceChain::new();
        let r1 = c.record(ideal_input(1), &ring3());
        let r2 = c.record(ideal_input(2), &ring3());
        let r3 = c.record(ideal_input(3), &ring3());
        assert_eq!(r1.prev_hash, RESONANCE_ANCHOR_GENESIS_HASH);
        assert_eq!(r2.prev_hash, r1.report_hash);
        assert_eq!(r3.prev_hash, r2.report_hash);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let c = ResonanceChain::new();
        let (ok, idx) = c.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_three_ok() {
        let mut c = ResonanceChain::new();
        c.record(ideal_input(1), &ring3());
        c.record(ideal_input(2), &ring5());
        c.record(ideal_input(3), &ring3());
        let (ok, idx) = c.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_tampered_report_hash() {
        let mut c = ResonanceChain::new();
        c.record(ideal_input(1), &ring3());
        c.record(ideal_input(2), &ring3());
        // Tamper record[1] report_hash
        c.records[1].report_hash[0] ^= 0xFF;
        let (ok, idx) = c.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn verify_chain_tampered_prev_hash() {
        let mut c = ResonanceChain::new();
        c.record(ideal_input(1), &ring3());
        c.record(ideal_input(2), &ring3());
        // Tamper record[1] prev_hash to break the link
        c.records[1].prev_hash[0] ^= 0x01;
        let (ok, idx) = c.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    // ── Determinism ───────────────────────────────────────────────────────────

    #[test]
    fn determinism_same_input_three_times() {
        let inp = ideal_input(7);
        let hashes = ring3();

        let mut c1 = ResonanceChain::new(); let r1 = c1.record(inp, &hashes);
        let mut c2 = ResonanceChain::new(); let r2 = c2.record(inp, &hashes);
        let mut c3 = ResonanceChain::new(); let r3 = c3.record(inp, &hashes);

        assert_eq!(r1.report_hash, r2.report_hash);
        assert_eq!(r2.report_hash, r3.report_hash);
    }

    #[test]
    fn different_seq_different_hash() {
        let h = ring3();
        let mut c1 = ResonanceChain::new(); let r1 = c1.record(ideal_input(1), &h);
        let mut c2 = ResonanceChain::new(); let r2 = c2.record(ideal_input(2), &h);
        assert_ne!(r1.report_hash, r2.report_hash);
    }

    // ── Sequence ID ───────────────────────────────────────────────────────────

    #[test]
    fn sequence_id_preserved() {
        let mut c = ResonanceChain::new();
        let r = c.record(ideal_input(42), &ring3());
        assert_eq!(r.sequence_id, 42);
    }

    // ── Resonance depth and coefficient ──────────────────────────────────────

    #[test]
    fn resonance_depth_four_on_ideal() {
        let mut c = ResonanceChain::new();
        let r = c.record(ideal_input(1), &ring3());
        assert_eq!(r.resonance_depth, 4);
    }

    #[test]
    fn coefficient_positive_on_ideal() {
        let mut c = ResonanceChain::new();
        let r = c.record(ideal_input(1), &ring3());
        assert!(r.resonance_coefficient > 0.0);
        // Triadic + 4 invariants → 4 × 3.0 × phi_headroom ≈ 7.4
        assert!(r.resonance_coefficient > 5.0);
    }

    // ── anchor_resonance standalone ──────────────────────────────────────────

    #[test]
    fn anchor_resonance_standalone() {
        let prev = [0u8; 32];
        let inp  = ideal_input(1);
        let r    = anchor_resonance(&prev, inp, &ring3());
        assert_eq!(r.prev_hash, [0u8; 32]);
        assert!(r.is_resonant);
        assert!(r.certified_constitutional);
    }
}
