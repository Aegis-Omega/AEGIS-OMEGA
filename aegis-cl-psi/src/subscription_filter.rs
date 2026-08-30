//! Gate 314 — Gossip Subscription Filter: topic-based message forwarding decisions (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Determines whether a gossip message should be forwarded to a peer based on
//! their active topic subscriptions. Integrates with the topic subscription
//! registry (Gate 305) by taking a snapshot of subscribed topics and evaluating
//! each incoming message's topic tag.
//!
//! Constants:
//!   MAX_FILTER_TOPICS: usize = 64   (max topics in a filter snapshot)
//!
//! FilterDecision: Forward | Drop | NoSubscriptions
//!
//! FilterRecord:
//!   peer_id, epoch, topic_hash: [u8;32], decision
//!   record_hash = SHA-256(prev ‖ peer_be4 ‖ epoch_be8 ‖ topic_hash[32] ‖ decision_byte)
//!   prev_hash
//!
//! FilterLog: hash-chained FilterRecords (per-peer).
//!   push(), forward_count(), drop_count(), verify_chain().
//!
//! SubscriptionFilter:
//!   register_topics(peer_id, topics: &[u8;32] slice) — set current topic set for peer
//!   evaluate(peer_id, topic_hash, epoch) → FilterDecision
//!   clear_peer(peer_id)
//!   peer_count() → usize
//!   get_log(peer_id) → Option<&FilterLog>

use sha2::{Sha256, Digest};
use std::collections::{BTreeMap, BTreeSet};

pub const MAX_FILTER_TOPICS: usize = 64;

// ─── Filter decision ─────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FilterDecision {
    Forward         = 0,
    Drop            = 1,
    NoSubscriptions = 2,
}

impl FilterDecision {
    pub fn decision_byte(self) -> u8 { self as u8 }
}

// ─── Filter record ────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct FilterRecord {
    pub peer_id:     u32,
    pub epoch:       u64,
    pub topic_hash:  [u8; 32],
    pub decision:    FilterDecision,
    pub record_hash: [u8; 32],
    pub prev_hash:   [u8; 32],
}

pub const FILTER_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_filter_hash(
    peer_id:    u32,
    epoch:      u64,
    topic_hash: &[u8; 32],
    decision:   FilterDecision,
    prev:       &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update(topic_hash);
    h.update([decision.decision_byte()]);
    h.finalize().into()
}

pub fn build_filter_record(
    peer_id:    u32,
    epoch:      u64,
    topic_hash: [u8; 32],
    decision:   FilterDecision,
    prev_hash:  &[u8; 32],
) -> FilterRecord {
    let record_hash = compute_filter_hash(peer_id, epoch, &topic_hash, decision, prev_hash);
    FilterRecord { peer_id, epoch, topic_hash, decision, record_hash, prev_hash: *prev_hash }
}

// ─── Filter log (per-peer) ────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct FilterLog {
    records: Vec<FilterRecord>,
}

impl FilterLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[FilterRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(FILTER_GENESIS_HASH)
    }

    pub fn push(
        &mut self,
        peer_id:    u32,
        epoch:      u64,
        topic_hash: [u8; 32],
        decision:   FilterDecision,
    ) -> &FilterRecord {
        let prev = self.last_hash();
        let r = build_filter_record(peer_id, epoch, topic_hash, decision, &prev);
        self.records.push(r);
        self.records.last().unwrap()
    }

    pub fn forward_count(&self) -> usize {
        self.records.iter().filter(|r| r.decision == FilterDecision::Forward).count()
    }

    pub fn drop_count(&self) -> usize {
        self.records.iter().filter(|r| r.decision == FilterDecision::Drop).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = FILTER_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_filter_hash(r.peer_id, r.epoch, &r.topic_hash, r.decision, &r.prev_hash);
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for FilterLog {
    fn default() -> Self { Self::new() }
}

// ─── Peer filter state (internal) ─────────────────────────────────────────────

struct PeerFilterState {
    topics: BTreeSet<[u8; 32]>,
}

// ─── SubscriptionFilter ───────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct SubscriptionFilter {
    peers:    BTreeMap<u32, BTreeSet<[u8; 32]>>,
    pub logs: BTreeMap<u32, FilterLog>,
}

impl SubscriptionFilter {
    pub fn new() -> Self {
        Self { peers: BTreeMap::new(), logs: BTreeMap::new() }
    }

    /// Register (or replace) the topic set for a peer.
    /// Silently truncates to MAX_FILTER_TOPICS if more topics are supplied.
    pub fn register_topics(&mut self, peer_id: u32, topics: &[[u8; 32]]) {
        let set: BTreeSet<[u8; 32]> = topics.iter().take(MAX_FILTER_TOPICS).copied().collect();
        self.peers.insert(peer_id, set);
        self.logs.entry(peer_id).or_insert_with(FilterLog::new);
    }

    /// Evaluate whether a message with the given topic_hash should be forwarded to peer_id.
    /// Records the decision in the per-peer FilterLog.
    pub fn evaluate(&mut self, peer_id: u32, topic_hash: [u8; 32], epoch: u64) -> FilterDecision {
        let decision = match self.peers.get(&peer_id) {
            None => FilterDecision::NoSubscriptions,
            Some(topics) => {
                if topics.is_empty() {
                    FilterDecision::NoSubscriptions
                } else if topics.contains(&topic_hash) {
                    FilterDecision::Forward
                } else {
                    FilterDecision::Drop
                }
            }
        };
        let log = self.logs.entry(peer_id).or_insert_with(FilterLog::new);
        log.push(peer_id, epoch, topic_hash, decision);
        decision
    }

    /// Remove all subscription and log state for a peer.
    pub fn clear_peer(&mut self, peer_id: u32) {
        self.peers.remove(&peer_id);
        self.logs.remove(&peer_id);
    }

    pub fn peer_count(&self) -> usize { self.peers.len() }

    pub fn get_log(&self, peer_id: u32) -> Option<&FilterLog> {
        self.logs.get(&peer_id)
    }

    /// Topics registered for peer (sorted).
    pub fn topics_for(&self, peer_id: u32) -> Vec<[u8; 32]> {
        self.peers.get(&peer_id)
            .map(|s| s.iter().copied().collect())
            .unwrap_or_default()
    }
}

impl Default for SubscriptionFilter {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn topic(seed: u8) -> [u8; 32] {
        let mut h = [0u8; 32];
        h[0] = seed;
        h[31] = seed.wrapping_mul(13);
        h
    }

    // ── FilterDecision ────────────────────────────────────────────────────────

    #[test]
    fn decision_bytes() {
        assert_eq!(FilterDecision::Forward.decision_byte(),         0);
        assert_eq!(FilterDecision::Drop.decision_byte(),            1);
        assert_eq!(FilterDecision::NoSubscriptions.decision_byte(), 2);
    }

    // ── build_filter_record ───────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let r = build_filter_record(1, 1, topic(1), FilterDecision::Forward, &FILTER_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_filter_record(1, 1, topic(1), FilterDecision::Forward, &FILTER_GENESIS_HASH);
        let r2 = build_filter_record(1, 1, topic(1), FilterDecision::Forward, &FILTER_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    // ── FilterLog ─────────────────────────────────────────────────────────────

    #[test]
    fn log_counts() {
        let mut l = FilterLog::new();
        l.push(1, 1, topic(1), FilterDecision::Forward);
        l.push(1, 1, topic(2), FilterDecision::Drop);
        l.push(1, 1, topic(3), FilterDecision::Forward);
        assert_eq!(l.forward_count(), 2);
        assert_eq!(l.drop_count(), 1);
    }

    #[test]
    fn log_chain_links() {
        let mut l = FilterLog::new();
        l.push(1, 1, topic(1), FilterDecision::Forward);
        l.push(1, 2, topic(2), FilterDecision::Drop);
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    #[test]
    fn log_verify_chain_valid() {
        let mut l = FilterLog::new();
        for i in 0..5u8 {
            l.push(1, i as u64, topic(i), FilterDecision::Forward);
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    // ── SubscriptionFilter ────────────────────────────────────────────────────

    #[test]
    fn no_registration_gives_no_subscriptions() {
        let mut f = SubscriptionFilter::new();
        assert_eq!(f.evaluate(1, topic(1), 1), FilterDecision::NoSubscriptions);
    }

    #[test]
    fn empty_topics_gives_no_subscriptions() {
        let mut f = SubscriptionFilter::new();
        f.register_topics(1, &[]);
        assert_eq!(f.evaluate(1, topic(1), 1), FilterDecision::NoSubscriptions);
    }

    #[test]
    fn subscribed_topic_forwards() {
        let mut f = SubscriptionFilter::new();
        f.register_topics(1, &[topic(1), topic(2)]);
        assert_eq!(f.evaluate(1, topic(1), 1), FilterDecision::Forward);
        assert_eq!(f.evaluate(1, topic(2), 1), FilterDecision::Forward);
    }

    #[test]
    fn unsubscribed_topic_drops() {
        let mut f = SubscriptionFilter::new();
        f.register_topics(1, &[topic(1)]);
        assert_eq!(f.evaluate(1, topic(99), 1), FilterDecision::Drop);
    }

    #[test]
    fn log_records_evaluation() {
        let mut f = SubscriptionFilter::new();
        f.register_topics(1, &[topic(1)]);
        f.evaluate(1, topic(1), 1);  // Forward
        f.evaluate(1, topic(2), 1);  // Drop
        let log = f.get_log(1).unwrap();
        assert_eq!(log.forward_count(), 1);
        assert_eq!(log.drop_count(), 1);
        let (valid, _) = log.verify_chain();
        assert!(valid);
    }

    #[test]
    fn clear_peer_removes_state() {
        let mut f = SubscriptionFilter::new();
        f.register_topics(1, &[topic(1)]);
        f.evaluate(1, topic(1), 1);
        f.clear_peer(1);
        assert_eq!(f.peer_count(), 0);
        assert!(f.get_log(1).is_none());
        // After clear: NoSubscriptions again
        assert_eq!(f.evaluate(1, topic(1), 2), FilterDecision::NoSubscriptions);
    }

    #[test]
    fn topics_truncated_at_max() {
        let topics: Vec<[u8; 32]> = (0..70u8).map(topic).collect();
        let mut f = SubscriptionFilter::new();
        f.register_topics(1, &topics);
        assert_eq!(f.topics_for(1).len(), MAX_FILTER_TOPICS);
    }

    #[test]
    fn replace_topics_updates_filter() {
        let mut f = SubscriptionFilter::new();
        f.register_topics(1, &[topic(1)]);
        assert_eq!(f.evaluate(1, topic(2), 1), FilterDecision::Drop);
        // Replace with topic(2)
        f.register_topics(1, &[topic(2)]);
        assert_eq!(f.evaluate(1, topic(2), 2), FilterDecision::Forward);
        assert_eq!(f.evaluate(1, topic(1), 2), FilterDecision::Drop);
    }
}
