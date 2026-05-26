//! Gate 225: Constitutional Self-Certification — Autopoietic State Closure
//! EPISTEMIC TIER: T2 (engineering hypothesis) / T1 (hash chain integrity is T0-provable)
//!
//! The autopoietic closure: the system certifies its own constitutional state by
//! computing a deterministic SHA-256 hash over ALL active constitutional substrates:
//!   ResonanceReport (Gate 222) + NetworkResonanceReport structure (Gate 224) + version
//!
//! This IS the autopoietic loop made concrete:
//!   "As the agents drive in autopoietic state, so the full state does."
//!   The self-certificate IS the system's self-description. It changes exactly when
//!   the constitutional state changes and is unchanged when state is stable.
//!
//! CertificationVerdict:
//!   Certified           — all T1 invariants satisfied + network unified + T0 clean
//!   ProvisionallyGranted — T1 invariants satisfied but network clustered or phi-boundary
//!   Uncertified         — any T1 invariant violated OR network split OR above-phi
//!
//! The self_hash is deterministic across all platforms (pure arithmetic, no clock,
//! no RNG, no platform-specific behavior). Same inputs → same hash every call.
//!
//! Copyright (C) 2025 Tarik Skalić — AGPL-3.0-or-later

use sha2::{Sha256, Digest};
use crate::resonance_monitor::ResonanceReport;
use crate::chord_network::NetworkVerdict;

// ─── Verdict ──────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum CertificationVerdict {
    Certified            = 2, // full T1 proof + UNIFIED network + BelowPhi
    ProvisionallyGranted = 1, // T1 proof holds, network clustered or AtPhi boundary
    Uncertified          = 0, // any invariant violated or SPLIT or AbovePhi
}

// ─── Self-certificate ─────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct SelfCertificate {
    /// Deterministic verdict based on all constitutional inputs.
    pub verdict: CertificationVerdict,

    /// Constitutional hash bound into this certificate.
    pub bound_constitutional_hash: [u8; 32],

    /// Resonance state at time of certification.
    pub resonance_depth: u8,
    pub resonance_coefficient: f64,
    pub phi_convergent: bool,
    pub ring_valid: bool,
    pub sequence_monotone: bool,

    /// Network state at time of certification.
    pub network_verdict: NetworkVerdict,
    pub peer_count: usize,
    pub above_phi_count: usize,
    pub quorum_triadic: bool,

    /// System version string — bound into certificate hash.
    pub system_version: &'static str,

    /// SHA-256 of all fields above, serialized canonically (no serde — pure arithmetic).
    pub self_hash: [u8; 32],
}

impl SelfCertificate {
    /// Returns true iff this is a Certified or ProvisionallyGranted certificate.
    pub fn is_sound(&self) -> bool {
        self.verdict != CertificationVerdict::Uncertified
    }

    /// Returns true iff this is fully Certified (all invariants + UNIFIED + BelowPhi).
    pub fn is_certified(&self) -> bool {
        self.verdict == CertificationVerdict::Certified
    }
}

// ─── Network input ────────────────────────────────────────────────────────

/// Minimal network state needed for self-certification (avoids importing full ChordNetwork).
#[derive(Debug, Clone, Copy)]
pub struct NetworkSnapshot {
    pub verdict:        NetworkVerdict,
    pub peer_count:     usize,
    pub above_phi_count: usize,
    pub quorum_triadic: bool,
}

// ─── Canonical serialization ──────────────────────────────────────────────
// No serde — pure deterministic byte construction. Every field has fixed-width encoding.

fn serialize_bool(b: bool) -> u8 { if b { 1u8 } else { 0u8 } }

fn build_canonical_bytes(
    constitutional_hash: &[u8; 32],
    resonance: &ResonanceReport,
    network:   &NetworkSnapshot,
    version:   &str,
) -> Vec<u8> {
    let mut buf = Vec::with_capacity(128);

    // constitutional_hash — 32 bytes
    buf.extend_from_slice(constitutional_hash);

    // ResonanceReport — deterministic field serialization
    buf.push(serialize_bool(resonance.phi_convergent));
    buf.push(serialize_bool(resonance.ring_valid));
    buf.push(serialize_bool(resonance.sequence_monotone));
    buf.push(resonance.resonance_depth);

    // phi_headroom as fixed-point i32 (multiply by 10^6, truncate) — avoids float ambiguity
    let headroom_fixed = (resonance.phi_headroom * 1_000_000.0) as i32;
    buf.extend_from_slice(&headroom_fixed.to_be_bytes());

    // resonance_coefficient as fixed-point i32
    let coeff_fixed = (resonance.resonance_coefficient * 1_000_000.0) as i32;
    buf.extend_from_slice(&coeff_fixed.to_be_bytes());

    // vortex_family: 0=Triadic, 1=Hexadic
    use crate::vortex_classifier::VortexFamily;
    buf.push(match resonance.vortex_family { VortexFamily::Triadic => 0, VortexFamily::Hexadic => 1 });

    // NetworkSnapshot
    buf.push(match network.verdict {
        NetworkVerdict::Unified   => 0,
        NetworkVerdict::Clustered => 1,
        NetworkVerdict::Split     => 2,
    });
    buf.extend_from_slice(&(network.peer_count as u32).to_be_bytes());
    buf.extend_from_slice(&(network.above_phi_count as u32).to_be_bytes());
    buf.push(serialize_bool(network.quorum_triadic));

    // version string — length-prefixed UTF-8
    let version_bytes = version.as_bytes();
    buf.extend_from_slice(&(version_bytes.len() as u16).to_be_bytes());
    buf.extend_from_slice(version_bytes);

    buf
}

// ─── Core function ────────────────────────────────────────────────────────

/// Compute the constitutional self-certificate.
///
/// Deterministic — same inputs → same SelfCertificate every call, on every platform.
pub fn certify_self(
    constitutional_hash: &[u8; 32],
    resonance:           &ResonanceReport,
    network:             &NetworkSnapshot,
    system_version:      &'static str,
) -> SelfCertificate {
    // ── Verdict logic ─────────────────────────────────────────────────────
    let t1_invariants_ok = resonance.phi_convergent && resonance.ring_valid && resonance.sequence_monotone;
    let network_clean    = network.verdict == NetworkVerdict::Unified;
    let no_drift         = network.above_phi_count == 0;

    let verdict = if !t1_invariants_ok || !no_drift {
        CertificationVerdict::Uncertified
    } else if network_clean && resonance.phi_convergent {
        CertificationVerdict::Certified
    } else {
        CertificationVerdict::ProvisionallyGranted
    };

    // ── Self-hash ─────────────────────────────────────────────────────────
    let canonical = build_canonical_bytes(constitutional_hash, resonance, network, system_version);
    let mut hasher = Sha256::new();
    hasher.update(&canonical);
    let hash_out: [u8; 32] = hasher.finalize().into();

    SelfCertificate {
        verdict,
        bound_constitutional_hash: *constitutional_hash,
        resonance_depth:           resonance.resonance_depth,
        resonance_coefficient:     resonance.resonance_coefficient,
        phi_convergent:            resonance.phi_convergent,
        ring_valid:                resonance.ring_valid,
        sequence_monotone:         resonance.sequence_monotone,
        network_verdict:           network.verdict,
        peer_count:                network.peer_count,
        above_phi_count:           network.above_phi_count,
        quorum_triadic:            network.quorum_triadic,
        system_version,
        self_hash:                 hash_out,
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::resonance_monitor::check_resonance;
    use crate::ring_composition::build_ring;
    use crate::chord_network::NetworkVerdict;

    fn hash_seed(v: u8) -> [u8; 32] {
        let mut h = [0u8; 32]; h[31] = v; h
    }

    fn certified_resonance() -> ResonanceReport {
        let ring = build_ring(&[hash_seed(1), hash_seed(2)], None);
        check_resonance(0.1, 1, 4, &ring, 10, Some(9))
    }

    fn uncertified_resonance() -> ResonanceReport {
        // phi_convergent=false (drift_risk=0.9 > phi)
        let ring = build_ring(&[hash_seed(1), hash_seed(2)], None);
        check_resonance(0.9, 1, 4, &ring, 10, Some(9))
    }

    fn unified_network() -> NetworkSnapshot {
        NetworkSnapshot { verdict: NetworkVerdict::Unified, peer_count: 5, above_phi_count: 0, quorum_triadic: true }
    }

    fn split_network() -> NetworkSnapshot {
        NetworkSnapshot { verdict: NetworkVerdict::Split, peer_count: 5, above_phi_count: 2, quorum_triadic: false }
    }

    fn clustered_network() -> NetworkSnapshot {
        NetworkSnapshot { verdict: NetworkVerdict::Clustered, peer_count: 5, above_phi_count: 0, quorum_triadic: true }
    }

    #[test]
    fn certified_when_all_invariants_unified_network() {
        let cert = certify_self(&hash_seed(9), &certified_resonance(), &unified_network(), "1.0.0");
        assert_eq!(cert.verdict, CertificationVerdict::Certified);
        assert!(cert.is_certified());
        assert!(cert.is_sound());
    }

    #[test]
    fn uncertified_when_resonance_fails() {
        let cert = certify_self(&hash_seed(9), &uncertified_resonance(), &unified_network(), "1.0.0");
        assert_eq!(cert.verdict, CertificationVerdict::Uncertified);
        assert!(!cert.is_certified());
        assert!(!cert.is_sound());
    }

    #[test]
    fn uncertified_when_network_split() {
        let cert = certify_self(&hash_seed(9), &certified_resonance(), &split_network(), "1.0.0");
        assert_eq!(cert.verdict, CertificationVerdict::Uncertified);
        assert!(!cert.is_sound());
    }

    #[test]
    fn provisional_when_clustered_network() {
        let cert = certify_self(&hash_seed(9), &certified_resonance(), &clustered_network(), "1.0.0");
        assert_eq!(cert.verdict, CertificationVerdict::ProvisionallyGranted);
        assert!(cert.is_sound());
        assert!(!cert.is_certified());
    }

    #[test]
    fn self_hash_is_32_bytes_nonzero() {
        let cert = certify_self(&hash_seed(9), &certified_resonance(), &unified_network(), "1.0.0");
        assert_ne!(cert.self_hash, [0u8; 32]);
    }

    #[test]
    fn determinism_x3() {
        let r = certified_resonance();
        let n = unified_network();
        let c1 = certify_self(&hash_seed(9), &r, &n, "1.0.0");
        let c2 = certify_self(&hash_seed(9), &r, &n, "1.0.0");
        let c3 = certify_self(&hash_seed(9), &r, &n, "1.0.0");
        assert_eq!(c1.self_hash, c2.self_hash);
        assert_eq!(c2.self_hash, c3.self_hash);
        assert_eq!(c1.verdict, c3.verdict);
    }

    #[test]
    fn different_constitutional_hash_yields_different_self_hash() {
        let r = certified_resonance();
        let n = unified_network();
        let c1 = certify_self(&hash_seed(1), &r, &n, "1.0.0");
        let c2 = certify_self(&hash_seed(2), &r, &n, "1.0.0");
        assert_ne!(c1.self_hash, c2.self_hash);
    }

    #[test]
    fn different_version_yields_different_self_hash() {
        let r = certified_resonance();
        let n = unified_network();
        let c1 = certify_self(&hash_seed(9), &r, &n, "1.0.0");
        let c2 = certify_self(&hash_seed(9), &r, &n, "1.0.1");
        assert_ne!(c1.self_hash, c2.self_hash);
    }

    #[test]
    fn self_hash_sensitive_to_resonance_depth() {
        // Two resonance reports with same phi_convergent but different depth
        // (depth changes because vortex changes)
        let ring1 = build_ring(&[hash_seed(1), hash_seed(2)], None);
        let r_triadic  = check_resonance(0.1, 1, 4, &ring1, 10, Some(9)); // span=3 → Triadic
        let r_hexadic  = check_resonance(0.1, 0, 1, &ring1, 10, Some(9)); // span=1 → Hexadic
        let n = unified_network();
        let c1 = certify_self(&hash_seed(9), &r_triadic, &n, "1.0.0");
        let c2 = certify_self(&hash_seed(9), &r_hexadic, &n, "1.0.0");
        assert_ne!(c1.self_hash, c2.self_hash);
    }

    #[test]
    fn bound_constitutional_hash_preserved() {
        let h = hash_seed(42);
        let cert = certify_self(&h, &certified_resonance(), &unified_network(), "1.0.0");
        assert_eq!(cert.bound_constitutional_hash, h);
    }

    #[test]
    fn resonance_fields_preserved() {
        let r = certified_resonance();
        let cert = certify_self(&hash_seed(9), &r, &unified_network(), "1.0.0");
        assert_eq!(cert.resonance_depth, r.resonance_depth);
        assert_eq!(cert.phi_convergent, r.phi_convergent);
        assert_eq!(cert.ring_valid, r.ring_valid);
        assert_eq!(cert.sequence_monotone, r.sequence_monotone);
    }

    #[test]
    fn network_fields_preserved() {
        let n = unified_network();
        let cert = certify_self(&hash_seed(9), &certified_resonance(), &n, "1.0.0");
        assert_eq!(cert.network_verdict, n.verdict);
        assert_eq!(cert.peer_count, n.peer_count);
        assert_eq!(cert.above_phi_count, n.above_phi_count);
        assert_eq!(cert.quorum_triadic, n.quorum_triadic);
    }

    #[test]
    fn verdict_ordering() {
        assert!(CertificationVerdict::Uncertified < CertificationVerdict::ProvisionallyGranted);
        assert!(CertificationVerdict::ProvisionallyGranted < CertificationVerdict::Certified);
    }

    #[test]
    fn system_version_preserved() {
        let cert = certify_self(&hash_seed(9), &certified_resonance(), &unified_network(), "2.5.0");
        assert_eq!(cert.system_version, "2.5.0");
    }

    #[test]
    fn no_drift_required_for_certified() {
        let n_drift = NetworkSnapshot {
            verdict: NetworkVerdict::Unified, peer_count: 5, above_phi_count: 1, quorum_triadic: true,
        };
        let cert = certify_self(&hash_seed(9), &certified_resonance(), &n_drift, "1.0.0");
        // above_phi_count=1 → above_phi>0 → Uncertified
        assert_eq!(cert.verdict, CertificationVerdict::Uncertified);
    }
}
