//! Gate 325 — Constitutional State Broadcaster (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Encodes the epoch synthesis seal (Gate 324) as a 40-byte network frame
//! for peer-to-peer broadcast of constitutional state. Closes the gossip loop:
//! constitutional verdict produced by Gates 320–324 propagates as a compact,
//! verifiable broadcast frame.
//!
//! Frame layout (40 bytes):
//!   [0..8]   epoch           (u64, big-endian)
//!   [8..16]  seal_hash_prefix (first 8 bytes of seal_hash)
//!   [16..24] gossip_hash_prefix (first 8 bytes of gossip_health_hash)
//!   [24..32] resonance_hash_prefix (first 8 bytes of resonance_hash)
//!   [32]     flags           (bit 0 = t0_consensus, bit 1 = quorum_t0)
//!   [33..40] checksum        (SHA-256(epoch‖sealhash_prefix‖flags)[0..7])
//!
//! StateFrame::encode(seal) → StateFrame
//! StateFrame::decode(bytes) → Result<StateFrame, BroadcastError>
//! StateFrame::verify_checksum() → bool
//!
//! BroadcastLog: hash-chained broadcast records.
//!   record_broadcast(), record_receipt(), consensus_received_count(), verify_chain().

use sha2::{Sha256, Digest};

pub const FRAME_SIZE: usize = 40;
pub const STATE_BROADCAST_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── Flags ────────────────────────────────────────────────────────────────────

pub const FLAG_T0_CONSENSUS: u8 = 0b0000_0001;
pub const FLAG_QUORUM_T0:    u8 = 0b0000_0010;

// ─── StateFrame ───────────────────────────────────────────────────────────────

/// 40-byte constitutional state broadcast frame.
#[derive(Debug, Clone, PartialEq)]
pub struct StateFrame {
    pub epoch:                    u64,
    pub seal_hash_prefix:         [u8; 8],
    pub gossip_hash_prefix:       [u8; 8],
    pub resonance_hash_prefix:    [u8; 8],
    pub flags:                    u8,
    pub checksum:                 [u8; 7],
}

impl StateFrame {
    /// Encode a synthesis seal as a 40-byte StateFrame.
    pub fn encode(
        epoch:              u64,
        seal_hash:          &[u8; 32],
        gossip_health_hash: &[u8; 32],
        resonance_hash:     &[u8; 32],
        t0_consensus:       bool,
        quorum_t0:          bool,
    ) -> Self {
        let mut seal_hash_prefix    = [0u8; 8];
        let mut gossip_hash_prefix  = [0u8; 8];
        let mut resonance_hash_prefix = [0u8; 8];
        seal_hash_prefix.copy_from_slice(&seal_hash[0..8]);
        gossip_hash_prefix.copy_from_slice(&gossip_health_hash[0..8]);
        resonance_hash_prefix.copy_from_slice(&resonance_hash[0..8]);

        let mut flags = 0u8;
        if t0_consensus { flags |= FLAG_T0_CONSENSUS; }
        if quorum_t0    { flags |= FLAG_QUORUM_T0; }

        let checksum = compute_checksum(epoch, &seal_hash_prefix, flags);

        Self {
            epoch,
            seal_hash_prefix,
            gossip_hash_prefix,
            resonance_hash_prefix,
            flags,
            checksum,
        }
    }

    /// Serialize to 40-byte wire format.
    pub fn to_bytes(&self) -> [u8; FRAME_SIZE] {
        let mut buf = [0u8; FRAME_SIZE];
        buf[0..8].copy_from_slice(&self.epoch.to_be_bytes());
        buf[8..16].copy_from_slice(&self.seal_hash_prefix);
        buf[16..24].copy_from_slice(&self.gossip_hash_prefix);
        buf[24..32].copy_from_slice(&self.resonance_hash_prefix);
        buf[32] = self.flags;
        buf[33..40].copy_from_slice(&self.checksum);
        buf
    }

    /// Deserialize from 40-byte wire format.
    pub fn from_bytes(bytes: &[u8; FRAME_SIZE]) -> Result<Self, BroadcastError> {
        let mut epoch_bytes = [0u8; 8];
        epoch_bytes.copy_from_slice(&bytes[0..8]);
        let epoch = u64::from_be_bytes(epoch_bytes);

        let mut seal_hash_prefix = [0u8; 8];
        seal_hash_prefix.copy_from_slice(&bytes[8..16]);

        let mut gossip_hash_prefix = [0u8; 8];
        gossip_hash_prefix.copy_from_slice(&bytes[16..24]);

        let mut resonance_hash_prefix = [0u8; 8];
        resonance_hash_prefix.copy_from_slice(&bytes[24..32]);

        let flags = bytes[32];

        let mut checksum = [0u8; 7];
        checksum.copy_from_slice(&bytes[33..40]);

        let frame = Self {
            epoch,
            seal_hash_prefix,
            gossip_hash_prefix,
            resonance_hash_prefix,
            flags,
            checksum,
        };

        if !frame.verify_checksum() {
            return Err(BroadcastError("[BROADCAST] checksum mismatch"));
        }
        Ok(frame)
    }

    /// Verify frame checksum integrity.
    pub fn verify_checksum(&self) -> bool {
        let expected = compute_checksum(self.epoch, &self.seal_hash_prefix, self.flags);
        self.checksum == expected
    }

    /// `true` iff FLAG_T0_CONSENSUS bit is set.
    pub fn t0_consensus(&self) -> bool { self.flags & FLAG_T0_CONSENSUS != 0 }

    /// `true` iff FLAG_QUORUM_T0 bit is set.
    pub fn quorum_t0(&self) -> bool { self.flags & FLAG_QUORUM_T0 != 0 }
}

// ─── Checksum ─────────────────────────────────────────────────────────────────

fn compute_checksum(epoch: u64, seal_prefix: &[u8; 8], flags: u8) -> [u8; 7] {
    let mut h = Sha256::new();
    h.update(epoch.to_be_bytes());
    h.update(seal_prefix);
    h.update([flags]);
    let digest: [u8; 32] = h.finalize().into();
    let mut out = [0u8; 7];
    out.copy_from_slice(&digest[0..7]);
    out
}

// ─── BroadcastRecord ─────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BroadcastEvent {
    Sent,
    Received,
}

/// One hash-chained broadcast log entry.
#[derive(Debug, Clone, PartialEq)]
pub struct BroadcastRecord {
    pub epoch:      u64,
    pub event:      BroadcastEvent,
    pub t0_consensus: bool,
    pub record_hash: [u8; 32],
    pub prev_hash:   [u8; 32],
}

fn compute_record_hash(
    prev:         &[u8; 32],
    epoch:        u64,
    event:        BroadcastEvent,
    t0_consensus: bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update([event as u8]);
    h.update([t0_consensus as u8]);
    h.finalize().into()
}

// ─── BroadcastLog ─────────────────────────────────────────────────────────────

/// Append-only hash-chained log of sent/received constitutional state frames.
pub struct BroadcastLog {
    records: Vec<BroadcastRecord>,
}

impl BroadcastLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }

    fn append_record(&mut self, epoch: u64, event: BroadcastEvent, t0_consensus: bool) -> BroadcastRecord {
        let prev = self.records.last()
            .map(|r| r.record_hash)
            .unwrap_or(STATE_BROADCAST_GENESIS_HASH);
        let record_hash = compute_record_hash(&prev, epoch, event, t0_consensus);
        let rec = BroadcastRecord { epoch, event, t0_consensus, record_hash, prev_hash: prev };
        self.records.push(rec.clone());
        rec
    }

    /// Log a frame transmission.
    pub fn record_broadcast(&mut self, frame: &StateFrame) -> BroadcastRecord {
        self.append_record(frame.epoch, BroadcastEvent::Sent, frame.t0_consensus())
    }

    /// Log a frame receipt.
    pub fn record_receipt(&mut self, frame: &StateFrame) -> BroadcastRecord {
        self.append_record(frame.epoch, BroadcastEvent::Received, frame.t0_consensus())
    }

    /// Count of received frames where t0_consensus was true.
    pub fn consensus_received_count(&self) -> usize {
        self.records.iter()
            .filter(|r| r.event == BroadcastEvent::Received && r.t0_consensus)
            .count()
    }

    /// Verify hash chain integrity.
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = STATE_BROADCAST_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_record_hash(&prev, r.epoch, r.event, r.t0_consensus);
            if r.record_hash != expected {
                return (false, Some(i));
            }
            prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for BroadcastLog {
    fn default() -> Self { Self::new() }
}

// ─── Error ────────────────────────────────────────────────────────────────────

#[derive(Debug)]
pub struct BroadcastError(pub &'static str);

impl std::fmt::Display for BroadcastError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.0)
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn dummy_hash(seed: u8) -> [u8; 32] {
        let mut h = [0u8; 32];
        h[0] = seed; h[31] = seed.wrapping_mul(3);
        h
    }

    fn clean_frame(epoch: u64) -> StateFrame {
        StateFrame::encode(
            epoch,
            &dummy_hash(10),
            &dummy_hash(20),
            &dummy_hash(30),
            true,
            true,
        )
    }

    // ── Encode / decode ───────────────────────────────────────────────────────

    #[test]
    fn encode_decode_roundtrip() {
        let f = clean_frame(42);
        let bytes = f.to_bytes();
        let decoded = StateFrame::from_bytes(&bytes).unwrap();
        assert_eq!(f, decoded);
    }

    #[test]
    fn frame_size_is_forty() {
        let f = clean_frame(1);
        assert_eq!(f.to_bytes().len(), FRAME_SIZE);
    }

    #[test]
    fn flags_encoded_correctly() {
        let f_both = StateFrame::encode(1, &dummy_hash(1), &dummy_hash(2), &dummy_hash(3), true, true);
        assert!(f_both.t0_consensus());
        assert!(f_both.quorum_t0());

        let f_none = StateFrame::encode(1, &dummy_hash(1), &dummy_hash(2), &dummy_hash(3), false, false);
        assert!(!f_none.t0_consensus());
        assert!(!f_none.quorum_t0());

        let f_cons_only = StateFrame::encode(1, &dummy_hash(1), &dummy_hash(2), &dummy_hash(3), true, false);
        assert!(f_cons_only.t0_consensus());
        assert!(!f_cons_only.quorum_t0());
    }

    #[test]
    fn tampered_checksum_rejected() {
        let f = clean_frame(1);
        let mut bytes = f.to_bytes();
        bytes[33] ^= 0xFF; // corrupt checksum
        assert!(StateFrame::from_bytes(&bytes).is_err());
    }

    #[test]
    fn tampered_epoch_rejected_via_checksum() {
        let f = clean_frame(1);
        let mut bytes = f.to_bytes();
        bytes[7] ^= 0x01; // corrupt epoch (last byte)
        // checksum covers epoch so decode must fail
        assert!(StateFrame::from_bytes(&bytes).is_err());
    }

    #[test]
    fn verify_checksum_valid_frame() {
        let f = clean_frame(7);
        assert!(f.verify_checksum());
    }

    // ── Determinism ───────────────────────────────────────────────────────────

    #[test]
    fn encode_deterministic_three_times() {
        let sh = dummy_hash(10);
        let gh = dummy_hash(20);
        let rh = dummy_hash(30);
        let f1 = StateFrame::encode(5, &sh, &gh, &rh, true, true);
        let f2 = StateFrame::encode(5, &sh, &gh, &rh, true, true);
        let f3 = StateFrame::encode(5, &sh, &gh, &rh, true, true);
        assert_eq!(f1.seal_hash_prefix, f2.seal_hash_prefix);
        assert_eq!(f2.seal_hash_prefix, f3.seal_hash_prefix);
        assert_eq!(f1.checksum, f2.checksum);
    }

    #[test]
    fn different_epoch_different_frame() {
        let f1 = clean_frame(1);
        let f2 = clean_frame(2);
        assert_ne!(f1.to_bytes(), f2.to_bytes());
    }

    // ── BroadcastLog ──────────────────────────────────────────────────────────

    #[test]
    fn fresh_log_empty() {
        let l = BroadcastLog::new();
        assert!(l.is_empty());
        assert_eq!(l.consensus_received_count(), 0);
    }

    #[test]
    fn record_broadcast_and_receipt() {
        let mut l = BroadcastLog::new();
        let f = clean_frame(1);
        let sent = l.record_broadcast(&f);
        let recv = l.record_receipt(&f);
        assert_eq!(sent.event, BroadcastEvent::Sent);
        assert_eq!(recv.event, BroadcastEvent::Received);
        assert_eq!(l.len(), 2);
    }

    #[test]
    fn consensus_received_count() {
        let mut l = BroadcastLog::new();
        let f_yes = clean_frame(1);
        let f_no = StateFrame::encode(2, &dummy_hash(1), &dummy_hash(2), &dummy_hash(3), false, false);
        l.record_receipt(&f_yes);
        l.record_receipt(&f_no);
        l.record_receipt(&f_yes);
        assert_eq!(l.consensus_received_count(), 2);
    }

    #[test]
    fn broadcast_log_verify_chain_ok() {
        let mut l = BroadcastLog::new();
        l.record_broadcast(&clean_frame(1));
        l.record_receipt(&clean_frame(1));
        l.record_broadcast(&clean_frame(2));
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn broadcast_log_tamper_detected() {
        let mut l = BroadcastLog::new();
        l.record_broadcast(&clean_frame(1));
        l.record_receipt(&clean_frame(2));
        l.records[1].t0_consensus = !l.records[1].t0_consensus;
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(1));
    }

    #[test]
    fn broadcast_log_chain_prev_links() {
        let mut l = BroadcastLog::new();
        let r1 = l.record_broadcast(&clean_frame(1));
        let r2 = l.record_receipt(&clean_frame(2));
        assert_eq!(r2.prev_hash, r1.record_hash);
    }
}
