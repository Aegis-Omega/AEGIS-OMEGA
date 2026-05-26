//! Gate 211: Orthogonal Domain Verifier
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//! Constitutional root: D0 ∩ D1 = ∅ enforced via dot-product orthogonality check
//!
//! Two state vectors are orthogonal iff their dot product is zero.
//! Any non-zero dot product signals D0 (immutable core) contamination by D1 (mutable overlay).
//! Threshold: |dot(C, O)| < epsilon, where epsilon = 1e-9 (floating-point tolerance).

/// Returned when the D0/D1 orthogonality invariant is violated.
#[derive(Debug, Clone, PartialEq)]
pub struct EpistemicViolation {
    pub kind: ViolationKind,
    pub dot_product: f64,
}

#[derive(Debug, Clone, PartialEq)]
pub enum ViolationKind {
    /// |dot(C, O)| >= epsilon: immutable core contaminated by mutable overlay.
    DomainCorruption,
    /// Vectors have different lengths; comparison is undefined.
    DimensionMismatch,
}

impl std::fmt::Display for EpistemicViolation {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self.kind {
            ViolationKind::DomainCorruption => write!(
                f,
                "[DOMAIN_VIOLATION] dot(C, O) = {:.2e} — D0 contaminated by D1",
                self.dot_product
            ),
            ViolationKind::DimensionMismatch => write!(
                f,
                "[DOMAIN_VIOLATION] dimension mismatch — vectors must be equal length"
            ),
        }
    }
}

/// Epsilon for floating-point orthogonality tolerance.
pub const ORTHOGONALITY_EPSILON: f64 = 1e-9;

/// Verifies that two state vectors are orthogonal (dot product ≈ 0).
///
/// Returns Ok(()) if |Σ Cᵢ·Oᵢ| < epsilon, else Err(EpistemicViolation::DomainCorruption).
pub fn verify_orthogonal(
    core_vector: &[f64],
    overlay_vector: &[f64],
) -> Result<(), EpistemicViolation> {
    if core_vector.len() != overlay_vector.len() {
        return Err(EpistemicViolation {
            kind: ViolationKind::DimensionMismatch,
            dot_product: 0.0,
        });
    }

    let dot: f64 = core_vector
        .iter()
        .zip(overlay_vector.iter())
        .map(|(c, o)| c * o)
        .sum();

    if dot.abs() >= ORTHOGONALITY_EPSILON {
        return Err(EpistemicViolation {
            kind: ViolationKind::DomainCorruption,
            dot_product: dot,
        });
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_orthogonal_vectors_pass() {
        // [1, 0] · [0, 1] = 0 → valid
        assert!(verify_orthogonal(&[1.0, 0.0], &[0.0, 1.0]).is_ok());
    }

    #[test]
    fn test_parallel_vectors_fail() {
        // [1, 0] · [1, 0] = 1 → DomainCorruption
        let result = verify_orthogonal(&[1.0, 0.0], &[1.0, 0.0]);
        assert!(result.is_err());
        assert_eq!(result.unwrap_err().kind, ViolationKind::DomainCorruption);
    }

    #[test]
    fn test_zero_vector_is_orthogonal_to_all() {
        // [0, 0] · [5, 3] = 0 → valid (zero vector)
        assert!(verify_orthogonal(&[0.0, 0.0], &[5.0, 3.0]).is_ok());
    }

    #[test]
    fn test_dimension_mismatch_rejected() {
        let result = verify_orthogonal(&[1.0, 0.0], &[0.0, 1.0, 0.0]);
        assert_eq!(result.unwrap_err().kind, ViolationKind::DimensionMismatch);
    }

    #[test]
    fn test_near_zero_dot_product_passes() {
        // Within epsilon tolerance
        let result = verify_orthogonal(&[1.0, 0.0], &[1e-10, 1.0]);
        assert!(result.is_ok());
    }

    #[test]
    fn test_violation_message_contains_value() {
        let err = verify_orthogonal(&[1.0, 0.0], &[1.0, 0.0]).unwrap_err();
        let msg = err.to_string();
        assert!(msg.contains("D0 contaminated by D1"));
        assert!((err.dot_product - 1.0).abs() < 1e-9);
    }

    #[test]
    fn test_high_dimensional_orthogonal() {
        // Standard basis vectors in R^4
        let e1 = vec![1.0, 0.0, 0.0, 0.0];
        let e2 = vec![0.0, 1.0, 0.0, 0.0];
        assert!(verify_orthogonal(&e1, &e2).is_ok());
    }

    #[test]
    fn test_high_dimensional_non_orthogonal() {
        let a = vec![1.0, 1.0, 0.0, 0.0];
        let b = vec![1.0, 0.0, 1.0, 0.0];
        // dot = 1.0
        let result = verify_orthogonal(&a, &b);
        assert_eq!(result.unwrap_err().kind, ViolationKind::DomainCorruption);
    }
}
