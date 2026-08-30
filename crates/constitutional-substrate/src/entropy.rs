// Constitutional Substrate — Entropy Boundary Primitives
// EPISTEMIC TIER: T0
// ONTOLOGY TERM: Entropy
//
// EntropyVector stores pre-computed Q16.16 Shannon entropy values and enforces
// threshold bounds. Entropy computation occurs in the Python hardware_config.py
// layer (shannon_entropy_fixed). The substrate stores, validates, and enforces.
//
// No floating-point arithmetic. All entropy values in Q16.16 fixed-point.

use crate::primitives::{fixed_div, FIXED_SCALE};

// ─── EntropyVector ────────────────────────────────────────────────────────────

/// A bounded Shannon entropy measurement in Q16.16 fixed-point.
///
/// The `value_fixed` field holds H(P) = -Σ p_i log2(p_i) in Q16.16.
/// For a uniform distribution over N outcomes, max entropy = log2(N) * 65536.
/// The `threshold_fixed` is the maximum constitutional entropy — exceeding it
/// indicates a degradation in calibration quality that requires operator attention.
///
/// INVARIANT: value_fixed >= 0 (entropy is non-negative)
/// INVARIANT: dimensions >= 2 (degenerate single-outcome distributions are excluded)
///
/// Wire format (24 bytes, LE):
///   [0..8]   value_fixed: i64 LE Q16.16
///   [8..16]  threshold_fixed: i64 LE Q16.16
///   [16..20] dimensions: u32 LE
///   [20..24] reserved: [0u8; 4]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct EntropyVector {
    pub value_fixed: i64,
    pub threshold_fixed: i64,
    pub dimensions: u32,
}

impl EntropyVector {
    pub fn new(value_fixed: i64, threshold_fixed: i64, dimensions: u32) -> Self {
        assert!(value_fixed >= 0, "EntropyVector: negative entropy — invariant-breach");
        assert!(dimensions >= 2, "EntropyVector: degenerate distribution (dimensions < 2)");
        Self { value_fixed, threshold_fixed, dimensions }
    }

    /// True if entropy exceeds the constitutional threshold — requires operator intervention.
    pub fn exceeds_threshold(&self) -> bool {
        self.value_fixed > self.threshold_fixed
    }

    /// Entropy headroom: (threshold - value) / threshold in Q16.16.
    /// 0 = at threshold, positive = below threshold, negative = exceeded.
    /// Returns 0 if threshold is 0 (degenerate).
    pub fn headroom_ratio_fixed(&self) -> i64 {
        if self.threshold_fixed == 0 {
            return 0;
        }
        let numerator = (self.threshold_fixed - self.value_fixed) * FIXED_SCALE;
        numerator / self.threshold_fixed
    }

    /// Normalised entropy in Q16.16: value / threshold.
    /// 1.0 (= FIXED_SCALE) means at threshold. > 1.0 means exceeded.
    pub fn normalised_fixed(&self) -> i64 {
        if self.threshold_fixed == 0 {
            return 0;
        }
        fixed_div(self.value_fixed, self.threshold_fixed)
    }

    /// Serialise to 24-byte canonical wire format.
    pub fn to_bytes(self) -> [u8; 24] {
        let mut out = [0u8; 24];
        out[0..8].copy_from_slice(&self.value_fixed.to_le_bytes());
        out[8..16].copy_from_slice(&self.threshold_fixed.to_le_bytes());
        out[16..20].copy_from_slice(&self.dimensions.to_le_bytes());
        // [20..24] reserved zeros
        out
    }

    /// Deserialise from 24-byte canonical wire format.
    pub fn from_bytes(b: &[u8; 24]) -> Option<Self> {
        let value_fixed = i64::from_le_bytes(b[0..8].try_into().ok()?);
        let threshold_fixed = i64::from_le_bytes(b[8..16].try_into().ok()?);
        let dimensions = u32::from_le_bytes(b[16..20].try_into().ok()?);
        if value_fixed < 0 || dimensions < 2 {
            return None;
        }
        Some(Self { value_fixed, threshold_fixed, dimensions })
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::primitives::FIXED_SCALE;

    #[test]
    fn entropy_below_threshold_passes() {
        // value = 0.79 * 65536 ≈ 51814, threshold = 1.0 * 65536 = 65536
        let ev = EntropyVector::new(51_814, FIXED_SCALE, 4);
        assert!(!ev.exceeds_threshold());
    }

    #[test]
    fn entropy_at_threshold_does_not_exceed() {
        let ev = EntropyVector::new(FIXED_SCALE, FIXED_SCALE, 4);
        assert!(!ev.exceeds_threshold());
    }

    #[test]
    fn entropy_above_threshold_exceeds() {
        // value slightly > threshold
        let ev = EntropyVector::new(FIXED_SCALE + 1, FIXED_SCALE, 4);
        assert!(ev.exceeds_threshold());
    }

    #[test]
    fn entropy_zero_value_is_valid() {
        let ev = EntropyVector::new(0, FIXED_SCALE, 2);
        assert!(!ev.exceeds_threshold());
    }

    #[test]
    fn entropy_normalised_at_half_threshold() {
        // value = 0.5, threshold = 1.0 → normalised = 0.5 in Q16.16
        let ev = EntropyVector::new(FIXED_SCALE / 2, FIXED_SCALE, 2);
        let norm = ev.normalised_fixed();
        // Should be FIXED_SCALE / 2 = 32768
        assert_eq!(norm, FIXED_SCALE / 2);
    }

    #[test]
    fn entropy_serialization_roundtrip() {
        let ev = EntropyVector::new(51_814, FIXED_SCALE, 4);
        let bytes = ev.to_bytes();
        let recovered = EntropyVector::from_bytes(&bytes).unwrap();
        assert_eq!(ev, recovered);
    }

    #[test]
    fn entropy_serialization_stability() {
        let ev = EntropyVector::new(32_768, 65_536, 8);
        assert_eq!(ev.to_bytes(), ev.to_bytes());
    }

    #[test]
    fn entropy_invalid_from_bytes_rejected() {
        // Negative value_fixed should be rejected
        let mut bytes = EntropyVector::new(1000, 65536, 2).to_bytes();
        // Overwrite value_fixed with -1 in LE
        bytes[0..8].copy_from_slice(&(-1i64).to_le_bytes());
        assert!(EntropyVector::from_bytes(&bytes).is_none());
    }

    #[test]
    #[should_panic(expected = "degenerate distribution")]
    fn entropy_panics_on_single_dimension() {
        EntropyVector::new(0, FIXED_SCALE, 1);
    }

    #[test]
    fn headroom_positive_when_below_threshold() {
        let ev = EntropyVector::new(32_768, 65_536, 2); // at 50% of threshold
        let headroom = ev.headroom_ratio_fixed();
        assert!(headroom > 0);
    }

    #[test]
    fn headroom_negative_when_exceeds_threshold() {
        let ev = EntropyVector::new(70_000, 65_536, 2);
        let headroom = ev.headroom_ratio_fixed();
        assert!(headroom < 0);
    }
}
