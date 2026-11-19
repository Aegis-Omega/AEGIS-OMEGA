//! GCCE Core: Geometric Calligraphic Cognition Engine
//!
//! EPISTEMIC TIER: T0 (Nuqta/Alif) | T1 (Rasm) | T2 (Tashkeel/Tanasub)
//! Constitutional root: Khatt Loop Protocol
//!
//! # Five Dimensions of Calligraphic Cognition
//!
//! 1. `nuqta`    — Atomic truth unit (D₀): H(x) = S_genesis
//! 2. `alif`     — Primary causal axis (D₁): Hard constraint invariant
//! 3. `rasm`     — Continuous causal flow (D₂): Smooth manifold traversal
//! 4. `tashkeel` — Epistemic metadata (D₃): Uncertainty gradient ∇T
//! 5. `tanasub`  — Proportional scaling (D₄+): Golden Ratio φ fractal replication
//!
//! # The Khatt Loop Protocol
//!
//! 1. Inscribe the Nuqta   → Verify atomic truth anchor
//! 2. Raise the Alif       → Establish non-negotiable constraints
//! 3. Weave the Rasm       → Generate continuous interconnected graph
//! 4. Apply the Tashkeel   → Overlay uncertainty metadata
//! 5. Balance the Tanasub  → Ensure fractal scalability
//!
//! # Output Function
//!
//! O(N, A, R, T) = ∫[t₀→tₙ] (dR/dt · A) dt + ∇T
//!
//! Where:
//! - N anchors starting state
//! - A provides rigid vertical constraint
//! - dR/dt is velocity of causal flow
//! - ∇T is gradient of uncertainty

pub mod nuqta;
pub mod alif;
pub mod rasm;
pub mod tashkeel;
pub mod tanasub;

pub use nuqta::Nuqta;
pub use alif::{Alif, Constraint, ConstraintViolation};
pub use rasm::{RasmNode, CausalManifold, SmoothPath};
pub use tashkeel::{TashkeelLayer, Confidence, RiskLevel};
pub use tanasub::{FractalScaler, GOLDEN_RATIO, ResourceAllocation};

/// GCCE Protocol Magic Number (matches AEGIS protocol)
pub const GCCE_PROTOCOL_MAGIC: u16 = 0xE0E0;

/// Khatt Loop Phase Identifier
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum KhattPhase {
    NuqtaInscribe = 0x01,
    AlifRaise = 0x02,
    RasmWeave = 0x03,
    TashkeelApply = 0x04,
    TanasubBalance = 0x05,
}

impl KhattPhase {
    pub fn next(&self) -> Option<KhattPhase> {
        match self {
            KhattPhase::NuqtaInscribe => Some(KhattPhase::AlifRaise),
            KhattPhase::AlifRaise => Some(KhattPhase::RasmWeave),
            KhattPhase::RasmWeave => Some(KhattPhase::TashkeelApply),
            KhattPhase::TashkeelApply => Some(KhattPhase::TanasubBalance),
            KhattPhase::TanasubBalance => None, // Loop complete
        }
    }
}

/// Complete Khatt Loop Execution State
pub struct KhattState {
    pub current_phase: KhattPhase,
    pub nuqta_verified: bool,
    pub alif_constraints: Vec<Constraint>,
    pub rasm_nodes: usize,
    pub tashkeel_confidence: Option<f64>,
    pub tanasub_scale_factor: f64,
}

impl KhattState {
    pub fn new() -> Self {
        Self {
            current_phase: KhattPhase::NuqtaInscribe,
            nuqta_verified: false,
            alif_constraints: Vec::new(),
            rasm_nodes: 0,
            tashkeel_confidence: None,
            tanasub_scale_factor: 1.0,
        }
    }

    pub fn advance(&mut self) -> Result<KhattPhase, &'static str> {
        if let Some(next) = self.current_phase.next() {
            self.current_phase = next;
            Ok(next)
        } else {
            Err("Khatt Loop complete")
        }
    }

    pub fn is_complete(&self) -> bool {
        self.current_phase == KhattPhase::TanasubBalance && self.tashkeel_confidence.is_some()
    }
}

impl Default for KhattState {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_khatt_phase_sequence() {
        let mut state = KhattState::new();
        assert_eq!(state.current_phase, KhattPhase::NuqtaInscribe);

        state.advance().unwrap();
        assert_eq!(state.current_phase, KhattPhase::AlifRaise);

        state.advance().unwrap();
        assert_eq!(state.current_phase, KhattPhase::RasmWeave);

        state.advance().unwrap();
        assert_eq!(state.current_phase, KhattPhase::TashkeelApply);

        state.advance().unwrap();
        assert_eq!(state.current_phase, KhattPhase::TanasubBalance);

        assert!(state.advance().is_err());
    }

    #[test]
    fn test_golden_ratio_constant() {
        // Verify golden ratio precision
        let phi = GOLDEN_RATIO;
        assert!((phi - 1.618033988749895).abs() < 1e-15);
        // Golden ratio property: φ² = φ + 1
        assert!((phi * phi - (phi + 1.0)).abs() < 1e-14);
    }
}
