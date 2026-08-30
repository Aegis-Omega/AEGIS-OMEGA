//! Gate 354 — Compaction Gossip Dispatcher (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Ties together the broadcast layer: dispatches a BroadcastFrame to all
//! registered peers, records per-peer delivery results in a hash-chained
//! DispatchLog, and exposes aggregate delivery statistics.
//!
//! DispatchResult (per peer, per dispatch):
//!   peer_id:      u64
//!   epoch_end:    u64
//!   delivered:    bool   — true if peer was in registry at dispatch time
//!
//! DispatchRecord (hash-chained):
//!   epoch_end:        u64
//!   peer_count:       u32   — registry size at dispatch time
//!   delivered_count:  u32   — peers that received the frame
//!   record_hash:      [u8;32]
//!   prev_hash:        [u8;32]
//!
//! record_hash = SHA-256(prev[32] ‖ epoch_end_be8 ‖ peer_count_be4 ‖ delivered_count_be4)
//!
//! CompactionGossipDispatcher: dispatch(frame, registry),
//!   record_count(), total_delivered(), total_missed(),
//!   records(), verify_chain().

use sha2::{Sha256, Digest};
use crate::compaction_broadcaster::{BROADCAST_FRAME_LEN, CompactionBroadcaster};
use crate::compaction_peer_registry::CompactionPeerRegistry;

pub const DISPATCHER_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── DispatchResult ───────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct DispatchResult {
    pub peer_id:   u64,
    pub epoch_end: u64,
    pub delivered: bool,
}

// ─── DispatchRecord ───────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct DispatchRecord {
    pub epoch_end:       u64,
    pub peer_count:      u32,
    pub delivered_count: u32,
    pub record_hash:     [u8; 32],
    pub prev_hash:       [u8; 32],
}

fn compute_dispatch_hash(
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

// ─── CompactionGossipDispatcher ───────────────────────────────────────────────

pub struct CompactionGossipDispatcher {
    records: Vec<DispatchRecord>,
}

#[derive(Debug)]
pub struct DispatchError(pub &'static str);

impl CompactionGossipDispatcher {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn record_count(&self) -> usize { self.records.len() }
    pub fn is_empty(&self)     -> bool  { self.records.is_empty() }
    pub fn records(&self)      -> &[DispatchRecord] { &self.records }
    pub fn latest(&self)       -> Option<&DispatchRecord> { self.records.last() }

    pub fn total_delivered(&self) -> u64 {
        self.records.iter().map(|r| r.delivered_count as u64).sum()
    }

    pub fn total_missed(&self) -> u64 {
        self.records.iter().map(|r| {
            r.peer_count.saturating_sub(r.delivered_count) as u64
        }).sum()
    }

    /// Dispatch a BroadcastFrame to all peers currently in the registry.
    ///
    /// Returns Err if the frame fails checksum (will not dispatch corrupt frames).
    /// The registry is consulted read-only — no peer state is modified here.
    pub fn dispatch(
        &mut self,
        frame:    &[u8; BROADCAST_FRAME_LEN],
        registry: &CompactionPeerRegistry,
    ) -> Result<(Vec<DispatchResult>, &DispatchRecord), DispatchError> {
        // Validate frame integrity before dispatch
        CompactionBroadcaster::decode(frame)
            .map_err(|_| DispatchError("[DISPATCH] Corrupt frame — checksum failed"))?;

        // Extract epoch_end from frame [0..8]
        let mut epoch_bytes = [0u8; 8];
        epoch_bytes.copy_from_slice(&frame[0..8]);
        let epoch_end = u64::from_be_bytes(epoch_bytes);

        let peer_count = registry.peer_count() as u32;

        // Build per-peer results (BTreeMap iteration is sorted → deterministic)
        let results: Vec<DispatchResult> = if peer_count == 0 {
            Vec::new()
        } else {
            // We can only iterate peers via the registry's public API
            // Build results for all peer_ids known from registry
            // Since CompactionPeerRegistry doesn't expose an iterator, we
            // track delivery by scanning events for admitted-but-not-evicted peers.
            // Simpler: peer_count gives us the count; all registered peers receive the frame.
            // For the result vec, we'd need peer_ids — use event log to collect them.
            let mut admitted: std::collections::BTreeMap<u64, bool> = std::collections::BTreeMap::new();
            for ev in registry.events() {
                match ev.kind {
                    crate::compaction_peer_registry::RegistryEventKind::Admitted => {
                        admitted.insert(ev.peer_id, true);
                    }
                    crate::compaction_peer_registry::RegistryEventKind::Evicted => {
                        admitted.remove(&ev.peer_id);
                    }
                }
            }
            admitted.keys().map(|&pid| DispatchResult {
                peer_id:   pid,
                epoch_end,
                delivered: true, // all admitted peers receive the frame
            }).collect()
        };

        let delivered_count = results.iter().filter(|r| r.delivered).count() as u32;

        let prev = self.records.last()
            .map(|r| r.record_hash)
            .unwrap_or(DISPATCHER_GENESIS_HASH);

        let record_hash = compute_dispatch_hash(&prev, epoch_end, peer_count, delivered_count);

        self.records.push(DispatchRecord {
            epoch_end,
            peer_count,
            delivered_count,
            record_hash,
            prev_hash: prev,
        });

        Ok((results, self.records.last().unwrap()))
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = DISPATCHER_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_dispatch_hash(
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

impl Default for CompactionGossipDispatcher {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::compaction_audit_seal::CompactionAuditSeal;
    use crate::compaction_broadcaster::CompactionBroadcaster;

    fn fp(seed: u8) -> [u8; 32] {
        let mut f = [0u8; 32];
        for (i, b) in f.iter_mut().enumerate() { *b = seed.wrapping_add(i as u8); }
        f
    }

    fn make_seal(epoch_end: u64) -> CompactionAuditSeal {
        CompactionAuditSeal {
            epoch_start:   1,
            epoch_end,
            epoch_count:   epoch_end,
            chains_valid:  true,
            terminal_hash: fp(epoch_end as u8),
            seal_hash:     fp(epoch_end as u8 + 10),
            prev_hash:     [0u8; 32],
        }
    }

    fn valid_frame(epoch_end: u64) -> [u8; BROADCAST_FRAME_LEN] {
        let mut bc = CompactionBroadcaster::new();
        bc.encode(&make_seal(epoch_end)).frame
    }

    fn registry_with_peers(n: u64) -> CompactionPeerRegistry {
        let mut r = CompactionPeerRegistry::new();
        for i in 1..=n { r.admit(i, fp(i as u8), 1).unwrap(); }
        r
    }

    // ── dispatch — empty registry ─────────────────────────────────────────────

    #[test]
    fn dispatch_empty_registry_zero_delivered() {
        let mut d = CompactionGossipDispatcher::new();
        let registry = CompactionPeerRegistry::new();
        let (results, rec) = d.dispatch(&valid_frame(5), &registry).unwrap();
        assert_eq!(results.len(), 0);
        assert_eq!(rec.peer_count, 0);
        assert_eq!(rec.delivered_count, 0);
    }

    // ── dispatch — with peers ─────────────────────────────────────────────────

    #[test]
    fn dispatch_three_peers_all_delivered() {
        let mut d = CompactionGossipDispatcher::new();
        let registry = registry_with_peers(3);
        let (results, rec) = d.dispatch(&valid_frame(7), &registry).unwrap();
        assert_eq!(results.len(), 3);
        assert_eq!(rec.peer_count, 3);
        assert_eq!(rec.delivered_count, 3);
        assert!(results.iter().all(|r| r.delivered));
    }

    #[test]
    fn dispatch_epoch_end_stored_in_record() {
        let mut d = CompactionGossipDispatcher::new();
        let registry = registry_with_peers(2);
        let (_, rec) = d.dispatch(&valid_frame(42), &registry).unwrap();
        assert_eq!(rec.epoch_end, 42);
    }

    #[test]
    fn dispatch_result_peer_ids_sorted() {
        let mut d = CompactionGossipDispatcher::new();
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
        let mut d = CompactionGossipDispatcher::new();
        let registry = registry_with_peers(2);
        let mut bad = valid_frame(5);
        bad[0] ^= 0xFF;
        assert!(d.dispatch(&bad, &registry).is_err());
    }

    #[test]
    fn dispatch_corrupt_frame_does_not_record() {
        let mut d = CompactionGossipDispatcher::new();
        let registry = registry_with_peers(2);
        let mut bad = valid_frame(5);
        bad[1] ^= 0xFF;
        let _ = d.dispatch(&bad, &registry);
        assert_eq!(d.record_count(), 0);
    }

    // ── aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn total_delivered_accumulates() {
        let mut d = CompactionGossipDispatcher::new();
        let registry = registry_with_peers(3);
        d.dispatch(&valid_frame(1), &registry).unwrap();
        d.dispatch(&valid_frame(2), &registry).unwrap();
        assert_eq!(d.total_delivered(), 6);
    }

    #[test]
    fn total_missed_zero_when_all_delivered() {
        let mut d = CompactionGossipDispatcher::new();
        let registry = registry_with_peers(2);
        d.dispatch(&valid_frame(1), &registry).unwrap();
        assert_eq!(d.total_missed(), 0);
    }

    // ── hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let mut d = CompactionGossipDispatcher::new();
        let registry = registry_with_peers(1);
        let (_, rec) = d.dispatch(&valid_frame(1), &registry).unwrap();
        assert_ne!(rec.record_hash, [0u8; 32]);
    }

    #[test]
    fn first_record_prev_hash_is_genesis() {
        let mut d = CompactionGossipDispatcher::new();
        let registry = registry_with_peers(1);
        let (_, rec) = d.dispatch(&valid_frame(1), &registry).unwrap();
        assert_eq!(rec.prev_hash, DISPATCHER_GENESIS_HASH);
    }

    #[test]
    fn prev_hash_links_correctly() {
        let mut d = CompactionGossipDispatcher::new();
        let registry = registry_with_peers(2);
        d.dispatch(&valid_frame(1), &registry).unwrap();
        let h0 = d.records()[0].record_hash;
        d.dispatch(&valid_frame(2), &registry).unwrap();
        assert_eq!(d.records()[1].prev_hash, h0);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let d = CompactionGossipDispatcher::new();
        let (ok, idx) = d.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_three_dispatches_ok() {
        let mut d = CompactionGossipDispatcher::new();
        let registry = registry_with_peers(2);
        for i in 1u64..=3 { d.dispatch(&valid_frame(i), &registry).unwrap(); }
        let (ok, idx) = d.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut d = CompactionGossipDispatcher::new();
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
        let mut d1 = CompactionGossipDispatcher::new();
        let mut d2 = CompactionGossipDispatcher::new();
        let h1 = d1.dispatch(&valid_frame(9), &registry).unwrap().1.record_hash;
        let h2 = d2.dispatch(&valid_frame(9), &registry).unwrap().1.record_hash;
        assert_eq!(h1, h2);
    }
}
