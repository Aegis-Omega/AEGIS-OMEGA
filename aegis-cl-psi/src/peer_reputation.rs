//! Gate 278 — Peer Reputation Scorer: integer 0–100 reputation tracking (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks peer behavior events and computes a reputation score on a 0–100 scale.
//!
//! ReputationEvent (observed behaviors, each adjusts score):
//!   ValidMessage        → +2 (up to max)
//!   InvalidMessage      → -10
//!   TimelyDelivery      → +1
//!   LateDelivery        → -3
//!   DuplicateMessage    → -2
//!   TtlViolation        → -15 (forwarding message with inflated TTL)
//!   ManifestMismatch    → -20 (advertised vs observed capability mismatch)
//!   ReliableQuorum      → +5 (peer was in winning quorum)
//!
//! Score dynamics:
//!   Initial score: 50
//!   Score clamped to [0, 100] at all times
//!   ReputationTier: Trusted(80–100), Good(60–79), Neutral(40–59), Suspicious(20–39), Blocked(0–19)
//!
//! PeerReputation:
//!   peer_id        — u32
//!   score          — u8 (0–100)
//!   tier           — ReputationTier
//!   event_count    — u64
//!   positive_events — u64
//!   negative_events — u64
//!   rep_hash       — SHA-256(prev ‖ peer_id_be4 ‖ score ‖ event_count_be8)
//!   prev_hash      — [u8; 32]
//!
//! ReputationLedger: BTreeMap<peer_id, PeerReputation>.
//!   record_event(), trusted_peers(), blocked_peers(), weakest_peer().

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const INITIAL_SCORE: u8 = 50;

// ─── Events ───────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ReputationEvent {
    ValidMessage,
    InvalidMessage,
    TimelyDelivery,
    LateDelivery,
    DuplicateMessage,
    TtlViolation,
    ManifestMismatch,
    ReliableQuorum,
}

impl ReputationEvent {
    /// Signed score delta for this event. Negative = penalty.
    pub fn delta(self) -> i16 {
        match self {
            Self::ValidMessage     =>   2,
            Self::InvalidMessage   => -10,
            Self::TimelyDelivery   =>   1,
            Self::LateDelivery     =>  -3,
            Self::DuplicateMessage =>  -2,
            Self::TtlViolation     => -15,
            Self::ManifestMismatch => -20,
            Self::ReliableQuorum   =>   5,
        }
    }

    pub fn is_positive(self) -> bool { self.delta() > 0 }
}

// ─── Tier ─────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ReputationTier {
    Blocked    = 0,  // 0–19
    Suspicious = 1,  // 20–39
    Neutral    = 2,  // 40–59
    Good       = 3,  // 60–79
    Trusted    = 4,  // 80–100
}

pub fn classify_tier(score: u8) -> ReputationTier {
    if score < 20      { ReputationTier::Blocked }
    else if score < 40 { ReputationTier::Suspicious }
    else if score < 60 { ReputationTier::Neutral }
    else if score < 80 { ReputationTier::Good }
    else               { ReputationTier::Trusted }
}

// ─── Peer reputation ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct PeerReputation {
    pub peer_id:         u32,
    pub score:           u8,
    pub tier:            ReputationTier,
    pub event_count:     u64,
    pub positive_events: u64,
    pub negative_events: u64,
    pub rep_hash:        [u8; 32],
    pub prev_hash:       [u8; 32],
}

pub const REP_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_rep_hash(
    peer_id:     u32,
    score:       u8,
    event_count: u64,
    prev:        &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update([score]);
    h.update(event_count.to_be_bytes());
    h.finalize().into()
}

impl PeerReputation {
    pub fn new(peer_id: u32) -> Self {
        let score = INITIAL_SCORE;
        let tier  = classify_tier(score);
        let rep_hash = compute_rep_hash(peer_id, score, 0, &REP_GENESIS_HASH);
        Self {
            peer_id, score, tier,
            event_count: 0, positive_events: 0, negative_events: 0,
            rep_hash, prev_hash: REP_GENESIS_HASH,
        }
    }

    pub fn apply_event(&mut self, event: ReputationEvent) {
        let new_score = (self.score as i16 + event.delta())
            .max(0).min(100) as u8;
        self.event_count += 1;
        if event.is_positive() { self.positive_events += 1; }
        else { self.negative_events += 1; }
        let prev = self.rep_hash;
        self.score    = new_score;
        self.tier     = classify_tier(new_score);
        self.rep_hash = compute_rep_hash(self.peer_id, self.score, self.event_count, &prev);
        self.prev_hash = prev;
    }

    pub fn is_blocked(&self) -> bool { self.tier == ReputationTier::Blocked }
    pub fn is_trusted(&self) -> bool { self.tier == ReputationTier::Trusted }
}

// ─── Reputation ledger ────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct ReputationLedger {
    peers: BTreeMap<u32, PeerReputation>,
}

impl ReputationLedger {
    pub fn new() -> Self { Self { peers: BTreeMap::new() } }

    pub fn peer_count(&self) -> usize { self.peers.len() }

    pub fn record_event(&mut self, peer_id: u32, event: ReputationEvent) {
        let rep = self.peers.entry(peer_id)
            .or_insert_with(|| PeerReputation::new(peer_id));
        rep.apply_event(event);
    }

    pub fn get(&self, peer_id: u32) -> Option<&PeerReputation> {
        self.peers.get(&peer_id)
    }

    /// All peers at Trusted tier (BTreeMap order — deterministic).
    pub fn trusted_peers(&self) -> Vec<u32> {
        self.peers.iter()
            .filter(|(_, r)| r.is_trusted())
            .map(|(&id, _)| id)
            .collect()
    }

    /// All peers at Blocked tier.
    pub fn blocked_peers(&self) -> Vec<u32> {
        self.peers.iter()
            .filter(|(_, r)| r.is_blocked())
            .map(|(&id, _)| id)
            .collect()
    }

    /// Peer with lowest score (None if empty).
    pub fn weakest_peer(&self) -> Option<u32> {
        self.peers.iter()
            .min_by_key(|(_, r)| r.score)
            .map(|(&id, _)| id)
    }

    /// Average score across all peers (integer, truncated). 0 if empty.
    pub fn average_score(&self) -> u8 {
        if self.peers.is_empty() { return 0; }
        let sum: usize = self.peers.values().map(|r| r.score as usize).sum();
        (sum / self.peers.len()) as u8
    }
}

impl Default for ReputationLedger {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── ReputationEvent ───────────────────────────────────────────────────────

    #[test]
    fn event_deltas_correct() {
        assert_eq!(ReputationEvent::ValidMessage.delta(),      2);
        assert_eq!(ReputationEvent::InvalidMessage.delta(),   -10);
        assert_eq!(ReputationEvent::TtlViolation.delta(),     -15);
        assert_eq!(ReputationEvent::ManifestMismatch.delta(), -20);
        assert_eq!(ReputationEvent::ReliableQuorum.delta(),    5);
    }

    #[test]
    fn is_positive_correct() {
        assert!(ReputationEvent::ValidMessage.is_positive());
        assert!(!ReputationEvent::InvalidMessage.is_positive());
    }

    // ── classify_tier ─────────────────────────────────────────────────────────

    #[test]
    fn tier_boundaries() {
        assert_eq!(classify_tier(0),   ReputationTier::Blocked);
        assert_eq!(classify_tier(19),  ReputationTier::Blocked);
        assert_eq!(classify_tier(20),  ReputationTier::Suspicious);
        assert_eq!(classify_tier(39),  ReputationTier::Suspicious);
        assert_eq!(classify_tier(40),  ReputationTier::Neutral);
        assert_eq!(classify_tier(59),  ReputationTier::Neutral);
        assert_eq!(classify_tier(60),  ReputationTier::Good);
        assert_eq!(classify_tier(79),  ReputationTier::Good);
        assert_eq!(classify_tier(80),  ReputationTier::Trusted);
        assert_eq!(classify_tier(100), ReputationTier::Trusted);
    }

    // ── PeerReputation ────────────────────────────────────────────────────────

    #[test]
    fn new_peer_starts_neutral() {
        let r = PeerReputation::new(1);
        assert_eq!(r.score, 50);
        assert_eq!(r.tier, ReputationTier::Neutral);
        assert_eq!(r.event_count, 0);
    }

    #[test]
    fn positive_events_increase_score() {
        let mut r = PeerReputation::new(1);
        r.apply_event(ReputationEvent::ReliableQuorum); // +5
        assert_eq!(r.score, 55);
    }

    #[test]
    fn negative_events_decrease_score() {
        let mut r = PeerReputation::new(1);
        r.apply_event(ReputationEvent::InvalidMessage); // -10
        assert_eq!(r.score, 40);
    }

    #[test]
    fn score_clamped_at_zero() {
        let mut r = PeerReputation::new(1);
        for _ in 0..10 {
            r.apply_event(ReputationEvent::ManifestMismatch); // -20 each
        }
        assert_eq!(r.score, 0);
        assert!(r.is_blocked());
    }

    #[test]
    fn score_clamped_at_100() {
        let mut r = PeerReputation::new(1);
        for _ in 0..30 {
            r.apply_event(ReputationEvent::ValidMessage); // +2 each
        }
        assert_eq!(r.score, 100);
        assert!(r.is_trusted());
    }

    #[test]
    fn event_count_tracks() {
        let mut r = PeerReputation::new(1);
        r.apply_event(ReputationEvent::ValidMessage);
        r.apply_event(ReputationEvent::InvalidMessage);
        assert_eq!(r.event_count, 2);
        assert_eq!(r.positive_events, 1);
        assert_eq!(r.negative_events, 1);
    }

    #[test]
    fn rep_hash_nonzero_after_event() {
        let mut r = PeerReputation::new(1);
        let initial_hash = r.rep_hash;
        r.apply_event(ReputationEvent::ValidMessage);
        assert_ne!(r.rep_hash, initial_hash);
        assert_ne!(r.rep_hash, [0u8; 32]);
    }

    #[test]
    fn rep_hash_chain_links() {
        let mut r = PeerReputation::new(1);
        let hash0 = r.rep_hash;
        r.apply_event(ReputationEvent::ValidMessage);
        assert_eq!(r.prev_hash, hash0);
    }

    // ── ReputationLedger ──────────────────────────────────────────────────────

    #[test]
    fn new_ledger_empty() {
        let l = ReputationLedger::new();
        assert_eq!(l.peer_count(), 0);
        assert_eq!(l.average_score(), 0);
    }

    #[test]
    fn record_event_creates_peer() {
        let mut l = ReputationLedger::new();
        l.record_event(1, ReputationEvent::ValidMessage);
        assert_eq!(l.peer_count(), 1);
    }

    #[test]
    fn trusted_and_blocked_peers() {
        let mut l = ReputationLedger::new();
        // Peer 1 → trusted
        for _ in 0..20 { l.record_event(1, ReputationEvent::ValidMessage); } // +40 → 90
        // Peer 2 → blocked
        for _ in 0..5  { l.record_event(2, ReputationEvent::ManifestMismatch); } // -100 → 0
        assert_eq!(l.trusted_peers(), vec![1]);
        assert_eq!(l.blocked_peers(), vec![2]);
    }

    #[test]
    fn weakest_peer() {
        let mut l = ReputationLedger::new();
        l.record_event(1, ReputationEvent::ValidMessage);    // 52
        l.record_event(2, ReputationEvent::InvalidMessage);  // 40
        assert_eq!(l.weakest_peer(), Some(2));
    }

    #[test]
    fn average_score_correct() {
        let mut l = ReputationLedger::new();
        l.record_event(1, ReputationEvent::ReliableQuorum);  // 55
        l.record_event(2, ReputationEvent::LateDelivery);    // 47
        // avg = (55 + 47) / 2 = 51
        assert_eq!(l.average_score(), 51);
    }
}
