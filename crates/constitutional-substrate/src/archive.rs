// Constitutional Substrate — Schema-Versioned Archive Primitives
// EPISTEMIC TIER: T0
// ONTOLOGY TERM: Epoch (archive boundaries map to epoch transitions)
//
// Serialization canon decisions are effectively irreversible once replay archives
// accumulate. Wire format is frozen at v1.0.0. Major version increments indicate
// breaking changes; minor increments add fields read as optional by prior readers.
//
// Wire format: all fields little-endian, no padding, no alignment requirements.

use crate::primitives::{OntologyReference, ProvenanceReference, StateHash};

// ─── ArchiveVersion ───────────────────────────────────────────────────────────

/// Schema version for a replay archive. Version 1.0.0 is the initial constitutional release.
/// REPLAY CONSTITUTION LAW-02: archive version boundaries must be explicit and machine-readable.
///
/// Wire format (6 bytes, LE):
///   [0..2] major: u16 LE — breaking change
///   [2..4] minor: u16 LE — backward-compatible extension
///   [4..6] patch: u16 LE — bug fix, no format change
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ArchiveVersion {
    pub major: u16,
    pub minor: u16,
    pub patch: u16,
}

/// The initial constitutional release — replay archives must declare this version.
pub const ARCHIVE_V1_0_0: ArchiveVersion = ArchiveVersion { major: 1, minor: 0, patch: 0 };

impl ArchiveVersion {
    /// Serialise to 6-byte canonical little-endian wire format.
    pub fn to_bytes(self) -> [u8; 6] {
        let mut out = [0u8; 6];
        out[0..2].copy_from_slice(&self.major.to_le_bytes());
        out[2..4].copy_from_slice(&self.minor.to_le_bytes());
        out[4..6].copy_from_slice(&self.patch.to_le_bytes());
        out
    }

    /// Deserialise from 6-byte canonical little-endian wire format.
    pub fn from_bytes(b: &[u8; 6]) -> Self {
        Self {
            major: u16::from_le_bytes([b[0], b[1]]),
            minor: u16::from_le_bytes([b[2], b[3]]),
            patch: u16::from_le_bytes([b[4], b[5]]),
        }
    }

    /// True if a reader at `self` version can decode an archive at `archive` version.
    /// Same major = backward-compatible. Different major = breaking — must reject.
    /// REPLAY CONSTITUTION LAW-03: replay decoding compatibility is mandatory across
    /// deprecated schemas within the same major version.
    pub fn is_compatible_with(self, archive: ArchiveVersion) -> bool {
        self.major == archive.major
    }

    /// Reject decode if the archive's major version exceeds the reader's.
    /// Panic is constitutional here — reading an incompatible archive corrupts replay.
    pub fn assert_compatible(self, archive: ArchiveVersion) {
        assert!(
            self.is_compatible_with(archive),
            "archive schema incompatible: reader v{}.{}.{} cannot decode archive v{}.{}.{}",
            self.major, self.minor, self.patch,
            archive.major, archive.minor, archive.patch,
        );
    }
}

// ─── ArchiveHeader ────────────────────────────────────────────────────────────

/// Canonical header for a schema-versioned replay archive.
/// Every archive must begin with this header — deserializers check version before
/// reading any payload.
///
/// Wire format (118 bytes, LE):
///   [0..6]    archive_version: ArchiveVersion
///   [6..14]   archived_at_sequence: u64 LE — sequence number at export time
///   [14..22]  total_cycles: u64 LE
///   [22..30]  entropy_at_start: i64 LE Q16.16
///   [30..38]  entropy_at_end: i64 LE Q16.16 (0 = not recorded)
///   [38..40]  has_entropy_at_end: u16 LE (0=false, 1=true)
///   [40..72]  integrity_hash: StateHash — SHA-256 of the cycle payload (boundary-computed)
///   [72..118] reserved: [0u8; 46] — reserved for future minor-version extensions
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ArchiveHeader {
    pub archive_version: ArchiveVersion,
    pub archived_at_sequence: u64,
    pub total_cycles: u64,
    pub entropy_at_start: i64,
    pub entropy_at_end: Option<i64>,
    pub integrity_hash: StateHash,
}

impl ArchiveHeader {
    pub fn to_bytes(&self) -> [u8; 118] {
        let mut out = [0u8; 118];
        out[0..6].copy_from_slice(&self.archive_version.to_bytes());
        out[6..14].copy_from_slice(&self.archived_at_sequence.to_le_bytes());
        out[14..22].copy_from_slice(&self.total_cycles.to_le_bytes());
        out[22..30].copy_from_slice(&self.entropy_at_start.to_le_bytes());
        let (eta_val, has_eta) = self.entropy_at_end.map_or((0i64, 0u16), |e| (e, 1u16));
        out[30..38].copy_from_slice(&eta_val.to_le_bytes());
        out[38..40].copy_from_slice(&has_eta.to_le_bytes());
        out[40..72].copy_from_slice(&self.integrity_hash);
        // [72..118] reserved zeros
        out
    }

    pub fn from_bytes(b: &[u8; 118]) -> Option<Self> {
        let av = ArchiveVersion::from_bytes(b[0..6].try_into().ok()?);
        let archived_at_sequence = u64::from_le_bytes(b[6..14].try_into().ok()?);
        let total_cycles = u64::from_le_bytes(b[14..22].try_into().ok()?);
        let entropy_at_start = i64::from_le_bytes(b[22..30].try_into().ok()?);
        let eta_raw = i64::from_le_bytes(b[30..38].try_into().ok()?);
        let has_eta = u16::from_le_bytes(b[38..40].try_into().ok()?);
        let entropy_at_end = if has_eta == 1 { Some(eta_raw) } else { None };
        let mut integrity_hash = [0u8; 32];
        integrity_hash.copy_from_slice(&b[40..72]);
        Some(Self {
            archive_version: av,
            archived_at_sequence,
            total_cycles,
            entropy_at_start,
            entropy_at_end,
            integrity_hash,
        })
    }
}

// ─── ArchiveAttachment ────────────────────────────────────────────────────────

/// Provenance and ontology attachments for an archive — constitutional metadata.
/// Not part of the replay payload; stored alongside for audit and traceability.
pub struct ArchiveAttachment {
    pub provenance: ProvenanceReference,
    pub ontology: OntologyReference,
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn archive_version_roundtrip() {
        let v = ARCHIVE_V1_0_0;
        let bytes = v.to_bytes();
        let recovered = ArchiveVersion::from_bytes(&bytes);
        assert_eq!(v, recovered);
    }

    #[test]
    fn archive_version_serialization_stability() {
        // Identical inputs → identical bytes — serialization canon
        assert_eq!(ARCHIVE_V1_0_0.to_bytes(), ARCHIVE_V1_0_0.to_bytes());
    }

    #[test]
    fn archive_version_compatibility_same_major() {
        let v1_0 = ARCHIVE_V1_0_0;
        let v1_1 = ArchiveVersion { major: 1, minor: 1, patch: 0 };
        let v1_99 = ArchiveVersion { major: 1, minor: 99, patch: 3 };
        // Same major — reader can decode all minor/patch variants
        assert!(v1_0.is_compatible_with(v1_1));
        assert!(v1_0.is_compatible_with(v1_99));
        assert!(v1_0.is_compatible_with(v1_0));
    }

    #[test]
    fn archive_version_incompatibility_different_major() {
        let v1 = ARCHIVE_V1_0_0;
        let v2 = ArchiveVersion { major: 2, minor: 0, patch: 0 };
        let v0 = ArchiveVersion { major: 0, minor: 9, patch: 0 };
        assert!(!v1.is_compatible_with(v2));
        assert!(!v1.is_compatible_with(v0));
    }

    #[test]
    #[should_panic(expected = "archive schema incompatible")]
    fn archive_version_assert_compatible_panics_on_major_mismatch() {
        let v1 = ARCHIVE_V1_0_0;
        let v2 = ArchiveVersion { major: 2, minor: 0, patch: 0 };
        v1.assert_compatible(v2);
    }

    #[test]
    fn archive_header_roundtrip_with_entropy() {
        let header = ArchiveHeader {
            archive_version: ARCHIVE_V1_0_0,
            archived_at_sequence: 999,
            total_cycles: 100,
            entropy_at_start: 65536, // 1.0 in Q16.16
            entropy_at_end: Some(6554), // ~0.1 in Q16.16
            integrity_hash: [0xABu8; 32],
        };
        let bytes = header.to_bytes();
        let recovered = ArchiveHeader::from_bytes(&bytes).unwrap();
        assert_eq!(header.archive_version, recovered.archive_version);
        assert_eq!(header.archived_at_sequence, recovered.archived_at_sequence);
        assert_eq!(header.total_cycles, recovered.total_cycles);
        assert_eq!(header.entropy_at_start, recovered.entropy_at_start);
        assert_eq!(header.entropy_at_end, recovered.entropy_at_end);
        assert_eq!(header.integrity_hash, recovered.integrity_hash);
    }

    #[test]
    fn archive_header_roundtrip_without_entropy() {
        let header = ArchiveHeader {
            archive_version: ARCHIVE_V1_0_0,
            archived_at_sequence: 42,
            total_cycles: 10,
            entropy_at_start: 32768, // 0.5 in Q16.16
            entropy_at_end: None,
            integrity_hash: [0u8; 32],
        };
        let bytes = header.to_bytes();
        let recovered = ArchiveHeader::from_bytes(&bytes).unwrap();
        assert_eq!(recovered.entropy_at_end, None);
    }

    #[test]
    fn archive_header_serialization_stability() {
        let header = ArchiveHeader {
            archive_version: ARCHIVE_V1_0_0,
            archived_at_sequence: 1,
            total_cycles: 1,
            entropy_at_start: 65536,
            entropy_at_end: None,
            integrity_hash: [0u8; 32],
        };
        assert_eq!(header.to_bytes(), header.to_bytes());
    }
}
