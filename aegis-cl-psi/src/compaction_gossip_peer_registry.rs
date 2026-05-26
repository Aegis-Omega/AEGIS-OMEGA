//! Gate 375 — Compaction Gossip Peer Registry (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Maintains the canonical set of known broadcast peers for the gossip
//! subsystem. Each peer is identified by a u64 peer_id and carries a 32-byte
//! public fingerprint (opaque — no PKI assumed at T2).
//! Mirrors Gate 353 for the gossip subsystem.
//!
//! GossipPeerRecord:
//!   peer_id:      u64
//!   fingerprint:  [u8;32]  — opaque peer identity (e.g. public key hash)
//!   admitted_at:  u64      — epoch at which the peer was admitted
//!
//! GossipRegistryEvent (hash-chained log):
//!   kind:         GossipRegistryEventKind (Admitted / Evicted)
//!   peer_id:      u64
//!   epoch:        u64
//!   fingerprint:  [u8;32]
//!   event_hash:   [u8;32]
//!   prev_hash:    [u8;32]
//!
//! event_hash = SHA-256(prev[32] ‖ kind_byte ‖ peer_id_be8 ‖ epoch_be8 ‖ fingerprint[32])
//!
//! GossipPeerRegistry: admit(peer_id, fingerprint, epoch),
//!   evict(peer_id, epoch), contains(peer_id), get(peer_id),
//!   peer_count(), events(), verify_chain().

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const GOSSIP_REGISTRY_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── GossipRegistryEventKind ──────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum GossipRegistryEventKind {
    Admitted = 0,
    Evicted  = 1,
}

impl GossipRegistryEventKind {
    pub fn as_u8(self) -> u8 { self as u8 }
}

// ─── GossipPeerRecord ─────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipPeerRecord {
    pub peer_id:     u64,
    pub fingerprint: [u8; 32],
    pub admitted_at: u64,
}

// ─── GossipRegistryEvent ─────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipRegistryEvent {
    pub kind:        GossipRegistryEventKind,
    pub peer_id:     u64,
    pub epoch:       u64,
    pub fingerprint: [u8; 32],
    pub event_hash:  [u8; 32],
    pub prev_hash:   [u8; 32],
}

fn compute_gossip_registry_hash(
    prev:        &[u8; 32],
    kind:        GossipRegistryEventKind,
    peer_id:     u64,
    epoch:       u64,
    fingerprint: &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update([kind.as_u8()]);
    h.update(peer_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update(fingerprint);
    h.finalize().into()
}

// ─── GossipPeerRegistry ───────────────────────────────────────────────────────

pub struct GossipPeerRegistry {
    peers:  BTreeMap<u64, GossipPeerRecord>,
    events: Vec<GossipRegistryEvent>,
}

#[derive(Debug)]
pub struct GossipRegistryError(pub &'static str);

impl GossipPeerRegistry {
    pub fn new() -> Self {
        Self { peers: BTreeMap::new(), events: Vec::new() }
    }

    pub fn peer_count(&self)  -> usize { self.peers.len() }
    pub fn event_count(&self) -> usize { self.events.len() }
    pub fn events(&self)      -> &[GossipRegistryEvent] { &self.events }
    pub fn is_empty(&self)    -> bool  { self.peers.is_empty() }

    pub fn contains(&self, peer_id: u64) -> bool {
        self.peers.contains_key(&peer_id)
    }

    pub fn get(&self, peer_id: u64) -> Option<&GossipPeerRecord> {
        self.peers.get(&peer_id)
    }

    /// Admit a peer. Returns Err if already present.
    pub fn admit(
        &mut self,
        peer_id:     u64,
        fingerprint: [u8; 32],
        epoch:       u64,
    ) -> Result<&GossipRegistryEvent, GossipRegistryError> {
        if self.peers.contains_key(&peer_id) {
            return Err(GossipRegistryError("[GOSSIP_REGISTRY] Peer already admitted"));
        }
        self.peers.insert(peer_id, GossipPeerRecord { peer_id, fingerprint, admitted_at: epoch });
        Ok(self.push_event(GossipRegistryEventKind::Admitted, peer_id, epoch, fingerprint))
    }

    /// Evict a peer. Returns Err if not present.
    pub fn evict(
        &mut self,
        peer_id: u64,
        epoch:   u64,
    ) -> Result<&GossipRegistryEvent, GossipRegistryError> {
        let fingerprint = self.peers.remove(&peer_id)
            .ok_or(GossipRegistryError("[GOSSIP_REGISTRY] Peer not found"))?
            .fingerprint;
        Ok(self.push_event(GossipRegistryEventKind::Evicted, peer_id, epoch, fingerprint))
    }

    fn push_event(
        &mut self,
        kind:        GossipRegistryEventKind,
        peer_id:     u64,
        epoch:       u64,
        fingerprint: [u8; 32],
    ) -> &GossipRegistryEvent {
        let prev = self.events.last()
            .map(|e| e.event_hash)
            .unwrap_or(GOSSIP_REGISTRY_GENESIS_HASH);

        let event_hash = compute_gossip_registry_hash(&prev, kind, peer_id, epoch, &fingerprint);

        self.events.push(GossipRegistryEvent {
            kind,
            peer_id,
            epoch,
            fingerprint,
            event_hash,
            prev_hash: prev,
        });
        self.events.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_REGISTRY_GENESIS_HASH;
        for (i, e) in self.events.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_gossip_registry_hash(
                &prev, e.kind, e.peer_id, e.epoch, &e.fingerprint,
            );
            if e.event_hash != expected {
                return (false, Some(i));
            }
            prev = e.event_hash;
        }
        (true, None)
    }
}

impl Default for GossipPeerRegistry {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn fp(seed: u8) -> [u8; 32] {
        let mut f = [0u8; 32];
        for (i, b) in f.iter_mut().enumerate() { *b = seed.wrapping_add(i as u8); }
        f
    }

    // ── admit ─────────────────────────────────────────────────────────────────

    #[test]
    fn admit_single_peer() {
        let mut r = GossipPeerRegistry::new();
        r.admit(1, fp(1), 10).unwrap();
        assert!(r.contains(1));
        assert_eq!(r.peer_count(), 1);
    }

    #[test]
    fn admit_stores_fingerprint_and_epoch() {
        let mut r = GossipPeerRegistry::new();
        r.admit(2, fp(2), 5).unwrap();
        let p = r.get(2).unwrap();
        assert_eq!(p.fingerprint, fp(2));
        assert_eq!(p.admitted_at, 5);
    }

    #[test]
    fn admit_duplicate_returns_err() {
        let mut r = GossipPeerRegistry::new();
        r.admit(3, fp(3), 1).unwrap();
        assert!(r.admit(3, fp(3), 2).is_err());
    }

    #[test]
    fn get_unknown_peer_returns_none() {
        let r = GossipPeerRegistry::new();
        assert!(r.get(99).is_none());
    }

    // ── evict ─────────────────────────────────────────────────────────────────

    #[test]
    fn evict_removes_peer() {
        let mut r = GossipPeerRegistry::new();
        r.admit(4, fp(4), 1).unwrap();
        r.evict(4, 2).unwrap();
        assert!(!r.contains(4));
        assert_eq!(r.peer_count(), 0);
    }

    #[test]
    fn evict_unknown_peer_returns_err() {
        let mut r = GossipPeerRegistry::new();
        assert!(r.evict(99, 1).is_err());
    }

    #[test]
    fn admit_after_evict_succeeds() {
        let mut r = GossipPeerRegistry::new();
        r.admit(5, fp(5), 1).unwrap();
        r.evict(5, 2).unwrap();
        r.admit(5, fp(6), 3).unwrap(); // re-admitted with new fingerprint
        assert_eq!(r.get(5).unwrap().fingerprint, fp(6));
    }

    // ── event log ─────────────────────────────────────────────────────────────

    #[test]
    fn admit_records_event_kind() {
        let mut r = GossipPeerRegistry::new();
        let ev = r.admit(1, fp(1), 1).unwrap();
        assert_eq!(ev.kind, GossipRegistryEventKind::Admitted);
    }

    #[test]
    fn evict_records_event_kind() {
        let mut r = GossipPeerRegistry::new();
        r.admit(1, fp(1), 1).unwrap();
        let ev = r.evict(1, 2).unwrap();
        assert_eq!(ev.kind, GossipRegistryEventKind::Evicted);
    }

    #[test]
    fn event_hash_nonzero() {
        let mut r = GossipPeerRegistry::new();
        let ev = r.admit(1, fp(1), 1).unwrap();
        assert_ne!(ev.event_hash, [0u8; 32]);
    }

    #[test]
    fn first_event_prev_hash_is_genesis() {
        let mut r = GossipPeerRegistry::new();
        let ev = r.admit(1, fp(1), 1).unwrap();
        assert_eq!(ev.prev_hash, GOSSIP_REGISTRY_GENESIS_HASH);
    }

    #[test]
    fn event_chain_prev_links() {
        let mut r = GossipPeerRegistry::new();
        r.admit(1, fp(1), 1).unwrap();
        let h0 = r.events()[0].event_hash;
        r.admit(2, fp(2), 2).unwrap();
        assert_eq!(r.events()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let r = GossipPeerRegistry::new();
        let (ok, idx) = r.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_admit_evict_ok() {
        let mut r = GossipPeerRegistry::new();
        r.admit(1, fp(1), 1).unwrap();
        r.admit(2, fp(2), 2).unwrap();
        r.evict(1, 3).unwrap();
        let (ok, idx) = r.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut r = GossipPeerRegistry::new();
        r.admit(1, fp(1), 1).unwrap();
        r.admit(2, fp(2), 2).unwrap();
        r.events[0].event_hash[0] ^= 0xFF;
        let (ok, idx) = r.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn event_hash_deterministic() {
        let mut r1 = GossipPeerRegistry::new();
        let mut r2 = GossipPeerRegistry::new();
        let h1 = r1.admit(7, fp(7), 5).unwrap().event_hash;
        let h2 = r2.admit(7, fp(7), 5).unwrap().event_hash;
        assert_eq!(h1, h2);
    }
}
