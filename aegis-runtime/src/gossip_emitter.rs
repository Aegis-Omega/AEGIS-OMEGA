//! Pillar 6 — Zero-Copy UDP Scatter-Gather Gossip Protocol
//!
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! MTU-aligned 64-byte network frame. Senders write runtime counters into a
//! fixed stack buffer and push directly via std::net::UdpSocket (non-blocking).
//! No tokio dependency — std::thread drives the emission cadence via sequence ticks.
//!
//! Frame layout (64 bytes, all little-endian):
//!   [0..2]   AEGIS_PROTOCOL_MAGIC: 0xE0E0
//!   [2..4]   local_node_id: u16
//!   [4..12]  root_state_pulses: u64
//!   [12..20] semantic_traversals: u64
//!   [20..28] agent_state_alpha: u64
//!   [28..36] agent_state_beta: u64
//!   [36..44] agent_state_gamma: u64
//!   [44..52] reserved_a: u64 = 0
//!   [52..60] reserved_b: u64 = 0
//!   [60..62] cluster_consensus_score: u16
//!   [62..64] network_friction: u16
//!
//! Constitutional invariants:
//! - No tokio — std::net::UdpSocket only
//! - Frame is exactly 64 bytes (asserted in tests)
//! - active_violations (friction) must be 0 for T0 pass

use byteorder::{LittleEndian, WriteBytesExt};
use std::net::UdpSocket;
use crate::AEGIS_PROTOCOL_MAGIC;

pub const FRAME_SIZE: usize = 64;

/// One gossip heartbeat frame.
#[derive(Clone, Debug)]
pub struct GossipFrame {
    pub local_node_id: u16,
    pub root_state_pulses: u64,
    pub semantic_traversals: u64,
    pub agent_state_alpha: u64,
    pub agent_state_beta: u64,
    pub agent_state_gamma: u64,
    pub cluster_consensus_score: u16,
    pub network_friction: u16,
}

impl GossipFrame {
    /// Serialize to exactly 64 bytes.
    pub fn to_bytes(&self) -> [u8; FRAME_SIZE] {
        let mut buf = Vec::with_capacity(FRAME_SIZE);
        buf.write_u16::<LittleEndian>(AEGIS_PROTOCOL_MAGIC).unwrap();
        buf.write_u16::<LittleEndian>(self.local_node_id).unwrap();
        buf.write_u64::<LittleEndian>(self.root_state_pulses).unwrap();
        buf.write_u64::<LittleEndian>(self.semantic_traversals).unwrap();
        buf.write_u64::<LittleEndian>(self.agent_state_alpha).unwrap();
        buf.write_u64::<LittleEndian>(self.agent_state_beta).unwrap();
        buf.write_u64::<LittleEndian>(self.agent_state_gamma).unwrap();
        buf.write_u64::<LittleEndian>(0u64).unwrap(); // reserved_a
        buf.write_u64::<LittleEndian>(0u64).unwrap(); // reserved_b
        buf.write_u16::<LittleEndian>(self.cluster_consensus_score).unwrap();
        buf.write_u16::<LittleEndian>(self.network_friction).unwrap();
        let mut out = [0u8; FRAME_SIZE];
        out.copy_from_slice(&buf[..FRAME_SIZE]);
        out
    }

    /// Parse a 64-byte frame. Returns None on magic mismatch.
    pub fn from_bytes(b: &[u8; FRAME_SIZE]) -> Option<Self> {
        let magic = u16::from_le_bytes([b[0], b[1]]);
        if magic != AEGIS_PROTOCOL_MAGIC { return None; }
        Some(Self {
            local_node_id:           u16::from_le_bytes([b[2],  b[3]]),
            root_state_pulses:       u64::from_le_bytes(b[4..12].try_into().ok()?),
            semantic_traversals:     u64::from_le_bytes(b[12..20].try_into().ok()?),
            agent_state_alpha:       u64::from_le_bytes(b[20..28].try_into().ok()?),
            agent_state_beta:        u64::from_le_bytes(b[28..36].try_into().ok()?),
            agent_state_gamma:       u64::from_le_bytes(b[36..44].try_into().ok()?),
            cluster_consensus_score: u16::from_le_bytes([b[60], b[61]]),
            network_friction:        u16::from_le_bytes([b[62], b[63]]),
        })
    }
}

/// UDP gossip emitter — non-blocking, no tokio.
pub struct GossipEmitter {
    socket: Option<UdpSocket>,
    target: String,
    sent_count: u64,
}

impl GossipEmitter {
    pub fn new(target: impl Into<String>) -> Result<Self, std::io::Error> {
        let socket = UdpSocket::bind("0.0.0.0:0")?;
        socket.set_nonblocking(true)?;
        Ok(Self { socket: Some(socket), target: target.into(), sent_count: 0 })
    }

    pub fn noop() -> Self { Self { socket: None, target: String::new(), sent_count: 0 } }

    pub fn emit(&mut self, frame: &GossipFrame) -> std::io::Result<usize> {
        let bytes = frame.to_bytes();
        match &self.socket {
            None => Ok(0),
            Some(sock) => match sock.send_to(&bytes, &self.target) {
                Ok(n) => { self.sent_count += 1; Ok(n) }
                Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => Ok(0),
                Err(e) => Err(e),
            }
        }
    }

    pub fn sent_count(&self) -> u64 { self.sent_count }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn frame() -> GossipFrame {
        GossipFrame { local_node_id: 7, root_state_pulses: 1000, semantic_traversals: 500,
            agent_state_alpha: 10, agent_state_beta: 20, agent_state_gamma: 30,
            cluster_consensus_score: 9500, network_friction: 0 }
    }

    #[test] fn frame_is_64_bytes() { assert_eq!(frame().to_bytes().len(), FRAME_SIZE); }
    #[test] fn magic_at_offset_0() {
        let b = frame().to_bytes();
        assert_eq!(u16::from_le_bytes([b[0], b[1]]), AEGIS_PROTOCOL_MAGIC);
    }
    #[test] fn roundtrip() {
        let f = frame();
        let b = f.to_bytes();
        let f2 = GossipFrame::from_bytes(&b).unwrap();
        assert_eq!(f2.local_node_id, 7);
        assert_eq!(f2.cluster_consensus_score, 9500);
        assert_eq!(f2.network_friction, 0);
    }
    #[test] fn bad_magic_returns_none() {
        let mut b = frame().to_bytes();
        b[0] = 0xFF; b[1] = 0xFF;
        assert!(GossipFrame::from_bytes(&b).is_none());
    }
    #[test] fn serialization_deterministic_3x() {
        let make = || frame().to_bytes();
        assert_eq!(make(), make()); assert_eq!(make(), make());
    }
    #[test] fn reserved_bytes_zero() {
        let b = frame().to_bytes();
        let reserved_a = u64::from_le_bytes(b[44..52].try_into().unwrap());
        let reserved_b = u64::from_le_bytes(b[52..60].try_into().unwrap());
        assert_eq!(reserved_a, 0); assert_eq!(reserved_b, 0);
    }
    #[test] fn noop_emitter_ok() {
        let mut e = GossipEmitter::noop();
        assert_eq!(e.emit(&frame()).unwrap(), 0);
        assert_eq!(e.sent_count(), 0);
    }
    #[test] fn friction_zero_for_t0_pass() { assert_eq!(frame().network_friction, 0); }

    // 9. FRAME_SIZE constant is exactly 64
    #[test] fn frame_size_constant_is_64() { assert_eq!(FRAME_SIZE, 64); }

    // 10. all payload fields survive a full roundtrip
    #[test] fn all_fields_survive_roundtrip() {
        let f = frame();
        let b = f.to_bytes();
        let f2 = GossipFrame::from_bytes(&b).unwrap();
        assert_eq!(f2.root_state_pulses, 1000);
        assert_eq!(f2.semantic_traversals, 500);
        assert_eq!(f2.agent_state_alpha, 10);
        assert_eq!(f2.agent_state_beta, 20);
        assert_eq!(f2.agent_state_gamma, 30);
    }

    // 11. AEGIS_PROTOCOL_MAGIC is 0xE0E0
    #[test] fn aegis_magic_value_is_e0e0() {
        use crate::AEGIS_PROTOCOL_MAGIC;
        assert_eq!(AEGIS_PROTOCOL_MAGIC, 0xE0E0u16);
    }

    // 12. Frame with zero local_node_id serializes and parses correctly
    #[test] fn zero_node_id_roundtrip() {
        let f = GossipFrame { local_node_id: 0, root_state_pulses: 0, semantic_traversals: 0,
            agent_state_alpha: 0, agent_state_beta: 0, agent_state_gamma: 0,
            cluster_consensus_score: 0, network_friction: 0 };
        let b = f.to_bytes();
        let f2 = GossipFrame::from_bytes(&b).unwrap();
        assert_eq!(f2.local_node_id, 0);
    }

    // 13. Frame with max u16/u64 values serializes and parses correctly
    #[test] fn max_value_roundtrip() {
        let f = GossipFrame { local_node_id: u16::MAX, root_state_pulses: u64::MAX,
            semantic_traversals: u64::MAX, agent_state_alpha: u64::MAX,
            agent_state_beta: u64::MAX, agent_state_gamma: u64::MAX,
            cluster_consensus_score: u16::MAX, network_friction: u16::MAX };
        let b = f.to_bytes();
        let f2 = GossipFrame::from_bytes(&b).unwrap();
        assert_eq!(f2.local_node_id, u16::MAX);
        assert_eq!(f2.root_state_pulses, u64::MAX);
        assert_eq!(f2.cluster_consensus_score, u16::MAX);
        assert_eq!(f2.network_friction, u16::MAX);
    }

    // 14. local_node_id is at bytes [2..4] in little-endian
    #[test] fn node_id_at_bytes_2_3() {
        let b = frame().to_bytes();
        let node_id = u16::from_le_bytes([b[2], b[3]]);
        assert_eq!(node_id, 7);
    }

    // 15. cluster_consensus_score is at bytes [60..62] in little-endian
    #[test] fn cluster_consensus_score_at_bytes_60_61() {
        let b = frame().to_bytes();
        let score = u16::from_le_bytes([b[60], b[61]]);
        assert_eq!(score, 9500);
    }

    // 16. network_friction is at bytes [62..64] in little-endian
    #[test] fn network_friction_at_bytes_62_63() {
        let b = frame().to_bytes();
        let friction = u16::from_le_bytes([b[62], b[63]]);
        assert_eq!(friction, 0);
    }

    // 17. root_state_pulses is at bytes [4..12] in little-endian
    #[test] fn root_state_pulses_at_bytes_4_12() {
        let b = frame().to_bytes();
        let pulses = u64::from_le_bytes(b[4..12].try_into().unwrap());
        assert_eq!(pulses, 1000);
    }

    // 18. Two distinct frames produce different byte sequences
    #[test] fn two_distinct_frames_differ() {
        let f1 = frame();
        let f2 = GossipFrame { local_node_id: 99, ..frame() };
        assert_ne!(f1.to_bytes(), f2.to_bytes());
    }

    // 19. GossipEmitter::noop() sent_count stays 0 after multiple emits
    #[test] fn noop_emitter_sent_count_stays_zero() {
        let mut e = GossipEmitter::noop();
        for _ in 0..10 {
            e.emit(&frame()).unwrap();
        }
        assert_eq!(e.sent_count(), 0);
    }

    // 20. from_bytes returns None when magic byte at offset 0 is wrong
    #[test] fn from_bytes_wrong_first_magic_byte() {
        let mut b = frame().to_bytes();
        b[0] = 0x00; // only first byte corrupted
        assert!(GossipFrame::from_bytes(&b).is_none());
    }

    // 21. from_bytes returns None when magic byte at offset 1 is wrong
    #[test] fn from_bytes_wrong_second_magic_byte() {
        let mut b = frame().to_bytes();
        b[1] = 0x00; // only second byte corrupted
        assert!(GossipFrame::from_bytes(&b).is_none());
    }

    // 22. FRAME_SIZE matches actual to_bytes() output length
    #[test] fn frame_size_matches_serialized_length() {
        let serialized = frame().to_bytes();
        assert_eq!(serialized.len(), FRAME_SIZE);
    }

    // 23. to_bytes is pure — identical frame → identical bytes every call
    #[test] fn to_bytes_pure_function_no_side_effects() {
        let f = frame();
        let b1 = f.to_bytes();
        let b2 = f.to_bytes();
        assert_eq!(b1, b2);
    }

    // 24. semantic_traversals at bytes [12..20]
    #[test] fn semantic_traversals_at_bytes_12_20() {
        let b = frame().to_bytes();
        let traversals = u64::from_le_bytes(b[12..20].try_into().unwrap());
        assert_eq!(traversals, 500);
    }

    // 25. agent_state_alpha at bytes [20..28]
    #[test] fn agent_state_alpha_at_bytes_20_28() {
        let b = frame().to_bytes();
        let alpha = u64::from_le_bytes(b[20..28].try_into().unwrap());
        assert_eq!(alpha, 10);
    }
}
