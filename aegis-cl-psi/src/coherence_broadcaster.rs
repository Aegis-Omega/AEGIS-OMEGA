//! Gate 228: Coherence Broadcaster — Global Section Announcement
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Bridges the LatticeCoherence report to the GossipEmitter, encoding the
//! global section verdict as a constitutional broadcast frame.
//!
//! Frame encoding (16 bytes):
//!   [0]    = global_section_exists (0x01 = true, 0x00 = false)
//!   [1]    = satisfied_count (0..=5)
//!   [2]    = first_obstruction (0xFF = none, 0..=4 = level)
//!   [3..7] = coherence_score as u32 fixed-point ×1_000_000 big-endian
//!   [7]    = ObstructionLevels bitmask: bit0=L0, bit1=L1, bit2=L2, bit3=L3, bit4=L4
//!   [8..16]= constitutional_hash prefix (first 8 bytes)
//!
//! The broadcast frame is deterministic: same CoherenceReport + constitutional_hash
//! always produces the same 16 bytes. No timestamps, no RNG.

use crate::lattice_coherence::CoherenceReport;

/// 16-byte broadcast frame encoding a CoherenceReport.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct CoherenceFrame {
    pub bytes: [u8; 16],
}

impl CoherenceFrame {
    /// Decode back to structured fields (for verification / tests).
    pub fn global_section_exists(&self) -> bool { self.bytes[0] == 0x01 }
    pub fn satisfied_count(&self) -> u8 { self.bytes[1] }
    pub fn first_obstruction(&self) -> Option<u8> {
        if self.bytes[2] == 0xFF { None } else { Some(self.bytes[2]) }
    }
    pub fn coherence_score(&self) -> f64 {
        let fixed = u32::from_be_bytes([self.bytes[3], self.bytes[4], self.bytes[5], self.bytes[6]]);
        f64::from(fixed) / 1_000_000.0
    }
    pub fn level_bitmask(&self) -> u8 { self.bytes[7] }
    pub fn hash_prefix(&self) -> [u8; 8] {
        let mut p = [0u8; 8];
        p.copy_from_slice(&self.bytes[8..16]);
        p
    }
}

#[derive(Debug)]
pub struct BroadcastError(pub &'static str);

/// Encode a CoherenceReport + constitutional_hash prefix into a 16-byte frame.
/// Pure function — deterministic, no I/O.
pub fn encode_coherence_frame(
    report: &CoherenceReport,
    constitutional_hash: &[u8; 32],
) -> Result<CoherenceFrame, BroadcastError> {
    // Fixed-point score: multiply by 1_000_000 and clamp to u32
    let score_fp = (report.coherence_score * 1_000_000.0).round();
    if score_fp < 0.0 || score_fp > 1_000_001.0 {
        return Err(BroadcastError("coherence_score out of [0,1] range"));
    }
    let score_u32 = score_fp as u32;
    let score_bytes = score_u32.to_be_bytes();

    let obs_byte = report.first_obstruction.unwrap_or(0xFF);

    // Bitmask: bit i set iff level i is satisfied
    let lvl = &report.levels;
    let bitmask: u8 = (if lvl.l0_ralph_frame        { 0x01 } else { 0 })
                    | (if lvl.l1_mutation_authority  { 0x02 } else { 0 })
                    | (if lvl.l2_resonance           { 0x04 } else { 0 })
                    | (if lvl.l3_chord_unity         { 0x08 } else { 0 })
                    | (if lvl.l4_autopoietic         { 0x10 } else { 0 });

    let mut frame = [0u8; 16];
    frame[0] = if report.global_section_exists { 0x01 } else { 0x00 };
    frame[1] = report.satisfied_count;
    frame[2] = obs_byte;
    frame[3] = score_bytes[0];
    frame[4] = score_bytes[1];
    frame[5] = score_bytes[2];
    frame[6] = score_bytes[3];
    frame[7] = bitmask;
    frame[8..16].copy_from_slice(&constitutional_hash[0..8]);

    Ok(CoherenceFrame { bytes: frame })
}

/// Decode a CoherenceFrame back to a structured report summary.
/// Used by receiving peers to verify the broadcast.
pub fn decode_coherence_frame(frame: &CoherenceFrame) -> DecodedCoherence {
    let bitmask = frame.level_bitmask();
    DecodedCoherence {
        global_section_exists: frame.global_section_exists(),
        satisfied_count: frame.satisfied_count(),
        first_obstruction: frame.first_obstruction(),
        coherence_score: frame.coherence_score(),
        l0: bitmask & 0x01 != 0,
        l1: bitmask & 0x02 != 0,
        l2: bitmask & 0x04 != 0,
        l3: bitmask & 0x08 != 0,
        l4: bitmask & 0x10 != 0,
        hash_prefix: frame.hash_prefix(),
    }
}

/// Structured summary decoded from a CoherenceFrame by a receiving peer.
#[derive(Debug, Clone, PartialEq)]
pub struct DecodedCoherence {
    pub global_section_exists: bool,
    pub satisfied_count: u8,
    pub first_obstruction: Option<u8>,
    pub coherence_score: f64,
    pub l0: bool, pub l1: bool, pub l2: bool, pub l3: bool, pub l4: bool,
    pub hash_prefix: [u8; 8],
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::lattice_coherence::{CoherenceReport, ObstructionLevels};

    fn full_report() -> CoherenceReport {
        CoherenceReport {
            global_section_exists: true,
            levels: ObstructionLevels {
                l0_ralph_frame: true, l1_mutation_authority: true,
                l2_resonance: true, l3_chord_unity: true, l4_autopoietic: true,
            },
            coherence_score: 1.0,
            satisfied_count: 5,
            first_obstruction: None,
        }
    }

    fn partial_report() -> CoherenceReport {
        CoherenceReport {
            global_section_exists: false,
            levels: ObstructionLevels {
                l0_ralph_frame: true, l1_mutation_authority: true,
                l2_resonance: true, l3_chord_unity: false, l4_autopoietic: false,
            },
            coherence_score: 4.0 / 12.0,
            satisfied_count: 3,
            first_obstruction: Some(3),
        }
    }

    fn zero_hash() -> [u8; 32] { [0u8; 32] }

    fn distinct_hash() -> [u8; 32] {
        let mut h = [0u8; 32];
        for (i, b) in h.iter_mut().enumerate() { *b = i as u8; }
        h
    }

    #[test]
    fn encode_full_report_global_section_true() {
        let frame = encode_coherence_frame(&full_report(), &zero_hash()).unwrap();
        assert!(frame.global_section_exists());
    }

    #[test]
    fn encode_satisfied_count() {
        let frame = encode_coherence_frame(&full_report(), &zero_hash()).unwrap();
        assert_eq!(frame.satisfied_count(), 5);
    }

    #[test]
    fn encode_first_obstruction_none() {
        let frame = encode_coherence_frame(&full_report(), &zero_hash()).unwrap();
        assert_eq!(frame.first_obstruction(), None);
    }

    #[test]
    fn encode_coherence_score_roundtrip() {
        let frame = encode_coherence_frame(&full_report(), &zero_hash()).unwrap();
        let score = frame.coherence_score();
        let delta = (score - 1.0).abs();
        assert!(delta < 1e-5, "expected 1.0, got {score}");
    }

    #[test]
    fn encode_partial_report_obstruction_level() {
        let frame = encode_coherence_frame(&partial_report(), &zero_hash()).unwrap();
        assert!(!frame.global_section_exists());
        assert_eq!(frame.first_obstruction(), Some(3));
        assert_eq!(frame.satisfied_count(), 3);
    }

    #[test]
    fn encode_partial_score_roundtrip() {
        let frame = encode_coherence_frame(&partial_report(), &zero_hash()).unwrap();
        let expected = 4.0 / 12.0;
        let delta = (frame.coherence_score() - expected).abs();
        assert!(delta < 1e-4, "expected {expected}, got {}", frame.coherence_score());
    }

    #[test]
    fn bitmask_all_levels_set() {
        let frame = encode_coherence_frame(&full_report(), &zero_hash()).unwrap();
        assert_eq!(frame.level_bitmask(), 0x1F); // all 5 bits
    }

    #[test]
    fn bitmask_partial_levels() {
        // L0+L1+L2 = bits 0,1,2 = 0x07
        let frame = encode_coherence_frame(&partial_report(), &zero_hash()).unwrap();
        assert_eq!(frame.level_bitmask(), 0x07);
    }

    #[test]
    fn hash_prefix_encoded() {
        let h = distinct_hash();
        let frame = encode_coherence_frame(&full_report(), &h).unwrap();
        let prefix = frame.hash_prefix();
        assert_eq!(prefix, [0, 1, 2, 3, 4, 5, 6, 7]);
    }

    #[test]
    fn different_hashes_different_frames() {
        let f1 = encode_coherence_frame(&full_report(), &zero_hash()).unwrap();
        let f2 = encode_coherence_frame(&full_report(), &distinct_hash()).unwrap();
        assert_ne!(f1.bytes, f2.bytes);
    }

    #[test]
    fn determinism_full_report() {
        let r = full_report();
        let h = distinct_hash();
        let f1 = encode_coherence_frame(&r, &h).unwrap();
        let f2 = encode_coherence_frame(&r, &h).unwrap();
        let f3 = encode_coherence_frame(&r, &h).unwrap();
        assert_eq!(f1.bytes, f2.bytes);
        assert_eq!(f2.bytes, f3.bytes);
    }

    #[test]
    fn decode_roundtrip_full() {
        let frame = encode_coherence_frame(&full_report(), &zero_hash()).unwrap();
        let decoded = decode_coherence_frame(&frame);
        assert!(decoded.global_section_exists);
        assert_eq!(decoded.satisfied_count, 5);
        assert_eq!(decoded.first_obstruction, None);
        assert!(decoded.l0 && decoded.l1 && decoded.l2 && decoded.l3 && decoded.l4);
    }

    #[test]
    fn decode_roundtrip_partial() {
        let frame = encode_coherence_frame(&partial_report(), &zero_hash()).unwrap();
        let decoded = decode_coherence_frame(&frame);
        assert!(!decoded.global_section_exists);
        assert_eq!(decoded.satisfied_count, 3);
        assert_eq!(decoded.first_obstruction, Some(3));
        assert!(decoded.l0 && decoded.l1 && decoded.l2);
        assert!(!decoded.l3 && !decoded.l4);
    }

    #[test]
    fn decode_hash_prefix() {
        let h = distinct_hash();
        let frame = encode_coherence_frame(&full_report(), &h).unwrap();
        let decoded = decode_coherence_frame(&frame);
        assert_eq!(decoded.hash_prefix, [0, 1, 2, 3, 4, 5, 6, 7]);
    }

    #[test]
    fn frame_is_16_bytes() {
        let frame = encode_coherence_frame(&full_report(), &zero_hash()).unwrap();
        assert_eq!(frame.bytes.len(), 16);
    }

    #[test]
    fn broadcast_error_type() {
        let e = BroadcastError("test");
        assert_eq!(e.0, "test");
    }
}
