//! Gate 373 — Compaction Gossip Broadcast Validator (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Validates incoming GossipBroadcastFrames (Gate 372) from peers, enforcing:
//!   1. Checksum integrity (SHA-256 over frame[0..25])
//!   2. Epoch monotonicity (each frame's epoch_end >= previous)
//! Mirrors Gate 351 for the gossip subsystem.
//!
//! GossipValidationRecord:
//!   frame_epoch_end:  u64
//!   verdict:          GossipValidationVerdict (Valid / ChecksumFail / EpochRegressed / ChecksumAndEpoch)
//!   frame:            [u8; GOSSIP_BROADCAST_FRAME_LEN]
//!   record_hash:      [u8;32]
//!   prev_hash:        [u8;32]
//!
//! record_hash = SHA-256(prev[32] ‖ frame_epoch_end_be8 ‖ verdict_byte ‖ frame[32])
//!
//! GossipBroadcastValidator: validate(frame), log(), record_count(), verify_chain().

use sha2::{Sha256, Digest};
use crate::compaction_gossip_broadcaster::{GOSSIP_BROADCAST_FRAME_LEN, GossipBroadcaster};

pub const GOSSIP_VALIDATOR_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── GossipValidationVerdict ──────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum GossipValidationVerdict {
    Valid            = 0,
    ChecksumFail     = 1,
    EpochRegressed   = 2,
    ChecksumAndEpoch = 3,
}

impl GossipValidationVerdict {
    pub fn as_u8(self) -> u8 { self as u8 }

    pub fn is_valid(self) -> bool { self == Self::Valid }

    pub fn has_checksum_fail(self) -> bool {
        self == Self::ChecksumFail || self == Self::ChecksumAndEpoch
    }

    pub fn has_epoch_regression(self) -> bool {
        self == Self::EpochRegressed || self == Self::ChecksumAndEpoch
    }
}

// ─── GossipValidationRecord ───────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipValidationRecord {
    pub frame_epoch_end: u64,
    pub verdict:         GossipValidationVerdict,
    pub frame:           [u8; GOSSIP_BROADCAST_FRAME_LEN],
    pub record_hash:     [u8; 32],
    pub prev_hash:       [u8; 32],
}

fn compute_validation_hash(
    prev:            &[u8; 32],
    frame_epoch_end: u64,
    verdict_byte:    u8,
    frame:           &[u8; GOSSIP_BROADCAST_FRAME_LEN],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(frame_epoch_end.to_be_bytes());
    h.update([verdict_byte]);
    h.update(frame);
    h.finalize().into()
}

// ─── GossipBroadcastValidator ─────────────────────────────────────────────────

pub struct GossipBroadcastValidator {
    log:            Vec<GossipValidationRecord>,
    last_epoch_end: Option<u64>,
}

impl GossipBroadcastValidator {
    pub fn new() -> Self {
        Self { log: Vec::new(), last_epoch_end: None }
    }

    pub fn record_count(&self) -> usize { self.log.len() }
    pub fn is_empty(&self)    -> bool   { self.log.is_empty() }
    pub fn log(&self)         -> &[GossipValidationRecord] { &self.log }
    pub fn latest(&self)      -> Option<&GossipValidationRecord> { self.log.last() }

    pub fn count_verdict(&self, v: GossipValidationVerdict) -> usize {
        self.log.iter().filter(|r| r.verdict == v).count()
    }

    pub fn validate(&mut self, frame: &[u8; GOSSIP_BROADCAST_FRAME_LEN]) -> &GossipValidationRecord {
        let checksum_ok = GossipBroadcaster::decode(frame).is_ok();

        let mut epoch_bytes = [0u8; 8];
        epoch_bytes.copy_from_slice(&frame[0..8]);
        let frame_epoch_end = u64::from_be_bytes(epoch_bytes);

        let epoch_ok = match self.last_epoch_end {
            None    => true,
            Some(p) => frame_epoch_end >= p,
        };

        let verdict = match (checksum_ok, epoch_ok) {
            (true,  true)  => GossipValidationVerdict::Valid,
            (false, true)  => GossipValidationVerdict::ChecksumFail,
            (true,  false) => GossipValidationVerdict::EpochRegressed,
            (false, false) => GossipValidationVerdict::ChecksumAndEpoch,
        };

        if verdict.is_valid() {
            self.last_epoch_end = Some(frame_epoch_end);
        }

        let prev = self.log.last()
            .map(|r| r.record_hash)
            .unwrap_or(GOSSIP_VALIDATOR_GENESIS_HASH);

        let record_hash = compute_validation_hash(&prev, frame_epoch_end, verdict.as_u8(), frame);

        self.log.push(GossipValidationRecord {
            frame_epoch_end,
            verdict,
            frame: *frame,
            record_hash,
            prev_hash: prev,
        });
        self.log.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_VALIDATOR_GENESIS_HASH;
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

impl Default for GossipBroadcastValidator {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::compaction_gossip_audit_seal::GossipAuditSeal;
    use crate::compaction_gossip_broadcaster::GossipBroadcaster;

    fn rnd_hash(seed: u8) -> [u8; 32] {
        let mut h = [0u8; 32];
        for (i, b) in h.iter_mut().enumerate() { *b = seed.wrapping_add(i as u8); }
        h
    }

    fn make_seal(epoch_end: u64) -> GossipAuditSeal {
        GossipAuditSeal {
            epoch_start:   1,
            epoch_end,
            epoch_count:   epoch_end,
            chains_valid:  true,
            terminal_hash: rnd_hash(epoch_end as u8),
            seal_hash:     rnd_hash(epoch_end as u8 + 10),
            prev_hash:     [0u8; 32],
        }
    }

    fn valid_frame(epoch_end: u64) -> [u8; GOSSIP_BROADCAST_FRAME_LEN] {
        let mut bc = GossipBroadcaster::new();
        let seal = make_seal(epoch_end);
        bc.encode(&seal).frame
    }

    // ── GossipValidationVerdict helpers ───────────────────────────────────────

    #[test]
    fn valid_is_valid() {
        assert!(GossipValidationVerdict::Valid.is_valid());
    }

    #[test]
    fn checksum_fail_not_valid() {
        assert!(!GossipValidationVerdict::ChecksumFail.is_valid());
    }

    #[test]
    fn has_checksum_fail_combined() {
        assert!(GossipValidationVerdict::ChecksumAndEpoch.has_checksum_fail());
        assert!(GossipValidationVerdict::ChecksumFail.has_checksum_fail());
        assert!(!GossipValidationVerdict::EpochRegressed.has_checksum_fail());
    }

    #[test]
    fn has_epoch_regression_combined() {
        assert!(GossipValidationVerdict::ChecksumAndEpoch.has_epoch_regression());
        assert!(GossipValidationVerdict::EpochRegressed.has_epoch_regression());
        assert!(!GossipValidationVerdict::ChecksumFail.has_epoch_regression());
    }

    // ── validate() — valid frames ─────────────────────────────────────────────

    #[test]
    fn validate_first_valid_frame() {
        let mut v = GossipBroadcastValidator::new();
        let frame = valid_frame(5);
        let rec = v.validate(&frame);
        assert_eq!(rec.verdict, GossipValidationVerdict::Valid);
        assert_eq!(rec.frame_epoch_end, 5);
    }

    #[test]
    fn validate_two_increasing_epochs() {
        let mut v = GossipBroadcastValidator::new();
        v.validate(&valid_frame(3));
        let rec = v.validate(&valid_frame(7));
        assert_eq!(rec.verdict, GossipValidationVerdict::Valid);
    }

    #[test]
    fn validate_same_epoch_accepted() {
        let mut v = GossipBroadcastValidator::new();
        v.validate(&valid_frame(4));
        let rec = v.validate(&valid_frame(4));
        assert_eq!(rec.verdict, GossipValidationVerdict::Valid);
    }

    // ── validate() — checksum failures ────────────────────────────────────────

    #[test]
    fn validate_corrupted_frame_checksum_fail() {
        let mut v = GossipBroadcastValidator::new();
        let mut bad = valid_frame(2);
        bad[1] ^= 0xFF;
        let rec = v.validate(&bad);
        assert_eq!(rec.verdict, GossipValidationVerdict::ChecksumFail);
    }

    #[test]
    fn checksum_fail_does_not_update_tracked_epoch() {
        let mut v = GossipBroadcastValidator::new();
        v.validate(&valid_frame(10));
        let mut bad = valid_frame(5);
        bad[1] ^= 0xFF;
        v.validate(&bad);
        let rec = v.validate(&valid_frame(3));
        assert_eq!(rec.verdict, GossipValidationVerdict::EpochRegressed);
    }

    // ── validate() — epoch regression ─────────────────────────────────────────

    #[test]
    fn validate_epoch_regression_detected() {
        let mut v = GossipBroadcastValidator::new();
        v.validate(&valid_frame(10));
        let rec = v.validate(&valid_frame(5));
        assert_eq!(rec.verdict, GossipValidationVerdict::EpochRegressed);
    }

    // ── validate() — both failures ────────────────────────────────────────────

    #[test]
    fn validate_checksum_and_epoch_regression() {
        let mut v = GossipBroadcastValidator::new();
        v.validate(&valid_frame(10));
        let mut bad = valid_frame(2);
        bad[25] ^= 0xFF;
        let rec = v.validate(&bad);
        assert_eq!(rec.verdict, GossipValidationVerdict::ChecksumAndEpoch);
    }

    // ── count_verdict / aggregate ─────────────────────────────────────────────

    #[test]
    fn count_verdict_mixed_log() {
        let mut v = GossipBroadcastValidator::new();
        v.validate(&valid_frame(1));
        v.validate(&valid_frame(2));
        let mut bad = valid_frame(3);
        bad[0] ^= 0xFF;
        v.validate(&bad);
        assert_eq!(v.count_verdict(GossipValidationVerdict::Valid), 2);
        assert_eq!(v.count_verdict(GossipValidationVerdict::ChecksumFail), 1);
    }

    // ── record hash and chaining ──────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let mut v = GossipBroadcastValidator::new();
        let rec = v.validate(&valid_frame(1));
        assert_ne!(rec.record_hash, [0u8; 32]);
    }

    #[test]
    fn prev_hash_links_correctly() {
        let mut v = GossipBroadcastValidator::new();
        v.validate(&valid_frame(1));
        let h0 = v.log()[0].record_hash;
        v.validate(&valid_frame(2));
        assert_eq!(v.log()[1].prev_hash, h0);
    }

    #[test]
    fn first_record_prev_hash_is_genesis() {
        let mut v = GossipBroadcastValidator::new();
        v.validate(&valid_frame(1));
        assert_eq!(v.log()[0].prev_hash, GOSSIP_VALIDATOR_GENESIS_HASH);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let v = GossipBroadcastValidator::new();
        let (ok, idx) = v.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_three_records_ok() {
        let mut v = GossipBroadcastValidator::new();
        for i in 1u64..=3 { v.validate(&valid_frame(i)); }
        let (ok, idx) = v.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut v = GossipBroadcastValidator::new();
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
        let mut v1 = GossipBroadcastValidator::new();
        let mut v2 = GossipBroadcastValidator::new();
        let r1 = v1.validate(&frame).record_hash;
        let r2 = v2.validate(&frame).record_hash;
        assert_eq!(r1, r2);
    }
}
