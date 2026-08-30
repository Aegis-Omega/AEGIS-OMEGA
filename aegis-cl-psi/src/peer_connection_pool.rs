//! Gate 309 — Gossip Peer Connection Pool: connection lifecycle management (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Manages a pool of peer connections with lifecycle tracking. Each connection
//! transitions through states: Idle → Active → Draining → Closed. The pool enforces
//! a maximum connection limit and provides connection reuse. Connection events are
//! recorded as hash-chained PoolRecords.
//!
//! Constants:
//!   MAX_POOL_SIZE: usize = 64       (max simultaneous connections)
//!   MAX_IDLE_EPOCHS: u64 = 20       (idle connections evicted after this many epochs)
//!
//! ConnectionState: Idle | Active | Draining | Closed
//!
//! PoolRecord:
//!   peer_id, epoch, from_state, to_state
//!   record_hash = SHA-256(prev ‖ peer_be4 ‖ epoch_be8 ‖ from_byte ‖ to_byte)
//!   prev_hash
//!
//! PoolLog: hash-chained PoolRecords.
//!   push(), transition_count_to(state), verify_chain().
//!
//! ConnectionEntry: peer_id, state, opened_epoch, last_used_epoch (internal)
//!
//! PeerConnectionPool:
//!   connect(peer_id, epoch) → Result<(), PoolError>  (Idle→Active; creates entry if needed)
//!   release(peer_id, epoch) → bool  (Active→Idle; false if not Active)
//!   drain(peer_id, epoch) → bool    (Active|Idle→Draining)
//!   close(peer_id, epoch) → bool    (any→Closed; removes from pool)
//!   evict_idle(current_epoch)       — closes connections idle ≥ MAX_IDLE_EPOCHS
//!   state(peer_id) → Option<ConnectionState>
//!   active_count() → usize
//!   idle_count() → usize
//!   get_log() → &PoolLog

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const MAX_POOL_SIZE:   usize = 64;
pub const MAX_IDLE_EPOCHS: u64   = 20;

// ─── Connection state ─────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ConnectionState {
    Idle     = 0,
    Active   = 1,
    Draining = 2,
    Closed   = 3,
}

impl ConnectionState {
    pub fn state_byte(self) -> u8 { self as u8 }
}

// ─── Pool record ──────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct PoolRecord {
    pub peer_id:    u32,
    pub epoch:      u64,
    pub from_state: ConnectionState,
    pub to_state:   ConnectionState,
    pub record_hash: [u8; 32],
    pub prev_hash:   [u8; 32],
}

pub const POOL_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_pool_hash(
    peer_id:    u32,
    epoch:      u64,
    from_state: ConnectionState,
    to_state:   ConnectionState,
    prev:       &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update([from_state.state_byte(), to_state.state_byte()]);
    h.finalize().into()
}

pub fn build_pool_record(
    peer_id:    u32,
    epoch:      u64,
    from_state: ConnectionState,
    to_state:   ConnectionState,
    prev_hash:  &[u8; 32],
) -> PoolRecord {
    let record_hash = compute_pool_hash(peer_id, epoch, from_state, to_state, prev_hash);
    PoolRecord { peer_id, epoch, from_state, to_state, record_hash, prev_hash: *prev_hash }
}

// ─── Pool log ─────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct PoolLog {
    records: Vec<PoolRecord>,
}

impl PoolLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[PoolRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(POOL_GENESIS_HASH)
    }

    pub fn push(
        &mut self,
        peer_id:    u32,
        epoch:      u64,
        from_state: ConnectionState,
        to_state:   ConnectionState,
    ) -> &PoolRecord {
        let prev = self.last_hash();
        let r = build_pool_record(peer_id, epoch, from_state, to_state, &prev);
        self.records.push(r);
        self.records.last().unwrap()
    }

    pub fn transition_count_to(&self, state: ConnectionState) -> usize {
        self.records.iter().filter(|r| r.to_state == state).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = POOL_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_pool_hash(r.peer_id, r.epoch, r.from_state, r.to_state, &r.prev_hash);
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for PoolLog {
    fn default() -> Self { Self::new() }
}

// ─── Connection entry ─────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
struct ConnectionEntry {
    state:           ConnectionState,
    opened_epoch:    u64,
    last_used_epoch: u64,
}

// ─── Errors ───────────────────────────────────────────────────────────────────

#[derive(Debug)]
pub enum PoolError {
    PoolFull,
    InvalidTransition,
}

// ─── PeerConnectionPool ───────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct PeerConnectionPool {
    connections: BTreeMap<u32, ConnectionEntry>,
    pub log: PoolLog,
}

impl PeerConnectionPool {
    pub fn new() -> Self { Self { connections: BTreeMap::new(), log: PoolLog::new() } }

    /// Open a connection (new→Idle→Active or existing Idle→Active).
    pub fn connect(&mut self, peer_id: u32, epoch: u64) -> Result<(), PoolError> {
        if let Some(entry) = self.connections.get_mut(&peer_id) {
            match entry.state {
                ConnectionState::Idle => {
                    let from = entry.state;
                    entry.state = ConnectionState::Active;
                    entry.last_used_epoch = epoch;
                    self.log.push(peer_id, epoch, from, ConnectionState::Active);
                    Ok(())
                }
                ConnectionState::Active => Ok(()), // already active
                _ => Err(PoolError::InvalidTransition),
            }
        } else {
            // New connection
            if self.connections.len() >= MAX_POOL_SIZE { return Err(PoolError::PoolFull); }
            self.connections.insert(peer_id, ConnectionEntry {
                state: ConnectionState::Active,
                opened_epoch: epoch,
                last_used_epoch: epoch,
            });
            self.log.push(peer_id, epoch, ConnectionState::Idle, ConnectionState::Active);
            Ok(())
        }
    }

    /// Return a connection to Idle. Returns true if transition succeeded.
    pub fn release(&mut self, peer_id: u32, epoch: u64) -> bool {
        if let Some(entry) = self.connections.get_mut(&peer_id) {
            if entry.state == ConnectionState::Active {
                entry.state = ConnectionState::Idle;
                entry.last_used_epoch = epoch;
                self.log.push(peer_id, epoch, ConnectionState::Active, ConnectionState::Idle);
                return true;
            }
        }
        false
    }

    /// Mark connection as Draining (Active or Idle → Draining).
    pub fn drain(&mut self, peer_id: u32, epoch: u64) -> bool {
        if let Some(entry) = self.connections.get_mut(&peer_id) {
            let from = entry.state;
            if from == ConnectionState::Active || from == ConnectionState::Idle {
                entry.state = ConnectionState::Draining;
                self.log.push(peer_id, epoch, from, ConnectionState::Draining);
                return true;
            }
        }
        false
    }

    /// Close and remove a connection. Returns true if it existed.
    pub fn close(&mut self, peer_id: u32, epoch: u64) -> bool {
        if let Some(entry) = self.connections.remove(&peer_id) {
            self.log.push(peer_id, epoch, entry.state, ConnectionState::Closed);
            true
        } else {
            false
        }
    }

    /// Close all connections idle for ≥ MAX_IDLE_EPOCHS.
    pub fn evict_idle(&mut self, current_epoch: u64) {
        let to_evict: Vec<(u32, ConnectionState)> = self.connections.iter()
            .filter(|(_, e)| {
                e.state == ConnectionState::Idle
                    && current_epoch >= e.last_used_epoch.saturating_add(MAX_IDLE_EPOCHS)
            })
            .map(|(&pid, e)| (pid, e.state))
            .collect();
        for (pid, from) in to_evict {
            self.connections.remove(&pid);
            self.log.push(pid, current_epoch, from, ConnectionState::Closed);
        }
    }

    pub fn state(&self, peer_id: u32) -> Option<ConnectionState> {
        self.connections.get(&peer_id).map(|e| e.state)
    }

    pub fn active_count(&self) -> usize {
        self.connections.values().filter(|e| e.state == ConnectionState::Active).count()
    }

    pub fn idle_count(&self) -> usize {
        self.connections.values().filter(|e| e.state == ConnectionState::Idle).count()
    }

    pub fn pool_size(&self) -> usize { self.connections.len() }
}

impl Default for PeerConnectionPool {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── ConnectionState ───────────────────────────────────────────────────────

    #[test]
    fn state_bytes() {
        assert_eq!(ConnectionState::Idle.state_byte(),     0);
        assert_eq!(ConnectionState::Active.state_byte(),   1);
        assert_eq!(ConnectionState::Draining.state_byte(), 2);
        assert_eq!(ConnectionState::Closed.state_byte(),   3);
    }

    // ── build_pool_record ─────────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let r = build_pool_record(1, 1, ConnectionState::Idle, ConnectionState::Active, &POOL_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_pool_record(1, 1, ConnectionState::Idle, ConnectionState::Active, &POOL_GENESIS_HASH);
        let r2 = build_pool_record(1, 1, ConnectionState::Idle, ConnectionState::Active, &POOL_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    // ── PoolLog ───────────────────────────────────────────────────────────────

    #[test]
    fn log_transition_counts() {
        let mut l = PoolLog::new();
        l.push(1, 1, ConnectionState::Idle, ConnectionState::Active);
        l.push(1, 2, ConnectionState::Active, ConnectionState::Idle);
        l.push(2, 1, ConnectionState::Idle, ConnectionState::Active);
        assert_eq!(l.transition_count_to(ConnectionState::Active), 2);
        assert_eq!(l.transition_count_to(ConnectionState::Idle), 1);
    }

    #[test]
    fn log_chain_links() {
        let mut l = PoolLog::new();
        l.push(1, 1, ConnectionState::Idle, ConnectionState::Active);
        l.push(1, 2, ConnectionState::Active, ConnectionState::Idle);
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    #[test]
    fn log_verify_chain_valid() {
        let mut l = PoolLog::new();
        for i in 0..5u32 {
            l.push(i, i as u64, ConnectionState::Idle, ConnectionState::Active);
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    // ── PeerConnectionPool ────────────────────────────────────────────────────

    #[test]
    fn connect_creates_active() {
        let mut p = PeerConnectionPool::new();
        p.connect(1, 1).unwrap();
        assert_eq!(p.state(1), Some(ConnectionState::Active));
        assert_eq!(p.active_count(), 1);
    }

    #[test]
    fn release_to_idle() {
        let mut p = PeerConnectionPool::new();
        p.connect(1, 1).unwrap();
        assert!(p.release(1, 2));
        assert_eq!(p.state(1), Some(ConnectionState::Idle));
        assert_eq!(p.idle_count(), 1);
    }

    #[test]
    fn reconnect_idle_to_active() {
        let mut p = PeerConnectionPool::new();
        p.connect(1, 1).unwrap();
        p.release(1, 2);
        p.connect(1, 3).unwrap();
        assert_eq!(p.state(1), Some(ConnectionState::Active));
    }

    #[test]
    fn drain_from_active() {
        let mut p = PeerConnectionPool::new();
        p.connect(1, 1).unwrap();
        assert!(p.drain(1, 2));
        assert_eq!(p.state(1), Some(ConnectionState::Draining));
    }

    #[test]
    fn close_removes_peer() {
        let mut p = PeerConnectionPool::new();
        p.connect(1, 1).unwrap();
        assert!(p.close(1, 2));
        assert_eq!(p.state(1), None);
        assert_eq!(p.pool_size(), 0);
        assert_eq!(p.log.transition_count_to(ConnectionState::Closed), 1);
    }

    #[test]
    fn evict_idle_removes_stale() {
        let mut p = PeerConnectionPool::new();
        p.connect(1, 1).unwrap();
        p.release(1, 1);  // idle at epoch 1
        p.connect(2, 1).unwrap(); // active, not idle
        p.evict_idle(1 + MAX_IDLE_EPOCHS); // epoch 21
        assert_eq!(p.state(1), None);  // evicted
        assert_eq!(p.state(2), Some(ConnectionState::Active)); // not evicted
        assert_eq!(p.pool_size(), 1);
    }

    #[test]
    fn release_non_active_returns_false() {
        let mut p = PeerConnectionPool::new();
        assert!(!p.release(99, 1)); // peer not in pool
    }
}
