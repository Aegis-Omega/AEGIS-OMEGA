//! Gate 352 — Compaction Sync State Machine (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks per-peer synchronization state for the compaction broadcast layer.
//! Each peer has a SyncEntry recording its last acknowledged epoch and lag.
//! Transitions are recorded in a hash-chained SyncEventLog.
//!
//! SyncState (per peer):
//!   Unsynced  — no frame received yet
//!   Synced    — last acked epoch equals current epoch
//!   Lagging   — last acked epoch < current epoch (lag > 0)
//!   Diverged  — peer acknowledged an epoch that exceeds the current epoch
//!
//! SyncEntry:
//!   peer_id:          u64
//!   last_acked_epoch: u64
//!   current_epoch:    u64
//!   state:            SyncState
//!   lag:              u64  — current_epoch.saturating_sub(last_acked_epoch)
//!
//! SyncEvent (hash-chained log):
//!   peer_id:          u64
//!   new_state:        SyncState
//!   last_acked_epoch: u64
//!   current_epoch:    u64
//!   event_hash:       [u8;32]
//!   prev_hash:        [u8;32]
//!
//! event_hash = SHA-256(prev[32] ‖ peer_id_be8 ‖ new_state_byte ‖ acked_be8 ‖ current_be8)
//!
//! CompactionSyncTracker: update(peer_id, acked_epoch, current_epoch),
//!   get(peer_id), lagging_count(), diverged_count(), synced_count(),
//!   events(), verify_chain().

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const SYNC_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── SyncState ────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum SyncState {
    Unsynced  = 0,
    Synced    = 1,
    Lagging   = 2,
    Diverged  = 3,
}

impl SyncState {
    pub fn as_u8(self) -> u8 { self as u8 }

    fn classify(last_acked: u64, current: u64) -> Self {
        if current == 0 && last_acked == 0 { return Self::Synced; }
        if last_acked == current            { return Self::Synced; }
        if last_acked < current             { return Self::Lagging; }
        // last_acked > current → peer is ahead of what we know
        Self::Diverged
    }
}

// ─── SyncEntry ────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct SyncEntry {
    pub peer_id:          u64,
    pub last_acked_epoch: u64,
    pub current_epoch:    u64,
    pub state:            SyncState,
    pub lag:              u64,
}

impl SyncEntry {
    fn new(peer_id: u64, last_acked_epoch: u64, current_epoch: u64) -> Self {
        let state = SyncState::classify(last_acked_epoch, current_epoch);
        let lag   = current_epoch.saturating_sub(last_acked_epoch);
        Self { peer_id, last_acked_epoch, current_epoch, state, lag }
    }
}

// ─── SyncEvent ────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct SyncEvent {
    pub peer_id:          u64,
    pub new_state:        SyncState,
    pub last_acked_epoch: u64,
    pub current_epoch:    u64,
    pub event_hash:       [u8; 32],
    pub prev_hash:        [u8; 32],
}

fn compute_event_hash(
    prev:            &[u8; 32],
    peer_id:         u64,
    new_state:       SyncState,
    last_acked:      u64,
    current:         u64,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update([new_state.as_u8()]);
    h.update(last_acked.to_be_bytes());
    h.update(current.to_be_bytes());
    h.finalize().into()
}

// ─── CompactionSyncTracker ────────────────────────────────────────────────────

pub struct CompactionSyncTracker {
    peers:  BTreeMap<u64, SyncEntry>,
    events: Vec<SyncEvent>,
}

impl CompactionSyncTracker {
    pub fn new() -> Self {
        Self { peers: BTreeMap::new(), events: Vec::new() }
    }

    pub fn peer_count(&self)   -> usize { self.peers.len() }
    pub fn event_count(&self)  -> usize { self.events.len() }
    pub fn events(&self)       -> &[SyncEvent] { &self.events }
    pub fn is_empty(&self)     -> bool   { self.peers.is_empty() }

    /// Update a peer's acknowledged epoch and record the state transition.
    pub fn update(&mut self, peer_id: u64, acked_epoch: u64, current_epoch: u64) -> &SyncEvent {
        let entry = SyncEntry::new(peer_id, acked_epoch, current_epoch);
        self.peers.insert(peer_id, entry.clone());

        let prev = self.events.last()
            .map(|e| e.event_hash)
            .unwrap_or(SYNC_GENESIS_HASH);

        let event_hash = compute_event_hash(
            &prev, peer_id, entry.state, acked_epoch, current_epoch,
        );

        self.events.push(SyncEvent {
            peer_id,
            new_state:        entry.state,
            last_acked_epoch: acked_epoch,
            current_epoch,
            event_hash,
            prev_hash: prev,
        });
        self.events.last().unwrap()
    }

    /// Look up the latest SyncEntry for a peer.
    pub fn get(&self, peer_id: u64) -> Option<&SyncEntry> {
        self.peers.get(&peer_id)
    }

    pub fn synced_count(&self) -> usize {
        self.peers.values().filter(|e| e.state == SyncState::Synced).count()
    }

    pub fn lagging_count(&self) -> usize {
        self.peers.values().filter(|e| e.state == SyncState::Lagging).count()
    }

    pub fn diverged_count(&self) -> usize {
        self.peers.values().filter(|e| e.state == SyncState::Diverged).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = SYNC_GENESIS_HASH;
        for (i, e) in self.events.iter().enumerate() {
            if e.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_event_hash(
                &prev, e.peer_id, e.new_state, e.last_acked_epoch, e.current_epoch,
            );
            if e.event_hash != expected {
                return (false, Some(i));
            }
            prev = e.event_hash;
        }
        (true, None)
    }
}

impl Default for CompactionSyncTracker {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── SyncState classification ──────────────────────────────────────────────

    #[test]
    fn state_synced_equal_epochs() {
        assert_eq!(SyncState::classify(5, 5), SyncState::Synced);
    }

    #[test]
    fn state_synced_both_zero() {
        assert_eq!(SyncState::classify(0, 0), SyncState::Synced);
    }

    #[test]
    fn state_lagging_behind() {
        assert_eq!(SyncState::classify(3, 7), SyncState::Lagging);
    }

    #[test]
    fn state_diverged_ahead() {
        assert_eq!(SyncState::classify(10, 5), SyncState::Diverged);
    }

    // ── SyncEntry construction ────────────────────────────────────────────────

    #[test]
    fn entry_lag_computed() {
        let e = SyncEntry::new(1, 3, 10);
        assert_eq!(e.lag, 7);
        assert_eq!(e.state, SyncState::Lagging);
    }

    #[test]
    fn entry_lag_zero_when_synced() {
        let e = SyncEntry::new(1, 5, 5);
        assert_eq!(e.lag, 0);
        assert_eq!(e.state, SyncState::Synced);
    }

    #[test]
    fn entry_lag_saturates_on_diverged() {
        // last_acked > current → lag would underflow → saturating_sub = 0
        let e = SyncEntry::new(1, 10, 5);
        assert_eq!(e.lag, 0);
        assert_eq!(e.state, SyncState::Diverged);
    }

    // ── update() and get() ────────────────────────────────────────────────────

    #[test]
    fn update_single_peer_synced() {
        let mut t = CompactionSyncTracker::new();
        t.update(1, 5, 5);
        let e = t.get(1).unwrap();
        assert_eq!(e.state, SyncState::Synced);
        assert_eq!(e.lag, 0);
    }

    #[test]
    fn update_single_peer_lagging() {
        let mut t = CompactionSyncTracker::new();
        t.update(2, 3, 8);
        let e = t.get(2).unwrap();
        assert_eq!(e.state, SyncState::Lagging);
        assert_eq!(e.lag, 5);
    }

    #[test]
    fn update_overwrites_previous_entry() {
        let mut t = CompactionSyncTracker::new();
        t.update(1, 3, 10);
        t.update(1, 10, 10); // peer catches up
        let e = t.get(1).unwrap();
        assert_eq!(e.state, SyncState::Synced);
    }

    #[test]
    fn get_unknown_peer_returns_none() {
        let t = CompactionSyncTracker::new();
        assert!(t.get(99).is_none());
    }

    // ── aggregate counts ──────────────────────────────────────────────────────

    #[test]
    fn aggregate_counts_correct() {
        let mut t = CompactionSyncTracker::new();
        t.update(1, 5, 5);    // Synced
        t.update(2, 3, 8);    // Lagging
        t.update(3, 20, 10);  // Diverged
        assert_eq!(t.synced_count(), 1);
        assert_eq!(t.lagging_count(), 1);
        assert_eq!(t.diverged_count(), 1);
        assert_eq!(t.peer_count(), 3);
    }

    // ── event log and hash chain ──────────────────────────────────────────────

    #[test]
    fn event_hash_nonzero() {
        let mut t = CompactionSyncTracker::new();
        let ev = t.update(1, 5, 5);
        assert_ne!(ev.event_hash, [0u8; 32]);
    }

    #[test]
    fn first_event_prev_hash_is_genesis() {
        let mut t = CompactionSyncTracker::new();
        let ev = t.update(1, 1, 2);
        assert_eq!(ev.prev_hash, SYNC_GENESIS_HASH);
    }

    #[test]
    fn event_chain_prev_links() {
        let mut t = CompactionSyncTracker::new();
        t.update(1, 1, 5);
        let h0 = t.events()[0].event_hash;
        t.update(2, 3, 5);
        assert_eq!(t.events()[1].prev_hash, h0);
    }

    #[test]
    fn verify_chain_empty_ok() {
        let t = CompactionSyncTracker::new();
        let (ok, idx) = t.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_multiple_events_ok() {
        let mut t = CompactionSyncTracker::new();
        for i in 1u64..=4 { t.update(i, i, 5); }
        let (ok, idx) = t.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut t = CompactionSyncTracker::new();
        t.update(1, 1, 5);
        t.update(2, 2, 5);
        t.events[0].event_hash[0] ^= 0xFF;
        let (ok, idx) = t.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    // ── determinism ───────────────────────────────────────────────────────────

    #[test]
    fn event_hash_deterministic() {
        let mut t1 = CompactionSyncTracker::new();
        let mut t2 = CompactionSyncTracker::new();
        let h1 = t1.update(7, 3, 10).event_hash;
        let h2 = t2.update(7, 3, 10).event_hash;
        assert_eq!(h1, h2);
    }
}
