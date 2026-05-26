//! Gate 255 — Gossip Broadcaster: signed GossipMessage for peer broadcast (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Wraps a TelemetryPacket into a GossipMessage with node attribution and
//! a compact 8-byte MAC for tamper detection.
//!
//! GossipMessage:
//!   node_id    — u32 (opaque node identifier)
//!   sequence   — u64 (monotone per node)
//!   packet     — TelemetryPacket (32 bytes)
//!   mac        — [u8; 8] = SHA-256(node_id_be4 ‖ sequence_be8 ‖ packet_bytes)[:8]
//!
//! Total wire size: 4 + 8 + 32 + 8 = 52 bytes per message.
//!
//! GossipLog: ordered log of received messages per node_id.
//!   append(msg)     — validate MAC; append if valid + sequence strictly increasing
//!   messages()      — all messages in insertion order
//!   node_messages(id) — messages from a specific node_id
//!   latest_sequence(id) — highest sequence seen from node_id

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;
use crate::telemetry_encoder::TelemetryPacket;

// ─── Gossip message ───────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipMessage {
    pub node_id:  u32,
    pub sequence: u64,
    pub packet:   TelemetryPacket,
    pub mac:      [u8; 8],
}

impl GossipMessage {
    pub fn is_mac_valid(&self) -> bool {
        compute_mac(self.node_id, self.sequence, &self.packet) == self.mac
    }
}

fn compute_mac(node_id: u32, sequence: u64, packet: &TelemetryPacket) -> [u8; 8] {
    let mut h = Sha256::new();
    h.update(node_id.to_be_bytes());
    h.update(sequence.to_be_bytes());
    h.update(packet.as_bytes());
    let digest = h.finalize();
    digest[0..8].try_into().unwrap()
}

// ─── Build message ────────────────────────────────────────────────────────────

pub fn build_message(node_id: u32, sequence: u64, packet: TelemetryPacket) -> GossipMessage {
    let mac = compute_mac(node_id, sequence, &packet);
    GossipMessage { node_id, sequence, packet, mac }
}

// ─── Gossip log ───────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct GossipLog {
    messages:        Vec<GossipMessage>,
    /// Highest sequence seen per node_id
    node_sequences:  BTreeMap<u32, u64>,
}

#[derive(Debug)]
pub enum GossipError {
    InvalidMac,
    StaleSequence,
}

impl GossipError {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::InvalidMac    => "invalid MAC",
            Self::StaleSequence => "stale sequence",
        }
    }
}

impl GossipLog {
    pub fn new() -> Self {
        Self { messages: Vec::new(), node_sequences: BTreeMap::new() }
    }

    pub fn len(&self) -> usize { self.messages.len() }
    pub fn is_empty(&self) -> bool { self.messages.is_empty() }
    pub fn messages(&self) -> &[GossipMessage] { &self.messages }

    pub fn node_count(&self) -> usize { self.node_sequences.len() }

    /// Highest sequence seen from node_id, or None if unseen.
    pub fn latest_sequence(&self, node_id: u32) -> Option<u64> {
        self.node_sequences.get(&node_id).copied()
    }

    /// Messages from a specific node_id, in insertion order.
    pub fn node_messages(&self, node_id: u32) -> Vec<&GossipMessage> {
        self.messages.iter().filter(|m| m.node_id == node_id).collect()
    }

    /// Append a GossipMessage. Validates MAC; rejects stale/duplicate sequences.
    pub fn append(&mut self, msg: GossipMessage) -> Result<(), GossipError> {
        if !msg.is_mac_valid() {
            return Err(GossipError::InvalidMac);
        }
        if let Some(&last_seq) = self.node_sequences.get(&msg.node_id) {
            if msg.sequence <= last_seq {
                return Err(GossipError::StaleSequence);
            }
        }
        self.node_sequences.insert(msg.node_id, msg.sequence);
        self.messages.push(msg);
        Ok(())
    }
}

impl Default for GossipLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::health_aggregator::{build_vector, VECTOR_GENESIS_HASH};
    use crate::health_dashboard::{build_frame, DASHBOARD_GENESIS_HASH};
    use crate::alert_engine::AlertSeverity;
    use crate::telemetry_encoder::encode;
    use crate::swarm_health::HealthVerdict;
    use crate::resilience_watchdog::ResilienceVerdict;
    use crate::constitutional_pulse::PulseVerdict;
    use crate::coherence_stability::StabilityGrade;
    use crate::momentum_tracker::MomentumDir;
    use crate::phase_transition::ConstitutionalPhase;

    fn make_packet(epoch: u64) -> TelemetryPacket {
        let v = build_vector(epoch,
            HealthVerdict::Pass, ResilienceVerdict::Stable,
            PulseVerdict::Green, StabilityGrade::A,
            MomentumDir::Stable, ConstitutionalPhase::Nominal,
            &VECTOR_GENESIS_HASH);
        let f = build_frame(epoch, v, ConstitutionalPhase::Nominal,
                            MomentumDir::Stable, 0, &DASHBOARD_GENESIS_HASH);
        encode(&f, AlertSeverity::None)
    }

    fn msg(node_id: u32, seq: u64, epoch: u64) -> GossipMessage {
        build_message(node_id, seq, make_packet(epoch))
    }

    // ── GossipMessage ─────────────────────────────────────────────────────────

    #[test]
    fn valid_message_mac_passes() {
        let m = msg(1, 1, 10);
        assert!(m.is_mac_valid());
    }

    #[test]
    fn tampered_node_id_invalidates_mac() {
        let mut m = msg(1, 1, 10);
        m.node_id = 99;
        assert!(!m.is_mac_valid());
    }

    #[test]
    fn tampered_sequence_invalidates_mac() {
        let mut m = msg(1, 1, 10);
        m.sequence = 99;
        assert!(!m.is_mac_valid());
    }

    #[test]
    fn tampered_packet_invalidates_mac() {
        let mut m = msg(1, 1, 10);
        m.packet.0[0] ^= 0xFF;
        assert!(!m.is_mac_valid());
    }

    #[test]
    fn mac_deterministic() {
        let m1 = msg(42, 7, 5);
        let m2 = msg(42, 7, 5);
        let m3 = msg(42, 7, 5);
        assert_eq!(m1.mac, m2.mac);
        assert_eq!(m2.mac, m3.mac);
    }

    #[test]
    fn different_node_id_different_mac() {
        let p = make_packet(1);
        let m1 = build_message(1, 1, p.clone());
        let m2 = build_message(2, 1, p);
        assert_ne!(m1.mac, m2.mac);
    }

    #[test]
    fn different_sequence_different_mac() {
        let p1 = make_packet(1);
        let p2 = make_packet(1);
        let m1 = build_message(1, 1, p1);
        let m2 = build_message(1, 2, p2);
        assert_ne!(m1.mac, m2.mac);
    }

    // ── GossipLog ─────────────────────────────────────────────────────────────

    #[test]
    fn new_log_empty() {
        let l = GossipLog::new();
        assert!(l.is_empty());
        assert_eq!(l.node_count(), 0);
        assert_eq!(l.latest_sequence(1), None);
    }

    #[test]
    fn append_valid_message_succeeds() {
        let mut l = GossipLog::new();
        l.append(msg(1, 1, 10)).unwrap();
        assert_eq!(l.len(), 1);
    }

    #[test]
    fn invalid_mac_is_rejected() {
        let mut l = GossipLog::new();
        let mut bad = msg(1, 1, 10);
        bad.mac[0] ^= 0xFF;
        assert!(matches!(l.append(bad), Err(GossipError::InvalidMac)));
    }

    #[test]
    fn stale_sequence_is_rejected() {
        let mut l = GossipLog::new();
        l.append(msg(1, 5, 10)).unwrap();
        assert!(matches!(l.append(msg(1, 5, 11)), Err(GossipError::StaleSequence)));
        assert!(matches!(l.append(msg(1, 4, 12)), Err(GossipError::StaleSequence)));
    }

    #[test]
    fn strictly_increasing_sequence_accepted() {
        let mut l = GossipLog::new();
        l.append(msg(1, 1, 10)).unwrap();
        l.append(msg(1, 2, 11)).unwrap();
        l.append(msg(1, 10, 12)).unwrap();
        assert_eq!(l.len(), 3);
    }

    #[test]
    fn multiple_nodes_independent_sequences() {
        let mut l = GossipLog::new();
        l.append(msg(1, 5, 10)).unwrap();
        l.append(msg(2, 1, 11)).unwrap(); // node 2 starts at seq=1, independent
        l.append(msg(1, 6, 12)).unwrap();
        assert_eq!(l.len(), 3);
        assert_eq!(l.node_count(), 2);
    }

    #[test]
    fn latest_sequence_tracks() {
        let mut l = GossipLog::new();
        l.append(msg(7, 3, 10)).unwrap();
        l.append(msg(7, 9, 11)).unwrap();
        assert_eq!(l.latest_sequence(7), Some(9));
        assert_eq!(l.latest_sequence(99), None);
    }

    #[test]
    fn node_messages_filters_correctly() {
        let mut l = GossipLog::new();
        l.append(msg(1, 1, 10)).unwrap();
        l.append(msg(2, 1, 11)).unwrap();
        l.append(msg(1, 2, 12)).unwrap();
        assert_eq!(l.node_messages(1).len(), 2);
        assert_eq!(l.node_messages(2).len(), 1);
        assert_eq!(l.node_messages(99).len(), 0);
    }

    #[test]
    fn error_as_str() {
        assert_eq!(GossipError::InvalidMac.as_str(), "invalid MAC");
        assert_eq!(GossipError::StaleSequence.as_str(), "stale sequence");
    }
}
