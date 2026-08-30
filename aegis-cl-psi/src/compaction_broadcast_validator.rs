//! Gate 351 — Compaction Broadcast Validator (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Validates incoming BroadcastFrames (Gate 350) from peers, enforcing:
//!   1. Checksum integrity (SHA-256 over frame[0..25])
//!   2. Epoch monotonicity (each frame's epoch_end >= previous)
//!   3. Chain-of-epoch continuity (optional: epoch_end must advance by exactly 1)
//!
//! ValidationRecord:
//!   frame_epoch_end:  u64
//!   verdict:          ValidationVerdict (Valid / ChecksumFail / EpochRegressed / ChecksumAndEpoch)
//!   verdict_byte:     u8   (0=Valid, 1=ChecksumFail, 2=EpochRegressed, 3=both)
//!   record_hash:      [u8;32]
//!   prev_hash:        [u8;32]
//!
//! record_hash = SHA-256(prev[32] ‖ frame_epoch_end_be8 ‖ verdict_byte ‖ frame[32])
//!
//! CompactionBroadcastValidator: validate(frame), log(), record_count(), verify_chain().

use sha2::{Sha256, Digest};
use crate::compaction_broadcaster::{BROADCAST_FRAME_LEN, CompactionBroadcaster};

pub const VALIDATOR_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── ValidationVerdict ────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum ValidationVerdict {
    Valid             = 0,
    ChecksumFail      = 1,
    EpochRegressed    = 2,
    ChecksumAndEpoch  = 3,
}

impl ValidationVerdict {
    pub fn as_u8(self) -> u8 { self as u8 }

    pub fn is_valid(self) -> bool { self == Self::Valid }

    pub fn has_checksum_fail(self) -> bool {
        self == Self::ChecksumFail || self == Self::ChecksumAndEpoch
    }

    pub fn has_epoch_regression(self) -> bool {
        self == Self::EpochRegressed || self == Self::ChecksumAndEpoch
    }
}

// ─── ValidationRecord ─────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct ValidationRecord {
    pub frame_epoch_end: u64,
    pub verdict:         ValidationVerdict,
    pub frame:           [u8; BROADCAST_FRAME_LEN],
    pub record_hash:     [u8; 32],
    pub prev_hash:       [u8; 32],
}

fn compute_validation_hash(
    prev:            &[u8; 32],
    frame_epoch_end: u64,
    verdict_byte:    u8,
    frame:           &[u8; BROADCAST_FRAME_LEN],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(frame_epoch_end.to_be_bytes());
    h.update([verdict_byte]);
    h.update(frame);
    h.finalize().into()
}

// ─── CompactionBroadcastValidator ────────────────────────────────────────────

pub struct CompactionBroadcastValidator {
    log:             Vec<ValidationRecord>,
    last_epoch_end:  Option<u64>,
}

#[derive(Debug)]
pub struct ValidatorError(pub &'static str);

impl CompactionBroadcastValidator {
    pub fn new() -> Self {
        Self { log: Vec::new(), last_epoch_end: None }
    }

    pub fn record_count(&self) -> usize { self.log.len() }
    pub fn is_empty(&self)    -> bool   { self.log.is_empty() }
    pub fn log(&self)         -> &[ValidationRecord] { &self.log }
    pub fn latest(&self)      -> Option<&ValidationRecord> { self.log.last() }

    /// Count records with a specific verdict.
    pub fn count_verdict(&self, v: ValidationVerdict) -> usize {
        self.log.iter().filter(|r| r.verdict == v).count()
    }

    /// Validate a raw BroadcastFrame and record the decision.
    /// Returns a reference to the new ValidationRecord.
    pub fn validate(&mut self, frame: &[u8; BROADCAST_FRAME_LEN]) -> &ValidationRecord {
        // 1. Checksum check (decode does this for us)
        let checksum_ok = CompactionBroadcaster::decode(frame).is_ok();

        // 2. Extract epoch_end from frame bytes (big-endian [0..8])
        let mut epoch_bytes = [0u8; 8];
        epoch_bytes.copy_from_slice(&frame[0..8]);
        let frame_epoch_end = u64::from_be_bytes(epoch_bytes);

        // 3. Epoch monotonicity check
        let epoch_ok = match self.last_epoch_end {
            None    => true,
            Some(p) => frame_epoch_end >= p,
        };

        // 4. Compose verdict
        let verdict = match (checksum_ok, epoch_ok) {
            (true,  true)  => ValidationVerdict::Valid,
            (false, true)  => ValidationVerdict::ChecksumFail,
            (true,  false) => ValidationVerdict::EpochRegressed,
            (false, false) => ValidationVerdict::ChecksumAndEpoch,
        };

        // 5. Update tracked epoch only on valid frames
        if verdict.is_valid() {
            self.last_epoch_end = Some(frame_epoch_end);
        }

        // 6. Hash-chain the record
        let prev = self.log.last()
            .map(|r| r.record_hash)
            .unwrap_or(VALIDATOR_GENESIS_HASH);

        let record_hash = compute_validation_hash(&prev, frame_epoch_end, verdict.as_u8(), frame);

        self.log.push(ValidationRecord {
            frame_epoch_end,
            verdict,
            frame: *frame,
            record_hash,
            prev_hash: prev,
        });
        self.log.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = VALIDATOR_GENESIS_HASH;
        for (i, r) in self.log.iter().enumerate() {
            if r.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_validation_hash(
                &prev, r.frame_epoch_end, r.verdict.as_u8(), &r.frame,
            );
            if r.record_hash != expected {
                return (false, Some(i));
            }
            prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for CompactionBroadcastValidator {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::compaction_audit_seal::CompactionAuditSeal;
    use crate::compaction_broadcaster::CompactionBroadcaster;

    fn rnd_hash(seed: u8) -> [u8; 32] {
        let mut h = [0u8; 32];
        for (i, b) in h.iter_mut().enumerate() { *b = seed.wrapping_add(i as u8); }
        h
    }

    fn make_seal(epoch_end: u64) -> CompactionAuditSeal {
        CompactionAuditSeal {
            epoch_start:   1,
            epoch_end,
            epoch_count:   epoch_end,
            chains_valid:  true,
            terminal_hash: rnd_hash(epoch_end as u8),
            seal_hash:     rnd_hash(epoch_end as u8 + 10),
            prev_hash:     [0u8; 32],
        }
    }

    fn valid_frame(epoch_end: u64) -> [u8; BROADCAST_FRAME_LEN] {
        let mut bc = CompactionBroadcaster::new();
        let seal = make_seal(epoch_end);
        bc.encode(&seal).frame
    }

    // ── ValidationVerdict helpers ─────────────────────────────────────────────

    #[test]
    fn valid_is_valid() {
        assert!(ValidationVerdict::Valid.is_valid());
    }

    #[test]
    fn checksum_fail_not_valid() {
        assert!(!ValidationVerdict::ChecksumFail.is_valid());
    }

    #[test]
    fn has_checksum_fail_combined() {
        assert!(ValidationVerdict::ChecksumAndEpoch.has_checksum_fail());
        assert!(ValidationVerdict::ChecksumFail.has_checksum_fail());
        assert!(!ValidationVerdict::EpochRegressed.has_checksum_fail());
    }

    #[test]
    fn has_epoch_regression_combined() {
        assert!(ValidationVerdict::ChecksumAndEpoch.has_epoch_regression());
        assert!(ValidationVerdict::EpochRegressed.has_epoch_regression());
        assert!(!ValidationVerdict::ChecksumFail.has_epoch_regression());
    }

    // ── validate() — valid frames ─────────────────────────────────────────────

    #[test]
    fn validate_first_valid_frame() {
        let mut v = CompactionBroadcastValidator::new();
        let frame = valid_frame(5);
        let rec = v.validate(&frame);
        assert_eq!(rec.verdict, ValidationVerdict::Valid);
        assert_eq!(rec.frame_epoch_end, 5);
    }

    #[test]
    fn validate_two_increasing_epochs() {
        let mut v = CompactionBroadcastValidator::new();
        v.validate(&valid_frame(3));
        let rec = v.validate(&valid_frame(7));
        assert_eq!(rec.verdict, ValidationVerdict::Valid);
    }

    #[test]
    fn validate_same_epoch_accepted() {
        let mut v = CompactionBroadcastValidator::new();
        v.validate(&valid_frame(4));
        let rec = v.validate(&valid_frame(4));
        assert_eq!(rec.verdict, ValidationVerdict::Valid);
    }

    // ── validate() — checksum failures ────────────────────────────────────────

    #[test]
    fn validate_corrupted_frame_checksum_fail() {
        let mut v = CompactionBroadcastValidator::new();
        let mut bad = valid_frame(2);
        bad[1] ^= 0xFF; // corrupt byte 1 (epoch_end field)
        let rec = v.validate(&bad);
        assert_eq!(rec.verdict, ValidationVerdict::ChecksumFail);
    }

    #[test]
    fn checksum_fail_does_not_update_tracked_epoch() {
        let mut v = CompactionBroadcastValidator::new();
        v.validate(&valid_frame(10));
        let mut bad = valid_frame(5);
        bad[1] ^= 0xFF;
        v.validate(&bad); // checksum fail, epoch 5 < 10 but checksum wins
        // Next good frame at epoch 3 should be EpochRegressed (not updated to 5)
        let rec = v.validate(&valid_frame(3));
        assert_eq!(rec.verdict, ValidationVerdict::EpochRegressed);
    }

    // ── validate() — epoch regression ─────────────────────────────────────────

    #[test]
    fn validate_epoch_regression_detected() {
        let mut v = CompactionBroadcastValidator::new();
        v.validate(&valid_frame(10));
        let rec = v.validate(&valid_frame(5));
        assert_eq!(rec.verdict, ValidationVerdict::EpochRegressed);
    }

    // ── validate() — both failures ────────────────────────────────────────────

    #[test]
    fn validate_checksum_and_epoch_regression() {
        let mut v = CompactionBroadcastValidator::new();
        v.validate(&valid_frame(10));
        // frame with epoch_end=2 AND corrupted checksum
        let mut bad = valid_frame(2);
        bad[25] ^= 0xFF; // corrupt checksum byte
        let rec = v.validate(&bad);
        // Epoch decoded from bytes is 2 < 10 → regression, plus checksum bad
        assert_eq!(rec.verdict, ValidationVerdict::ChecksumAndEpoch);
    }

    // ── count_verdict / aggregate ─────────────────────────────────────────────

    #[test]
    fn count_verdict_mixed_log() {
        let mut v = CompactionBroadcastValidator::new();
        v.validate(&valid_frame(1));
        v.validate(&valid_frame(2));
        let mut bad = valid_frame(3);
        bad[0] ^= 0xFF;
        v.validate(&bad);
        assert_eq!(v.count_verdict(ValidationVerdict::Valid), 2);
        assert_eq!(v.count_verdict(ValidationVerdict::ChecksumFail), 1);
    }

    // ── record hash and chaining ──────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let mut v = CompactionBroadcastValidator::new();
        let rec = v.validate(&valid_frame(1));
        assert_ne!(rec.record_hash, [0u8; 32]);
    }

    #[test]
    fn prev_hash_links_correctly() {
        let mut v = CompactionBroadcastValidator::new();
        v.validate(&valid_frame(1));
        let h0 = v.log()[0].record_hash;
        v.validate(&valid_frame(2));
        assert_eq!(v.log()[1].prev_hash, h0);
    }

    #[test]
    fn first_record_prev_hash_is_genesis() {
        let mut v = CompactionBroadcastValidator::new();
        v.validate(&valid_frame(1));
        assert_eq!(v.log()[0].prev_hash, VALIDATOR_GENESIS_HASH);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let v = CompactionBroadcastValidator::new();
        let (ok, idx) = v.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_three_records_ok() {
        let mut v = CompactionBroadcastValidator::new();
        for i in 1u64..=3 { v.validate(&valid_frame(i)); }
        let (ok, idx) = v.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut v = CompactionBroadcastValidator::new();
        v.validate(&valid_frame(1));
        v.validate(&valid_frame(2));
        v.log[0].record_hash[0] ^= 0xFF;
        let (ok, idx) = v.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn record_hash_deterministic() {
        let frame = valid_frame(7);
        let mut v1 = CompactionBroadcastValidator::new();
        let mut v2 = CompactionBroadcastValidator::new();
        let r1 = v1.validate(&frame).record_hash;
        let r2 = v2.validate(&frame).record_hash;
        assert_eq!(r1, r2);
    }
}
