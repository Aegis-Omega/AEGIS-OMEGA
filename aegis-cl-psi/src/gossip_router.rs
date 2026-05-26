//! Gate 256 — Gossip Router: multi-hop peer routing with deduplication and TTL (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Routes GossipMessages across a peer mesh using a routing table.
//! Deduplication prevents re-broadcasting already-seen (node_id, sequence) pairs.
//! TTL (time-to-live in hops) limits propagation depth.
//!
//! RoutingTable:
//!   peers             — BTreeMap<u32, PeerEntry> (peer_id → entry)
//!   seen              — BTreeMap<(u32, u64), ()> (node_id, sequence) already routed
//!
//! PeerEntry:
//!   peer_id           — u32 (opaque peer identifier)
//!   hop_count         — u8 (distance from local node — 0 = direct peer)
//!
//! RouteDecision:
//!   Forward(Vec<u32>) — forward to these peer_ids
//!   Drop(DropReason)  — do not forward
//!
//! DropReason:
//!   AlreadySeen       — (node_id, sequence) already routed
//!   TtlExpired        — ttl == 0
//!   NoPeers           — routing table has no peers
//!   SelfMessage       — message originated from local node_id

use std::collections::BTreeMap;
use crate::gossip_broadcaster::GossipMessage;

// ─── Peer entry ───────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PeerEntry {
    pub peer_id:   u32,
    pub hop_count: u8,
}

// ─── Drop reason ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DropReason {
    AlreadySeen,
    TtlExpired,
    NoPeers,
    SelfMessage,
}

impl DropReason {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::AlreadySeen  => "already seen",
            Self::TtlExpired   => "TTL expired",
            Self::NoPeers      => "no peers",
            Self::SelfMessage  => "self message",
        }
    }
}

// ─── Route decision ───────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RouteDecision {
    Forward(Vec<u32>),
    Drop(DropReason),
}

impl RouteDecision {
    pub fn is_forward(&self) -> bool { matches!(self, Self::Forward(_)) }
    pub fn is_drop(&self) -> bool    { matches!(self, Self::Drop(_)) }

    pub fn peer_ids(&self) -> &[u32] {
        match self {
            Self::Forward(ids) => ids,
            Self::Drop(_)      => &[],
        }
    }
}

// ─── Routing table ────────────────────────────────────────────────────────────

/// Maximum TTL allowed (prevents unbounded mesh storms).
pub const MAX_TTL: u8 = 8;

#[derive(Debug, Clone)]
pub struct RoutingTable {
    local_node_id: u32,
    peers:         BTreeMap<u32, PeerEntry>,
    /// (node_id, sequence) pairs already routed — deduplication set.
    seen:          BTreeMap<(u32, u64), ()>,
}

impl RoutingTable {
    pub fn new(local_node_id: u32) -> Self {
        Self {
            local_node_id,
            peers: BTreeMap::new(),
            seen:  BTreeMap::new(),
        }
    }

    pub fn local_node_id(&self) -> u32  { self.local_node_id }
    pub fn peer_count(&self) -> usize   { self.peers.len() }
    pub fn seen_count(&self) -> usize   { self.seen.len() }

    /// Add or update a peer. Returns true if new.
    pub fn add_peer(&mut self, peer_id: u32, hop_count: u8) -> bool {
        let is_new = !self.peers.contains_key(&peer_id);
        self.peers.insert(peer_id, PeerEntry { peer_id, hop_count });
        is_new
    }

    /// Remove a peer. Returns true if it existed.
    pub fn remove_peer(&mut self, peer_id: u32) -> bool {
        self.peers.remove(&peer_id).is_some()
    }

    pub fn has_peer(&self, peer_id: u32) -> bool {
        self.peers.contains_key(&peer_id)
    }

    pub fn peers(&self) -> impl Iterator<Item = &PeerEntry> {
        self.peers.values()
    }

    /// Decide how to route a message with the given TTL.
    /// Records the message as seen if forwarded.
    pub fn route(&mut self, msg: &GossipMessage, ttl: u8) -> RouteDecision {
        // Self-originating messages are never re-broadcast.
        if msg.node_id == self.local_node_id {
            return RouteDecision::Drop(DropReason::SelfMessage);
        }

        // TTL = 0 means this message has already travelled its maximum hops.
        if ttl == 0 {
            return RouteDecision::Drop(DropReason::TtlExpired);
        }

        // Deduplication: already forwarded this (node_id, sequence)?
        let key = (msg.node_id, msg.sequence);
        if self.seen.contains_key(&key) {
            return RouteDecision::Drop(DropReason::AlreadySeen);
        }

        if self.peers.is_empty() {
            return RouteDecision::Drop(DropReason::NoPeers);
        }

        // Mark as seen before forwarding (prevent re-entry on echo).
        self.seen.insert(key, ());

        // Forward to all known peers in deterministic (BTreeMap) order.
        let peer_ids: Vec<u32> = self.peers.keys().copied().collect();
        RouteDecision::Forward(peer_ids)
    }

    /// Drain seen entries older than `keep_below_sequence` for the given node.
    /// Used for garbage collection of the dedup table.
    pub fn prune_seen(&mut self, node_id: u32, keep_below_sequence: u64) {
        self.seen.retain(|&(nid, seq), _| {
            !(nid == node_id && seq < keep_below_sequence)
        });
    }
}

// ─── Router error ─────────────────────────────────────────────────────────────

#[derive(Debug)]
pub struct RouterError(pub &'static str);

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::gossip_broadcaster::build_message;
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

    fn make_msg(node_id: u32, seq: u64) -> GossipMessage {
        let v = build_vector(seq,
            HealthVerdict::Pass, ResilienceVerdict::Stable,
            PulseVerdict::Green, StabilityGrade::A,
            MomentumDir::Stable, ConstitutionalPhase::Nominal,
            &VECTOR_GENESIS_HASH);
        let f = build_frame(seq, v, ConstitutionalPhase::Nominal,
                            MomentumDir::Stable, 0, &DASHBOARD_GENESIS_HASH);
        let p = encode(&f, AlertSeverity::None);
        build_message(node_id, seq, p)
    }

    // ── PeerEntry / DropReason ────────────────────────────────────────────────

    #[test]
    fn drop_reason_as_str() {
        assert_eq!(DropReason::AlreadySeen.as_str(), "already seen");
        assert_eq!(DropReason::TtlExpired.as_str(),  "TTL expired");
        assert_eq!(DropReason::NoPeers.as_str(),     "no peers");
        assert_eq!(DropReason::SelfMessage.as_str(), "self message");
    }

    #[test]
    fn route_decision_accessors() {
        let fwd = RouteDecision::Forward(vec![1, 2]);
        assert!(fwd.is_forward());
        assert!(!fwd.is_drop());
        assert_eq!(fwd.peer_ids(), &[1u32, 2u32]);

        let drop = RouteDecision::Drop(DropReason::NoPeers);
        assert!(drop.is_drop());
        assert!(!drop.is_forward());
        assert_eq!(drop.peer_ids(), &[] as &[u32]);
    }

    // ── RoutingTable construction ─────────────────────────────────────────────

    #[test]
    fn new_table_empty() {
        let t = RoutingTable::new(42);
        assert_eq!(t.local_node_id(), 42);
        assert_eq!(t.peer_count(), 0);
        assert_eq!(t.seen_count(), 0);
    }

    #[test]
    fn add_and_remove_peers() {
        let mut t = RoutingTable::new(1);
        assert!(t.add_peer(10, 0));   // new
        assert!(!t.add_peer(10, 0));  // already present
        assert_eq!(t.peer_count(), 1);
        assert!(t.has_peer(10));
        assert!(t.remove_peer(10));
        assert!(!t.remove_peer(10));
        assert_eq!(t.peer_count(), 0);
    }

    // ── Route decisions ───────────────────────────────────────────────────────

    #[test]
    fn no_peers_drops() {
        let mut t = RoutingTable::new(1);
        let msg = make_msg(2, 1);
        assert_eq!(t.route(&msg, 3), RouteDecision::Drop(DropReason::NoPeers));
    }

    #[test]
    fn self_message_drops() {
        let mut t = RoutingTable::new(1);
        t.add_peer(2, 0);
        let msg = make_msg(1, 1); // local_node_id == msg.node_id
        assert_eq!(t.route(&msg, 3), RouteDecision::Drop(DropReason::SelfMessage));
    }

    #[test]
    fn ttl_zero_drops() {
        let mut t = RoutingTable::new(1);
        t.add_peer(2, 0);
        let msg = make_msg(3, 1);
        assert_eq!(t.route(&msg, 0), RouteDecision::Drop(DropReason::TtlExpired));
    }

    #[test]
    fn valid_message_forwards_to_all_peers() {
        let mut t = RoutingTable::new(1);
        t.add_peer(10, 0);
        t.add_peer(20, 1);
        let msg = make_msg(2, 1);
        let decision = t.route(&msg, 3);
        assert_eq!(decision, RouteDecision::Forward(vec![10, 20]));
    }

    #[test]
    fn peer_ids_in_btreemap_order() {
        let mut t = RoutingTable::new(1);
        t.add_peer(30, 0);
        t.add_peer(10, 0);
        t.add_peer(20, 0);
        let msg = make_msg(2, 1);
        let decision = t.route(&msg, 3);
        // BTreeMap iteration is sorted ascending
        assert_eq!(decision.peer_ids(), &[10u32, 20, 30]);
    }

    #[test]
    fn already_seen_drops_on_second_route() {
        let mut t = RoutingTable::new(1);
        t.add_peer(10, 0);
        let msg = make_msg(2, 5);
        let first  = t.route(&msg, 3);
        let second = t.route(&msg, 3);
        assert!(first.is_forward());
        assert_eq!(second, RouteDecision::Drop(DropReason::AlreadySeen));
        assert_eq!(t.seen_count(), 1);
    }

    #[test]
    fn different_sequence_not_deduplicated() {
        let mut t = RoutingTable::new(1);
        t.add_peer(10, 0);
        let m1 = make_msg(2, 1);
        let m2 = make_msg(2, 2);
        assert!(t.route(&m1, 3).is_forward());
        assert!(t.route(&m2, 3).is_forward());
        assert_eq!(t.seen_count(), 2);
    }

    #[test]
    fn different_node_id_not_deduplicated() {
        let mut t = RoutingTable::new(1);
        t.add_peer(10, 0);
        let m1 = make_msg(2, 1);
        let m2 = make_msg(3, 1); // same seq, different node
        assert!(t.route(&m1, 3).is_forward());
        assert!(t.route(&m2, 3).is_forward());
        assert_eq!(t.seen_count(), 2);
    }

    // ── prune_seen ────────────────────────────────────────────────────────────

    #[test]
    fn prune_seen_removes_old_entries() {
        let mut t = RoutingTable::new(1);
        t.add_peer(10, 0);
        for seq in 1..=5u64 {
            t.route(&make_msg(2, seq), 3);
        }
        assert_eq!(t.seen_count(), 5);
        t.prune_seen(2, 4); // remove seq < 4 for node 2
        assert_eq!(t.seen_count(), 2); // seq 4 and 5 remain
    }

    #[test]
    fn prune_seen_only_affects_target_node() {
        let mut t = RoutingTable::new(1);
        t.add_peer(10, 0);
        t.route(&make_msg(2, 1), 3);
        t.route(&make_msg(3, 1), 3);
        t.prune_seen(2, 100); // prune all of node 2
        assert_eq!(t.seen_count(), 1); // node 3 seq 1 remains
    }

    // ── MAX_TTL ───────────────────────────────────────────────────────────────

    #[test]
    fn max_ttl_is_8() {
        assert_eq!(MAX_TTL, 8);
    }
}
