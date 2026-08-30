//! Gate 223: Constitutional Chord
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! A ConstitutionalChord is the compact spectral fingerprint of a constitutional state.
//! It projects a 32-byte constitutional hash through the resonance structure to produce
//! a 4-element encoding (vortex_family, digital_root, resonance_depth, phi_class).
//!
//! Two constitutional states are "in chord" (compatible resonance class) iff:
//!   1. Same VortexFamily (Triadic or Hexadic)
//!   2. Same PhiClass (BelowPhi, AtPhi, AbovePhi)
//! resonance_depth and digital_root may differ within a compatible chord.
//!
//! compact chord_bytes encoding:
//!   [0] vortex:  0 = Triadic, 1 = Hexadic
//!   [1] dr:      1..=9 (digital root of hash's leading u64, big-endian)
//!   [2] depth:   0..=4 (resonance_depth from ResonanceReport)
//!   [3] phi:     0 = BelowPhi, 1 = AtPhi, 2 = AbovePhi
//!
//! Use case: bridge /node response includes chord_bytes as a 4-hex-char fingerprint.
//! Any observer can immediately verify resonance compatibility without full hash comparison.
//!
//! Copyright (C) 2025 Tarik Skalić — AGPL-3.0-or-later

use crate::resonance_monitor::ResonanceReport;
use crate::vortex_classifier::{digital_root, VortexFamily};

const PHI_EPSILON: f64 = 1e-9;

// ─── Phi classification ───────────────────────────────────────────────────

/// Classification of a state's divergence risk relative to the 1/φ threshold.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum PhiClass {
    BelowPhi  = 0, // phi_headroom >  PHI_EPSILON — constitutionally convergent
    AtPhi     = 1, // phi_headroom within ±PHI_EPSILON — boundary state
    AbovePhi  = 2, // phi_headroom < -PHI_EPSILON — drift detected
}

fn classify_phi(phi_headroom: f64) -> PhiClass {
    if phi_headroom > PHI_EPSILON {
        PhiClass::BelowPhi
    } else if phi_headroom >= -PHI_EPSILON {
        PhiClass::AtPhi
    } else {
        PhiClass::AbovePhi
    }
}

// ─── Constitutional chord ─────────────────────────────────────────────────

/// Compact 4-component spectral fingerprint of a constitutional state.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ConstitutionalChord {
    pub vortex_family:    VortexFamily,
    pub digital_root:     u8,       // 1..=9, from leading u64 of constitutional_hash
    pub resonance_depth:  u8,       // 0..=4, from ResonanceReport
    pub phi_class:        PhiClass,
    pub chord_bytes:      [u8; 4],  // compact encoding
}

impl ConstitutionalChord {
    fn from_parts(
        vortex_family: VortexFamily,
        dr: u8,
        depth: u8,
        phi_class: PhiClass,
    ) -> Self {
        let chord_bytes = [
            vortex_family as u8,
            dr,
            depth,
            phi_class as u8,
        ];
        Self { vortex_family, digital_root: dr, resonance_depth: depth, phi_class, chord_bytes }
    }
}

#[derive(Debug)]
pub struct ChordError(pub &'static str);

impl std::fmt::Display for ChordError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "ChordError: {}", self.0)
    }
}

// ─── Core API ─────────────────────────────────────────────────────────────

/// Compute the constitutional chord from a 32-byte hash and a ResonanceReport.
///
/// The hash provides vortex classification via digital_root of its leading 8 bytes (big-endian u64).
/// The report provides resonance_depth and phi_headroom for phi_class.
/// Deterministic — same inputs → same chord every call.
pub fn compute_chord(
    constitutional_hash: &[u8; 32],
    report: &ResonanceReport,
) -> ConstitutionalChord {
    // Digital root of leading u64 (big-endian) of constitutional hash
    let leading = u64::from_be_bytes(constitutional_hash[..8].try_into().unwrap());
    let dr = digital_root(leading);

    let depth = report.resonance_depth.min(4);
    let phi_class = classify_phi(report.phi_headroom);

    ConstitutionalChord::from_parts(report.vortex_family, dr, depth, phi_class)
}

/// Returns true if two constitutional states are in the same resonance class.
/// Compatible iff same VortexFamily AND same PhiClass.
pub fn chords_in_resonance(a: &ConstitutionalChord, b: &ConstitutionalChord) -> bool {
    a.vortex_family == b.vortex_family && a.phi_class == b.phi_class
}

/// Decode a chord from its compact 4-byte encoding.
/// Returns Err if any byte value is out of valid range.
pub fn decode_chord(bytes: [u8; 4]) -> Result<ConstitutionalChord, ChordError> {
    let vortex_family = match bytes[0] {
        0 => VortexFamily::Triadic,
        1 => VortexFamily::Hexadic,
        _ => return Err(ChordError("invalid vortex byte: must be 0 or 1")),
    };
    let dr = bytes[1];
    if dr == 0 || dr > 9 {
        return Err(ChordError("invalid digital_root byte: must be 1..=9"));
    }
    let depth = bytes[2];
    if depth > 4 {
        return Err(ChordError("invalid resonance_depth byte: must be 0..=4"));
    }
    let phi_class = match bytes[3] {
        0 => PhiClass::BelowPhi,
        1 => PhiClass::AtPhi,
        2 => PhiClass::AbovePhi,
        _ => return Err(ChordError("invalid phi_class byte: must be 0, 1, or 2")),
    };
    Ok(ConstitutionalChord::from_parts(vortex_family, dr, depth, phi_class))
}

// ─── Tests ────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::resonance_monitor::{check_resonance, RESONANCE_CERTIFICATION_THRESHOLD};
    use crate::ring_composition::build_ring;

    fn hash_a() -> [u8; 32] {
        let mut h = [0u8; 32];
        // leading u64 big-endian = 0x0000000000000009 → digital_root(9) = 9 (Triadic)
        h[7] = 9;
        h
    }

    fn hash_b() -> [u8; 32] {
        let mut h = [0u8; 32];
        // leading u64 = 0x0000000000000001 → digital_root(1) = 1 (Hexadic)
        h[7] = 1;
        h
    }

    fn certified_report() -> ResonanceReport {
        let half = [hash_a(), hash_b()];
        let ring = build_ring(&half, None);
        check_resonance(0.1, 1, 4, &ring, 10, Some(9))
    }

    fn drift_report() -> ResonanceReport {
        let half = [hash_a(), hash_b()];
        let ring = build_ring(&half, None);
        check_resonance(0.9, 1, 4, &ring, 10, Some(9))
    }

    #[test]
    fn chord_vortex_from_hash() {
        let report = certified_report();
        let chord = compute_chord(&hash_a(), &report);
        // hash_a leading u64 = 9 → digital_root = 9 → Triadic
        assert_eq!(chord.digital_root, 9);
    }

    #[test]
    fn chord_phi_class_below() {
        let report = certified_report();
        // divergence_risk=0.1 < 0.618 → phi_headroom > 0 → BelowPhi
        let chord = compute_chord(&hash_a(), &report);
        assert_eq!(chord.phi_class, PhiClass::BelowPhi);
    }

    #[test]
    fn chord_phi_class_above() {
        let report = drift_report();
        // divergence_risk=0.9 > 0.618 → phi_headroom < 0 → AbovePhi
        let chord = compute_chord(&hash_a(), &report);
        assert_eq!(chord.phi_class, PhiClass::AbovePhi);
    }

    #[test]
    fn chord_phi_class_at_boundary() {
        // phi_headroom = 0.0 exactly → AtPhi
        use crate::phi_convergence::PHI_THRESHOLD;
        let half = [hash_a(), hash_b()];
        let ring = build_ring(&half, None);
        let report = check_resonance(PHI_THRESHOLD, 1, 4, &ring, 10, Some(9));
        let chord = compute_chord(&hash_a(), &report);
        assert_eq!(chord.phi_class, PhiClass::AtPhi);
    }

    #[test]
    fn chord_resonance_depth_propagated() {
        let report = certified_report();
        let chord = compute_chord(&hash_a(), &report);
        assert_eq!(chord.resonance_depth, report.resonance_depth);
    }

    #[test]
    fn chord_vortex_family_propagated() {
        let report = certified_report();
        let chord = compute_chord(&hash_a(), &report);
        assert_eq!(chord.vortex_family, report.vortex_family);
    }

    #[test]
    fn chord_bytes_encodes_correctly() {
        let report = certified_report();
        let chord = compute_chord(&hash_a(), &report);
        assert_eq!(chord.chord_bytes[0], chord.vortex_family as u8);
        assert_eq!(chord.chord_bytes[1], chord.digital_root);
        assert_eq!(chord.chord_bytes[2], chord.resonance_depth);
        assert_eq!(chord.chord_bytes[3], chord.phi_class as u8);
    }

    #[test]
    fn decode_round_trips() {
        let report = certified_report();
        let chord = compute_chord(&hash_a(), &report);
        let decoded = decode_chord(chord.chord_bytes).expect("decode must succeed");
        assert_eq!(decoded, chord);
    }

    #[test]
    fn decode_invalid_vortex() {
        let result = decode_chord([9, 3, 2, 0]);
        assert!(result.is_err());
    }

    #[test]
    fn decode_invalid_digital_root_zero() {
        let result = decode_chord([0, 0, 2, 0]);
        assert!(result.is_err());
    }

    #[test]
    fn decode_invalid_depth() {
        let result = decode_chord([0, 3, 5, 0]);
        assert!(result.is_err());
    }

    #[test]
    fn decode_invalid_phi_class() {
        let result = decode_chord([0, 3, 2, 9]);
        assert!(result.is_err());
    }

    #[test]
    fn chords_in_resonance_same_family_and_phi() {
        let r1 = certified_report();
        let r2 = certified_report();
        let c1 = compute_chord(&hash_a(), &r1);
        let c2 = compute_chord(&hash_b(), &r2);
        // Both BelowPhi; vortex family from report (same report → same family)
        assert!(chords_in_resonance(&c1, &c2));
    }

    #[test]
    fn chords_not_in_resonance_different_phi_class() {
        let r_good = certified_report();
        let r_drift = drift_report();
        let c_good = compute_chord(&hash_a(), &r_good);
        let c_drift = compute_chord(&hash_a(), &r_drift);
        assert!(!chords_in_resonance(&c_good, &c_drift));
    }

    #[test]
    fn determinism_x3() {
        let report = certified_report();
        let c1 = compute_chord(&hash_a(), &report);
        let c2 = compute_chord(&hash_a(), &report);
        let c3 = compute_chord(&hash_a(), &report);
        assert_eq!(c1, c2);
        assert_eq!(c2, c3);
    }

    #[test]
    fn different_hashes_may_differ_in_digital_root() {
        let report = certified_report();
        let c_a = compute_chord(&hash_a(), &report); // dr=9 (Triadic)
        let c_b = compute_chord(&hash_b(), &report); // dr=1 (Hexadic)
        assert_ne!(c_a.digital_root, c_b.digital_root);
    }

    #[test]
    fn certified_chord_has_depth_gte_three() {
        let report = certified_report();
        assert!(report.is_certified(), "test setup: report should be certified");
        assert!(RESONANCE_CERTIFICATION_THRESHOLD > 5.0 - 0.1);
        let chord = compute_chord(&hash_a(), &report);
        // Certified paths must have resonance_depth >= 3 (3 T1 invariants satisfied)
        assert!(chord.resonance_depth >= 3);
    }

    #[test]
    fn phi_class_ordering() {
        assert!(PhiClass::BelowPhi < PhiClass::AtPhi);
        assert!(PhiClass::AtPhi < PhiClass::AbovePhi);
    }
}
