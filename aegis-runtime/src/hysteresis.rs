//! Pillar 7 — Non-Linear Hysteresis Peer Reputation Filter
//!
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Prevents network flapping and state-manipulation exploits. Peers that emit
//! malformed packets or drift from consensus are throttled via an exponential
//! dampening curve. The penalty scales non-linearly — isolated errors cause
//! minimal degradation; recurring faults create a steep mathematical cliff.
//!
//! Reputation score: 0–10000 (scaled integer, 10000 = fully trusted).
//! Recovery rate decreases exponentially with demotion count.
//! Quarantine threshold: score < QUARANTINE_THRESHOLD.
//!
//! Constitutional invariants:
//! - No floating-point — all arithmetic is integer
//! - BTreeMap<PeerId, PeerRecord> — deterministic iteration
//! - Recovery is strictly bounded: can never exceed MAX_SCORE
//! - Penalty is non-linear: each demotion doubles the penalty weight (bit-shift)

use std::collections::BTreeMap;

pub type PeerId = u64;

/// Maximum reputation score (fully trusted).
pub const MAX_SCORE: u16 = 10_000;

/// Score below which a peer is quarantined (no messages routed).
pub const QUARANTINE_THRESHOLD: u16 = 2_000;

/// Score below which a peer is soft-throttled (messages delayed).
pub const THROTTLE_THRESHOLD: u16 = 5_000;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum PeerStatus {
    Trusted,
    Throttled,
    Quarantined,
}

/// Per-peer reputation record.
#[derive(Clone, Debug)]
pub struct PeerRecord {
    pub peer_id: PeerId,
    pub score: u16,
    pub demotion_count: u16,
    pub penalty_events: u32,
    pub recovery_events: u32,
}

impl PeerRecord {
    pub fn new(peer_id: PeerId) -> Self {
        Self { peer_id, score: MAX_SCORE, demotion_count: 0, penalty_events: 0, recovery_events: 0 }
    }

    pub fn status(&self) -> PeerStatus {
        if self.score < QUARANTINE_THRESHOLD { PeerStatus::Quarantined }
        else if self.score < THROTTLE_THRESHOLD { PeerStatus::Throttled }
        else { PeerStatus::Trusted }
    }

    pub fn is_quarantined(&self) -> bool { self.status() == PeerStatus::Quarantined }
}

/// Non-linear penalty weight for the n-th demotion event.
/// penalty_weight(0) = 500, penalty_weight(1) = 1000, penalty_weight(2) = 2000...
/// Capped at MAX_SCORE to prevent overflow.
///
/// Fixes the spec's `calculate_hysteresis_recovery` bug (1i16.checked_shr always returns 0).
pub fn penalty_weight(demotion_count: u16) -> u16 {
    let shift = demotion_count.min(4) as u32; // cap at shift=4 → max weight 8000
    let base: u32 = 500u32 << shift;          // 500 * 2^n
    base.min(MAX_SCORE as u32) as u16
}

/// Recovery increment after n demotions — halves with each demotion.
/// recovery_increment(0) = 200, (1) = 100, (2) = 50, (3) = 25, ... floor at 1.
pub fn recovery_increment(demotion_count: u16) -> u16 {
    let shift = demotion_count.min(7) as u32;
    let inc: u32 = 200u32 >> shift;
    inc.max(1) as u16
}

/// The peer reputation registry and filter.
pub struct HysteresisFilter {
    peers: BTreeMap<PeerId, PeerRecord>,
    total_quarantined: u32,
    total_penalties: u32,
}

impl HysteresisFilter {
    pub fn new() -> Self {
        Self { peers: BTreeMap::new(), total_quarantined: 0, total_penalties: 0 }
    }

    /// Register a new peer at full trust.
    pub fn register_peer(&mut self, id: PeerId) {
        self.peers.entry(id).or_insert_with(|| PeerRecord::new(id));
    }

    /// Apply a penalty event (malformed packet, consensus drift, etc.).
    /// Returns the new status.
    pub fn penalize(&mut self, id: PeerId) -> PeerStatus {
        let rec = self.peers.entry(id).or_insert_with(|| PeerRecord::new(id));
        let weight = penalty_weight(rec.demotion_count);
        rec.score = rec.score.saturating_sub(weight);
        rec.demotion_count += 1;
        rec.penalty_events += 1;
        self.total_penalties += 1;
        let status = rec.status();
        if status == PeerStatus::Quarantined { self.total_quarantined += 1; }
        status
    }

    /// Apply a recovery tick (positive behavior observed).
    /// Returns the new score.
    pub fn recover(&mut self, id: PeerId) -> u16 {
        let rec = self.peers.entry(id).or_insert_with(|| PeerRecord::new(id));
        let inc = recovery_increment(rec.demotion_count);
        rec.score = rec.score.saturating_add(inc).min(MAX_SCORE);
        rec.recovery_events += 1;
        rec.score
    }

    pub fn get_peer(&self, id: PeerId) -> Option<&PeerRecord> { self.peers.get(&id) }
    pub fn peer_count(&self) -> usize { self.peers.len() }
    pub fn quarantined_count(&self) -> u32 { self.total_quarantined }
    pub fn total_penalties(&self) -> u32 { self.total_penalties }

    /// Active quarantine count — peers currently below threshold.
    pub fn active_quarantines(&self) -> u16 {
        self.peers.values().filter(|r| r.is_quarantined()).count() as u16
    }
}

impl Default for HysteresisFilter { fn default() -> Self { Self::new() } }

#[cfg(test)]
mod tests {
    use super::*;

    #[test] fn new_peer_is_trusted() {
        let mut f = HysteresisFilter::new();
        f.register_peer(1);
        assert_eq!(f.get_peer(1).unwrap().status(), PeerStatus::Trusted);
    }

    #[test] fn single_penalty_reduces_score() {
        let mut f = HysteresisFilter::new();
        f.register_peer(1);
        f.penalize(1);
        let score = f.get_peer(1).unwrap().score;
        assert!(score < MAX_SCORE);
    }

    #[test] fn repeated_penalties_quarantine() {
        let mut f = HysteresisFilter::new();
        f.register_peer(42);
        // Apply enough penalties to drop below QUARANTINE_THRESHOLD
        for _ in 0..8 { f.penalize(42); }
        assert!(f.get_peer(42).unwrap().is_quarantined());
    }

    #[test] fn penalty_weight_increases_nonlinearly() {
        let w0 = penalty_weight(0);
        let w1 = penalty_weight(1);
        let w2 = penalty_weight(2);
        assert!(w0 < w1 && w1 < w2, "penalty must be non-linear: w0={} w1={} w2={}", w0, w1, w2);
        assert_eq!(w1, w0 * 2); // exactly doubles
    }

    #[test] fn recovery_decreases_with_demotions() {
        let r0 = recovery_increment(0);
        let r1 = recovery_increment(1);
        let r3 = recovery_increment(3);
        assert!(r0 > r1 && r1 > r3);
    }

    #[test] fn recovery_floor_is_1() {
        assert_eq!(recovery_increment(100), 1);
    }

    #[test] fn penalty_weight_capped_at_max() {
        assert!(penalty_weight(100) <= MAX_SCORE);
    }

    #[test] fn recovery_cannot_exceed_max_score() {
        let mut f = HysteresisFilter::new();
        f.register_peer(1);
        for _ in 0..1000 { f.recover(1); }
        assert_eq!(f.get_peer(1).unwrap().score, MAX_SCORE);
    }

    #[test] fn active_quarantines_counts_correctly() {
        let mut f = HysteresisFilter::new();
        for id in 1..=3u64 { f.register_peer(id); }
        for _ in 0..8 { f.penalize(1); f.penalize(2); }
        assert_eq!(f.active_quarantines(), 2);
    }

    #[test] fn btreemap_peer_order_deterministic() {
        let mut f = HysteresisFilter::new();
        for id in [5u64, 2, 8, 1, 3] { f.register_peer(id); }
        let ids: Vec<PeerId> = f.peers.keys().copied().collect();
        assert_eq!(ids, vec![1, 2, 3, 5, 8]);
    }

    // 11. MAX_SCORE constant is 10_000
    #[test] fn max_score_is_10000() {
        assert_eq!(MAX_SCORE, 10_000);
    }

    // 12. QUARANTINE_THRESHOLD is 2_000
    #[test] fn quarantine_threshold_is_2000() {
        assert_eq!(QUARANTINE_THRESHOLD, 2_000);
    }

    // 13. THROTTLE_THRESHOLD is 5_000
    #[test] fn throttle_threshold_is_5000() {
        assert_eq!(THROTTLE_THRESHOLD, 5_000);
    }

    // 14. New peer starts at MAX_SCORE
    #[test] fn new_peer_score_is_max() {
        let mut f = HysteresisFilter::new();
        f.register_peer(7);
        assert_eq!(f.get_peer(7).unwrap().score, MAX_SCORE);
    }

    // 15. New peer demotion_count starts at 0
    #[test] fn new_peer_demotion_count_zero() {
        let mut f = HysteresisFilter::new();
        f.register_peer(1);
        assert_eq!(f.get_peer(1).unwrap().demotion_count, 0);
    }

    // 16. New peer penalty_events starts at 0
    #[test] fn new_peer_penalty_events_zero() {
        let mut f = HysteresisFilter::new();
        f.register_peer(2);
        assert_eq!(f.get_peer(2).unwrap().penalty_events, 0);
    }

    // 17. penalty_weight(0) == 500
    #[test] fn penalty_weight_0_is_500() {
        assert_eq!(penalty_weight(0), 500);
    }

    // 18. penalty_weight(1) == 1000
    #[test] fn penalty_weight_1_is_1000() {
        assert_eq!(penalty_weight(1), 1000);
    }

    // 19. penalty_weight(2) == 2000
    #[test] fn penalty_weight_2_is_2000() {
        assert_eq!(penalty_weight(2), 2000);
    }

    // 20. penalty_weight(4) == 8000 (max shift = 4, cap at MAX_SCORE prevents overflow)
    #[test] fn penalty_weight_4_is_8000() {
        assert_eq!(penalty_weight(4), 8000);
    }

    // 21. penalty_weight(5) == 8000 (shift capped at 4, so same as penalty_weight(4))
    #[test] fn penalty_weight_5_capped_at_max() {
        // shift is capped at 4: 500 << 4 = 8000; counts > 4 return the same value
        assert_eq!(penalty_weight(5), 8000);
        assert_eq!(penalty_weight(10), 8000);
    }

    // 22. recovery_increment(0) == 200
    #[test] fn recovery_increment_0_is_200() {
        assert_eq!(recovery_increment(0), 200);
    }

    // 23. recovery_increment(1) == 100
    #[test] fn recovery_increment_1_is_100() {
        assert_eq!(recovery_increment(1), 100);
    }

    // 24. recovery_increment(2) == 50
    #[test] fn recovery_increment_2_is_50() {
        assert_eq!(recovery_increment(2), 50);
    }

    // 25. recovery_increment(7) == 1 (floor: 200>>7 = 1)
    #[test] fn recovery_increment_7_is_1() {
        assert_eq!(recovery_increment(7), 1);
    }

    // 26. total_penalties counter increments on each penalize call
    #[test] fn total_penalties_increments_per_call() {
        let mut f = HysteresisFilter::new();
        f.register_peer(1);
        f.penalize(1);
        f.penalize(1);
        assert_eq!(f.total_penalties(), 2);
    }

    // 27. get_peer returns None for unregistered peer
    #[test] fn get_peer_none_for_unknown() {
        let f = HysteresisFilter::new();
        assert!(f.get_peer(9999).is_none());
    }

    // 28. peer_count increments with each register_peer
    #[test] fn peer_count_increments() {
        let mut f = HysteresisFilter::new();
        assert_eq!(f.peer_count(), 0);
        f.register_peer(1);
        assert_eq!(f.peer_count(), 1);
        f.register_peer(2);
        assert_eq!(f.peer_count(), 2);
    }

    // 29. register_peer is idempotent — second call does not overwrite
    #[test] fn register_peer_idempotent() {
        let mut f = HysteresisFilter::new();
        f.register_peer(5);
        f.penalize(5); // score drops
        let score_after_penalty = f.get_peer(5).unwrap().score;
        f.register_peer(5); // second register — should not reset
        assert_eq!(f.get_peer(5).unwrap().score, score_after_penalty);
        assert_eq!(f.peer_count(), 1);
    }

    // 30. penalize auto-registers a peer not previously registered
    #[test] fn penalize_auto_registers_peer() {
        let mut f = HysteresisFilter::new();
        f.penalize(77); // auto-register via or_insert_with
        assert!(f.get_peer(77).is_some());
    }

    // 31. recover auto-registers a peer not previously registered
    #[test] fn recover_auto_registers_peer() {
        let mut f = HysteresisFilter::new();
        let score = f.recover(88);
        assert_eq!(score, MAX_SCORE); // fresh peer: MAX_SCORE + increment → still MAX_SCORE (saturating)
    }

    // 32. PeerStatus::Trusted when score >= THROTTLE_THRESHOLD
    #[test] fn peer_trusted_when_score_at_or_above_throttle() {
        let mut f = HysteresisFilter::new();
        f.register_peer(10);
        assert_eq!(f.get_peer(10).unwrap().status(), PeerStatus::Trusted);
    }

    // 33. PeerStatus::Throttled when score in [QUARANTINE_THRESHOLD, THROTTLE_THRESHOLD)
    #[test] fn peer_throttled_when_score_in_middle_band() {
        let r = PeerRecord { peer_id: 1, score: 3000, demotion_count: 0, penalty_events: 0, recovery_events: 0 };
        assert_eq!(r.status(), PeerStatus::Throttled);
    }

    // 34. PeerStatus::Quarantined when score < QUARANTINE_THRESHOLD
    #[test] fn peer_quarantined_when_score_below_threshold() {
        let r = PeerRecord { peer_id: 1, score: 1999, demotion_count: 0, penalty_events: 0, recovery_events: 0 };
        assert_eq!(r.status(), PeerStatus::Quarantined);
        assert!(r.is_quarantined());
    }

    // 35. active_quarantines is 0 when no peers are quarantined
    #[test] fn active_quarantines_zero_initially() {
        let mut f = HysteresisFilter::new();
        for id in 1..=5u64 { f.register_peer(id); }
        assert_eq!(f.active_quarantines(), 0);
    }

    // 36. Default HysteresisFilter has no peers
    #[test] fn default_filter_no_peers() {
        let f = HysteresisFilter::default();
        assert_eq!(f.peer_count(), 0);
        assert_eq!(f.active_quarantines(), 0);
        assert_eq!(f.total_penalties(), 0);
    }

    // 37. quarantined_count cumulative total vs active_quarantines
    #[test] fn quarantined_count_vs_active_quarantines() {
        let mut f = HysteresisFilter::new();
        f.register_peer(1);
        for _ in 0..8 { f.penalize(1); }
        // quarantined_count is cumulative (counts every time a penalize transitions to quarantine)
        assert!(f.quarantined_count() >= 1);
        assert_eq!(f.active_quarantines(), 1);
    }

    // 38. recovery_events counter increments on each recover call
    #[test] fn recovery_events_increments() {
        let mut f = HysteresisFilter::new();
        f.register_peer(1);
        f.recover(1);
        f.recover(1);
        assert_eq!(f.get_peer(1).unwrap().recovery_events, 2);
    }

    // 39. score never drops below 0 (saturating_sub)
    #[test] fn score_never_below_zero() {
        let mut f = HysteresisFilter::new();
        f.register_peer(1);
        for _ in 0..100 { f.penalize(1); }
        assert_eq!(f.get_peer(1).unwrap().score, 0);
    }

    // 40. score never exceeds MAX_SCORE after recovery
    #[test] fn score_never_exceeds_max_on_recovery() {
        let mut f = HysteresisFilter::new();
        f.register_peer(1);
        for _ in 0..100 { f.recover(1); }
        assert_eq!(f.get_peer(1).unwrap().score, MAX_SCORE);
    }
}
