//! Gate 214: Vortex Sequence Classifier
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//! Digital root cycle detection and family classification.
//!
//! Empirically verified cycle structure:
//!   Triadic {3,6,9}: under repeated triadic addition, cycle is 3→6→9→3 (period 3)
//!   Hexadic {1,2,4,5,7,8}: under doubling, cycle is 1→2→4→8→7→5→1 (period 6)
//!   9 is fixed point under doubling (18 → digital_root=9)
//!
//! T0 constants: TRIADIC_SUM=18, HEXADIC_SUM=27, TRIADIC_SUM+HEXADIC_SUM=45=Σi(i=1..9)

pub const TRIADIC_MEMBERS: [u8; 3] = [3, 6, 9];
pub const TRIADIC_SUM: u64 = 18;
pub const HEXADIC_SUM: u64 = 27;
pub const ALL_DR_SUM: u64 = 45;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum VortexFamily {
    Triadic,
    Hexadic,
}

pub fn digital_root(n: u64) -> u8 {
    if n == 0 {
        return 9;
    }
    let r = (n % 9) as u8;
    if r == 0 { 9 } else { r }
}

pub fn classify_vortex(n: u64) -> VortexFamily {
    let root = digital_root(n);
    if TRIADIC_MEMBERS.contains(&root) {
        VortexFamily::Triadic
    } else {
        VortexFamily::Hexadic
    }
}

pub fn is_sequence_stable(seq: &[u64]) -> bool {
    if seq.is_empty() {
        return true;
    }
    let first_family = classify_vortex(seq[0]);
    seq.iter().all(|&n| classify_vortex(n) == first_family)
}

pub fn vortex_cycle_length(start: u64) -> Option<u8> {
    if start == 0 {
        return None;
    }
    match classify_vortex(start) {
        VortexFamily::Triadic => Some(3),
        VortexFamily::Hexadic => Some(6),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_digital_root_convention() {
        assert_eq!(digital_root(0), 9);
    }

    #[test]
    fn test_digital_root_values() {
        assert_eq!(digital_root(18), 9);
        assert_eq!(digital_root(204), 6);
        assert_eq!(digital_root(1), 1);
        assert_eq!(digital_root(114), 6);
        assert_eq!(digital_root(30), 3);
    }

    #[test]
    fn test_classification() {
        assert_eq!(classify_vortex(3), VortexFamily::Triadic);
        assert_eq!(classify_vortex(9), VortexFamily::Triadic);
        assert_eq!(classify_vortex(18), VortexFamily::Triadic);
        assert_eq!(classify_vortex(1), VortexFamily::Hexadic);
        assert_eq!(classify_vortex(5), VortexFamily::Hexadic);
    }

    #[test]
    fn test_sequence_stability() {
        assert!(is_sequence_stable(&[3, 6, 9, 12, 18]));
        assert!(!is_sequence_stable(&[3, 6, 1]));
        assert!(is_sequence_stable(&[]));
    }

    #[test]
    fn test_cycle_lengths() {
        assert_eq!(vortex_cycle_length(3), Some(3));
        assert_eq!(vortex_cycle_length(1), Some(6));
        assert_eq!(vortex_cycle_length(0), None);
    }

    #[test]
    fn test_triadic_sum() {
        assert_eq!(TRIADIC_SUM, 18);
        assert_eq!(HEXADIC_SUM, 27);
        assert_eq!(ALL_DR_SUM, 45);
        assert_eq!(TRIADIC_SUM + HEXADIC_SUM, ALL_DR_SUM);
    }

    #[test]
    fn test_204_invariant() {
        assert_eq!(digital_root(204), 6);
        assert_eq!(classify_vortex(204), VortexFamily::Triadic);
    }

    #[test]
    fn test_all_dr_sum_equals_triangular_9() {
        let triangular_9: u64 = (1..=9).sum();
        assert_eq!(ALL_DR_SUM, triangular_9);
    }

    // 9. single-element sequence is always stable
    #[test]
    fn single_element_sequence_is_stable() {
        assert!(is_sequence_stable(&[3]));
        assert!(is_sequence_stable(&[1]));
        assert!(is_sequence_stable(&[9]));
    }

    // 10. all six hexadic members classify as Hexadic
    #[test]
    fn hexadic_members_all_classify_hexadic() {
        for &n in &[1u64, 2, 4, 5, 7, 8] {
            assert_eq!(
                classify_vortex(n),
                VortexFamily::Hexadic,
                "expected Hexadic for {n}"
            );
        }
    }
}
