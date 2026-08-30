//! Gate 353 — Compaction Peer Registry (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Maintains the canonical set of known broadcast peers for the compaction
//! subsystem. Each peer is identified by a u64 peer_id and carries a 32-byte
//! public fingerprint (opaque — no PKI assumed at T2).
//!
//! PeerRecord:
//!   peer_id:      u64
//!   fingerprint:  [u8;32]  — opaque peer identity (e.g. public key hash)
//!   admitted_at:  u64      — epoch at which the peer was admitted
//!
//! RegistryEvent (hash-chained log):
//!   kind:         RegistryEventKind (Admitted / Evicted)
//!   peer_id:      u64
//!   epoch:        u64
//!   event_hash:   [u8;32]
//!   prev_hash:    [u8;32]
//!
//! event_hash = SHA-256(prev[32] ‖ kind_byte ‖ peer_id_be8 ‖ epoch_be8 ‖ fingerprint[32])
//!
//! CompactionPeerRegistry: admit(peer_id, fingerprint, epoch),
//!   evict(peer_id, epoch), contains(peer_id), get(peer_id),
//!   peer_count(), events(), verify_chain().

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const REGISTRY_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── RegistryEventKind ────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum RegistryEventKind {
    Admitted = 0,
    Evicted  = 1,
}

impl RegistryEventKind {
    pub fn as_u8(self) -> u8 { self as u8 }
}

// ─── PeerRecord ───────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct PeerRecord {
    pub peer_id:     u64,
    pub fingerprint: [u8; 32],
    pub admitted_at: u64,
}

// ─── RegistryEvent ────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct RegistryEvent {
    pub kind:        RegistryEventKind,
    pub peer_id:     u64,
    pub epoch:       u64,
    pub fingerprint: [u8; 32],
    pub event_hash:  [u8; 32],
    pub prev_hash:   [u8; 32],
}

fn compute_registry_hash(
    prev:        &[u8; 32],
    kind:        RegistryEventKind,
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

// ─── CompactionPeerRegistry ───────────────────────────────────────────────────

pub struct CompactionPeerRegistry {
    peers:  BTreeMap<u64, PeerRecord>,
    events: Vec<RegistryEvent>,
}

#[derive(Debug)]
pub struct RegistryError(pub &'static str);

impl CompactionPeerRegistry {
    pub fn new() -> Self {
        Self { peers: BTreeMap::new(), events: Vec::new() }
    }

    pub fn peer_count(&self)  -> usize { self.peers.len() }
    pub fn event_count(&self) -> usize { self.events.len() }
    pub fn events(&self)      -> &[RegistryEvent] { &self.events }
    pub fn is_empty(&self)    -> bool  { self.peers.is_empty() }

    pub fn contains(&self, peer_id: u64) -> bool {
        self.peers.contains_key(&peer_id)
    }

    pub fn get(&self, peer_id: u64) -> Option<&PeerRecord> {
        self.peers.get(&peer_id)
    }

    /// Admit a peer. Returns Err if already present.
    pub fn admit(
        &mut self,
        peer_id:     u64,
        fingerprint: [u8; 32],
        epoch:       u64,
    ) -> Result<&RegistryEvent, RegistryError> {
        if self.peers.contains_key(&peer_id) {
            return Err(RegistryError("[REGISTRY] Peer already admitted"));
        }
        self.peers.insert(peer_id, PeerRecord { peer_id, fingerprint, admitted_at: epoch });
        Ok(self.push_event(RegistryEventKind::Admitted, peer_id, epoch, fingerprint))
    }

    /// Evict a peer. Returns Err if not present.
    pub fn evict(
        &mut self,
        peer_id: u64,
        epoch:   u64,
    ) -> Result<&RegistryEvent, RegistryError> {
        let fingerprint = self.peers.remove(&peer_id)
            .ok_or(RegistryError("[REGISTRY] Peer not found"))?
            .fingerprint;
        Ok(self.push_event(RegistryEventKind::Evicted, peer_id, epoch, fingerprint))
    }

    fn push_event(
        &mut self,
        kind:        RegistryEventKind,
        peer_id:     u64,
        epoch:       u64,
        fingerprint: [u8; 32],
    ) -> &RegistryEvent {
        let prev = self.events.last()
            .map(|e| e.event_hash)
            .unwrap_or(REGISTRY_GENESIS_HASH);

        let event_hash = compute_registry_hash(&prev, kind, peer_id, epoch, &fingerprint);

        self.events.push(RegistryEvent {
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
        let mut prev = REGISTRY_GENESIS_HASH;
        for (i, e) in self.events.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_registry_hash(
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

impl Default for CompactionPeerRegistry {
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
        let mut r = CompactionPeerRegistry::new();
        r.admit(1, fp(1), 10).unwrap();
        assert!(r.contains(1));
        assert_eq!(r.peer_count(), 1);
    }

    #[test]
    fn admit_stores_fingerprint_and_epoch() {
        let mut r = CompactionPeerRegistry::new();
        r.admit(2, fp(2), 5).unwrap();
        let p = r.get(2).unwrap();
        assert_eq!(p.fingerprint, fp(2));
        assert_eq!(p.admitted_at, 5);
    }

    #[test]
    fn admit_duplicate_returns_err() {
        let mut r = CompactionPeerRegistry::new();
        r.admit(3, fp(3), 1).unwrap();
        assert!(r.admit(3, fp(3), 2).is_err());
    }

    #[test]
    fn get_unknown_peer_returns_none() {
        let r = CompactionPeerRegistry::new();
        assert!(r.get(99).is_none());
    }

    // ── evict ─────────────────────────────────────────────────────────────────

    #[test]
    fn evict_removes_peer() {
        let mut r = CompactionPeerRegistry::new();
        r.admit(4, fp(4), 1).unwrap();
        r.evict(4, 2).unwrap();
        assert!(!r.contains(4));
        assert_eq!(r.peer_count(), 0);
    }

    #[test]
    fn evict_unknown_peer_returns_err() {
        let mut r = CompactionPeerRegistry::new();
        assert!(r.evict(99, 1).is_err());
    }

    #[test]
    fn admit_after_evict_succeeds() {
        let mut r = CompactionPeerRegistry::new();
        r.admit(5, fp(5), 1).unwrap();
        r.evict(5, 2).unwrap();
        r.admit(5, fp(6), 3).unwrap(); // re-admitted with new fingerprint
        assert_eq!(r.get(5).unwrap().fingerprint, fp(6));
    }

    // ── event log ─────────────────────────────────────────────────────────────

    #[test]
    fn admit_records_event_kind() {
        let mut r = CompactionPeerRegistry::new();
        let ev = r.admit(1, fp(1), 1).unwrap();
        assert_eq!(ev.kind, RegistryEventKind::Admitted);
    }

    #[test]
    fn evict_records_event_kind() {
        let mut r = CompactionPeerRegistry::new();
        r.admit(1, fp(1), 1).unwrap();
        let ev = r.evict(1, 2).unwrap();
        assert_eq!(ev.kind, RegistryEventKind::Evicted);
    }

    #[test]
    fn event_hash_nonzero() {
        let mut r = CompactionPeerRegistry::new();
        let ev = r.admit(1, fp(1), 1).unwrap();
        assert_ne!(ev.event_hash, [0u8; 32]);
    }

    #[test]
    fn first_event_prev_hash_is_genesis() {
        let mut r = CompactionPeerRegistry::new();
        let ev = r.admit(1, fp(1), 1).unwrap();
        assert_eq!(ev.prev_hash, REGISTRY_GENESIS_HASH);
    }

    #[test]
    fn event_chain_prev_links() {
        let mut r = CompactionPeerRegistry::new();
        r.admit(1, fp(1), 1).unwrap();
        let h0 = r.events()[0].event_hash;
        r.admit(2, fp(2), 2).unwrap();
        assert_eq!(r.events()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let r = CompactionPeerRegistry::new();
        let (ok, idx) = r.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_admit_evict_ok() {
        let mut r = CompactionPeerRegistry::new();
        r.admit(1, fp(1), 1).unwrap();
        r.admit(2, fp(2), 2).unwrap();
        r.evict(1, 3).unwrap();
        let (ok, idx) = r.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut r = CompactionPeerRegistry::new();
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
        let mut r1 = CompactionPeerRegistry::new();
        let mut r2 = CompactionPeerRegistry::new();
        let h1 = r1.admit(7, fp(7), 5).unwrap().event_hash;
        let h2 = r2.admit(7, fp(7), 5).unwrap().event_hash;
        assert_eq!(h1, h2);
    }
}
