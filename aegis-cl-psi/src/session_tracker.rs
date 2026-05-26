//! Gate 293 — Gossip Session Tracker: per-peer session lifecycle management (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks the lifecycle of gossip sessions per peer: open, active, suspended, closed.
//! A session is identified by (peer_id, session_id). Each state transition is
//! recorded as a hash-linked SessionRecord. Sessions can only advance forward
//! through allowed transitions.
//!
//! SessionState:
//!   Open        — connection established, no messages yet
//!   Active      — messages exchanged
//!   Suspended   — temporarily paused (e.g., rate limit hit)
//!   Closed      — session terminated
//!
//! Allowed transitions: Open→Active, Open→Closed, Active→Suspended, Active→Closed,
//!                      Suspended→Active, Suspended→Closed.
//! Illegal transitions are rejected with SessionError::InvalidTransition.
//!
//! SessionRecord:
//!   peer_id       — u32
//!   session_id    — u64
//!   epoch         — u64
//!   from_state    — SessionState
//!   to_state      — SessionState
//!   record_hash   — SHA-256(prev ‖ peer_be4 ‖ sess_be8 ‖ epoch_be8 ‖ from_byte ‖ to_byte)
//!   prev_hash     — [u8; 32]
//!
//! SessionHistory: hash-chained records per (peer_id, session_id).
//!   transition(), current_state(), closed_count(), suspended_count(), verify_chain().
//!
//! SessionRegistry: BTreeMap<(peer_id, session_id), SessionHistory>.
//!   open_session(), transition(), active_sessions(), closed_session_count().

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

// ─── Session state ────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum SessionState {
    Open      = 0,
    Active    = 1,
    Suspended = 2,
    Closed    = 3,
}

impl SessionState {
    pub fn state_byte(self) -> u8 { self as u8 }

    pub fn is_terminal(self) -> bool { matches!(self, Self::Closed) }

    /// Returns true if transitioning from self to next is allowed.
    pub fn can_transition_to(self, next: SessionState) -> bool {
        matches!(
            (self, next),
            (SessionState::Open,      SessionState::Active)
            | (SessionState::Open,      SessionState::Closed)
            | (SessionState::Active,    SessionState::Suspended)
            | (SessionState::Active,    SessionState::Closed)
            | (SessionState::Suspended, SessionState::Active)
            | (SessionState::Suspended, SessionState::Closed)
        )
    }
}

// ─── Session record ───────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct SessionRecord {
    pub peer_id:    u32,
    pub session_id: u64,
    pub epoch:      u64,
    pub from_state: SessionState,
    pub to_state:   SessionState,
    pub record_hash:[u8; 32],
    pub prev_hash:  [u8; 32],
}

pub const SESSION_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_session_hash(
    peer_id:    u32,
    session_id: u64,
    epoch:      u64,
    from_state: SessionState,
    to_state:   SessionState,
    prev:       &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(session_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update([from_state.state_byte(), to_state.state_byte()]);
    h.finalize().into()
}

pub fn build_session_record(
    peer_id:    u32,
    session_id: u64,
    epoch:      u64,
    from_state: SessionState,
    to_state:   SessionState,
    prev_hash:  &[u8; 32],
) -> SessionRecord {
    let record_hash = compute_session_hash(peer_id, session_id, epoch, from_state, to_state, prev_hash);
    SessionRecord { peer_id, session_id, epoch, from_state, to_state, record_hash, prev_hash: *prev_hash }
}

// ─── Session history ──────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct SessionHistory {
    peer_id:    u32,
    session_id: u64,
    current:    SessionState,
    records:    Vec<SessionRecord>,
}

#[derive(Debug)]
pub enum SessionError {
    InvalidTransition { from: SessionState, to: SessionState },
    SessionAlreadyClosed,
    SessionNotFound,
    DuplicateSessionId,
}

impl SessionHistory {
    pub fn new(peer_id: u32, session_id: u64) -> Self {
        Self { peer_id, session_id, current: SessionState::Open, records: Vec::new() }
    }

    pub fn current_state(&self) -> SessionState { self.current }

    pub fn len(&self)     -> usize { self.records.len() }
    pub fn is_empty(&self)-> bool  { self.records.is_empty() }
    pub fn records(&self) -> &[SessionRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(SESSION_GENESIS_HASH)
    }

    pub fn transition(
        &mut self,
        epoch:    u64,
        to_state: SessionState,
    ) -> Result<&SessionRecord, SessionError> {
        if self.current.is_terminal() {
            return Err(SessionError::SessionAlreadyClosed);
        }
        if !self.current.can_transition_to(to_state) {
            return Err(SessionError::InvalidTransition { from: self.current, to: to_state });
        }
        let from_state = self.current;
        let prev = self.last_hash();
        let r = build_session_record(
            self.peer_id, self.session_id, epoch, from_state, to_state, &prev,
        );
        self.records.push(r);
        self.current = to_state;
        Ok(self.records.last().unwrap())
    }

    pub fn closed_count(&self) -> usize {
        self.records.iter().filter(|r| r.to_state == SessionState::Closed).count()
    }

    pub fn suspended_count(&self) -> usize {
        self.records.iter().filter(|r| r.to_state == SessionState::Suspended).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = SESSION_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_session_hash(
                r.peer_id, r.session_id, r.epoch, r.from_state, r.to_state, &r.prev_hash,
            );
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

// ─── Session registry ─────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct SessionRegistry {
    sessions: BTreeMap<(u32, u64), SessionHistory>,
}

impl SessionRegistry {
    pub fn new() -> Self { Self { sessions: BTreeMap::new() } }

    pub fn session_count(&self) -> usize { self.sessions.len() }

    pub fn open_session(&mut self, peer_id: u32, session_id: u64) -> Result<(), SessionError> {
        if self.sessions.contains_key(&(peer_id, session_id)) {
            return Err(SessionError::DuplicateSessionId);
        }
        self.sessions.insert((peer_id, session_id), SessionHistory::new(peer_id, session_id));
        Ok(())
    }

    pub fn transition(
        &mut self,
        peer_id:    u32,
        session_id: u64,
        epoch:      u64,
        to_state:   SessionState,
    ) -> Result<SessionRecord, SessionError> {
        let history = self.sessions.get_mut(&(peer_id, session_id))
            .ok_or(SessionError::SessionNotFound)?;
        history.transition(epoch, to_state).map(|r| r.clone())
    }

    pub fn current_state(&self, peer_id: u32, session_id: u64) -> Option<SessionState> {
        self.sessions.get(&(peer_id, session_id)).map(|h| h.current_state())
    }

    /// All (peer_id, session_id) pairs that are NOT in Closed state.
    pub fn active_sessions(&self) -> Vec<(u32, u64)> {
        self.sessions.iter()
            .filter(|(_, h)| !h.current_state().is_terminal())
            .map(|(&key, _)| key)
            .collect()
    }

    pub fn closed_session_count(&self) -> usize {
        self.sessions.values()
            .filter(|h| h.current_state().is_terminal())
            .count()
    }

    pub fn get_history(&self, peer_id: u32, session_id: u64) -> Option<&SessionHistory> {
        self.sessions.get(&(peer_id, session_id))
    }
}

impl Default for SessionRegistry {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── SessionState ──────────────────────────────────────────────────────────

    #[test]
    fn state_bytes() {
        assert_eq!(SessionState::Open.state_byte(),      0);
        assert_eq!(SessionState::Active.state_byte(),    1);
        assert_eq!(SessionState::Suspended.state_byte(), 2);
        assert_eq!(SessionState::Closed.state_byte(),    3);
    }

    #[test]
    fn terminal_state() {
        assert!(SessionState::Closed.is_terminal());
        assert!(!SessionState::Active.is_terminal());
    }

    #[test]
    fn allowed_transitions() {
        assert!(SessionState::Open.can_transition_to(SessionState::Active));
        assert!(SessionState::Open.can_transition_to(SessionState::Closed));
        assert!(SessionState::Active.can_transition_to(SessionState::Suspended));
        assert!(SessionState::Active.can_transition_to(SessionState::Closed));
        assert!(SessionState::Suspended.can_transition_to(SessionState::Active));
        assert!(SessionState::Suspended.can_transition_to(SessionState::Closed));
    }

    #[test]
    fn forbidden_transitions() {
        assert!(!SessionState::Open.can_transition_to(SessionState::Suspended));
        assert!(!SessionState::Active.can_transition_to(SessionState::Open));
        assert!(!SessionState::Suspended.can_transition_to(SessionState::Open));
        assert!(!SessionState::Closed.can_transition_to(SessionState::Active));
    }

    // ── build_session_record ──────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let r = build_session_record(1, 1, 1, SessionState::Open, SessionState::Active, &SESSION_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_session_record(1, 1, 1, SessionState::Open, SessionState::Active, &SESSION_GENESIS_HASH);
        let r2 = build_session_record(1, 1, 1, SessionState::Open, SessionState::Active, &SESSION_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    // ── SessionHistory ────────────────────────────────────────────────────────

    #[test]
    fn new_history_open_state() {
        let h = SessionHistory::new(1, 42);
        assert_eq!(h.current_state(), SessionState::Open);
        assert!(h.is_empty());
    }

    #[test]
    fn valid_transition_chain() {
        let mut h = SessionHistory::new(1, 1);
        h.transition(1, SessionState::Active).unwrap();
        h.transition(2, SessionState::Suspended).unwrap();
        h.transition(3, SessionState::Active).unwrap();
        h.transition(4, SessionState::Closed).unwrap();
        assert_eq!(h.current_state(), SessionState::Closed);
        assert_eq!(h.len(), 4);
    }

    #[test]
    fn invalid_transition_rejected() {
        let mut h = SessionHistory::new(1, 1);
        assert!(matches!(
            h.transition(1, SessionState::Suspended),
            Err(SessionError::InvalidTransition { .. })
        ));
    }

    #[test]
    fn closed_session_rejects_further_transitions() {
        let mut h = SessionHistory::new(1, 1);
        h.transition(1, SessionState::Closed).unwrap();
        assert!(matches!(
            h.transition(2, SessionState::Active),
            Err(SessionError::SessionAlreadyClosed)
        ));
    }

    #[test]
    fn chain_links() {
        let mut h = SessionHistory::new(1, 1);
        h.transition(1, SessionState::Active).unwrap();
        h.transition(2, SessionState::Closed).unwrap();
        assert_eq!(h.records()[1].prev_hash, h.records()[0].record_hash);
    }

    #[test]
    fn suspended_count_tracked() {
        let mut h = SessionHistory::new(1, 1);
        h.transition(1, SessionState::Active).unwrap();
        h.transition(2, SessionState::Suspended).unwrap();
        h.transition(3, SessionState::Active).unwrap();
        h.transition(4, SessionState::Suspended).unwrap();
        assert_eq!(h.suspended_count(), 2);
    }

    #[test]
    fn verify_chain_valid() {
        let mut h = SessionHistory::new(1, 1);
        h.transition(1, SessionState::Active).unwrap();
        h.transition(2, SessionState::Suspended).unwrap();
        h.transition(3, SessionState::Active).unwrap();
        let (valid, broken) = h.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    // ── SessionRegistry ───────────────────────────────────────────────────────

    #[test]
    fn open_and_query() {
        let mut reg = SessionRegistry::new();
        reg.open_session(1, 100).unwrap();
        assert_eq!(reg.current_state(1, 100), Some(SessionState::Open));
        assert_eq!(reg.active_sessions(), vec![(1, 100)]);
    }

    #[test]
    fn duplicate_session_rejected() {
        let mut reg = SessionRegistry::new();
        reg.open_session(1, 100).unwrap();
        assert!(matches!(reg.open_session(1, 100), Err(SessionError::DuplicateSessionId)));
    }

    #[test]
    fn transition_via_registry() {
        let mut reg = SessionRegistry::new();
        reg.open_session(1, 100).unwrap();
        reg.transition(1, 100, 1, SessionState::Active).unwrap();
        reg.transition(1, 100, 2, SessionState::Closed).unwrap();
        assert_eq!(reg.current_state(1, 100), Some(SessionState::Closed));
        assert_eq!(reg.closed_session_count(), 1);
    }

    #[test]
    fn active_sessions_excludes_closed() {
        let mut reg = SessionRegistry::new();
        reg.open_session(1, 1).unwrap();
        reg.open_session(2, 2).unwrap();
        reg.transition(2, 2, 1, SessionState::Closed).unwrap();
        let active = reg.active_sessions();
        assert_eq!(active, vec![(1, 1)]);
    }

    #[test]
    fn unknown_session_errors() {
        let mut reg = SessionRegistry::new();
        assert!(matches!(
            reg.transition(99, 99, 1, SessionState::Active),
            Err(SessionError::SessionNotFound)
        ));
    }
}
