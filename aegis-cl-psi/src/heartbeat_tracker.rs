//! Gate 302 — Gossip Heartbeat Tracker: per-peer liveness via periodic beat monitoring (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks heartbeat signals from gossip peers. Each received beat updates the peer's
//! last_seen_epoch. Missed beats increment a miss counter; exceeding MISS_THRESHOLD
//! marks the peer as Suspect. Reaching DEAD_THRESHOLD marks it Dead.
//!
//! Constants:
//!   MISS_THRESHOLD: u32 = 3   (misses before Suspect)
//!   DEAD_THRESHOLD: u32 = 6   (misses before Dead)
//!
//! PeerStatus:
//!   Alive    — last beat within miss threshold
//!   Suspect  — MISS_THRESHOLD ≤ misses < DEAD_THRESHOLD
//!   Dead     — misses ≥ DEAD_THRESHOLD
//!
//! HeartbeatRecord:
//!   peer_id, epoch, event: HeartbeatEvent, miss_count, status,
//!   record_hash = SHA-256(prev ‖ peer_be4 ‖ epoch_be8 ‖ event_byte ‖ miss_be4 ‖ status_byte)
//!   prev_hash
//!
//! HeartbeatEvent: Beat | Miss
//!
//! HeartbeatLog: hash-chained HeartbeatRecords per peer.
//!   push(), beat_count(), miss_count_total(), verify_chain().
//!
//! HeartbeatTracker:
//!   beat(peer_id, epoch)         — record received beat; resets miss counter to 0; status=Alive
//!   tick_miss(peer_id, epoch)    — record a missed beat; increments miss counter
//!   status(peer_id) → PeerStatus
//!   miss_count(peer_id) → u32
//!   suspect_peers() → Vec<u32>
//!   dead_peers() → Vec<u32>
//!   alive_peers() → Vec<u32>
//!   get_log(peer_id) → Option<&HeartbeatLog>

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const MISS_THRESHOLD: u32 = 3;
pub const DEAD_THRESHOLD: u32 = 6;

// ─── Peer status ──────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PeerStatus {
    Alive   = 0,
    Suspect = 1,
    Dead    = 2,
}

impl PeerStatus {
    pub fn status_byte(self) -> u8 { self as u8 }

    pub fn from_miss_count(misses: u32) -> Self {
        if misses >= DEAD_THRESHOLD {
            PeerStatus::Dead
        } else if misses >= MISS_THRESHOLD {
            PeerStatus::Suspect
        } else {
            PeerStatus::Alive
        }
    }
}

// ─── Heartbeat event ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum HeartbeatEvent {
    Beat = 0,
    Miss = 1,
}

impl HeartbeatEvent {
    pub fn event_byte(self) -> u8 { self as u8 }
}

// ─── Heartbeat record ─────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct HeartbeatRecord {
    pub peer_id:     u32,
    pub epoch:       u64,
    pub event:       HeartbeatEvent,
    pub miss_count:  u32,
    pub status:      PeerStatus,
    pub record_hash: [u8; 32],
    pub prev_hash:   [u8; 32],
}

pub const HEARTBEAT_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_heartbeat_hash(
    peer_id:    u32,
    epoch:      u64,
    event:      HeartbeatEvent,
    miss_count: u32,
    status:     PeerStatus,
    prev:       &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update([event.event_byte()]);
    h.update(miss_count.to_be_bytes());
    h.update([status.status_byte()]);
    h.finalize().into()
}

pub fn build_heartbeat_record(
    peer_id:    u32,
    epoch:      u64,
    event:      HeartbeatEvent,
    miss_count: u32,
    status:     PeerStatus,
    prev_hash:  &[u8; 32],
) -> HeartbeatRecord {
    let record_hash = compute_heartbeat_hash(peer_id, epoch, event, miss_count, status, prev_hash);
    HeartbeatRecord { peer_id, epoch, event, miss_count, status, record_hash, prev_hash: *prev_hash }
}

// ─── Heartbeat log ────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct HeartbeatLog {
    peer_id: u32,
    records: Vec<HeartbeatRecord>,
}

impl HeartbeatLog {
    pub fn new(peer_id: u32) -> Self { Self { peer_id, records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[HeartbeatRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(HEARTBEAT_GENESIS_HASH)
    }

    pub fn push(
        &mut self,
        epoch:      u64,
        event:      HeartbeatEvent,
        miss_count: u32,
        status:     PeerStatus,
    ) -> &HeartbeatRecord {
        let prev = self.last_hash();
        let r = build_heartbeat_record(self.peer_id, epoch, event, miss_count, status, &prev);
        self.records.push(r);
        self.records.last().unwrap()
    }

    pub fn beat_count(&self) -> usize {
        self.records.iter().filter(|r| r.event == HeartbeatEvent::Beat).count()
    }

    pub fn miss_count_total(&self) -> usize {
        self.records.iter().filter(|r| r.event == HeartbeatEvent::Miss).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = HEARTBEAT_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_heartbeat_hash(
                r.peer_id, r.epoch, r.event, r.miss_count, r.status, &r.prev_hash,
            );
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

// ─── Heartbeat tracker ────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
struct PeerHeartbeatState {
    miss_count: u32,
    log:        HeartbeatLog,
}

#[derive(Debug, Clone)]
pub struct HeartbeatTracker {
    peers: BTreeMap<u32, PeerHeartbeatState>,
}

impl HeartbeatTracker {
    pub fn new() -> Self { Self { peers: BTreeMap::new() } }

    /// Record a received heartbeat. Resets miss counter; status → Alive.
    pub fn beat(&mut self, peer_id: u32, epoch: u64) {
        let state = self.peers.entry(peer_id)
            .or_insert_with(|| PeerHeartbeatState {
                miss_count: 0,
                log: HeartbeatLog::new(peer_id),
            });
        state.miss_count = 0;
        state.log.push(epoch, HeartbeatEvent::Beat, 0, PeerStatus::Alive);
    }

    /// Record a missed heartbeat. Increments miss counter; updates status.
    pub fn tick_miss(&mut self, peer_id: u32, epoch: u64) {
        let state = self.peers.entry(peer_id)
            .or_insert_with(|| PeerHeartbeatState {
                miss_count: 0,
                log: HeartbeatLog::new(peer_id),
            });
        state.miss_count = state.miss_count.saturating_add(1);
        let mc = state.miss_count;
        let status = PeerStatus::from_miss_count(mc);
        state.log.push(epoch, HeartbeatEvent::Miss, mc, status);
    }

    pub fn status(&self, peer_id: u32) -> PeerStatus {
        self.peers.get(&peer_id)
            .map(|s| PeerStatus::from_miss_count(s.miss_count))
            .unwrap_or(PeerStatus::Alive) // unknown peers treated as alive until seen
    }

    pub fn miss_count(&self, peer_id: u32) -> u32 {
        self.peers.get(&peer_id).map(|s| s.miss_count).unwrap_or(0)
    }

    pub fn suspect_peers(&self) -> Vec<u32> {
        self.peers.iter()
            .filter(|(_, s)| PeerStatus::from_miss_count(s.miss_count) == PeerStatus::Suspect)
            .map(|(&pid, _)| pid)
            .collect()
    }

    pub fn dead_peers(&self) -> Vec<u32> {
        self.peers.iter()
            .filter(|(_, s)| PeerStatus::from_miss_count(s.miss_count) == PeerStatus::Dead)
            .map(|(&pid, _)| pid)
            .collect()
    }

    pub fn alive_peers(&self) -> Vec<u32> {
        self.peers.iter()
            .filter(|(_, s)| PeerStatus::from_miss_count(s.miss_count) == PeerStatus::Alive)
            .map(|(&pid, _)| pid)
            .collect()
    }

    pub fn get_log(&self, peer_id: u32) -> Option<&HeartbeatLog> {
        self.peers.get(&peer_id).map(|s| &s.log)
    }
}

impl Default for HeartbeatTracker {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── PeerStatus ────────────────────────────────────────────────────────────

    #[test]
    fn status_bytes() {
        assert_eq!(PeerStatus::Alive.status_byte(),   0);
        assert_eq!(PeerStatus::Suspect.status_byte(), 1);
        assert_eq!(PeerStatus::Dead.status_byte(),    2);
    }

    #[test]
    fn status_from_miss_count() {
        assert_eq!(PeerStatus::from_miss_count(0), PeerStatus::Alive);
        assert_eq!(PeerStatus::from_miss_count(2), PeerStatus::Alive);   // < MISS_THRESHOLD=3
        assert_eq!(PeerStatus::from_miss_count(3), PeerStatus::Suspect); // = MISS_THRESHOLD
        assert_eq!(PeerStatus::from_miss_count(5), PeerStatus::Suspect); // < DEAD_THRESHOLD=6
        assert_eq!(PeerStatus::from_miss_count(6), PeerStatus::Dead);    // = DEAD_THRESHOLD
        assert_eq!(PeerStatus::from_miss_count(9), PeerStatus::Dead);
    }

    // ── build_heartbeat_record ────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let r = build_heartbeat_record(1, 1, HeartbeatEvent::Beat, 0, PeerStatus::Alive, &HEARTBEAT_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_heartbeat_record(1, 1, HeartbeatEvent::Beat, 0, PeerStatus::Alive, &HEARTBEAT_GENESIS_HASH);
        let r2 = build_heartbeat_record(1, 1, HeartbeatEvent::Beat, 0, PeerStatus::Alive, &HEARTBEAT_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    // ── HeartbeatLog ──────────────────────────────────────────────────────────

    #[test]
    fn log_counts_events() {
        let mut l = HeartbeatLog::new(1);
        l.push(1, HeartbeatEvent::Beat, 0, PeerStatus::Alive);
        l.push(2, HeartbeatEvent::Miss, 1, PeerStatus::Alive);
        l.push(3, HeartbeatEvent::Miss, 2, PeerStatus::Alive);
        assert_eq!(l.beat_count(), 1);
        assert_eq!(l.miss_count_total(), 2);
    }

    #[test]
    fn log_chain_links() {
        let mut l = HeartbeatLog::new(1);
        l.push(1, HeartbeatEvent::Beat, 0, PeerStatus::Alive);
        l.push(2, HeartbeatEvent::Miss, 1, PeerStatus::Alive);
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    #[test]
    fn log_verify_chain_valid() {
        let mut l = HeartbeatLog::new(1);
        for e in 1..=5u64 {
            l.push(e, HeartbeatEvent::Beat, 0, PeerStatus::Alive);
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    // ── HeartbeatTracker ──────────────────────────────────────────────────────

    #[test]
    fn unknown_peer_is_alive() {
        let t = HeartbeatTracker::new();
        assert_eq!(t.status(99), PeerStatus::Alive);
        assert_eq!(t.miss_count(99), 0);
    }

    #[test]
    fn beat_keeps_alive() {
        let mut t = HeartbeatTracker::new();
        t.beat(1, 1);
        assert_eq!(t.status(1), PeerStatus::Alive);
        assert_eq!(t.miss_count(1), 0);
    }

    #[test]
    fn misses_progress_to_suspect_then_dead() {
        let mut t = HeartbeatTracker::new();
        t.beat(1, 1);
        for e in 2..=3u64 { t.tick_miss(1, e); }
        assert_eq!(t.status(1), PeerStatus::Alive); // 2 misses < 3
        t.tick_miss(1, 4);
        assert_eq!(t.status(1), PeerStatus::Suspect); // 3 misses = MISS_THRESHOLD
        for e in 5..=7u64 { t.tick_miss(1, e); }
        assert_eq!(t.status(1), PeerStatus::Dead); // 6 misses = DEAD_THRESHOLD
    }

    #[test]
    fn beat_resets_miss_counter() {
        let mut t = HeartbeatTracker::new();
        for e in 1..=6u64 { t.tick_miss(1, e); }
        assert_eq!(t.status(1), PeerStatus::Dead);
        t.beat(1, 6);
        assert_eq!(t.status(1), PeerStatus::Alive);
        assert_eq!(t.miss_count(1), 0);
    }

    #[test]
    fn suspect_and_dead_peers_listed() {
        let mut t = HeartbeatTracker::new();
        t.beat(1, 1); // Alive: 0 misses
        for e in 1..=3u64 { t.tick_miss(2, e); } // Suspect: 3 misses
        for e in 1..=6u64 { t.tick_miss(3, e); } // Dead: 6 misses
        assert_eq!(t.suspect_peers(), vec![2]);
        assert_eq!(t.dead_peers(), vec![3]);
        assert_eq!(t.alive_peers(), vec![1]);
    }
}
