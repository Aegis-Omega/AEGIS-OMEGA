// Constitutional Substrate — Verifier Attestation Primitives
// EPISTEMIC TIER: T0
// ONTOLOGY TERM: Bernstein Bound (gate decision substrate)
//
// VerifierAttestation records the outcome of a V1–V3 verifier evaluation.
// V4 (statistical) and V5 (human) attestations are tracked but are
// constitutionally excluded from VCG weight — they may not ground gate decisions.
//
// Wire format: all fields little-endian, no padding.

use crate::archive::{ArchiveVersion, ARCHIVE_V1_0_0};
use crate::primitives::StateHash;

// ─── Verifier Class Constants ─────────────────────────────────────────────────
// Mirror of TypeScript VerifierClass enum.

pub const VERIFIER_V1_DETERMINISTIC: u8 = 1; // compilers, theorem provers, execution
pub const VERIFIER_V2_SCHEMA: u8 = 2;        // JSON Schema, SQL, type checkers
pub const VERIFIER_V3_RETRIEVAL: u8 = 3;     // KB lookups, RAG grounding
pub const VERIFIER_V4_STATISTICAL: u8 = 4;   // LLM judges, ensembles — VCG excluded
pub const VERIFIER_V5_HUMAN: u8 = 5;         // human review — audit only, VCG excluded

/// Classes at or above this threshold are excluded from VCG weight calculations.
/// Constitutional invariant: V4 and V5 NEVER contribute to gate decisions.
pub const VCG_WEIGHT_EXCLUDED_CLASS: u8 = VERIFIER_V4_STATISTICAL;

// ─── VerifierAttestation ──────────────────────────────────────────────────────

/// A recorded verifier evaluation result — substrate for gate admissibility decisions.
///
/// Wire format (106 bytes, LE):
///   [0..64]   verifier_id: UTF-8 zero-padded identifier
///   [64..96]  artifact_hash: StateHash — SHA-256 of the evaluated artifact
///   [96]      passed: u8 (0x00=false, 0x01=true)
///   [97]      verifier_class: u8 (VERIFIER_V1..V5 constants)
///   [98..100] reserved: [0u8; 2]
///   [100..106] archive_version: ArchiveVersion wire format
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct VerifierAttestation {
    pub verifier_id: [u8; 64],
    pub artifact_hash: StateHash,
    pub passed: bool,
    pub verifier_class: u8,
    pub archive_version: ArchiveVersion,
}

impl VerifierAttestation {
    pub fn new(
        verifier_id: &str,
        artifact_hash: StateHash,
        passed: bool,
        verifier_class: u8,
    ) -> Self {
        let mut id = [0u8; 64];
        let bytes = verifier_id.as_bytes();
        let len = bytes.len().min(64);
        id[..len].copy_from_slice(&bytes[..len]);
        Self {
            verifier_id: id,
            artifact_hash,
            passed,
            verifier_class,
            archive_version: ARCHIVE_V1_0_0,
        }
    }

    /// True if this attestation may contribute to a VCG gate decision.
    /// V4 and V5 are constitutionally excluded — they may never ground gate acceptance.
    pub fn is_vcg_admissible(&self) -> bool {
        self.verifier_class < VCG_WEIGHT_EXCLUDED_CLASS
    }

    /// Serialise to 106-byte canonical wire format.
    pub fn to_bytes(&self) -> [u8; 106] {
        let mut out = [0u8; 106];
        out[0..64].copy_from_slice(&self.verifier_id);
        out[64..96].copy_from_slice(&self.artifact_hash);
        out[96] = self.passed as u8;
        out[97] = self.verifier_class;
        // [98..100] reserved zeros
        out[100..106].copy_from_slice(&self.archive_version.to_bytes());
        out
    }

    /// Deserialise from 106-byte canonical wire format.
    pub fn from_bytes(b: &[u8; 106]) -> Option<Self> {
        let mut verifier_id = [0u8; 64];
        verifier_id.copy_from_slice(&b[0..64]);
        let mut artifact_hash = [0u8; 32];
        artifact_hash.copy_from_slice(&b[64..96]);
        let passed = match b[96] {
            0x00 => false,
            0x01 => true,
            _ => return None, // invalid boolean encoding — reject
        };
        let verifier_class = b[97];
        let archive_version = ArchiveVersion::from_bytes(b[100..106].try_into().ok()?);
        Some(Self { verifier_id, artifact_hash, passed, verifier_class, archive_version })
    }

    pub fn verifier_id_str(&self) -> &str {
        let end = self.verifier_id.iter().position(|&b| b == 0).unwrap_or(64);
        core::str::from_utf8(&self.verifier_id[..end]).unwrap_or("<invalid utf-8>")
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    const TEST_HASH: StateHash = [0xCDu8; 32];

    #[test]
    fn v1_is_vcg_admissible() {
        let a = VerifierAttestation::new("v1-test", TEST_HASH, true, VERIFIER_V1_DETERMINISTIC);
        assert!(a.is_vcg_admissible());
    }

    #[test]
    fn v2_is_vcg_admissible() {
        let a = VerifierAttestation::new("v2-test", TEST_HASH, true, VERIFIER_V2_SCHEMA);
        assert!(a.is_vcg_admissible());
    }

    #[test]
    fn v3_is_vcg_admissible() {
        let a = VerifierAttestation::new("v3-test", TEST_HASH, false, VERIFIER_V3_RETRIEVAL);
        assert!(a.is_vcg_admissible());
    }

    #[test]
    fn v4_excluded_from_vcg() {
        let a = VerifierAttestation::new("llm-judge", TEST_HASH, true, VERIFIER_V4_STATISTICAL);
        assert!(!a.is_vcg_admissible());
    }

    #[test]
    fn v5_excluded_from_vcg() {
        let a = VerifierAttestation::new("human-review", TEST_HASH, true, VERIFIER_V5_HUMAN);
        assert!(!a.is_vcg_admissible());
    }

    #[test]
    fn attestation_roundtrip() {
        let a = VerifierAttestation::new("gate-v1", TEST_HASH, true, VERIFIER_V1_DETERMINISTIC);
        let bytes = a.to_bytes();
        let recovered = VerifierAttestation::from_bytes(&bytes).unwrap();
        assert_eq!(a, recovered);
    }

    #[test]
    fn attestation_false_roundtrip() {
        let a = VerifierAttestation::new("schema-v2", TEST_HASH, false, VERIFIER_V2_SCHEMA);
        let bytes = a.to_bytes();
        let recovered = VerifierAttestation::from_bytes(&bytes).unwrap();
        assert!(!recovered.passed);
    }

    #[test]
    fn attestation_serialization_stability() {
        let a = VerifierAttestation::new("v1-deterministic", TEST_HASH, true, VERIFIER_V1_DETERMINISTIC);
        assert_eq!(a.to_bytes(), a.to_bytes());
    }

    #[test]
    fn invalid_boolean_rejected() {
        let a = VerifierAttestation::new("v1", TEST_HASH, true, VERIFIER_V1_DETERMINISTIC);
        let mut bytes = a.to_bytes();
        bytes[96] = 0xFF; // invalid boolean
        assert!(VerifierAttestation::from_bytes(&bytes).is_none());
    }

    #[test]
    fn verifier_id_str_decode() {
        let a = VerifierAttestation::new("sovereign-v1-gate", TEST_HASH, true, VERIFIER_V1_DETERMINISTIC);
        assert_eq!(a.verifier_id_str(), "sovereign-v1-gate");
    }
}
