//! Gate 222: Constitutional Resonance Monitor
//! EPISTEMIC TIER: T1 (invariants proven) / T2 (real-time application)
//!
//! Unifies all four mathematical substrate modules into a single ResonanceReport.
//!
//! Four invariants are checked:
//!   1. phi_convergent    — divergence_risk < 1/φ (phi_convergence.rs, T1)
//!   2. ring_valid        — A-B-C-B'-A' chiastic symmetry (ring_composition.rs, T1)
//!   3. sequence_monotone — sequence_id > max_committed (SPSF monotone law, T2)
//!   4. vortex_triadic    — rank span has Triadic digital root {3,6,9} (vortex_classifier.rs, T2)
//!
//! A path is RESONANT iff the three T1 invariants hold:
//!   is_resonant = phi_convergent AND ring_valid AND sequence_monotone
//!
//! resonance_depth = count of satisfied invariants (0..=4)
//! vortex_factor   = 3.0 if Triadic else 1.0
//! resonance_coefficient = resonance_depth × vortex_factor × phi_headroom.max(0.0)
//!
//! When resonance_coefficient > 5.0 → certified constitutional path (T1 proof).
//! Triadic paths with full invariants: 4 × 3.0 × 0.618 ≈ 7.4 > 5.0 ✓
//! Hexadic paths with full T1 invariants: 3 × 1.0 × 0.618 ≈ 1.85 < 5.0 (not certified)
//!
//! Copyright (C) 2025 Tarik Skalić — All rights reserved. AGPL-3.0-or-later

use crate::phi_convergence::PHI_THRESHOLD;
use crate::ring_composition::{verify_ring, RingVerdict};
use crate::vortex_classifier::{classify_vortex, VortexFamily};

// ─── Resonance coefficient threshold ─────────────────────────────────────

/// A resonance_coefficient above this value certifies a constitutional path (T1 proof).
pub const RESONANCE_CERTIFICATION_THRESHOLD: f64 = 5.0;

/// Vortex factor for Triadic rank spans (digital root in {3,6,9}).
pub const VORTEX_FACTOR_TRIADIC: f64 = 3.0;

/// Vortex factor for Hexadic rank spans (digital root in {1,2,4,5,7,8}).
pub const VORTEX_FACTOR_HEXADIC: f64 = 1.0;

// ─── Resonance report ────────────────────────────────────────────────────

/// Full resonance assessment for a constitutional path.
///
/// All fields are pure functions of the inputs — same inputs → same report every run.
#[derive(Debug, Clone, PartialEq)]
pub struct ResonanceReport {
    /// True iff phi_convergent AND ring_valid AND sequence_monotone.
    pub is_resonant: bool,

    /// Divergence risk is below 1/φ threshold (Lawvere metric safe zone).
    pub phi_convergent: bool,

    /// Vortex family of the rank span (Triadic = {3,6,9}, Hexadic = {1,2,4,5,7,8}).
    pub vortex_family: VortexFamily,

    /// Ring composition A-B-C-B'-A' holds over the provided hash sequence.
    pub ring_valid: bool,

    /// Sequence ID is strictly greater than max_committed (monotone write law).
    pub sequence_monotone: bool,

    /// Number of satisfied invariants: phi_convergent + ring_valid + sequence_monotone + vortex_triadic.
    pub resonance_depth: u8,

    /// resonance_depth × vortex_factor × phi_headroom.max(0.0)
    pub resonance_coefficient: f64,

    /// 1/φ − divergence_risk (positive = convergent, negative = breach).
    pub phi_headroom: f64,
}

impl ResonanceReport {
    /// Returns true if the resonance_coefficient exceeds the certification threshold.
    #[inline]
    pub fn is_certified(&self) -> bool {
        self.resonance_coefficient > RESONANCE_CERTIFICATION_THRESHOLD
    }
}

// ─── Core function ────────────────────────────────────────────────────────

/// Compute the full resonance assessment for a constitutional path.
///
/// # Arguments
/// * `divergence_risk` — cumulative Lawvere divergence risk of the path
/// * `start_rank`      — RANK of the path start node
/// * `end_rank`        — RANK of the path end node (must exceed start_rank for phi check)
/// * `ring_hashes`     — hash sequence for A-B-C-B'-A' ring verification (≥ 3 elements required)
/// * `sequence_id`     — current sequence ID to check for monotonicity
/// * `max_committed`   — maximum sequence ID already committed (None = first write)
///
/// # Determinism
/// Same inputs → same ResonanceReport every call. No clock, no randomness, no heap state.
pub fn check_resonance(
    divergence_risk: f64,
    start_rank: usize,
    end_rank: usize,
    ring_hashes: &[[u8; 32]],
    sequence_id: u64,
    max_committed: Option<u64>,
) -> ResonanceReport {
    // ── 1. Phi convergence ────────────────────────────────────────────────
    let phi_headroom = PHI_THRESHOLD - divergence_risk;
    let phi_convergent = phi_headroom > 0.0;

    // ── 2. Vortex family from rank span ──────────────────────────────────
    // If end_rank <= start_rank the span is invalid; fall back to Hexadic.
    let vortex_family = if end_rank > start_rank {
        let span = (end_rank - start_rank) as u64;
        classify_vortex(span)
    } else {
        VortexFamily::Hexadic
    };

    // ── 3. Ring composition ──────────────────────────────────────────────
    let ring_result = verify_ring(ring_hashes);
    let ring_valid = ring_result.verdict == RingVerdict::Valid;

    // ── 4. Sequence monotonicity ─────────────────────────────────────────
    let sequence_monotone = match max_committed {
        None => true,                      // first write — always monotone
        Some(max) => sequence_id > max,
    };

    // ── Resonance depth (count of 4 satisfied conditions) ────────────────
    let vortex_triadic = vortex_family == VortexFamily::Triadic;
    let resonance_depth = [phi_convergent, ring_valid, sequence_monotone, vortex_triadic]
        .iter()
        .filter(|&&b| b)
        .count() as u8;

    // ── Resonance coefficient ─────────────────────────────────────────────
    let vortex_factor = if vortex_triadic {
        VORTEX_FACTOR_TRIADIC
    } else {
        VORTEX_FACTOR_HEXADIC
    };
    let headroom_clamped = phi_headroom.max(0.0);
    let resonance_coefficient = (resonance_depth as f64) * vortex_factor * headroom_clamped;

    // ── is_resonant: three T1 invariants ─────────────────────────────────
    let is_resonant = phi_convergent && ring_valid && sequence_monotone;

    ResonanceReport {
        is_resonant,
        phi_convergent,
        vortex_family,
        ring_valid,
        sequence_monotone,
        resonance_depth,
        resonance_coefficient,
        phi_headroom,
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::vortex_classifier::VortexFamily;

    // ─── Helpers ──────────────────────────────────────────────────────────

    fn make_ring_5() -> Vec<[u8; 32]> {
        let a = [0x01u8; 32];
        let b = [0x02u8; 32];
        let c = [0x03u8; 32];
        vec![a, b, c, b, a]  // A-B-C-B-A valid ring
    }

    fn make_ring_broken() -> Vec<[u8; 32]> {
        let a = [0x01u8; 32];
        let b = [0x02u8; 32];
        let c = [0x03u8; 32];
        let x = [0x99u8; 32];
        vec![a, b, c, b, x]  // last element != first → broken
    }

    // Safe risk = 0.1 (well below 1/φ ≈ 0.618), headroom ≈ 0.518
    // Triadic rank span: 1 → 4, span=3, digital_root=3 (Triadic)
    // Ring: valid 5-element ring
    // Sequence: first write (max_committed=None)

    #[test]
    fn ideal_triadic_path_is_resonant() {
        let report = check_resonance(0.1, 1, 4, &make_ring_5(), 1, None);
        assert!(report.is_resonant, "triadic path with all invariants must be resonant");
        assert!(report.phi_convergent);
        assert!(report.ring_valid);
        assert!(report.sequence_monotone);
        assert_eq!(report.vortex_family, VortexFamily::Triadic);
    }

    #[test]
    fn ideal_triadic_path_coefficient_exceeds_threshold() {
        let report = check_resonance(0.05, 1, 4, &make_ring_5(), 1, None);
        assert!(
            report.resonance_coefficient > RESONANCE_CERTIFICATION_THRESHOLD,
            "coefficient {} should exceed {}",
            report.resonance_coefficient,
            RESONANCE_CERTIFICATION_THRESHOLD
        );
        assert!(report.is_certified());
    }

    #[test]
    fn resonance_depth_all_four_satisfied() {
        // rank span 3 = Triadic, risk 0.1 < 1/φ, valid ring, first write
        let report = check_resonance(0.1, 1, 4, &make_ring_5(), 1, None);
        assert_eq!(report.resonance_depth, 4, "all 4 invariants satisfied");
    }

    #[test]
    fn hexadic_path_lower_coefficient_than_triadic() {
        // rank span 1 → 2 = span=1, digital_root=1 (Hexadic)
        let hex = check_resonance(0.1, 1, 2, &make_ring_5(), 1, None);
        let tri = check_resonance(0.1, 1, 4, &make_ring_5(), 1, None);
        assert_eq!(hex.vortex_family, VortexFamily::Hexadic);
        assert_eq!(tri.vortex_family, VortexFamily::Triadic);
        assert!(
            hex.resonance_coefficient < tri.resonance_coefficient,
            "hexadic {} < triadic {}",
            hex.resonance_coefficient,
            tri.resonance_coefficient
        );
    }

    #[test]
    fn hexadic_path_does_not_exceed_threshold() {
        // Hexadic: depth 3 (no triadic bonus), vortex_factor=1.0, headroom max ~0.618
        // max coefficient: 3 * 1.0 * 0.618 ≈ 1.854 < 5.0
        let report = check_resonance(0.01, 1, 2, &make_ring_5(), 1, None);
        assert_eq!(report.vortex_family, VortexFamily::Hexadic);
        assert!(!report.is_certified(), "hexadic path must not be certified");
    }

    #[test]
    fn above_phi_risk_not_convergent() {
        // risk = 0.65 > 1/φ ≈ 0.618 → phi_convergent=false
        let report = check_resonance(0.65, 1, 4, &make_ring_5(), 1, None);
        assert!(!report.phi_convergent);
        assert!(!report.is_resonant);
        assert!(report.phi_headroom < 0.0);
    }

    #[test]
    fn above_phi_resonance_depth_reduced() {
        // phi fails → depth loses at least 1
        let report = check_resonance(0.65, 1, 4, &make_ring_5(), 1, None);
        // phi not satisfied, ring OK, seq OK, vortex Triadic → depth = 3
        assert_eq!(report.resonance_depth, 3);
    }

    #[test]
    fn above_phi_coefficient_is_zero() {
        // headroom negative → clamped to 0.0 → coefficient = 0
        let report = check_resonance(0.65, 1, 4, &make_ring_5(), 1, None);
        assert_eq!(report.resonance_coefficient, 0.0);
    }

    #[test]
    fn broken_ring_not_resonant() {
        let report = check_resonance(0.1, 1, 4, &make_ring_broken(), 1, None);
        assert!(!report.ring_valid);
        assert!(!report.is_resonant);
    }

    #[test]
    fn too_short_ring_not_valid() {
        // fewer than 3 hashes → TooShort → ring_valid=false
        let short = vec![[0u8; 32], [1u8; 32]];
        let report = check_resonance(0.1, 1, 4, &short, 1, None);
        assert!(!report.ring_valid);
        assert!(!report.is_resonant);
    }

    #[test]
    fn empty_ring_not_valid() {
        let report = check_resonance(0.1, 1, 4, &[], 1, None);
        assert!(!report.ring_valid);
    }

    #[test]
    fn sequence_gap_not_monotone() {
        // max_committed=5, sequence_id=3 → not monotone
        let report = check_resonance(0.1, 1, 4, &make_ring_5(), 3, Some(5));
        assert!(!report.sequence_monotone);
        assert!(!report.is_resonant);
    }

    #[test]
    fn sequence_equal_not_monotone() {
        // max_committed=5, sequence_id=5 → equal → not strictly greater → not monotone
        let report = check_resonance(0.1, 1, 4, &make_ring_5(), 5, Some(5));
        assert!(!report.sequence_monotone);
    }

    #[test]
    fn sequence_first_write_always_monotone() {
        // max_committed=None → first write → monotone regardless of sequence_id
        let report = check_resonance(0.1, 1, 4, &make_ring_5(), 0, None);
        assert!(report.sequence_monotone);
    }

    #[test]
    fn sequence_advancing_is_monotone() {
        // max_committed=5, sequence_id=6 → monotone
        let report = check_resonance(0.1, 1, 4, &make_ring_5(), 6, Some(5));
        assert!(report.sequence_monotone);
        assert!(report.is_resonant);
    }

    #[test]
    fn invalid_rank_span_falls_back_to_hexadic() {
        // end_rank <= start_rank → invalid span → Hexadic fallback
        let report = check_resonance(0.1, 5, 3, &make_ring_5(), 1, None);
        assert_eq!(report.vortex_family, VortexFamily::Hexadic);
    }

    #[test]
    fn equal_ranks_falls_back_to_hexadic() {
        let report = check_resonance(0.1, 4, 4, &make_ring_5(), 1, None);
        assert_eq!(report.vortex_family, VortexFamily::Hexadic);
    }

    #[test]
    fn vortex_family_9_is_triadic() {
        // rank span 1 → 10 = 9, digital_root=9 (Triadic, fixed point)
        let report = check_resonance(0.1, 1, 10, &make_ring_5(), 1, None);
        assert_eq!(report.vortex_family, VortexFamily::Triadic);
    }

    #[test]
    fn vortex_family_6_is_triadic() {
        // rank span 1 → 7 = 6, digital_root=6 (Triadic)
        let report = check_resonance(0.1, 1, 7, &make_ring_5(), 1, None);
        assert_eq!(report.vortex_family, VortexFamily::Triadic);
    }

    #[test]
    fn coefficient_formula_verified() {
        // depth=4, vortex_factor=3.0, headroom=PHI_THRESHOLD - 0.1
        let risk = 0.1_f64;
        let headroom = PHI_THRESHOLD - risk;
        let expected_coeff = 4.0 * VORTEX_FACTOR_TRIADIC * headroom;
        let report = check_resonance(risk, 1, 4, &make_ring_5(), 1, None);
        let diff = (report.resonance_coefficient - expected_coeff).abs();
        assert!(diff < 1e-12, "coefficient formula mismatch: {} vs {}", report.resonance_coefficient, expected_coeff);
    }

    #[test]
    fn determinism_run_1() {
        let r1 = check_resonance(0.1, 1, 4, &make_ring_5(), 1, None);
        let r2 = check_resonance(0.1, 1, 4, &make_ring_5(), 1, None);
        let r3 = check_resonance(0.1, 1, 4, &make_ring_5(), 1, None);
        assert_eq!(r1, r2);
        assert_eq!(r2, r3);
    }

    #[test]
    fn determinism_run_2() {
        let r1 = check_resonance(0.55, 2, 8, &make_ring_5(), 10, Some(9));
        let r2 = check_resonance(0.55, 2, 8, &make_ring_5(), 10, Some(9));
        let r3 = check_resonance(0.55, 2, 8, &make_ring_5(), 10, Some(9));
        assert_eq!(r1, r2);
        assert_eq!(r2, r3);
    }

    #[test]
    fn determinism_run_3() {
        let r1 = check_resonance(0.65, 1, 2, &make_ring_broken(), 3, Some(5));
        let r2 = check_resonance(0.65, 1, 2, &make_ring_broken(), 3, Some(5));
        let r3 = check_resonance(0.65, 1, 2, &make_ring_broken(), 3, Some(5));
        assert_eq!(r1, r2);
        assert_eq!(r2, r3);
    }

    #[test]
    fn no_invariants_satisfied_depth_zero() {
        // All invariants fail except vortex (Hexadic means vortex_triadic=false too)
        // risk > 1/φ, broken ring, sequence gap, hexadic span
        let report = check_resonance(0.65, 1, 2, &make_ring_broken(), 3, Some(5));
        assert_eq!(report.resonance_depth, 0);
        assert_eq!(report.resonance_coefficient, 0.0);
        assert!(!report.is_resonant);
        assert!(!report.is_certified());
    }

    #[test]
    fn phi_headroom_exactly_at_boundary() {
        // risk = PHI_THRESHOLD → headroom = 0.0 → NOT convergent (strict >)
        let report = check_resonance(PHI_THRESHOLD, 1, 4, &make_ring_5(), 1, None);
        assert!(!report.phi_convergent, "exactly at threshold is not convergent");
        assert_eq!(report.phi_headroom, 0.0);
    }

    #[test]
    fn triadic_depth_3_sequence_fail() {
        // phi OK, ring OK, seq FAIL, vortex Triadic → depth=3, is_resonant=false
        let report = check_resonance(0.1, 1, 4, &make_ring_5(), 3, Some(5));
        assert_eq!(report.resonance_depth, 3);
        assert!(!report.is_resonant);
        // depth=3, vortex_factor=3.0, headroom=0.518 → ~4.67 < 5.0
        assert!(!report.is_certified());
    }
}
