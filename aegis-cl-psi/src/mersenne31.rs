//! Mersenne-31 Prime Field Arithmetic
//! EPISTEMIC TIER: T2
//!
//! p = 2^31 − 1 = 2_147_483_647 (Mersenne prime)
//!
//! Reduction invariant: every M31 value is in [0, P-1] at all times.
//!
//! Fast reduction properties (no division):
//!   - Addition/subtraction: one conditional subtraction/addition
//!   - Multiplication: one 31-bit right-shift + add, then one conditional subtract
//!
//! This is the field substrate for Plonky3-style FRI-based proof systems.
//! Plonky3 full proof generation requires the external plonky3 crate; this
//! module provides the field arithmetic foundation independently.
//!
//! Source: plonky3-zk-compression skill (T2).

pub const P: u32 = (1u32 << 31) - 1;   // 2^31 - 1 = 2_147_483_647

/// An element of the Mersenne-31 field F_p.
/// Invariant: 0 ≤ inner < P at all times.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub struct M31 {
    inner: u32,
}

impl M31 {
    /// Construct from a raw u32, reducing mod P.
    #[inline]
    pub fn new(val: u32) -> Self {
        Self { inner: if val >= P { val - P } else { val } }
    }

    /// Construct from a u64, reducing mod P.
    /// Uses the Mersenne fast reduction: x mod (2^31-1) = hi + lo, then
    /// one conditional subtraction — no division.
    #[inline]
    pub fn from_u64(val: u64) -> Self {
        let hi = (val >> 31) as u32;
        let lo = (val & (P as u64)) as u32;
        let sum = hi.saturating_add(lo);
        Self { inner: if sum >= P { sum - P } else { sum } }
    }

    #[inline]
    pub fn as_u32(self) -> u32 { self.inner }

    pub const ZERO: Self = Self { inner: 0 };
    pub const ONE:  Self = Self { inner: 1 };

    /// Additive inverse: -x mod P
    #[inline]
    pub fn neg(self) -> Self {
        Self { inner: if self.inner == 0 { 0 } else { P - self.inner } }
    }

    /// Multiplicative inverse via Fermat: x^(P-2) mod P.
    /// Returns None for zero (no multiplicative inverse).
    pub fn inv(self) -> Option<Self> {
        if self.inner == 0 { return None; }
        Some(self.pow(P as u64 - 2))
    }

    /// Fast exponentiation via square-and-multiply.
    pub fn pow(self, mut exp: u64) -> Self {
        let mut base = self;
        let mut result = Self::ONE;
        while exp > 0 {
            if exp & 1 == 1 { result = result.mul(base); }
            base = base.mul(base);
            exp >>= 1;
        }
        result
    }

    #[inline]
    pub fn add(self, rhs: Self) -> Self {
        let sum = self.inner + rhs.inner;
        Self { inner: if sum >= P { sum - P } else { sum } }
    }

    #[inline]
    pub fn sub(self, rhs: Self) -> Self {
        if self.inner >= rhs.inner {
            Self { inner: self.inner - rhs.inner }
        } else {
            Self { inner: P - rhs.inner + self.inner }
        }
    }

    #[inline]
    pub fn mul(self, rhs: Self) -> Self {
        Self::from_u64((self.inner as u64) * (rhs.inner as u64))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn p_is_mersenne_prime() { assert_eq!(P, 2_147_483_647); }

    #[test]
    fn new_reduces_mod_p() {
        assert_eq!(M31::new(P).as_u32(), 0);
        assert_eq!(M31::new(P + 1).as_u32(), 1);
    }

    #[test]
    fn add_does_not_exceed_p() {
        let a = M31::new(P - 1);
        let b = M31::new(1);
        assert_eq!(a.add(b).as_u32(), 0, "(P-1)+1 must wrap to 0");
    }

    #[test]
    fn add_commutativity() {
        let a = M31::new(123456);
        let b = M31::new(789012);
        assert_eq!(a.add(b), b.add(a));
    }

    #[test]
    fn sub_produces_correct_result() {
        let a = M31::new(10);
        let b = M31::new(3);
        assert_eq!(a.sub(b).as_u32(), 7);
    }

    #[test]
    fn sub_wraps_correctly() {
        let a = M31::new(0);
        let b = M31::new(1);
        assert_eq!(a.sub(b).as_u32(), P - 1, "0-1 must wrap to P-1");
    }

    #[test]
    fn add_sub_roundtrip() {
        let a = M31::new(999_999);
        let b = M31::new(1_234_567);
        assert_eq!(a.add(b).sub(b), a);
    }

    #[test]
    fn mul_identity() {
        let a = M31::new(42);
        assert_eq!(a.mul(M31::ONE), a);
        assert_eq!(M31::ONE.mul(a), a);
    }

    #[test]
    fn mul_zero() {
        let a = M31::new(12345678);
        assert_eq!(a.mul(M31::ZERO), M31::ZERO);
    }

    #[test]
    fn mul_stays_in_field() {
        let a = M31::new(P - 1);
        let result = a.mul(a);
        assert!(result.as_u32() < P, "result must be in [0, P)");
    }

    #[test]
    fn mul_commutativity() {
        let a = M31::new(1_000_000);
        let b = M31::new(2_000_000);
        assert_eq!(a.mul(b), b.mul(a));
    }

    #[test]
    fn neg_of_zero_is_zero() {
        assert_eq!(M31::ZERO.neg(), M31::ZERO);
    }

    #[test]
    fn neg_adds_to_zero() {
        let a = M31::new(7);
        assert_eq!(a.add(a.neg()), M31::ZERO);
    }

    #[test]
    fn from_u64_fast_reduction() {
        let val: u64 = (P as u64) * 3 + 5;
        assert_eq!(M31::from_u64(val).as_u32(), 5);
    }

    #[test]
    fn inv_of_one_is_one() {
        assert_eq!(M31::ONE.inv(), Some(M31::ONE));
    }

    #[test]
    fn inv_zero_is_none() {
        assert_eq!(M31::ZERO.inv(), None);
    }

    #[test]
    fn inv_round_trip() {
        let a = M31::new(13);
        let inv = a.inv().unwrap();
        assert_eq!(a.mul(inv), M31::ONE);
    }

    #[test]
    fn distributivity() {
        let a = M31::new(100);
        let b = M31::new(200);
        let c = M31::new(300);
        assert_eq!(a.mul(b.add(c)), a.mul(b).add(a.mul(c)));
    }

    #[test]
    fn determinism_triple() {
        let a = M31::new(1_111_111);
        let b = M31::new(2_222_222);
        let r1 = a.mul(b).add(a).sub(b);
        let r2 = a.mul(b).add(a).sub(b);
        let r3 = a.mul(b).add(a).sub(b);
        assert_eq!(r1, r2);
        assert_eq!(r2, r3);
    }
}
