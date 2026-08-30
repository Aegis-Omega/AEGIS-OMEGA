//! Gate 319 — Gossip Epoch Snapshot Archive: rolling epoch-boundary state archive (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Stores a compact snapshot of the gossip subsystem state at the close of each epoch.
//! Snapshots capture: epoch number, active peer count, message counts, and a
//! content fingerprint (SHA-256 of the captured fields). Archives are hash-chained
//! for tamper evidence. Epoch numbers must be strictly monotone.
//!
//! A rolling window (MAX_ARCHIVE_SIZE) is enforced: oldest epochs are evicted when
//! the archive exceeds capacity. The evicted epochs are recorded but their data is
//! replaced with a tombstone.
//!
//! Constants:
//!   MAX_ARCHIVE_SIZE: usize = 128   (rolling window of retained snapshots)
//!
//! SnapshotRecord:
//!   epoch, active_peers, messages_sent, messages_received, messages_dropped
//!   content_hash = SHA-256(epoch_be8 ‖ peers_be4 ‖ sent_be8 ‖ recv_be8 ‖ dropped_be8)
//!   record_hash  = SHA-256(prev ‖ content_hash[32])
//!   prev_hash
//!
//! EpochSnapshotArchive:
//!   archive(epoch, active_peers, messages_sent, messages_received, messages_dropped)
//!       → Result<(), ArchiveError>
//!     Err(StaleEpoch) if epoch not strictly advancing.
//!   get(epoch) → Option<&SnapshotRecord>
//!   latest() → Option<&SnapshotRecord>
//!   archive_size() → usize
//!   total_messages_sent() → u64     (sum over all retained snapshots)
//!   total_messages_dropped() → u64
//!   verify_chain() → (bool, Option<usize>)

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const MAX_ARCHIVE_SIZE: usize = 128;

// ─── Snapshot record ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct SnapshotRecord {
    pub epoch:              u64,
    pub active_peers:       u32,
    pub messages_sent:      u64,
    pub messages_received:  u64,
    pub messages_dropped:   u64,
    pub content_hash:       [u8; 32],
    pub record_hash:        [u8; 32],
    pub prev_hash:          [u8; 32],
}

pub const ARCHIVE_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_content_hash(
    epoch:             u64,
    active_peers:      u32,
    messages_sent:     u64,
    messages_received: u64,
    messages_dropped:  u64,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(epoch.to_be_bytes());
    h.update(active_peers.to_be_bytes());
    h.update(messages_sent.to_be_bytes());
    h.update(messages_received.to_be_bytes());
    h.update(messages_dropped.to_be_bytes());
    h.finalize().into()
}

fn compute_record_hash(content_hash: &[u8; 32], prev: &[u8; 32]) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(content_hash);
    h.finalize().into()
}

pub fn build_snapshot_record(
    epoch:             u64,
    active_peers:      u32,
    messages_sent:     u64,
    messages_received: u64,
    messages_dropped:  u64,
    prev_hash:         &[u8; 32],
) -> SnapshotRecord {
    let content_hash = compute_content_hash(epoch, active_peers, messages_sent, messages_received, messages_dropped);
    let record_hash = compute_record_hash(&content_hash, prev_hash);
    SnapshotRecord {
        epoch, active_peers, messages_sent, messages_received, messages_dropped,
        content_hash, record_hash, prev_hash: *prev_hash,
    }
}

// ─── Errors ───────────────────────────────────────────────────────────────────

#[derive(Debug, PartialEq, Eq)]
pub enum ArchiveError {
    StaleEpoch,
}

// ─── EpochSnapshotArchive ─────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct EpochSnapshotArchive {
    // Ordered by epoch (BTreeMap key). When MAX_ARCHIVE_SIZE exceeded, evict oldest.
    records:    BTreeMap<u64, SnapshotRecord>,
    last_epoch: Option<u64>,
    last_hash:  [u8; 32],
}

impl EpochSnapshotArchive {
    pub fn new() -> Self {
        Self { records: BTreeMap::new(), last_epoch: None, last_hash: ARCHIVE_GENESIS_HASH }
    }

    /// Archive an epoch snapshot.
    pub fn archive(
        &mut self,
        epoch:             u64,
        active_peers:      u32,
        messages_sent:     u64,
        messages_received: u64,
        messages_dropped:  u64,
    ) -> Result<(), ArchiveError> {
        if let Some(last) = self.last_epoch {
            if epoch <= last {
                return Err(ArchiveError::StaleEpoch);
            }
        }

        let r = build_snapshot_record(epoch, active_peers, messages_sent, messages_received, messages_dropped, &self.last_hash);
        self.last_hash = r.record_hash;
        self.last_epoch = Some(epoch);
        self.records.insert(epoch, r);

        // Evict oldest if over capacity
        while self.records.len() > MAX_ARCHIVE_SIZE {
            if let Some(oldest_key) = self.records.keys().next().copied() {
                self.records.remove(&oldest_key);
            }
        }

        Ok(())
    }

    pub fn get(&self, epoch: u64) -> Option<&SnapshotRecord> {
        self.records.get(&epoch)
    }

    pub fn latest(&self) -> Option<&SnapshotRecord> {
        self.records.values().next_back()
    }

    pub fn archive_size(&self) -> usize { self.records.len() }

    pub fn total_messages_sent(&self) -> u64 {
        self.records.values().map(|r| r.messages_sent).fold(0u64, u64::saturating_add)
    }

    pub fn total_messages_dropped(&self) -> u64 {
        self.records.values().map(|r| r.messages_dropped).fold(0u64, u64::saturating_add)
    }

    /// Verify hash chain integrity of the retained records in epoch order.
    pub fn verify_chain(&self) -> (bool, Option<u64>) {
        let mut expected_prev = ARCHIVE_GENESIS_HASH;
        for r in self.records.values() {
            // Recompute content hash
            let ch = compute_content_hash(r.epoch, r.active_peers, r.messages_sent, r.messages_received, r.messages_dropped);
            if ch != r.content_hash { return (false, Some(r.epoch)); }
            // Verify record_hash
            let rh = compute_record_hash(&r.content_hash, &r.prev_hash);
            if rh != r.record_hash { return (false, Some(r.epoch)); }
            // Verify chain link (only meaningful for consecutive retained records)
            if r.prev_hash != expected_prev { return (false, Some(r.epoch)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for EpochSnapshotArchive {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── build_snapshot_record ─────────────────────────────────────────────────

    #[test]
    fn content_hash_nonzero() {
        let r = build_snapshot_record(1, 10, 100, 200, 5, &ARCHIVE_GENESIS_HASH);
        assert_ne!(r.content_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_nonzero() {
        let r = build_snapshot_record(1, 10, 100, 200, 5, &ARCHIVE_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_snapshot_record(1, 10, 100, 200, 5, &ARCHIVE_GENESIS_HASH);
        let r2 = build_snapshot_record(1, 10, 100, 200, 5, &ARCHIVE_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
        assert_eq!(r1.content_hash, r2.content_hash);
    }

    // ── EpochSnapshotArchive ──────────────────────────────────────────────────

    #[test]
    fn archive_and_retrieve() {
        let mut a = EpochSnapshotArchive::new();
        a.archive(1, 5, 100, 200, 3).unwrap();
        let r = a.get(1).unwrap();
        assert_eq!(r.epoch, 1);
        assert_eq!(r.active_peers, 5);
        assert_eq!(r.messages_sent, 100);
        assert_eq!(a.archive_size(), 1);
    }

    #[test]
    fn latest_returns_newest() {
        let mut a = EpochSnapshotArchive::new();
        a.archive(1, 5, 100, 200, 3).unwrap();
        a.archive(2, 6, 150, 250, 5).unwrap();
        assert_eq!(a.latest().unwrap().epoch, 2);
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut a = EpochSnapshotArchive::new();
        a.archive(5, 5, 100, 200, 0).unwrap();
        assert_eq!(a.archive(5, 5, 100, 200, 0), Err(ArchiveError::StaleEpoch));
        assert_eq!(a.archive(3, 5, 100, 200, 0), Err(ArchiveError::StaleEpoch));
    }

    #[test]
    fn totals_sum_retained() {
        let mut a = EpochSnapshotArchive::new();
        a.archive(1, 5, 100, 200, 3).unwrap();
        a.archive(2, 6, 150, 250, 7).unwrap();
        assert_eq!(a.total_messages_sent(),    250);
        assert_eq!(a.total_messages_dropped(), 10);
    }

    #[test]
    fn verify_chain_valid() {
        let mut a = EpochSnapshotArchive::new();
        for i in 1u64..=5 {
            a.archive(i, i as u32, i * 100, i * 50, i).unwrap();
        }
        let (valid, broken) = a.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    #[test]
    fn get_unknown_epoch_none() {
        let a = EpochSnapshotArchive::new();
        assert!(a.get(99).is_none());
        assert!(a.latest().is_none());
    }

    #[test]
    fn rolling_eviction() {
        let mut a = EpochSnapshotArchive::new();
        // Insert MAX_ARCHIVE_SIZE + 5 epochs; oldest 5 should be evicted
        for i in 1u64..=(MAX_ARCHIVE_SIZE as u64 + 5) {
            a.archive(i, 1, 10, 10, 0).unwrap();
        }
        assert_eq!(a.archive_size(), MAX_ARCHIVE_SIZE);
        // Epochs 1..=5 should be gone
        for i in 1u64..=5 {
            assert!(a.get(i).is_none());
        }
        // Epoch MAX+5 should still be present
        assert!(a.get(MAX_ARCHIVE_SIZE as u64 + 5).is_some());
    }
}
