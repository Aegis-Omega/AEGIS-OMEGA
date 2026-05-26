//! Gate 305 — Gossip Topic Subscription Registry: peer topic interest tracking (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Maintains a registry of which topics each peer has subscribed to. Topics are
//! identified by a u32 topic_id. Subscriptions and withdrawals are recorded as
//! hash-chained SubRecords for audit.
//!
//! Constants:
//!   MAX_TOPICS_PER_PEER: usize = 64
//!
//! SubEvent: Subscribe | Unsubscribe
//!
//! SubRecord:
//!   peer_id, epoch, topic_id, event, record_hash, prev_hash
//!   record_hash = SHA-256(prev ‖ peer_be4 ‖ epoch_be8 ‖ topic_be4 ‖ event_byte)
//!
//! SubLog: hash-chained SubRecords.
//!   push(), subscribe_count(), unsubscribe_count(), verify_chain().
//!
//! TopicSubscriptionRegistry:
//!   subscribe(peer_id, epoch, topic_id) → Result<(), SubError>   (errors if already subscribed or limit reached)
//!   unsubscribe(peer_id, epoch, topic_id) → bool                  (false if not subscribed)
//!   is_subscribed(peer_id, topic_id) → bool
//!   topics_for(peer_id) → Vec<u32>           (sorted, BTreeSet)
//!   peers_for_topic(topic_id) → Vec<u32>     (peers subscribed to this topic, sorted)
//!   get_log(peer_id) → Option<&SubLog>

use sha2::{Sha256, Digest};
use std::collections::{BTreeMap, BTreeSet};

pub const MAX_TOPICS_PER_PEER: usize = 64;

// ─── Sub event ────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SubEvent {
    Subscribe   = 0,
    Unsubscribe = 1,
}

impl SubEvent {
    pub fn event_byte(self) -> u8 { self as u8 }
}

// ─── Sub record ───────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct SubRecord {
    pub peer_id:     u32,
    pub epoch:       u64,
    pub topic_id:    u32,
    pub event:       SubEvent,
    pub record_hash: [u8; 32],
    pub prev_hash:   [u8; 32],
}

pub const SUB_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_sub_hash(
    peer_id:  u32,
    epoch:    u64,
    topic_id: u32,
    event:    SubEvent,
    prev:     &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update(topic_id.to_be_bytes());
    h.update([event.event_byte()]);
    h.finalize().into()
}

pub fn build_sub_record(
    peer_id:   u32,
    epoch:     u64,
    topic_id:  u32,
    event:     SubEvent,
    prev_hash: &[u8; 32],
) -> SubRecord {
    let record_hash = compute_sub_hash(peer_id, epoch, topic_id, event, prev_hash);
    SubRecord { peer_id, epoch, topic_id, event, record_hash, prev_hash: *prev_hash }
}

// ─── Sub log ──────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct SubLog {
    peer_id: u32,
    records: Vec<SubRecord>,
}

impl SubLog {
    pub fn new(peer_id: u32) -> Self { Self { peer_id, records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[SubRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(SUB_GENESIS_HASH)
    }

    pub fn push(&mut self, epoch: u64, topic_id: u32, event: SubEvent) -> &SubRecord {
        let prev = self.last_hash();
        let r = build_sub_record(self.peer_id, epoch, topic_id, event, &prev);
        self.records.push(r);
        self.records.last().unwrap()
    }

    pub fn subscribe_count(&self) -> usize {
        self.records.iter().filter(|r| r.event == SubEvent::Subscribe).count()
    }

    pub fn unsubscribe_count(&self) -> usize {
        self.records.iter().filter(|r| r.event == SubEvent::Unsubscribe).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = SUB_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_sub_hash(r.peer_id, r.epoch, r.topic_id, r.event, &r.prev_hash);
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

// ─── Subscription registry ────────────────────────────────────────────────────

#[derive(Debug)]
pub enum SubError {
    AlreadySubscribed,
    TopicLimitReached,
}

#[derive(Debug, Clone)]
struct PeerSubState {
    topics: BTreeSet<u32>,
    log:    SubLog,
}

#[derive(Debug, Clone)]
pub struct TopicSubscriptionRegistry {
    peers: BTreeMap<u32, PeerSubState>,
}

impl TopicSubscriptionRegistry {
    pub fn new() -> Self { Self { peers: BTreeMap::new() } }

    fn ensure_peer(&mut self, peer_id: u32) {
        self.peers.entry(peer_id).or_insert_with(|| PeerSubState {
            topics: BTreeSet::new(),
            log:    SubLog::new(peer_id),
        });
    }

    pub fn subscribe(&mut self, peer_id: u32, epoch: u64, topic_id: u32) -> Result<(), SubError> {
        self.ensure_peer(peer_id);
        let state = self.peers.get_mut(&peer_id).unwrap();
        if state.topics.contains(&topic_id) { return Err(SubError::AlreadySubscribed); }
        if state.topics.len() >= MAX_TOPICS_PER_PEER { return Err(SubError::TopicLimitReached); }
        state.topics.insert(topic_id);
        state.log.push(epoch, topic_id, SubEvent::Subscribe);
        Ok(())
    }

    /// Returns true if the peer was subscribed to topic_id.
    pub fn unsubscribe(&mut self, peer_id: u32, epoch: u64, topic_id: u32) -> bool {
        if let Some(state) = self.peers.get_mut(&peer_id) {
            if state.topics.remove(&topic_id) {
                state.log.push(epoch, topic_id, SubEvent::Unsubscribe);
                return true;
            }
        }
        false
    }

    pub fn is_subscribed(&self, peer_id: u32, topic_id: u32) -> bool {
        self.peers.get(&peer_id).map(|s| s.topics.contains(&topic_id)).unwrap_or(false)
    }

    pub fn topics_for(&self, peer_id: u32) -> Vec<u32> {
        self.peers.get(&peer_id)
            .map(|s| s.topics.iter().copied().collect())
            .unwrap_or_default()
    }

    /// All peers subscribed to the given topic, sorted by peer_id.
    pub fn peers_for_topic(&self, topic_id: u32) -> Vec<u32> {
        self.peers.iter()
            .filter(|(_, s)| s.topics.contains(&topic_id))
            .map(|(&pid, _)| pid)
            .collect()
    }

    pub fn get_log(&self, peer_id: u32) -> Option<&SubLog> {
        self.peers.get(&peer_id).map(|s| &s.log)
    }

    pub fn peer_count(&self) -> usize { self.peers.len() }
}

impl Default for TopicSubscriptionRegistry {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── SubEvent ──────────────────────────────────────────────────────────────

    #[test]
    fn event_bytes() {
        assert_eq!(SubEvent::Subscribe.event_byte(),   0);
        assert_eq!(SubEvent::Unsubscribe.event_byte(), 1);
    }

    // ── build_sub_record ──────────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let r = build_sub_record(1, 1, 10, SubEvent::Subscribe, &SUB_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_sub_record(1, 1, 10, SubEvent::Subscribe, &SUB_GENESIS_HASH);
        let r2 = build_sub_record(1, 1, 10, SubEvent::Subscribe, &SUB_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    // ── SubLog ────────────────────────────────────────────────────────────────

    #[test]
    fn log_counts_events() {
        let mut l = SubLog::new(1);
        l.push(1, 10, SubEvent::Subscribe);
        l.push(2, 11, SubEvent::Subscribe);
        l.push(3, 10, SubEvent::Unsubscribe);
        assert_eq!(l.subscribe_count(), 2);
        assert_eq!(l.unsubscribe_count(), 1);
    }

    #[test]
    fn log_chain_links() {
        let mut l = SubLog::new(1);
        l.push(1, 10, SubEvent::Subscribe);
        l.push(2, 11, SubEvent::Unsubscribe);
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    #[test]
    fn log_verify_chain_valid() {
        let mut l = SubLog::new(1);
        for t in 0..5u32 { l.push(t as u64, t * 10, SubEvent::Subscribe); }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    // ── TopicSubscriptionRegistry ─────────────────────────────────────────────

    #[test]
    fn subscribe_and_check() {
        let mut r = TopicSubscriptionRegistry::new();
        r.subscribe(1, 1, 42).unwrap();
        assert!(r.is_subscribed(1, 42));
        assert!(!r.is_subscribed(1, 99));
    }

    #[test]
    fn duplicate_subscribe_errors() {
        let mut r = TopicSubscriptionRegistry::new();
        r.subscribe(1, 1, 42).unwrap();
        assert!(matches!(r.subscribe(1, 2, 42), Err(SubError::AlreadySubscribed)));
    }

    #[test]
    fn unsubscribe_removes_topic() {
        let mut r = TopicSubscriptionRegistry::new();
        r.subscribe(1, 1, 42).unwrap();
        let removed = r.unsubscribe(1, 2, 42);
        assert!(removed);
        assert!(!r.is_subscribed(1, 42));
    }

    #[test]
    fn unsubscribe_not_subscribed_returns_false() {
        let mut r = TopicSubscriptionRegistry::new();
        assert!(!r.unsubscribe(1, 1, 99));
    }

    #[test]
    fn topics_for_sorted() {
        let mut r = TopicSubscriptionRegistry::new();
        r.subscribe(1, 1, 30).unwrap();
        r.subscribe(1, 1, 10).unwrap();
        r.subscribe(1, 1, 20).unwrap();
        assert_eq!(r.topics_for(1), vec![10, 20, 30]);
    }

    #[test]
    fn peers_for_topic_sorted() {
        let mut r = TopicSubscriptionRegistry::new();
        r.subscribe(3, 1, 42).unwrap();
        r.subscribe(1, 1, 42).unwrap();
        r.subscribe(2, 1, 42).unwrap();
        assert_eq!(r.peers_for_topic(42), vec![1, 2, 3]);
    }

    #[test]
    fn log_records_subscribe_and_unsubscribe() {
        let mut r = TopicSubscriptionRegistry::new();
        r.subscribe(1, 1, 42).unwrap();
        r.unsubscribe(1, 2, 42);
        let log = r.get_log(1).unwrap();
        assert_eq!(log.subscribe_count(), 1);
        assert_eq!(log.unsubscribe_count(), 1);
        let (valid, _) = log.verify_chain();
        assert!(valid);
    }
}
