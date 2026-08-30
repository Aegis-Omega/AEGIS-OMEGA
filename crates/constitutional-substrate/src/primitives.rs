// Constitutional Substrate — Core Primitives
// EPISTEMIC TIER: T0
// ONTOLOGY TERMS: Invariant, EpistemicTier, HolonicScale, Provenance
//
// All numeric computation uses Q16.16 fixed-point arithmetic.
// Matches Python hardware_config.py INT_SHIFT=16, INT_SCALE=65536.
// No floating-point arithmetic anywhere in this module.

// ─── Fixed-Point Constants ────────────────────────────────────────────────────

/// Fractional bits in Q16.16 representation.
pub const FIXED_SHIFT: u32 = 16;

/// Multiplicative scale factor (2^16 = 65536).
pub const FIXED_SCALE: i64 = 1_i64 << FIXED_SHIFT;

// ─── Holonic Scale Constants ──────────────────────────────────────────────────
// Mirror of TypeScript HolonicScale enum — must stay in sync.

pub const HOLONIC_SUBATOMIC: u8 = 0; // byte invariants, hash chains, fixed-point arithmetic
pub const HOLONIC_ATOMIC:    u8 = 1; // files, functions, proof units
pub const HOLONIC_MOLECULAR: u8 = 2; // modules, pipelines
pub const HOLONIC_CELLULAR:  u8 = 3; // subsystems: E3, VCG, Python Core Matrix
pub const HOLONIC_ORGANISM:  u8 = 4; // full sovereign-omega-v2 runtime
pub const HOLONIC_FIELD:     u8 = 5; // Claude + ChatGPT + Qwen + operators + Drive corpus

// ─── StateHash ────────────────────────────────────────────────────────────────

/// SHA-256 digest — 32-byte architecture-independent hash.
/// Computation always occurs at the integration boundary (SHA-256 is not
/// implemented in this crate). The substrate stores and chains hashes only.
pub type StateHash = [u8; 32];

/// The genesis prev_hash: 64 ASCII zeros, matching the TypeScript layer convention.
pub const GENESIS_HASH: StateHash = [0u8; 32];

// ─── Fixed-Point Arithmetic ───────────────────────────────────────────────────

/// Q16.16 multiplication. Panics on overflow — invariant-breach.
pub fn fixed_mul(a: i64, b: i64) -> i64 {
    let result = (a as i128) * (b as i128);
    let shifted = result >> FIXED_SHIFT;
    assert!(
        shifted >= i64::MIN as i128 && shifted <= i64::MAX as i128,
        "fixed_mul: overflow on ({a}, {b}) — invariant-breach"
    );
    shifted as i64
}

/// Q16.16 division. Panics on zero divisor — invariant-breach.
pub fn fixed_div(a: i64, b: i64) -> i64 {
    assert!(b != 0, "fixed_div: zero divisor — invariant-breach");
    let numerator = (a as i128) * (FIXED_SCALE as i128);
    let result = numerator / (b as i128);
    assert!(
        result >= i64::MIN as i128 && result <= i64::MAX as i128,
        "fixed_div: overflow on ({a}, {b}) — invariant-breach"
    );
    result as i64
}

/// Convert an integer to Q16.16 fixed-point.
#[inline]
pub fn to_fixed(x: i64) -> i64 {
    x * FIXED_SCALE
}

/// Convert Q16.16 fixed-point to integer (floor).
#[inline]
pub fn from_fixed(x: i64) -> i64 {
    x >> FIXED_SHIFT
}

/// Clamp a Q16.16 value to [lo, hi]. Panics if lo > hi.
pub fn fixed_clamp(x: i64, lo: i64, hi: i64) -> i64 {
    assert!(lo <= hi, "fixed_clamp: lo > hi — invariant-breach");
    x.max(lo).min(hi)
}

// ─── ViolationSeverity ────────────────────────────────────────────────────────

#[repr(u8)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ViolationSeverity {
    T0Abort = 0, // constitutional halt — replay must stop
    T1Alert = 1, // empirical degradation — log and surface to operator
    T2Warn  = 2, // engineering hypothesis deviation — informational
}

impl ViolationSeverity {
    pub fn from_byte(b: u8) -> Option<Self> {
        match b {
            0 => Some(Self::T0Abort),
            1 => Some(Self::T1Alert),
            2 => Some(Self::T2Warn),
            _ => None,
        }
    }
}

// ─── InvariantViolation ───────────────────────────────────────────────────────

/// A recorded invariant breach — maps to INV-01..INV-10 in invariant-checker.ts.
///
/// Wire format (22 bytes, LE):
///   [0..16]  invariant_id: ASCII zero-padded identifier (e.g. b"INV-09\0\0\0\0\0\0\0\0\0\0")
///   [16]     severity:     ViolationSeverity as u8
///   [17]     holonic_scale: u8 (HOLONIC_* constants)
///   Omitted: observed/expected stored as Q16.16 i64 (8 bytes each) for full record
///
/// Full wire format (38 bytes):
///   [0..16]  invariant_id
///   [16]     severity
///   [17]     holonic_scale
///   [18..26] observed_fixed: i64 LE
///   [26..34] expected_fixed: i64 LE
///   [34..38] reserved: [0u8; 4] — reserved for future extensions
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct InvariantViolation {
    pub invariant_id: [u8; 16],
    pub severity: ViolationSeverity,
    pub holonic_scale: u8,
    pub observed_fixed: i64, // Q16.16 observed value
    pub expected_fixed: i64, // Q16.16 expected/threshold value
}

impl InvariantViolation {
    pub fn new(
        id: &[u8],
        severity: ViolationSeverity,
        observed_fixed: i64,
        expected_fixed: i64,
        holonic_scale: u8,
    ) -> Self {
        let mut invariant_id = [0u8; 16];
        let len = id.len().min(16);
        invariant_id[..len].copy_from_slice(&id[..len]);
        Self { invariant_id, severity, holonic_scale, observed_fixed, expected_fixed }
    }

    pub fn is_t0_abort(&self) -> bool {
        self.severity == ViolationSeverity::T0Abort
    }

    /// Serialise to 38-byte canonical wire format (little-endian).
    pub fn to_bytes(&self) -> [u8; 38] {
        let mut out = [0u8; 38];
        out[0..16].copy_from_slice(&self.invariant_id);
        out[16] = self.severity as u8;
        out[17] = self.holonic_scale;
        out[18..26].copy_from_slice(&self.observed_fixed.to_le_bytes());
        out[26..34].copy_from_slice(&self.expected_fixed.to_le_bytes());
        // [34..38] reserved zeros
        out
    }

    /// Deserialise from 38-byte canonical wire format.
    pub fn from_bytes(b: &[u8; 38]) -> Option<Self> {
        let mut invariant_id = [0u8; 16];
        invariant_id.copy_from_slice(&b[0..16]);
        let severity = ViolationSeverity::from_byte(b[16])?;
        let holonic_scale = b[17];
        let observed_fixed = i64::from_le_bytes(b[18..26].try_into().ok()?);
        let expected_fixed = i64::from_le_bytes(b[26..34].try_into().ok()?);
        Some(Self { invariant_id, severity, holonic_scale, observed_fixed, expected_fixed })
    }
}

// ─── ProvenanceReference ──────────────────────────────────────────────────────

/// A reference to a Drive corpus document that epistemically grounds a T0–T2 primitive.
/// ONTOLOGY TERM: Provenance
///
/// Wire format (97 bytes, LE):
///   [0..64]  drive_id: Google Drive file ID, UTF-8 zero-padded
///   [64..96] claim_hash: SHA-256 of the key claim text (computed at boundary)
///   [96]     tier: epistemic tier byte (0=T0 .. 5=T5)
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProvenanceReference {
    pub drive_id: [u8; 64],
    pub claim_hash: StateHash,
    pub tier: u8,
}

impl ProvenanceReference {
    pub fn new(drive_id: &str, claim_hash: StateHash, tier: u8) -> Self {
        let mut id = [0u8; 64];
        let bytes = drive_id.as_bytes();
        let len = bytes.len().min(64);
        id[..len].copy_from_slice(&bytes[..len]);
        Self { drive_id: id, claim_hash, tier }
    }

    pub fn to_bytes(&self) -> [u8; 97] {
        let mut out = [0u8; 97];
        out[0..64].copy_from_slice(&self.drive_id);
        out[64..96].copy_from_slice(&self.claim_hash);
        out[96] = self.tier;
        out
    }

    pub fn from_bytes(b: &[u8; 97]) -> Self {
        let mut drive_id = [0u8; 64];
        drive_id.copy_from_slice(&b[0..64]);
        let mut claim_hash = [0u8; 32];
        claim_hash.copy_from_slice(&b[64..96]);
        Self { drive_id, claim_hash, tier: b[96] }
    }
}

// ─── OntologyReference ───────────────────────────────────────────────────────

/// A reference to a canonical term defined in docs/ONTOLOGY.md.
/// ONTOLOGY TERM: (self-referential — every term maps to itself)
///
/// Wire format (132 bytes, LE):
///   [0..128] term: canonical term string, UTF-8 zero-padded
///   [128..132] ontology_version: u32 LE — version of ONTOLOGY.md at registration
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct OntologyReference {
    pub term: [u8; 128],
    pub ontology_version: u32,
}

impl OntologyReference {
    pub fn new(term: &str, ontology_version: u32) -> Self {
        let mut t = [0u8; 128];
        let bytes = term.as_bytes();
        let len = bytes.len().min(128);
        t[..len].copy_from_slice(&bytes[..len]);
        Self { term: t, ontology_version }
    }

    pub fn to_bytes(&self) -> [u8; 132] {
        let mut out = [0u8; 132];
        out[0..128].copy_from_slice(&self.term);
        out[128..132].copy_from_slice(&self.ontology_version.to_le_bytes());
        out
    }

    pub fn from_bytes(b: &[u8; 132]) -> Self {
        let mut term = [0u8; 128];
        term.copy_from_slice(&b[0..128]);
        let ontology_version = u32::from_le_bytes(b[128..132].try_into().unwrap());
        Self { term, ontology_version }
    }

    /// Decode the term as a UTF-8 string, trimming zero padding.
    pub fn term_str(&self) -> &str {
        let end = self.term.iter().position(|&b| b == 0).unwrap_or(128);
        core::str::from_utf8(&self.term[..end]).unwrap_or("<invalid utf-8>")
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fixed_mul_identity() {
        // 1.0 * 1.0 = 1.0 in Q16.16
        let one = FIXED_SCALE;
        assert_eq!(fixed_mul(one, one), one);
    }

    #[test]
    fn fixed_mul_half() {
        // 0.5 * 0.5 = 0.25 in Q16.16
        let half = FIXED_SCALE / 2;
        let quarter = FIXED_SCALE / 4;
        assert_eq!(fixed_mul(half, half), quarter);
    }

    #[test]
    fn fixed_div_identity() {
        let one = FIXED_SCALE;
        assert_eq!(fixed_div(one, one), one);
    }

    #[test]
    fn fixed_div_half() {
        // 1.0 / 2.0 = 0.5
        let one = FIXED_SCALE;
        let two = 2 * FIXED_SCALE;
        let half = FIXED_SCALE / 2;
        assert_eq!(fixed_div(one, two), half);
    }

    #[test]
    fn to_from_fixed_roundtrip() {
        for n in [0i64, 1, 42, 1000, -1, -42] {
            assert_eq!(from_fixed(to_fixed(n)), n);
        }
    }

    #[test]
    fn invariant_violation_roundtrip() {
        let v = InvariantViolation::new(
            b"INV-09",
            ViolationSeverity::T1Alert,
            63_700, // ~0.972 in Q16.16
            64_225, // ~0.980 in Q16.16
            HOLONIC_CELLULAR,
        );
        let bytes = v.to_bytes();
        let recovered = InvariantViolation::from_bytes(&bytes).unwrap();
        assert_eq!(v, recovered);
    }

    #[test]
    fn invariant_violation_t0_detection() {
        let t0 = InvariantViolation::new(b"INV-02", ViolationSeverity::T0Abort, 1, 0, HOLONIC_CELLULAR);
        let t1 = InvariantViolation::new(b"INV-09", ViolationSeverity::T1Alert, 60000, 64225, HOLONIC_CELLULAR);
        assert!(t0.is_t0_abort());
        assert!(!t1.is_t0_abort());
    }

    #[test]
    fn invariant_violation_serialization_stability() {
        // Same inputs → identical bytes across calls
        let v = InvariantViolation::new(b"INV-01", ViolationSeverity::T0Abort, 98304, 65536, HOLONIC_CELLULAR);
        assert_eq!(v.to_bytes(), v.to_bytes());
    }

    #[test]
    fn provenance_reference_roundtrip() {
        let hash = [0xABu8; 32];
        let p = ProvenanceReference::new("1cfFY59zAczNPCL7mvr_TxFo1yR7xfDNh", hash, 0);
        let bytes = p.to_bytes();
        let recovered = ProvenanceReference::from_bytes(&bytes);
        assert_eq!(p, recovered);
    }

    #[test]
    fn ontology_reference_term_str() {
        let r = OntologyReference::new("Holon", 1);
        assert_eq!(r.term_str(), "Holon");
        let bytes = r.to_bytes();
        let recovered = OntologyReference::from_bytes(&bytes);
        assert_eq!(recovered.term_str(), "Holon");
        assert_eq!(recovered.ontology_version, 1);
    }

    #[test]
    fn fixed_clamp_enforces_bounds() {
        assert_eq!(fixed_clamp(0, 0, FIXED_SCALE), 0);
        assert_eq!(fixed_clamp(2 * FIXED_SCALE, 0, FIXED_SCALE), FIXED_SCALE);
        assert_eq!(fixed_clamp(-FIXED_SCALE, 0, FIXED_SCALE), 0);
    }
}
