//! Gate 376 — Gossip Peer Dispatcher (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Ties together the gossip broadcast layer: dispatches a GossipBroadcastFrame
//! to all registered peers, records per-peer delivery results in a
//! hash-chained GossipDispatchLog, and exposes aggregate delivery statistics.
//! Mirrors Gate 354 for the gossip subsystem.
//!
//! GossipDispatchResult (per peer, per dispatch):
//!   peer_id:      u64
//!   epoch_end:    u64
//!   delivered:    bool   — true if peer was in registry at dispatch time
//!
//! GossipDispatchRecord (hash-chained):
//!   epoch_end:        u64
//!   peer_count:       u32   — registry size at dispatch time
//!   delivered_count:  u32   — peers that received the frame
//!   record_hash:      [u8;32]
//!   prev_hash:        [u8;32]
//!
//! record_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ peer_count_be4 ‖ delivered_count_be4)
//!
//! GossipPeerDispatcher: dispatch(frame, registry),
//!   record_count(), total_delivered(), total_missed(),
//!   records(), verify_chain().

use sha2::{Sha256, Digest};
use crate::compaction_gossip_broadcaster::{GOSSIP_BROADCAST_FRAME_LEN, GossipBroadcaster};
use crate::compaction_gossip_peer_registry::GossipPeerRegistry;

pub const GOSSIP_DISPATCHER_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── GossipDispatchResult ─────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipDispatchResult {
    pub peer_id:   u64,
    pub epoch_end: u64,
    pub delivered: bool,
}

// ─── GossipDispatchRecord ─────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipDispatchRecord {
    pub epoch_end:       u64,
    pub peer_count:      u32,
    pub delivered_count: u32,
    pub record_hash:     [u8; 32],
    pub prev_hash:       [u8; 32],
}

fn compute_gossip_dispatch_hash(
    prev:            &[u8; 32],
    epoch_end:       u64,
    peer_count:      u32,
    delivered_count: u32,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(peer_count.to_be_bytes());
    h.update(delivered_count.to_be_bytes());
    h.finalize().into()
}

// ─── GossipPeerDispatcher ─────────────────────────────────────────────────────

pub struct GossipPeerDispatcher {
    records: Vec<GossipDispatchRecord>,
}

#[derive(Debug)]
pub struct GossipDispatchError(pub &'static str);

impl GossipPeerDispatcher {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn record_count(&self) -> usize { self.records.len() }
    pub fn is_empty(&self)     -> bool  { self.records.is_empty() }
    pub fn records(&self)      -> &[GossipDispatchRecord] { &self.records }
    pub fn latest(&self)       -> Option<&GossipDispatchRecord> { self.records.last() }

    pub fn total_delivered(&self) -> u64 {
        self.records.iter().map(|r| r.delivered_count as u64).sum()
    }

    pub fn total_missed(&self) -> u64 {
        self.records.iter().map(|r| {
            r.peer_count.saturating_sub(r.delivered_count) as u64
        }).sum()
    }

    /// Dispatch a GossipBroadcastFrame to all peers currently in the registry.
    ///
    /// Returns Err if the frame fails checksum (will not dispatch corrupt frames).
    /// The registry is consulted read-only — no peer state is modified here.
    pub fn dispatch(
        &mut self,
        frame:    &[u8; GOSSIP_BROADCAST_FRAME_LEN],
        registry: &GossipPeerRegistry,
    ) -> Result<(Vec<GossipDispatchResult>, &GossipDispatchRecord), GossipDispatchError> {
        // Validate frame integrity before dispatch
        GossipBroadcaster::decode(frame)
            .map_err(|_| GossipDispatchError("[GOSSIP_DISPATCH] Corrupt frame — checksum failed"))?;

        // Extract epoch_end from frame [0..8]
        let mut epoch_bytes = [0u8; 8];
        epoch_bytes.copy_from_slice(&frame[0..8]);
        let epoch_end = u64::from_be_bytes(epoch_bytes);

        let peer_count = registry.peer_count() as u32;

        // Build per-peer results (BTreeMap iteration is sorted → deterministic)
        let results: Vec<GossipDispatchResult> = if peer_count == 0 {
            Vec::new()
        } else {
            // Collect admitted (not evicted) peer_ids from registry event log
            let mut admitted: std::collections::BTreeMap<u64, bool> =
                std::collections::BTreeMap::new();
            for ev in registry.events() {
                match ev.kind {
                    crate::compaction_gossip_peer_registry::GossipRegistryEventKind::Admitted => {
                        admitted.insert(ev.peer_id, true);
                    }
                    crate::compaction_gossip_peer_registry::GossipRegistryEventKind::Evicted => {
                        admitted.remove(&ev.peer_id);
                    }
                }
            }
            admitted.keys().map(|&pid| GossipDispatchResult {
                peer_id:   pid,
                epoch_end,
                delivered: true, // all admitted peers receive the frame
            }).collect()
        };

        let delivered_count = results.iter().filter(|r| r.delivered).count() as u32;

        let prev = self.records.last()
            .map(|r| r.record_hash)
            .unwrap_or(GOSSIP_DISPATCHER_GENESIS_HASH);

        let record_hash = compute_gossip_dispatch_hash(&prev, epoch_end, peer_count, delivered_count);

        self.records.push(GossipDispatchRecord {
            epoch_end,
            peer_count,
            delivered_count,
            record_hash,
            prev_hash: prev,
        });

        Ok((results, self.records.last().unwrap()))
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_DISPATCHER_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_gossip_dispatch_hash(
                &prev, r.epoch_end, r.peer_count, r.delivered_count,
            );
            if r.record_hash != expected {
                return (false, Some(i));
            }
            prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for GossipPeerDispatcher {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::compaction_gossip_audit_seal::GossipAuditSeal;
    use crate::compaction_gossip_broadcaster::GossipBroadcaster;

    fn fp(seed: u8) -> [u8; 32] {
        let mut f = [0u8; 32];
        for (i, b) in f.iter_mut().enumerate() { *b = seed.wrapping_add(i as u8); }
        f
    }

    fn make_seal(epoch_end: u64) -> GossipAuditSeal {
        GossipAuditSeal {
            epoch_start:   1,
            epoch_end,
            epoch_count:   epoch_end,
            chains_valid:  true,
            terminal_hash: fp(epoch_end as u8),
            seal_hash:     fp(epoch_end as u8 + 10),
            prev_hash:     [0u8; 32],
        }
    }

    fn valid_frame(epoch_end: u64) -> [u8; GOSSIP_BROADCAST_FRAME_LEN] {
        let mut bc = GossipBroadcaster::new();
        bc.encode(&make_seal(epoch_end)).frame
    }

    fn registry_with_peers(n: u64) -> GossipPeerRegistry {
        let mut r = GossipPeerRegistry::new();
        for i in 1..=n { r.admit(i, fp(i as u8), 1).unwrap(); }
        r
    }

    // ── dispatch — empty registry ─────────────────────────────────────────────

    #[test]
    fn dispatch_empty_registry_zero_delivered() {
        let mut d = GossipPeerDispatcher::new();
        let registry = GossipPeerRegistry::new();
        let (results, rec) = d.dispatch(&valid_frame(5), &registry).unwrap();
        assert_eq!(results.len(), 0);
        assert_eq!(rec.peer_count, 0);
        assert_eq!(rec.delivered_count, 0);
    }

    // ── dispatch — with peers ─────────────────────────────────────────────────

    #[test]
    fn dispatch_three_peers_all_delivered() {
        let mut d = GossipPeerDispatcher::new();
        let registry = registry_with_peers(3);
        let (results, rec) = d.dispatch(&valid_frame(7), &registry).unwrap();
        assert_eq!(results.len(), 3);
        assert_eq!(rec.peer_count, 3);
        assert_eq!(rec.delivered_count, 3);
        assert!(results.iter().all(|r| r.delivered));
    }

    #[test]
    fn dispatch_epoch_end_stored_in_record() {
        let mut d = GossipPeerDispatcher::new();
        let registry = registry_with_peers(2);
        let (_, rec) = d.dispatch(&valid_frame(42), &registry).unwrap();
        assert_eq!(rec.epoch_end, 42);
    }

    #[test]
    fn dispatch_result_peer_ids_sorted() {
        let mut d = GossipPeerDispatcher::new();
        let registry = registry_with_peers(4);
        let (results, _) = d.dispatch(&valid_frame(1), &registry).unwrap();
        let ids: Vec<u64> = results.iter().map(|r| r.peer_id).collect();
        let mut sorted = ids.clone();
        sorted.sort();
        assert_eq!(ids, sorted); // BTreeMap guarantees sorted order
    }

    // ── dispatch — corrupt frame ──────────────────────────────────────────────

    #[test]
    fn dispatch_corrupt_frame_returns_err() {
        let mut d = GossipPeerDispatcher::new();
        let registry = registry_with_peers(2);
        let mut bad = valid_frame(5);
        bad[0] ^= 0xFF;
        assert!(d.dispatch(&bad, &registry).is_err());
    }

    #[test]
    fn dispatch_corrupt_frame_does_not_record() {
        let mut d = GossipPeerDispatcher::new();
        let registry = registry_with_peers(2);
        let mut bad = valid_frame(5);
        bad[1] ^= 0xFF;
        let _ = d.dispatch(&bad, &registry);
        assert_eq!(d.record_count(), 0);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn total_delivered_accumulates() {
        let mut d = GossipPeerDispatcher::new();
        let registry = registry_with_peers(3);
        d.dispatch(&valid_frame(1), &registry).unwrap();
        d.dispatch(&valid_frame(2), &registry).unwrap();
        assert_eq!(d.total_delivered(), 6);
    }

    #[test]
    fn total_missed_zero_when_all_delivered() {
        let mut d = GossipPeerDispatcher::new();
        let registry = registry_with_peers(2);
        d.dispatch(&valid_frame(1), &registry).unwrap();
        assert_eq!(d.total_missed(), 0);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let mut d = GossipPeerDispatcher::new();
        let registry = registry_with_peers(1);
        let (_, rec) = d.dispatch(&valid_frame(1), &registry).unwrap();
        assert_ne!(rec.record_hash, [0u8; 32]);
    }

    #[test]
    fn first_record_prev_hash_is_genesis() {
        let mut d = GossipPeerDispatcher::new();
        let registry = registry_with_peers(1);
        let (_, rec) = d.dispatch(&valid_frame(1), &registry).unwrap();
        assert_eq!(rec.prev_hash, GOSSIP_DISPATCHER_GENESIS_HASH);
    }

    #[test]
    fn prev_hash_links_correctly() {
        let mut d = GossipPeerDispatcher::new();
        let registry = registry_with_peers(2);
        d.dispatch(&valid_frame(1), &registry).unwrap();
        let h0 = d.records()[0].record_hash;
        d.dispatch(&valid_frame(2), &registry).unwrap();
        assert_eq!(d.records()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let d = GossipPeerDispatcher::new();
        let (ok, idx) = d.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_three_dispatches_ok() {
        let mut d = GossipPeerDispatcher::new();
        let registry = registry_with_peers(2);
        for i in 1u64..=3 { d.dispatch(&valid_frame(i), &registry).unwrap(); }
        let (ok, idx) = d.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut d = GossipPeerDispatcher::new();
        let registry = registry_with_peers(1);
        d.dispatch(&valid_frame(1), &registry).unwrap();
        d.dispatch(&valid_frame(2), &registry).unwrap();
        d.records[0].record_hash[0] ^= 0xFF;
        let (ok, idx) = d.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn record_hash_deterministic() {
        let registry = registry_with_peers(2);
        let mut d1 = GossipPeerDispatcher::new();
        let mut d2 = GossipPeerDispatcher::new();
        let h1 = d1.dispatch(&valid_frame(9), &registry).unwrap().1.record_hash;
        let h2 = d2.dispatch(&valid_frame(9), &registry).unwrap().1.record_hash;
        assert_eq!(h1, h2);
    }
}
