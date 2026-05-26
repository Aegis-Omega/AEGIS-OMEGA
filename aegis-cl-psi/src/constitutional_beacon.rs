//! Gate 259 — Constitutional Beacon: 16-byte self-broadcast frame (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Each node periodically broadcasts a BeaconFrame advertising its current
//! constitutional state. Compact 16-byte wire format for efficient mesh propagation.
//!
//! BeaconFrame layout (16 bytes):
//!   [0..8]   epoch as u64 big-endian
//!   [8]      node_id_byte = (node_id >> 24) as u8 (top byte)
//!   [9]      ConstitutionalPhase as u8
//!   [10]     capabilities bitmask (from peer_manifest::cap)
//!   [11]     quorum_flag: 1 if operational quorum reached, 0 otherwise
//!   [12..16] SHA-256(bytes[0..12])[:4] — 4-byte integrity checksum
//!
//! BeaconLog: ordered sequence of emitted beacons; hash-chained for tamper evidence.
//! beacon_hash = SHA-256(prev_hash ‖ frame_bytes[16])
//!
//! Total wire size: 16 bytes per beacon.

use sha2::{Sha256, Digest};
use crate::phase_transition::ConstitutionalPhase;

// ─── Beacon frame ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct BeaconFrame(pub [u8; 16]);

impl BeaconFrame {
    pub fn as_bytes(&self) -> &[u8; 16] { &self.0 }

    pub fn epoch(&self) -> u64 {
        u64::from_be_bytes(self.0[0..8].try_into().unwrap())
    }

    pub fn node_id_byte(&self) -> u8 { self.0[8] }

    pub fn phase(&self) -> Option<ConstitutionalPhase> {
        decode_phase(self.0[9])
    }

    pub fn capabilities(&self) -> u8 { self.0[10] }

    pub fn quorum_flag(&self) -> bool { self.0[11] != 0 }

    pub fn checksum(&self) -> [u8; 4] {
        self.0[12..16].try_into().unwrap()
    }

    pub fn is_checksum_valid(&self) -> bool {
        beacon_checksum(&self.0[0..12]) == self.checksum()
    }
}

fn beacon_checksum(data: &[u8]) -> [u8; 4] {
    let digest = Sha256::digest(data);
    digest[0..4].try_into().unwrap()
}

fn decode_phase(b: u8) -> Option<ConstitutionalPhase> {
    match b {
        0 => Some(ConstitutionalPhase::Nominal),
        1 => Some(ConstitutionalPhase::Degraded),
        2 => Some(ConstitutionalPhase::Recovery),
        3 => Some(ConstitutionalPhase::Critical),
        _ => None,
    }
}

// ─── Build beacon frame ───────────────────────────────────────────────────────

pub fn build_beacon(
    node_id:      u32,
    epoch:        u64,
    phase:        ConstitutionalPhase,
    capabilities: u8,
    quorum:       bool,
) -> BeaconFrame {
    let mut buf = [0u8; 16];
    buf[0..8].copy_from_slice(&epoch.to_be_bytes());
    buf[8]  = (node_id >> 24) as u8;
    buf[9]  = phase.as_u8();
    buf[10] = capabilities;
    buf[11] = if quorum { 1 } else { 0 };
    let cs = beacon_checksum(&buf[0..12]);
    buf[12..16].copy_from_slice(&cs);
    BeaconFrame(buf)
}

// ─── Beacon record (hash-chained) ─────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct BeaconRecord {
    pub node_id:      u32,
    pub frame:        BeaconFrame,
    pub beacon_hash:  [u8; 32],
    pub prev_hash:    [u8; 32],
}

pub const BEACON_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_beacon_hash(prev: &[u8; 32], frame: &BeaconFrame) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(frame.as_bytes());
    h.finalize().into()
}

// ─── Beacon log ───────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct BeaconLog {
    records: Vec<BeaconRecord>,
}

#[derive(Debug)]
pub enum BeaconError {
    InvalidChecksum,
    StaleEpoch,
}

impl BeaconError {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::InvalidChecksum => "invalid checksum",
            Self::StaleEpoch      => "stale epoch",
        }
    }
}

impl BeaconLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self) -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool { self.records.is_empty() }
    pub fn records(&self) -> &[BeaconRecord] { &self.records }

    pub fn latest(&self) -> Option<&BeaconRecord> { self.records.last() }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last()
            .map(|r| r.beacon_hash)
            .unwrap_or(BEACON_GENESIS_HASH)
    }

    /// Append a beacon frame. Validates checksum; rejects stale epochs.
    pub fn append(
        &mut self,
        node_id: u32,
        frame:   BeaconFrame,
    ) -> Result<&BeaconRecord, BeaconError> {
        if !frame.is_checksum_valid() {
            return Err(BeaconError::InvalidChecksum);
        }
        if let Some(last) = self.records.last() {
            if frame.epoch() <= last.frame.epoch() {
                return Err(BeaconError::StaleEpoch);
            }
        }
        let prev_hash  = self.last_hash();
        let beacon_hash = compute_beacon_hash(&prev_hash, &frame);
        self.records.push(BeaconRecord { node_id, frame, beacon_hash, prev_hash });
        Ok(self.records.last().unwrap())
    }

    /// Verify full hash chain. Returns (is_valid, first_broken_index).
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = BEACON_GENESIS_HASH;
        for (i, rec) in self.records.iter().enumerate() {
            if rec.prev_hash != expected_prev {
                return (false, Some(i));
            }
            let recomputed = compute_beacon_hash(&rec.prev_hash, &rec.frame);
            if recomputed != rec.beacon_hash {
                return (false, Some(i));
            }
            expected_prev = rec.beacon_hash;
        }
        (true, None)
    }
}

impl Default for BeaconLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::peer_manifest::cap;

    fn nominal_beacon(node_id: u32, epoch: u64) -> BeaconFrame {
        build_beacon(node_id, epoch, ConstitutionalPhase::Nominal, cap::ALL, true)
    }

    // ── BeaconFrame ──────────────────────────────────────────────────────────

    #[test]
    fn beacon_is_16_bytes() {
        let f = nominal_beacon(1, 10);
        assert_eq!(f.as_bytes().len(), 16);
    }

    #[test]
    fn epoch_roundtrips() {
        let f = nominal_beacon(1, 42);
        assert_eq!(f.epoch(), 42);
    }

    #[test]
    fn phase_roundtrips() {
        let f = build_beacon(1, 1, ConstitutionalPhase::Degraded, cap::GOSSIP, false);
        assert_eq!(f.phase(), Some(ConstitutionalPhase::Degraded));
    }

    #[test]
    fn capabilities_roundtrip() {
        let f = build_beacon(1, 1, ConstitutionalPhase::Nominal, cap::GOSSIP | cap::RELAY, true);
        assert_eq!(f.capabilities(), cap::GOSSIP | cap::RELAY);
    }

    #[test]
    fn quorum_flag_roundtrips() {
        let yes = build_beacon(1, 1, ConstitutionalPhase::Nominal, cap::ALL, true);
        let no  = build_beacon(1, 1, ConstitutionalPhase::Nominal, cap::ALL, false);
        assert!(yes.quorum_flag());
        assert!(!no.quorum_flag());
    }

    #[test]
    fn checksum_valid() {
        let f = nominal_beacon(1, 5);
        assert!(f.is_checksum_valid());
    }

    #[test]
    fn tampered_epoch_fails_checksum() {
        let mut f = nominal_beacon(1, 5);
        f.0[0] ^= 0xFF;
        assert!(!f.is_checksum_valid());
    }

    #[test]
    fn tampered_phase_fails_checksum() {
        let mut f = nominal_beacon(1, 5);
        f.0[9] ^= 0xFF;
        assert!(!f.is_checksum_valid());
    }

    #[test]
    fn beacon_deterministic() {
        let f1 = nominal_beacon(7, 3);
        let f2 = nominal_beacon(7, 3);
        let f3 = nominal_beacon(7, 3);
        assert_eq!(f1, f2);
        assert_eq!(f2, f3);
    }

    #[test]
    fn different_epoch_different_frame() {
        let f1 = nominal_beacon(1, 1);
        let f2 = nominal_beacon(1, 2);
        assert_ne!(f1, f2);
    }

    // ── BeaconLog ────────────────────────────────────────────────────────────

    #[test]
    fn new_log_empty() {
        let l = BeaconLog::new();
        assert!(l.is_empty());
        assert_eq!(l.last_hash(), BEACON_GENESIS_HASH);
    }

    #[test]
    fn append_valid_beacon() {
        let mut l = BeaconLog::new();
        l.append(1, nominal_beacon(1, 1)).unwrap();
        assert_eq!(l.len(), 1);
    }

    #[test]
    fn invalid_checksum_rejected() {
        let mut l = BeaconLog::new();
        let mut bad = nominal_beacon(1, 1);
        bad.0[12] ^= 0xFF;
        assert!(matches!(l.append(1, bad), Err(BeaconError::InvalidChecksum)));
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut l = BeaconLog::new();
        l.append(1, nominal_beacon(1, 5)).unwrap();
        assert!(matches!(l.append(1, nominal_beacon(1, 5)), Err(BeaconError::StaleEpoch)));
        assert!(matches!(l.append(1, nominal_beacon(1, 4)), Err(BeaconError::StaleEpoch)));
    }

    #[test]
    fn chain_links_correctly() {
        let mut l = BeaconLog::new();
        l.append(1, nominal_beacon(1, 1)).unwrap();
        l.append(1, nominal_beacon(1, 2)).unwrap();
        assert_eq!(l.records()[1].prev_hash, l.records()[0].beacon_hash);
    }

    #[test]
    fn verify_chain_valid() {
        let mut l = BeaconLog::new();
        for e in 1..=5u64 {
            l.append(1, nominal_beacon(1, e)).unwrap();
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    #[test]
    fn tampered_record_fails_chain() {
        let mut l = BeaconLog::new();
        l.append(1, nominal_beacon(1, 1)).unwrap();
        l.append(1, nominal_beacon(1, 2)).unwrap();
        l.records[0].beacon_hash[0] ^= 0xFF;
        let (valid, broken) = l.verify_chain();
        assert!(!valid);
        assert_eq!(broken, Some(0));
    }

    #[test]
    fn error_as_str() {
        assert_eq!(BeaconError::InvalidChecksum.as_str(), "invalid checksum");
        assert_eq!(BeaconError::StaleEpoch.as_str(),      "stale epoch");
    }
}
