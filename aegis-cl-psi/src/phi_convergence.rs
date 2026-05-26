//! Gate 221: Constitutional Convergence Certifier
//! EPISTEMIC TIER: T1 (mathematical invariants) / T2 (application)
//!
//! ─── Three scales, one threshold ─────────────────────────────────────────
//!
//! 1/φ ≈ 0.6180339887 (the golden ratio complement) appears at three scales
//! in the constitutional stack. This module certifies the MOLECULAR scale:
//!
//!   SUBATOMIC:  DIVERGENCE_WEIGHT = 0.0025 per DAG edge (lattice_dag.rs)
//!   MOLECULAR:  path.total_divergence_risk() < 1/φ — THIS MODULE
//!   ORGANISM:   swarm quorum ≥ 618034/1000000 (edge_verifier.rs)
//!
//! The same constant governs: DAG path safety, swarm consensus, martingale
//! mutation rate (MUTATION_RATE_LIMIT in sovereign-omega-v2). This is not
//! coincidence — it is the constitutional invariant made explicit.
//!
//! ─── Vortex classification ────────────────────────────────────────────────
//!
//! The rank span of a certified path (RANK(EndNode) - RANK(StartNode)) is
//! classified by its digital root into the 3-6-9 vortex taxonomy:
//!
//!   Triadic  — digital root ∈ {3, 6, 9}: rank span resonates with 9-fold cycle
//!   Hexadic  — digital root ∈ {1, 2, 4, 5, 7, 8}: full 6-cycle period
//!
//! digital_root(9) = 9 (fixed point under doubling: 9→18→9→...)
//! digital_root(3) or digital_root(6): period-2 oscillator (3↔6)
//! Hexadic: period-6 cycle (1→2→4→8→7→5→1→...)
//!
//! ─── Phi-headroom ─────────────────────────────────────────────────────────
//!
//! phi_headroom = (1/φ) - total_divergence_risk
//! Positive headroom = convergent path. Zero or negative = constitutional breach.
//!
//! ─── Constitutional invariants ────────────────────────────────────────────
//! - PHI_THRESHOLD is an f64 constant, never compared via mutable f64 input
//! - No HashMap. No runtime entropy. No Date.now().
//! - ConvergenceCertificate is stack-allocated — zero heap overhead
//! - Certification is pure: same path → same certificate every run
//!
//! AdaptivePower(T) ≤ ReplayVerifiability(T)
//! Copyright (C) 2025 Tarik Skalić — All rights reserved. AGPL-3.0-or-later

use crate::lattice_dag::{Node, PathMetricExt, PathInvariants};
use crate::vortex_classifier::{digital_root, VortexFamily, classify_vortex};

// ─── Constitutional constant ──────────────────────────────────────────────

/// 1/φ = (√5 − 1) / 2 ≈ 0.6180339887498948
/// The golden ratio complement — constitutional threshold at all three scales.
/// Same value as DEFAULT_QUORUM_THRESHOLD (swarm.ts) and MUTATION_RATE_LIMIT (martingale.ts).
pub const PHI_THRESHOLD: f64 = 0.6180339887498948;

// ─── Vortex classification for rank spans ────────────────────────────────

/// Rank span of a certified path: RANK(End) − RANK(Start).
/// Classified by digital root into the 3-6-9 constitutional taxonomy.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RankSpan {
    pub value: u64,
    pub digital_root: u8,    // 1..9 — never 0
    pub vortex_family: VortexFamily,
}

impl RankSpan {
    pub fn compute(start_rank: usize, end_rank: usize) -> Option<Self> {
        if end_rank <= start_rank { return None; }
        let value = (end_rank - start_rank) as u64;
        let dr = digital_root(value);
        Some(Self {
            value,
            digital_root: dr,
            vortex_family: classify_vortex(value),
        })
    }
}

// ─── Convergence certificate ─────────────────────────────────────────────

/// The result of certifying a DAG path against the 1/φ constitutional threshold.
///
/// A certificate is CONVERGENT iff `phi_headroom > 0.0`.
/// A certificate is TRIADIC iff the rank span's digital root ∈ {3, 6, 9}.
///
/// Constitutional proof encoded in the certificate:
///   total_divergence_risk < PHI_THRESHOLD  →  AdaptivePower ≤ ReplayVerifiability
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct ConvergenceCertificate {
    /// Accumulated Lawvere divergence over all path hops.
    pub total_divergence_risk: f64,
    /// `true` iff total_divergence_risk < PHI_THRESHOLD (1/φ ≈ 0.6180).
    pub is_convergent: bool,
    /// Headroom below the threshold: (1/φ) − total_divergence_risk.
    /// Positive = safe. Zero or negative = constitutional breach.
    pub phi_headroom: f64,
    /// Rank span from StartNode to EndNode.
    pub rank_span: RankSpan,
    /// Number of hops in the path.
    pub hop_count: usize,
    /// Maximum additional hops before breaching 1/φ (floor division).
    /// Computed as floor(phi_headroom / DIVERGENCE_WEIGHT).
    /// Constitutional planning signal: how many more edges can be safely added.
    pub safe_hop_margin: u64,
}

impl ConvergenceCertificate {
    /// Headroom is positive iff the path is convergent.
    pub fn is_triadic(&self) -> bool {
        self.rank_span.vortex_family == VortexFamily::Triadic
    }

    /// True if the rank span is a fixed point under doubling (digital_root = 9).
    pub fn is_fixed_point(&self) -> bool {
        self.rank_span.digital_root == 9
    }

    /// True if the rank span oscillates in the {3, 6} pair.
    pub fn is_oscillator(&self) -> bool {
        self.rank_span.digital_root == 3 || self.rank_span.digital_root == 6
    }
}

// ─── Certify function ─────────────────────────────────────────────────────

pub struct CertificationError(pub &'static str);

impl std::fmt::Debug for CertificationError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.0)
    }
}

/// Certify a DAG path against the 1/φ constitutional convergence threshold.
///
/// Returns `Err` if the rank span is invalid (EndNode::RANK ≤ StartNode::RANK —
/// which cannot happen for a valid VerifiedEdge chain, but is checked defensively).
///
/// # Type parameters
/// - `P`: A type implementing `PathInvariants + PathMetricExt`
/// - `hop_count`: Number of hops in the path (cannot be derived from types alone)
pub fn certify_path<P>(hop_count: usize) -> Result<ConvergenceCertificate, CertificationError>
where
    P: PathInvariants + PathMetricExt,
{
    let start_rank = P::StartNode::RANK;
    let end_rank = P::EndNode::RANK;

    let rank_span = RankSpan::compute(start_rank, end_rank)
        .ok_or(CertificationError("[PHI_CONVERGENCE] Invalid rank span — EndNode::RANK must exceed StartNode::RANK"))?;

    let total_divergence_risk = P::total_divergence_risk();
    let phi_headroom = PHI_THRESHOLD - total_divergence_risk;
    let is_convergent = phi_headroom > 0.0;

    // floor(headroom / 0.0025) — integer safe_hop_margin
    // 0.0025 = 1/400; multiply by 400 then floor
    let safe_hop_margin = if phi_headroom > 0.0 {
        (phi_headroom * 400.0).floor() as u64
    } else {
        0
    };

    Ok(ConvergenceCertificate {
        total_divergence_risk,
        is_convergent,
        phi_headroom,
        rank_span,
        hop_count,
        safe_hop_margin,
    })
}

/// Certify a raw divergence risk value (for paths computed at runtime, not via type params).
///
/// Useful when the path shape is not statically known (e.g., deserialized from SPSF records).
/// The rank_span is provided explicitly.
pub fn certify_risk(
    total_divergence_risk: f64,
    hop_count: usize,
    start_rank: usize,
    end_rank: usize,
) -> Result<ConvergenceCertificate, CertificationError> {
    let rank_span = RankSpan::compute(start_rank, end_rank)
        .ok_or(CertificationError("[PHI_CONVERGENCE] Invalid rank span"))?;

    let phi_headroom = PHI_THRESHOLD - total_divergence_risk;
    let is_convergent = phi_headroom > 0.0;
    let safe_hop_margin = if phi_headroom > 0.0 {
        (phi_headroom * 400.0).floor() as u64
    } else {
        0
    };

    Ok(ConvergenceCertificate {
        total_divergence_risk,
        is_convergent,
        phi_headroom,
        rank_span,
        hop_count,
        safe_hop_margin,
    })
}

// ─── Tests ────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::lattice_dag::{BaseStep, ConsStep, VerifiedEdge};

    // ─── Test nodes ───────────────────────────────────────────────────────

    #[derive(Clone, PartialEq, Debug)] struct S(u8);

    struct N1; impl Node for N1 { const RANK: usize = 1; type State = S; }
    struct N2; impl Node for N2 { const RANK: usize = 2; type State = S; }
    struct N3; impl Node for N3 { const RANK: usize = 3; type State = S; }
    struct N4; impl Node for N4 { const RANK: usize = 4; type State = S; }
    struct N9; impl Node for N9 { const RANK: usize = 9; type State = S; }
    struct N10; impl Node for N10 { const RANK: usize = 10; type State = S; }
    struct N13; impl Node for N13 { const RANK: usize = 13; type State = S; } // rank span 12 → digital_root=3
    struct N19; impl Node for N19 { const RANK: usize = 19; type State = S; } // rank span 18 → digital_root=9

    // ─── PHI_THRESHOLD constant ───────────────────────────────────────────

    #[test]
    fn phi_threshold_is_golden_ratio_complement() {
        // 1/φ = (√5 − 1) / 2
        let expected = (5.0_f64.sqrt() - 1.0) / 2.0;
        assert!((PHI_THRESHOLD - expected).abs() < 1e-14);
    }

    #[test]
    fn phi_threshold_approx_0618() {
        assert!(PHI_THRESHOLD > 0.618);
        assert!(PHI_THRESHOLD < 0.619);
    }

    // ─── RankSpan ─────────────────────────────────────────────────────────

    #[test]
    fn rank_span_single_hop_rank1_to_rank2() {
        let rs = RankSpan::compute(1, 2).unwrap();
        assert_eq!(rs.value, 1);
        assert_eq!(rs.digital_root, 1);
        assert_eq!(rs.vortex_family, VortexFamily::Hexadic);
    }

    #[test]
    fn rank_span_digital_root_9_is_triadic_fixed_point() {
        // Rank span of 9: digital_root(9)=9, Triadic
        let rs = RankSpan::compute(1, 10).unwrap();
        assert_eq!(rs.value, 9);
        assert_eq!(rs.digital_root, 9);
        assert_eq!(rs.vortex_family, VortexFamily::Triadic);
    }

    #[test]
    fn rank_span_digital_root_3_is_triadic_oscillator() {
        // Rank span of 12: digital_root(12)=3, Triadic oscillator
        let rs = RankSpan::compute(1, 13).unwrap();
        assert_eq!(rs.value, 12);
        assert_eq!(rs.digital_root, 3);
        assert_eq!(rs.vortex_family, VortexFamily::Triadic);
    }

    #[test]
    fn rank_span_invalid_returns_none() {
        assert!(RankSpan::compute(5, 5).is_none()); // equal
        assert!(RankSpan::compute(5, 3).is_none()); // reversed
    }

    // ─── certify_path — static type-level certification ──────────────────

    #[test]
    fn single_hop_is_convergent() {
        type P = BaseStep<N1, N2>;
        let cert = certify_path::<P>(1).unwrap();
        assert!(cert.is_convergent);
        assert!((cert.total_divergence_risk - 0.0025).abs() < 1e-12);
        assert!(cert.phi_headroom > 0.6);
    }

    #[test]
    fn two_hop_is_convergent() {
        type P = ConsStep<N1, N2, BaseStep<N2, N3>>;
        let cert = certify_path::<P>(2).unwrap();
        assert!(cert.is_convergent);
        assert!((cert.total_divergence_risk - 0.005).abs() < 1e-12);
    }

    #[test]
    fn three_hop_is_convergent() {
        type P = ConsStep<N1, N2, ConsStep<N2, N3, BaseStep<N3, N4>>>;
        let cert = certify_path::<P>(3).unwrap();
        assert!(cert.is_convergent);
        assert!((cert.total_divergence_risk - 0.0075).abs() < 1e-12);
    }

    #[test]
    fn safe_hop_margin_is_large_for_few_hops() {
        type P = BaseStep<N1, N2>;
        let cert = certify_path::<P>(1).unwrap();
        // 1 hop = 0.0025 risk; headroom ≈ 0.6155; safe_margin = floor(0.6155*400) = 246
        assert!(cert.safe_hop_margin >= 246);
    }

    #[test]
    fn safe_hop_margin_at_three_hops() {
        type P = ConsStep<N1, N2, ConsStep<N2, N3, BaseStep<N3, N4>>>;
        let cert = certify_path::<P>(3).unwrap();
        // headroom = 0.6180339887 - 0.0075 = 0.6105339887; floor(0.6105*400)=244
        assert_eq!(cert.safe_hop_margin, 244);
    }

    #[test]
    fn hop_count_is_preserved() {
        type P = ConsStep<N1, N2, BaseStep<N2, N3>>;
        let cert = certify_path::<P>(2).unwrap();
        assert_eq!(cert.hop_count, 2);
    }

    #[test]
    fn rank_span_preserved_in_certificate() {
        type P = BaseStep<N1, N10>;
        let cert = certify_path::<P>(1).unwrap();
        assert_eq!(cert.rank_span.value, 9); // RANK(N10) - RANK(N1) = 10 - 1 = 9
        assert_eq!(cert.rank_span.digital_root, 9);
        assert!(cert.is_fixed_point());
    }

    #[test]
    fn triadic_classification_for_span_9() {
        type P = BaseStep<N1, N10>; // rank span 9 — triadic fixed point
        let cert = certify_path::<P>(1).unwrap();
        assert!(cert.is_triadic());
        assert!(cert.is_fixed_point());
        assert!(!cert.is_oscillator());
    }

    #[test]
    fn triadic_classification_for_span_12() {
        type P = BaseStep<N1, N13>; // rank span 12 → digital_root=3 — oscillator
        let cert = certify_path::<P>(1).unwrap();
        assert!(cert.is_triadic());
        assert!(cert.is_oscillator());
        assert!(!cert.is_fixed_point());
    }

    // ─── certify_risk — runtime certification ────────────────────────────

    #[test]
    fn certify_risk_below_threshold_is_convergent() {
        let cert = certify_risk(0.3, 120, 1, 10).unwrap();
        assert!(cert.is_convergent);
        assert!((cert.phi_headroom - (PHI_THRESHOLD - 0.3)).abs() < 1e-12);
    }

    #[test]
    fn certify_risk_above_threshold_is_not_convergent() {
        let cert = certify_risk(0.7, 280, 1, 10).unwrap();
        assert!(!cert.is_convergent);
        assert!(cert.phi_headroom < 0.0);
        assert_eq!(cert.safe_hop_margin, 0);
    }

    #[test]
    fn certify_risk_exactly_at_threshold_is_not_convergent() {
        // phi_headroom = 0.0 → not strictly positive → not convergent
        let cert = certify_risk(PHI_THRESHOLD, 247, 1, 10).unwrap();
        assert!(!cert.is_convergent);
        assert!(cert.phi_headroom.abs() < 1e-12);
    }

    #[test]
    fn certify_risk_invalid_rank_span_returns_err() {
        assert!(certify_risk(0.1, 1, 5, 5).is_err());
        assert!(certify_risk(0.1, 1, 5, 3).is_err());
    }

    // ─── Holonic triad proof ──────────────────────────────────────────────

    #[test]
    fn phi_threshold_matches_swarm_integer_ratio() {
        // edge_verifier.rs uses: valid * 1_000_000 >= total * 618_034
        // 618034/1000000 = 0.618034 which is slightly ABOVE 1/φ ≈ 0.6180339887...
        // The integer approximation is a conservative bound: requires marginally more
        // than 1/φ for quorum to pass. This preserves the holonic constant at all scales.
        let integer_approx = 618_034.0_f64 / 1_000_000.0;
        // PHI_THRESHOLD is the true 1/φ; the approximation is within 1 ULP at 6th decimal
        assert!((PHI_THRESHOLD - integer_approx).abs() < 1e-5);
        // The approximation rounds UP — conservative, not permissive
        assert!(integer_approx > PHI_THRESHOLD);
    }

    #[test]
    fn divergence_weight_times_247_stays_below_phi() {
        // floor(PHI_THRESHOLD / 0.0025) = floor(247.21...) = 247 hops safely fit
        let max_hops = (PHI_THRESHOLD / 0.0025).floor() as u64;
        assert_eq!(max_hops, 247);
        let risk_247 = 247.0 * 0.0025;
        assert!(risk_247 < PHI_THRESHOLD);
    }

    #[test]
    fn divergence_weight_times_248_breaches_phi() {
        // 248 hops = 0.620 > 0.6180 — constitutional breach
        let risk_248 = 248.0 * 0.0025;
        assert!(risk_248 > PHI_THRESHOLD);
    }

    // ─── Determinism ──────────────────────────────────────────────────────

    #[test]
    fn certification_is_deterministic_three_times() {
        type P = ConsStep<N1, N2, ConsStep<N2, N3, BaseStep<N3, N9>>>;
        let c1 = certify_path::<P>(3).unwrap();
        let c2 = certify_path::<P>(3).unwrap();
        let c3 = certify_path::<P>(3).unwrap();
        assert_eq!(c1.total_divergence_risk.to_bits(), c2.total_divergence_risk.to_bits());
        assert_eq!(c2.total_divergence_risk.to_bits(), c3.total_divergence_risk.to_bits());
        assert_eq!(c1.safe_hop_margin, c2.safe_hop_margin);
        assert_eq!(c2.safe_hop_margin, c3.safe_hop_margin);
    }

    #[test]
    fn rank_span_digital_root_18_is_9_triadic() {
        // Rank span 18: digital_root(18) = 9 (because 1+8=9)
        let rs = RankSpan::compute(1, 19).unwrap();
        assert_eq!(rs.value, 18);
        assert_eq!(rs.digital_root, 9);
        assert_eq!(rs.vortex_family, VortexFamily::Triadic);
    }
}
