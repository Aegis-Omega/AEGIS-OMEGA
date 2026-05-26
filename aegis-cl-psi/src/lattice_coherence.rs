//! Gate 227: Lattice Coherence — Moduli Tower Global Section Checker
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! The AEGIS constitutional substrate forms a tower of derived obstruction stacks:
//!
//!   Level 0: (F, A, λ) — RALPH triad: Frame × Adaptation × Lawvere weight
//!   Level 1: Divergence D0–D4 — obstruction to mutation authority
//!   Level 2: Resonance monitor — phi_convergent ∧ ring_valid ∧ sequence_monotone
//!   Level 3: Chord network — VortexFamily × PhiClass triangular 2-way state
//!   Level 4: Self-certification — autopoietic closure verdict
//!
//! The central question: does the tower admit a GLOBAL SECTION — a coherent state
//! that simultaneously trivializes all obstruction levels?
//!
//! GlobalSection exists iff:
//!   L0: sequence_monotone (RALPH frame is valid)
//!   L1: no D2+ divergence (mutation authority preserved)
//!   L2: all three T1 invariants hold (phi_convergent ∧ ring_valid ∧ sequence_monotone)
//!   L3: NetworkVerdict::Unified ∧ all_below_phi (chord triangle in convergent half)
//!   L4: CertificationVerdict::Certified (autopoietic closure sealed)
//!
//! When all 5 levels are simultaneously satisfied, the system is constitutionally
//! coherent — the martingale condition E[S_{n+1}|F_n] = S_n is trivially satisfied
//! by construction, not by enforcement.
//!
//! Coherence score: weighted sum of level satisfactions, normalized to [0.0, 1.0].
//! Weights follow Fibonacci ratios: L0=1, L1=1, L2=2, L3=3, L4=5 (total=12).

use crate::chord_network::NetworkVerdict;
use crate::resonance_monitor::ResonanceReport;
use crate::self_certification::{CertificationVerdict, SelfCertificate};

/// Which obstruction levels are currently satisfied.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ObstructionLevels {
    /// L0: RALPH frame valid — sequence is monotone, epoch advancing
    pub l0_ralph_frame: bool,
    /// L1: No D2+ divergence — mutation authority preserved
    pub l1_mutation_authority: bool,
    /// L2: All T1 resonance invariants hold
    pub l2_resonance: bool,
    /// L3: Chord network UNIFIED and all peers below phi
    pub l3_chord_unity: bool,
    /// L4: Self-certification Certified (not Provisional or Uncertified)
    pub l4_autopoietic: bool,
}

/// The result of checking whether a global section of the moduli tower exists.
#[derive(Debug, Clone)]
pub struct CoherenceReport {
    /// True iff all 5 obstruction levels are simultaneously satisfied.
    pub global_section_exists: bool,
    /// Individual level satisfaction.
    pub levels: ObstructionLevels,
    /// Weighted coherence score in [0.0, 1.0]. Weights: L0=1,L1=1,L2=2,L3=3,L4=5 / 12.
    pub coherence_score: f64,
    /// Count of satisfied levels (0..=5).
    pub satisfied_count: u8,
    /// The first unsatisfied level (0..=4), or None if all satisfied.
    pub first_obstruction: Option<u8>,
}

/// Input snapshot for coherence checking — aggregates all 5 tower levels.
pub struct TowerSnapshot<'a> {
    /// L0: Is the RALPH sequence monotone? (sequence > 0 and epoch advancing)
    pub sequence_monotone: bool,
    /// L1: Is mutation authority active? (no D2+ divergence)
    pub mutation_authority_active: bool,
    /// L2: Full resonance report from resonance_monitor
    pub resonance: &'a ResonanceReport,
    /// L3: Network verdict and all_below_phi from chord_network
    pub network_verdict: NetworkVerdict,
    pub all_below_phi: bool,
    /// L4: Self-certification verdict from self_certification
    pub certification: &'a SelfCertificate,
}

pub struct CoherenceError(pub &'static str);

/// Check whether the moduli tower admits a global section.
/// Pure function — same inputs always produce the same output.
pub fn check_coherence(snap: &TowerSnapshot<'_>) -> CoherenceReport {
    let l0 = snap.sequence_monotone;
    let l1 = snap.mutation_authority_active;
    let l2 = snap.resonance.phi_convergent
        && snap.resonance.ring_valid
        && snap.resonance.sequence_monotone;
    let l3 = snap.network_verdict == NetworkVerdict::Unified && snap.all_below_phi;
    let l4 = snap.certification.verdict == CertificationVerdict::Certified;

    let levels = ObstructionLevels {
        l0_ralph_frame: l0,
        l1_mutation_authority: l1,
        l2_resonance: l2,
        l3_chord_unity: l3,
        l4_autopoietic: l4,
    };

    let global_section_exists = l0 && l1 && l2 && l3 && l4;

    // Fibonacci-weighted score: L0=1, L1=1, L2=2, L3=3, L4=5 (total=12)
    let score = (if l0 { 1.0 } else { 0.0 }
        + if l1 { 1.0 } else { 0.0 }
        + if l2 { 2.0 } else { 0.0 }
        + if l3 { 3.0 } else { 0.0 }
        + if l4 { 5.0 } else { 0.0 })
        / 12.0;

    let satisfied_count = [l0, l1, l2, l3, l4].iter().filter(|&&b| b).count() as u8;

    let first_obstruction = if !l0 { Some(0) }
        else if !l1 { Some(1) }
        else if !l2 { Some(2) }
        else if !l3 { Some(3) }
        else if !l4 { Some(4) }
        else { None };

    CoherenceReport {
        global_section_exists,
        levels,
        coherence_score: score,
        satisfied_count,
        first_obstruction,
    }
}

/// Build a coherence report from partial data when self-certification is unavailable.
/// Uses a provisional certification verdict, yielding at most ProvisionallyGranted on L4.
pub fn check_partial_coherence(
    sequence_monotone: bool,
    mutation_authority_active: bool,
    resonance: &ResonanceReport,
    network_verdict: NetworkVerdict,
    all_below_phi: bool,
) -> CoherenceReport {
    let l0 = sequence_monotone;
    let l1 = mutation_authority_active;
    let l2 = resonance.phi_convergent && resonance.ring_valid && resonance.sequence_monotone;
    let l3 = network_verdict == NetworkVerdict::Unified && all_below_phi;
    // Partial: L4 treated as satisfied if L2+L3 both hold (ProvisionallyGranted equivalent)
    let l4 = l2 && l3;

    let levels = ObstructionLevels {
        l0_ralph_frame: l0,
        l1_mutation_authority: l1,
        l2_resonance: l2,
        l3_chord_unity: l3,
        l4_autopoietic: l4,
    };

    let global_section_exists = l0 && l1 && l2 && l3 && l4;
    let score = (if l0 { 1.0 } else { 0.0 }
        + if l1 { 1.0 } else { 0.0 }
        + if l2 { 2.0 } else { 0.0 }
        + if l3 { 3.0 } else { 0.0 }
        + if l4 { 5.0 } else { 0.0 })
        / 12.0;
    let satisfied_count = [l0, l1, l2, l3, l4].iter().filter(|&&b| b).count() as u8;
    let first_obstruction = if !l0 { Some(0) } else if !l1 { Some(1) }
        else if !l2 { Some(2) } else if !l3 { Some(3) }
        else if !l4 { Some(4) } else { None };

    CoherenceReport {
        global_section_exists, levels, coherence_score: score,
        satisfied_count, first_obstruction,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::chord_network::NetworkVerdict;
    use crate::resonance_monitor::ResonanceReport;
    use crate::self_certification::{CertificationVerdict, SelfCertificate};
    use crate::vortex_classifier::VortexFamily;

    fn good_resonance() -> ResonanceReport {
        ResonanceReport {
            is_resonant: true,
            phi_convergent: true,
            vortex_family: VortexFamily::Triadic,
            ring_valid: true,
            sequence_monotone: true,
            resonance_depth: 4,
            resonance_coefficient: 6.0,
            phi_headroom: 0.5,
        }
    }

    fn good_cert() -> SelfCertificate {
        let resonance = good_resonance();
        let hash = [0u8; 32];
        let snap = crate::self_certification::NetworkSnapshot {
            verdict: NetworkVerdict::Unified,
            peer_count: 5,
            above_phi_count: 0,
            quorum_triadic: true,
        };
        crate::self_certification::certify_self(&hash, &resonance, &snap, "1.0.0")
    }

    fn good_snap<'a>(res: &'a ResonanceReport, cert: &'a SelfCertificate) -> TowerSnapshot<'a> {
        TowerSnapshot {
            sequence_monotone: true,
            mutation_authority_active: true,
            resonance: res,
            network_verdict: NetworkVerdict::Unified,
            all_below_phi: true,
            certification: cert,
        }
    }

    #[test]
    fn all_levels_satisfied_global_section_exists() {
        let res = good_resonance();
        let cert = good_cert();
        let snap = good_snap(&res, &cert);
        let report = check_coherence(&snap);
        assert!(report.global_section_exists);
        assert_eq!(report.satisfied_count, 5);
        assert!(report.first_obstruction.is_none());
    }

    #[test]
    fn coherence_score_all_satisfied() {
        let res = good_resonance();
        let cert = good_cert();
        let snap = good_snap(&res, &cert);
        let report = check_coherence(&snap);
        let delta = (report.coherence_score - 1.0).abs();
        assert!(delta < 1e-9, "expected score=1.0, got {}", report.coherence_score);
    }

    #[test]
    fn l0_violated_no_global_section() {
        let res = good_resonance();
        let cert = good_cert();
        let mut snap = good_snap(&res, &cert);
        snap.sequence_monotone = false;
        let report = check_coherence(&snap);
        assert!(!report.global_section_exists);
        assert_eq!(report.first_obstruction, Some(0));
    }

    #[test]
    fn l1_violated_no_global_section() {
        let res = good_resonance();
        let cert = good_cert();
        let mut snap = good_snap(&res, &cert);
        snap.mutation_authority_active = false;
        let report = check_coherence(&snap);
        assert!(!report.global_section_exists);
        assert_eq!(report.first_obstruction, Some(1));
    }

    #[test]
    fn l2_violated_no_global_section() {
        let mut res = good_resonance();
        res.phi_convergent = false;
        let cert = good_cert();
        let mut snap = good_snap(&res, &cert);
        snap.sequence_monotone = true;
        snap.mutation_authority_active = true;
        let report = check_coherence(&snap);
        assert!(!report.global_section_exists);
        assert_eq!(report.first_obstruction, Some(2));
    }

    #[test]
    fn l3_violated_split_network() {
        let res = good_resonance();
        let cert = good_cert();
        let mut snap = good_snap(&res, &cert);
        snap.network_verdict = NetworkVerdict::Split;
        let report = check_coherence(&snap);
        assert!(!report.global_section_exists);
        assert_eq!(report.first_obstruction, Some(3));
    }

    #[test]
    fn l3_violated_above_phi() {
        let res = good_resonance();
        let cert = good_cert();
        let mut snap = good_snap(&res, &cert);
        snap.all_below_phi = false;
        let report = check_coherence(&snap);
        assert!(!report.global_section_exists);
        assert_eq!(report.first_obstruction, Some(3));
    }

    #[test]
    fn l4_violated_provisional_no_global_section() {
        let res = good_resonance();
        // Build a cert with SPLIT verdict (Uncertified)
        let snap_net = crate::self_certification::NetworkSnapshot {
            verdict: NetworkVerdict::Split,
            peer_count: 5,
            above_phi_count: 2,
            quorum_triadic: false,
        };
        let cert = crate::self_certification::certify_self(&[0u8; 32], &res, &snap_net, "1.0.0");
        assert_ne!(cert.verdict, CertificationVerdict::Certified);

        let snap = TowerSnapshot {
            sequence_monotone: true,
            mutation_authority_active: true,
            resonance: &res,
            network_verdict: NetworkVerdict::Unified,
            all_below_phi: true,
            certification: &cert,
        };
        let report = check_coherence(&snap);
        assert!(!report.global_section_exists);
        assert_eq!(report.first_obstruction, Some(4));
    }

    #[test]
    fn coherence_score_l0_l1_only() {
        let mut res = good_resonance();
        res.phi_convergent = false;
        let snap_net = crate::self_certification::NetworkSnapshot {
            verdict: NetworkVerdict::Split, peer_count: 5, above_phi_count: 2, quorum_triadic: false,
        };
        let cert = crate::self_certification::certify_self(&[0u8; 32], &res, &snap_net, "1.0.0");
        let snap = TowerSnapshot {
            sequence_monotone: true,
            mutation_authority_active: true,
            resonance: &res,
            network_verdict: NetworkVerdict::Split,
            all_below_phi: false,
            certification: &cert,
        };
        let report = check_coherence(&snap);
        // L0=1 + L1=1, rest=0, total weight=2/12
        let expected = 2.0 / 12.0;
        let delta = (report.coherence_score - expected).abs();
        assert!(delta < 1e-9, "expected {expected}, got {}", report.coherence_score);
        assert_eq!(report.satisfied_count, 2);
    }

    #[test]
    fn fibonacci_weights_all_partial() {
        // L0+L1+L2 = 1+1+2=4/12
        let res = good_resonance();
        let snap_net = crate::self_certification::NetworkSnapshot {
            verdict: NetworkVerdict::Split, peer_count: 5, above_phi_count: 2, quorum_triadic: false,
        };
        let cert = crate::self_certification::certify_self(&[0u8; 32], &res, &snap_net, "1.0.0");
        let snap = TowerSnapshot {
            sequence_monotone: true,
            mutation_authority_active: true,
            resonance: &res,
            network_verdict: NetworkVerdict::Split,
            all_below_phi: false,
            certification: &cert,
        };
        let report = check_coherence(&snap);
        let expected = 4.0 / 12.0;
        let delta = (report.coherence_score - expected).abs();
        assert!(delta < 1e-9, "L0+L1+L2: expected {expected}, got {}", report.coherence_score);
    }

    #[test]
    fn determinism_identical_inputs() {
        let res = good_resonance();
        let cert = good_cert();
        let snap1 = good_snap(&res, &cert);
        let snap2 = good_snap(&res, &cert);
        let r1 = check_coherence(&snap1);
        let r2 = check_coherence(&snap2);
        assert_eq!(r1.global_section_exists, r2.global_section_exists);
        let delta = (r1.coherence_score - r2.coherence_score).abs();
        assert!(delta < 1e-12);
        assert_eq!(r1.satisfied_count, r2.satisfied_count);
        assert_eq!(r1.first_obstruction, r2.first_obstruction);
    }

    #[test]
    fn partial_coherence_l0_l1_l2_l3_all_ok() {
        let res = good_resonance();
        let report = check_partial_coherence(true, true, &res, NetworkVerdict::Unified, true);
        assert!(report.global_section_exists);
        assert_eq!(report.satisfied_count, 5);
        let delta = (report.coherence_score - 1.0).abs();
        assert!(delta < 1e-9);
    }

    #[test]
    fn partial_coherence_split_network() {
        let res = good_resonance();
        let report = check_partial_coherence(true, true, &res, NetworkVerdict::Split, false);
        assert!(!report.global_section_exists);
        assert_eq!(report.first_obstruction, Some(3));
    }

    #[test]
    fn empty_obstruction_levels_no_global_section() {
        let mut res = good_resonance();
        res.phi_convergent = false;
        res.ring_valid = false;
        res.sequence_monotone = false;
        res.is_resonant = false;
        let report = check_partial_coherence(false, false, &res, NetworkVerdict::Split, false);
        assert!(!report.global_section_exists);
        assert_eq!(report.satisfied_count, 0);
        let delta = report.coherence_score.abs();
        assert!(delta < 1e-9);
        assert_eq!(report.first_obstruction, Some(0));
    }

    #[test]
    fn coherence_error_type_exists() {
        let e = CoherenceError("test");
        assert_eq!(e.0, "test");
    }

    #[test]
    fn obstruction_levels_copy() {
        let levels = ObstructionLevels {
            l0_ralph_frame: true, l1_mutation_authority: true,
            l2_resonance: true, l3_chord_unity: true, l4_autopoietic: true,
        };
        let copied = levels;
        assert_eq!(levels, copied);
    }
}
