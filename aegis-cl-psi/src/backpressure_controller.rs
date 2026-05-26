//! Gate 294 — Gossip Backpressure Controller: downstream-load-aware injection throttling (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! When downstream peers are overloaded (queue depth exceeds threshold), upstream message
//! injection is throttled by reducing an injection allowance. Each tick the allowance is
//! partially restored (leaky-bucket recovery). A BackpressureEvent is emitted whenever
//! the controller transitions between pressure states.
//!
//! PressureLevel:
//!   Normal   — queue_depth ≤ LOW_WATER  (no throttle)
//!   Moderate — LOW_WATER < queue_depth ≤ HIGH_WATER (50 % allowance)
//!   Severe   — queue_depth > HIGH_WATER (10 % allowance)
//!
//! Constants:
//!   LOW_WATER_MARK:  u32 = 100
//!   HIGH_WATER_MARK: u32 = 500
//!   RECOVERY_PER_TICK: u32 = 20   (allowance restored per tick)
//!   MAX_ALLOWANCE: u32 = 200
//!
//! BackpressureEvent:
//!   peer_id       — u32
//!   epoch         — u64
//!   queue_depth   — u32
//!   level         — PressureLevel
//!   allowance     — u32 (remaining after event)
//!   event_hash    — SHA-256(prev ‖ peer_be4 ‖ epoch_be8 ‖ depth_be4 ‖ level_byte ‖ allow_be4)
//!   prev_hash     — [u8; 32]
//!
//! BackpressureLog: hash-chained events per peer.
//!   record(), severe_count(), moderate_count(), verify_chain().
//!
//! BackpressureController: BTreeMap<peer_id, PeerPressureState>.
//!   update(peer_id, epoch, queue_depth) → (PressureLevel, u32 allowed)
//!   tick_recovery(peer_id) — restore allowance by RECOVERY_PER_TICK
//!   get_log(peer_id), peers_under_pressure() → Vec<u32>

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

// ─── Constants ────────────────────────────────────────────────────────────────

pub const LOW_WATER_MARK:    u32 = 100;
pub const HIGH_WATER_MARK:   u32 = 500;
pub const RECOVERY_PER_TICK: u32 = 20;
pub const MAX_ALLOWANCE:     u32 = 200;

// ─── Pressure level ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum PressureLevel {
    Normal   = 0,
    Moderate = 1,
    Severe   = 2,
}

impl PressureLevel {
    pub fn level_byte(self) -> u8 { self as u8 }

    pub fn from_queue_depth(depth: u32) -> Self {
        if depth > HIGH_WATER_MARK      { Self::Severe }
        else if depth > LOW_WATER_MARK  { Self::Moderate }
        else                            { Self::Normal }
    }

    /// Fraction of allowance to grant: Normal=100%, Moderate=50%, Severe=10%.
    /// Returns (numerator, denominator) to avoid f64.
    pub fn allowance_fraction(self) -> (u32, u32) {
        match self {
            Self::Normal   => (1, 1),
            Self::Moderate => (1, 2),
            Self::Severe   => (1, 10),
        }
    }
}

// ─── Backpressure event ───────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct BackpressureEvent {
    pub peer_id:     u32,
    pub epoch:       u64,
    pub queue_depth: u32,
    pub level:       PressureLevel,
    pub allowance:   u32,
    pub event_hash:  [u8; 32],
    pub prev_hash:   [u8; 32],
}

pub const BACKPRESSURE_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_backpressure_hash(
    peer_id:     u32,
    epoch:       u64,
    queue_depth: u32,
    level:       PressureLevel,
    allowance:   u32,
    prev:        &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update(queue_depth.to_be_bytes());
    h.update([level.level_byte()]);
    h.update(allowance.to_be_bytes());
    h.finalize().into()
}

pub fn build_backpressure_event(
    peer_id:     u32,
    epoch:       u64,
    queue_depth: u32,
    level:       PressureLevel,
    allowance:   u32,
    prev_hash:   &[u8; 32],
) -> BackpressureEvent {
    let event_hash = compute_backpressure_hash(peer_id, epoch, queue_depth, level, allowance, prev_hash);
    BackpressureEvent { peer_id, epoch, queue_depth, level, allowance, event_hash, prev_hash: *prev_hash }
}

// ─── Backpressure log ─────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct BackpressureLog {
    peer_id: u32,
    events:  Vec<BackpressureEvent>,
}

#[derive(Debug)]
pub enum BackpressureError {
    StaleEpoch,
}

impl BackpressureLog {
    pub fn new(peer_id: u32) -> Self { Self { peer_id, events: Vec::new() } }

    pub fn len(&self)      -> usize { self.events.len() }
    pub fn is_empty(&self) -> bool  { self.events.is_empty() }
    pub fn events(&self)   -> &[BackpressureEvent] { &self.events }

    pub fn last_hash(&self) -> [u8; 32] {
        self.events.last().map(|e| e.event_hash).unwrap_or(BACKPRESSURE_GENESIS_HASH)
    }

    pub fn record(
        &mut self,
        epoch:       u64,
        queue_depth: u32,
        level:       PressureLevel,
        allowance:   u32,
    ) -> Result<&BackpressureEvent, BackpressureError> {
        if let Some(last) = self.events.last() {
            if epoch < last.epoch { return Err(BackpressureError::StaleEpoch); }
        }
        let prev = self.last_hash();
        let e = build_backpressure_event(self.peer_id, epoch, queue_depth, level, allowance, &prev);
        self.events.push(e);
        Ok(self.events.last().unwrap())
    }

    pub fn severe_count(&self) -> usize {
        self.events.iter().filter(|e| e.level == PressureLevel::Severe).count()
    }

    pub fn moderate_count(&self) -> usize {
        self.events.iter().filter(|e| e.level == PressureLevel::Moderate).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = BACKPRESSURE_GENESIS_HASH;
        for (i, e) in self.events.iter().enumerate() {
            if e.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_backpressure_hash(
                e.peer_id, e.epoch, e.queue_depth, e.level, e.allowance, &e.prev_hash,
            );
            if recomputed != e.event_hash { return (false, Some(i)); }
            expected_prev = e.event_hash;
        }
        (true, None)
    }
}

// ─── Backpressure controller ──────────────────────────────────────────────────

#[derive(Debug, Clone)]
struct PeerPressureState {
    log:       BackpressureLog,
    allowance: u32,
}

#[derive(Debug, Clone)]
pub struct BackpressureController {
    peers: BTreeMap<u32, PeerPressureState>,
}

impl BackpressureController {
    pub fn new() -> Self { Self { peers: BTreeMap::new() } }

    pub fn peer_count(&self) -> usize { self.peers.len() }

    /// Update queue depth for a peer; returns (PressureLevel, granted_allowance).
    /// Allowance is computed as MAX_ALLOWANCE * fraction for the level.
    /// The controller records the event in the peer's log.
    pub fn update(&mut self, peer_id: u32, epoch: u64, queue_depth: u32) -> (PressureLevel, u32) {
        let level = PressureLevel::from_queue_depth(queue_depth);
        let (num, den) = level.allowance_fraction();
        let granted = (MAX_ALLOWANCE * num) / den;

        let state = self.peers.entry(peer_id).or_insert_with(|| PeerPressureState {
            log:       BackpressureLog::new(peer_id),
            allowance: MAX_ALLOWANCE,
        });

        state.allowance = granted;
        let _ = state.log.record(epoch, queue_depth, level, granted);
        (level, granted)
    }

    /// Restore allowance by RECOVERY_PER_TICK (capped at MAX_ALLOWANCE).
    pub fn tick_recovery(&mut self, peer_id: u32) {
        if let Some(state) = self.peers.get_mut(&peer_id) {
            state.allowance = state.allowance.saturating_add(RECOVERY_PER_TICK).min(MAX_ALLOWANCE);
        }
    }

    pub fn current_allowance(&self, peer_id: u32) -> Option<u32> {
        self.peers.get(&peer_id).map(|s| s.allowance)
    }

    pub fn get_log(&self, peer_id: u32) -> Option<&BackpressureLog> {
        self.peers.get(&peer_id).map(|s| &s.log)
    }

    /// All peers currently at Moderate or Severe pressure (last recorded level).
    pub fn peers_under_pressure(&self) -> Vec<u32> {
        self.peers.iter()
            .filter(|(_, s)| {
                s.log.events().last()
                    .map(|e| e.level != PressureLevel::Normal)
                    .unwrap_or(false)
            })
            .map(|(&id, _)| id)
            .collect()
    }
}

impl Default for BackpressureController {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── PressureLevel ─────────────────────────────────────────────────────────

    #[test]
    fn level_bytes() {
        assert_eq!(PressureLevel::Normal.level_byte(),   0);
        assert_eq!(PressureLevel::Moderate.level_byte(), 1);
        assert_eq!(PressureLevel::Severe.level_byte(),   2);
    }

    #[test]
    fn from_queue_depth_normal() {
        assert_eq!(PressureLevel::from_queue_depth(0),              PressureLevel::Normal);
        assert_eq!(PressureLevel::from_queue_depth(LOW_WATER_MARK), PressureLevel::Normal);
    }

    #[test]
    fn from_queue_depth_moderate() {
        assert_eq!(PressureLevel::from_queue_depth(LOW_WATER_MARK + 1),  PressureLevel::Moderate);
        assert_eq!(PressureLevel::from_queue_depth(HIGH_WATER_MARK),     PressureLevel::Moderate);
    }

    #[test]
    fn from_queue_depth_severe() {
        assert_eq!(PressureLevel::from_queue_depth(HIGH_WATER_MARK + 1), PressureLevel::Severe);
        assert_eq!(PressureLevel::from_queue_depth(u32::MAX),            PressureLevel::Severe);
    }

    #[test]
    fn allowance_fractions() {
        assert_eq!(PressureLevel::Normal.allowance_fraction(),   (1, 1));
        assert_eq!(PressureLevel::Moderate.allowance_fraction(), (1, 2));
        assert_eq!(PressureLevel::Severe.allowance_fraction(),   (1, 10));
    }

    // ── build_backpressure_event ──────────────────────────────────────────────

    #[test]
    fn event_hash_nonzero() {
        let e = build_backpressure_event(1, 1, 50, PressureLevel::Normal, 200, &BACKPRESSURE_GENESIS_HASH);
        assert_ne!(e.event_hash, [0u8; 32]);
    }

    #[test]
    fn event_hash_deterministic() {
        let e1 = build_backpressure_event(1, 1, 50, PressureLevel::Normal, 200, &BACKPRESSURE_GENESIS_HASH);
        let e2 = build_backpressure_event(1, 1, 50, PressureLevel::Normal, 200, &BACKPRESSURE_GENESIS_HASH);
        assert_eq!(e1.event_hash, e2.event_hash);
    }

    #[test]
    fn different_level_different_hash() {
        let e1 = build_backpressure_event(1, 1, 200, PressureLevel::Moderate, 100, &BACKPRESSURE_GENESIS_HASH);
        let e2 = build_backpressure_event(1, 1, 200, PressureLevel::Severe,   20,  &BACKPRESSURE_GENESIS_HASH);
        assert_ne!(e1.event_hash, e2.event_hash);
    }

    // ── BackpressureLog ───────────────────────────────────────────────────────

    #[test]
    fn new_log_empty() {
        let l = BackpressureLog::new(1);
        assert!(l.is_empty());
        assert_eq!(l.severe_count(), 0);
        assert_eq!(l.moderate_count(), 0);
    }

    #[test]
    fn log_records_severity_counts() {
        let mut l = BackpressureLog::new(1);
        l.record(1, 50,  PressureLevel::Normal,   200).unwrap();
        l.record(2, 200, PressureLevel::Moderate, 100).unwrap();
        l.record(3, 600, PressureLevel::Severe,   20).unwrap();
        l.record(4, 700, PressureLevel::Severe,   20).unwrap();
        assert_eq!(l.severe_count(), 2);
        assert_eq!(l.moderate_count(), 1);
    }

    #[test]
    fn chain_links() {
        let mut l = BackpressureLog::new(1);
        l.record(1, 50, PressureLevel::Normal, 200).unwrap();
        l.record(2, 50, PressureLevel::Normal, 200).unwrap();
        assert_eq!(l.events()[1].prev_hash, l.events()[0].event_hash);
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut l = BackpressureLog::new(1);
        l.record(5, 50, PressureLevel::Normal, 200).unwrap();
        assert!(matches!(l.record(4, 50, PressureLevel::Normal, 200), Err(BackpressureError::StaleEpoch)));
    }

    #[test]
    fn verify_chain_valid() {
        let mut l = BackpressureLog::new(1);
        for e in 1..=5u64 {
            l.record(e, e as u32 * 50, PressureLevel::Normal, 200).unwrap();
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    // ── BackpressureController ────────────────────────────────────────────────

    #[test]
    fn normal_grants_full_allowance() {
        let mut ctrl = BackpressureController::new();
        let (level, granted) = ctrl.update(1, 1, LOW_WATER_MARK);
        assert_eq!(level, PressureLevel::Normal);
        assert_eq!(granted, MAX_ALLOWANCE);
    }

    #[test]
    fn moderate_grants_half_allowance() {
        let mut ctrl = BackpressureController::new();
        let (level, granted) = ctrl.update(1, 1, LOW_WATER_MARK + 1);
        assert_eq!(level, PressureLevel::Moderate);
        assert_eq!(granted, MAX_ALLOWANCE / 2);
    }

    #[test]
    fn severe_grants_tenth_allowance() {
        let mut ctrl = BackpressureController::new();
        let (level, granted) = ctrl.update(1, 1, HIGH_WATER_MARK + 1);
        assert_eq!(level, PressureLevel::Severe);
        assert_eq!(granted, MAX_ALLOWANCE / 10);
    }

    #[test]
    fn tick_recovery_adds_tokens() {
        let mut ctrl = BackpressureController::new();
        ctrl.update(1, 1, HIGH_WATER_MARK + 1); // Severe → granted = 20
        ctrl.tick_recovery(1);
        assert_eq!(ctrl.current_allowance(1), Some(20 + RECOVERY_PER_TICK));
    }

    #[test]
    fn tick_recovery_caps_at_max() {
        let mut ctrl = BackpressureController::new();
        ctrl.update(1, 1, 0); // Normal → 200
        ctrl.tick_recovery(1); // would be 220 but capped at 200
        assert_eq!(ctrl.current_allowance(1), Some(MAX_ALLOWANCE));
    }

    #[test]
    fn peers_under_pressure_excludes_normal() {
        let mut ctrl = BackpressureController::new();
        ctrl.update(1, 1, 50);                // Normal
        ctrl.update(2, 1, HIGH_WATER_MARK + 1); // Severe
        ctrl.update(3, 1, LOW_WATER_MARK + 10); // Moderate
        let under = ctrl.peers_under_pressure();
        assert!(under.contains(&2));
        assert!(under.contains(&3));
        assert!(!under.contains(&1));
    }

    #[test]
    fn log_persisted_after_update() {
        let mut ctrl = BackpressureController::new();
        ctrl.update(1, 1, 200);
        ctrl.update(1, 2, 600);
        let log = ctrl.get_log(1).unwrap();
        assert_eq!(log.len(), 2);
        assert_eq!(log.severe_count(), 1);
    }

    #[test]
    fn unknown_peer_allowance_none() {
        let ctrl = BackpressureController::new();
        assert_eq!(ctrl.current_allowance(99), None);
        assert!(ctrl.get_log(99).is_none());
    }
}
