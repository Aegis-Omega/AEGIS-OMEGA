//! Gate 372 — Compaction Gossip Broadcaster (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Encodes a GossipAuditSeal (Gate 371) into a compact 32-byte network
//! frame for peer broadcast. Mirrors Gate 350 for the gossip subsystem.
//!
//! BroadcastFrame layout (32 bytes):
//!   [0..8]   epoch_end (u64 big-endian)
//!   [8..16]  epoch_count (u64 big-endian)
//!   [16..17] chains_valid (1 byte: 0x01=valid, 0x00=invalid)
//!   [17..21] seal_hash prefix (first 4 bytes)
//!   [21..25] terminal_hash prefix (first 4 bytes)
//!   [25..32] checksum (SHA-256(epoch_end‖epoch_count‖chains_valid‖seal_prefix‖terminal_prefix)[0..7])
//!
//! GossipBroadcastRecord: hash-chained records.
//!   record_hash = SHA-256(prev[32] ‖ frame[32] ‖ epoch_end_be8)
//!
//! GossipBroadcaster: encode(seal), decode(frame), frame_count(), verify_chain().

use sha2::{Sha256, Digest};
use crate::compaction_gossip_audit_seal::GossipAuditSeal;

pub const GOSSIP_BROADCAST_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const GOSSIP_BROADCAST_FRAME_LEN: usize = 32;

// ─── GossipBroadcastRecord ────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipBroadcastRecord {
    pub epoch_end:    u64,
    pub frame:        [u8; GOSSIP_BROADCAST_FRAME_LEN],
    pub record_hash:  [u8; 32],
    pub prev_hash:    [u8; 32],
}

fn encode_frame(seal: &GossipAuditSeal) -> [u8; GOSSIP_BROADCAST_FRAME_LEN] {
    let mut frame = [0u8; GOSSIP_BROADCAST_FRAME_LEN];

    frame[0..8].copy_from_slice(&seal.epoch_end.to_be_bytes());
    frame[8..16].copy_from_slice(&seal.epoch_count.to_be_bytes());
    frame[16] = seal.chains_valid as u8;
    frame[17..21].copy_from_slice(&seal.seal_hash[0..4]);
    frame[21..25].copy_from_slice(&seal.terminal_hash[0..4]);

    let mut h = Sha256::new();
    h.update(&frame[0..25]);
    let cs: [u8; 32] = h.finalize().into();
    frame[25..32].copy_from_slice(&cs[0..7]);

    frame
}

fn compute_record_hash(prev: &[u8; 32], frame: &[u8; 32], epoch_end: u64) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(frame);
    h.update(epoch_end.to_be_bytes());
    h.finalize().into()
}

// ─── GossipBroadcaster ────────────────────────────────────────────────────────

pub struct GossipBroadcaster {
    log: Vec<GossipBroadcastRecord>,
}

#[derive(Debug, PartialEq)]
pub struct GossipDecodedFrame {
    pub epoch_end:       u64,
    pub epoch_count:     u64,
    pub chains_valid:    bool,
    pub seal_prefix:     [u8; 4],
    pub terminal_prefix: [u8; 4],
}

#[derive(Debug)]
pub struct GossipBroadcastError(pub &'static str);

impl GossipBroadcaster {
    pub fn new() -> Self { Self { log: Vec::new() } }

    pub fn frame_count(&self) -> usize { self.log.len() }
    pub fn is_empty(&self)    -> bool  { self.log.is_empty() }
    pub fn records(&self)     -> &[GossipBroadcastRecord] { &self.log }
    pub fn latest(&self)      -> Option<&GossipBroadcastRecord> { self.log.last() }

    pub fn encode(&mut self, seal: &GossipAuditSeal) -> &GossipBroadcastRecord {
        let frame = encode_frame(seal);
        let prev = self.log.last()
            .map(|r| r.record_hash)
            .unwrap_or(GOSSIP_BROADCAST_GENESIS_HASH);
        let record_hash = compute_record_hash(&prev, &frame, seal.epoch_end);
        self.log.push(GossipBroadcastRecord {
            epoch_end: seal.epoch_end,
            frame,
            record_hash,
            prev_hash: prev,
        });
        self.log.last().unwrap()
    }

    pub fn decode(frame: &[u8; GOSSIP_BROADCAST_FRAME_LEN]) -> Result<GossipDecodedFrame, GossipBroadcastError> {
        let mut h = Sha256::new();
        h.update(&frame[0..25]);
        let cs: [u8; 32] = h.finalize().into();
        if frame[25..32] != cs[0..7] {
            return Err(GossipBroadcastError("[GOSSIP_BROADCAST] Checksum mismatch"));
        }

        let mut epoch_end_bytes = [0u8; 8];
        epoch_end_bytes.copy_from_slice(&frame[0..8]);
        let mut epoch_count_bytes = [0u8; 8];
        epoch_count_bytes.copy_from_slice(&frame[8..16]);

        let mut sp = [0u8; 4];
        sp.copy_from_slice(&frame[17..21]);
        let mut tp = [0u8; 4];
        tp.copy_from_slice(&frame[21..25]);

        Ok(GossipDecodedFrame {
            epoch_end:       u64::from_be_bytes(epoch_end_bytes),
            epoch_count:     u64::from_be_bytes(epoch_count_bytes),
            chains_valid:    frame[16] != 0,
            seal_prefix:     sp,
            terminal_prefix: tp,
        })
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_BROADCAST_GENESIS_HASH;
        for (i, r) in self.log.iter().enumerate() {
            if r.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_record_hash(&prev, &r.frame, r.epoch_end);
            if r.record_hash != expected {
                return (false, Some(i));
            }
            prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for GossipBroadcaster {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn rnd_hash(seed: u8) -> [u8; 32] {
        let mut h = [0u8; 32];
        for (i, b) in h.iter_mut().enumerate() { *b = seed.wrapping_add(i as u8); }
        h
    }

    fn make_seal(epoch_end: u64, chains_valid: bool) -> GossipAuditSeal {
        GossipAuditSeal {
            epoch_start:   1,
            epoch_end,
            epoch_count:   epoch_end,
            chains_valid,
            terminal_hash: rnd_hash(epoch_end as u8),
            seal_hash:     rnd_hash(epoch_end as u8 + 10),
            prev_hash:     [0u8; 32],
        }
    }

    // ── encode / decode round-trip ────────────────────────────────────────────

    #[test]
    fn encode_produces_32_bytes() {
        let seal = make_seal(5, true);
        let mut bc = GossipBroadcaster::new();
        let rec = bc.encode(&seal);
        assert_eq!(rec.frame.len(), GOSSIP_BROADCAST_FRAME_LEN);
    }

    #[test]
    fn decode_round_trip_valid_seal() {
        let seal = make_seal(7, true);
        let mut bc = GossipBroadcaster::new();
        let rec = bc.encode(&seal);
        let decoded = GossipBroadcaster::decode(&rec.frame).unwrap();
        assert_eq!(decoded.epoch_end, 7);
        assert_eq!(decoded.epoch_count, 7);
        assert!(decoded.chains_valid);
        assert_eq!(decoded.seal_prefix, seal.seal_hash[0..4]);
        assert_eq!(decoded.terminal_prefix, seal.terminal_hash[0..4]);
    }

    #[test]
    fn decode_chains_invalid_seal() {
        let seal = make_seal(3, false);
        let mut bc = GossipBroadcaster::new();
        let rec = bc.encode(&seal);
        let decoded = GossipBroadcaster::decode(&rec.frame).unwrap();
        assert!(!decoded.chains_valid);
    }

    #[test]
    fn decode_checksum_failure_on_tamper() {
        let seal = make_seal(4, true);
        let mut bc = GossipBroadcaster::new();
        let rec = bc.encode(&seal).clone();
        let mut bad_frame = rec.frame;
        bad_frame[0] ^= 0xFF;
        assert!(GossipBroadcaster::decode(&bad_frame).is_err());
    }

    // ── Record-level operations ───────────────────────────────────────────────

    #[test]
    fn record_hash_is_nonzero() {
        let seal = make_seal(1, true);
        let mut bc = GossipBroadcaster::new();
        let rec = bc.encode(&seal);
        assert_ne!(rec.record_hash, [0u8; 32]);
    }

    #[test]
    fn epoch_end_stored_in_record() {
        let seal = make_seal(12, true);
        let mut bc = GossipBroadcaster::new();
        bc.encode(&seal);
        assert_eq!(bc.latest().unwrap().epoch_end, 12);
    }

    #[test]
    fn encode_deterministic() {
        let seal = make_seal(9, true);
        let mut bc1 = GossipBroadcaster::new();
        let mut bc2 = GossipBroadcaster::new();
        let r1 = bc1.encode(&seal).clone();
        let r2 = bc2.encode(&seal).clone();
        assert_eq!(r1.frame, r2.frame);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    // ── Chain integrity ───────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let bc = GossipBroadcaster::new();
        let (ok, idx) = bc.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_three_records_ok() {
        let mut bc = GossipBroadcaster::new();
        for i in 1u64..=3 { bc.encode(&make_seal(i, true)); }
        let (ok, idx) = bc.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut bc = GossipBroadcaster::new();
        bc.encode(&make_seal(1, true));
        bc.encode(&make_seal(2, true));
        bc.log[0].record_hash[0] ^= 0xFF;
        let (ok, idx) = bc.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn prev_hash_links_correctly() {
        let mut bc = GossipBroadcaster::new();
        bc.encode(&make_seal(1, true));
        let h0 = bc.log[0].record_hash;
        bc.encode(&make_seal(2, false));
        assert_eq!(bc.log[1].prev_hash, h0);
    }
}
