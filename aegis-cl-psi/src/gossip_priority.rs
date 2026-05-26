//! Gate 277 — Gossip Priority Queue: deterministic outbound message scheduling (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Orders pending outbound gossip messages by computed priority score.
//! Priority is a pure integer function of message properties — no float.
//!
//! MessagePriority:
//!   Urgent   = 0 (highest — score ≥ 1000)
//!   High     = 1 (score 500–999)
//!   Normal   = 2 (score 100–499)
//!   Low      = 3 (score < 100)
//!
//! Priority score formula (integer):
//!   score = (ttl_remaining as u32 * urgency_weight as u32 * fanout as u32)
//!           / (elapsed_epochs as u32 + 1)
//!   where:
//!     ttl_remaining — hops remaining (0–15)
//!     urgency_weight — 1–10 (caller-supplied importance)
//!     fanout — number of peers to send to (1–8)
//!     elapsed_epochs — epochs since message was enqueued
//!
//! PendingMessage:
//!   message_id    — u64 (monotone, assigned at enqueue)
//!   node_id       — u32 (originating node)
//!   sequence      — u64
//!   ttl_remaining — u8
//!   urgency       — u8 (1–10)
//!   fanout        — u8
//!   enqueue_epoch — u64
//!   score         — u32
//!   priority      — MessagePriority
//!
//! GossipPriorityQueue:
//!   enqueue(node_id, seq, ttl, urgency, fanout, current_epoch)
//!   dequeue_batch(current_epoch, max_count) → Vec<PendingMessage> (ordered by score desc)
//!   peek_top(current_epoch) → Option<&PendingMessage>
//!   len(), is_empty(), discard_expired()

use std::collections::BTreeMap;

pub const URGENT_THRESHOLD: u32 = 1000;
pub const HIGH_THRESHOLD:   u32 = 500;
pub const NORMAL_THRESHOLD: u32 = 100;

// ─── Priority classification ──────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum MessagePriority {
    Urgent = 0,
    High   = 1,
    Normal = 2,
    Low    = 3,
}

pub fn classify_priority(score: u32) -> MessagePriority {
    if score >= URGENT_THRESHOLD     { MessagePriority::Urgent }
    else if score >= HIGH_THRESHOLD  { MessagePriority::High }
    else if score >= NORMAL_THRESHOLD { MessagePriority::Normal }
    else                              { MessagePriority::Low }
}

/// Compute priority score: (ttl * urgency * fanout) / (elapsed + 1).
/// All inputs clipped to prevent overflow: ttl ≤ 15, urgency ≤ 10, fanout ≤ 8.
pub fn compute_score(ttl_remaining: u8, urgency: u8, fanout: u8, elapsed_epochs: u64) -> u32 {
    let ttl  = (ttl_remaining.min(15)) as u32;
    let urg  = (urgency.max(1).min(10)) as u32;
    let fan  = (fanout.max(1).min(8)) as u32;
    let elap = (elapsed_epochs.min(1000)) as u32;
    (ttl * urg * fan) / (elap + 1)
}

// ─── Pending message ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PendingMessage {
    pub message_id:    u64,
    pub node_id:       u32,
    pub sequence:      u64,
    pub ttl_remaining: u8,
    pub urgency:       u8,
    pub fanout:        u8,
    pub enqueue_epoch: u64,
    pub score:         u32,
    pub priority:      MessagePriority,
}

impl PendingMessage {
    /// Recompute score and priority at query time (score decays as epoch advances).
    pub fn effective_score(&self, current_epoch: u64) -> u32 {
        let elapsed = current_epoch.saturating_sub(self.enqueue_epoch);
        compute_score(self.ttl_remaining, self.urgency, self.fanout, elapsed)
    }

    /// True if TTL has expired (remaining == 0 after accounting for elapsed epochs).
    pub fn is_expired(&self, current_epoch: u64) -> bool {
        let elapsed = current_epoch.saturating_sub(self.enqueue_epoch);
        elapsed > self.ttl_remaining as u64
    }
}

// ─── Priority queue ───────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct GossipPriorityQueue {
    next_id:  u64,
    // BTreeMap<(neg_score, message_id), PendingMessage>
    // Negated score for descending order within BTreeMap's ascending iteration.
    // message_id as tiebreaker → FIFO within same score.
    inner: BTreeMap<(i64, u64), PendingMessage>,
}

impl GossipPriorityQueue {
    pub fn new() -> Self { Self { next_id: 0, inner: BTreeMap::new() } }

    pub fn len(&self)      -> usize { self.inner.len() }
    pub fn is_empty(&self) -> bool  { self.inner.is_empty() }

    pub fn enqueue(
        &mut self,
        node_id:       u32,
        sequence:      u64,
        ttl_remaining: u8,
        urgency:       u8,
        fanout:        u8,
        current_epoch: u64,
    ) -> u64 {
        let id    = self.next_id;
        self.next_id += 1;
        let score    = compute_score(ttl_remaining, urgency, fanout, 0);
        let priority = classify_priority(score);
        let msg = PendingMessage {
            message_id: id, node_id, sequence, ttl_remaining, urgency,
            fanout, enqueue_epoch: current_epoch, score, priority,
        };
        // Key: (-score as i64, message_id) → highest score first, FIFO within score
        self.inner.insert((-(score as i64), id), msg);
        id
    }

    /// Remove and return up to max_count messages in descending score order
    /// (re-sorted by effective_score at current_epoch).
    pub fn dequeue_batch(&mut self, current_epoch: u64, max_count: usize) -> Vec<PendingMessage> {
        if max_count == 0 { return Vec::new(); }

        // Re-sort by current effective score, collect all keys
        let mut scored: Vec<(u32, u64, (i64, u64))> = self.inner.iter()
            .map(|(k, msg)| (msg.effective_score(current_epoch), msg.message_id, *k))
            .collect();
        // Sort descending by effective score, then ascending by message_id (FIFO tiebreak)
        scored.sort_by(|a, b| b.0.cmp(&a.0).then(a.1.cmp(&b.1)));

        let take = max_count.min(scored.len());
        let mut result = Vec::with_capacity(take);
        for (_, _, key) in scored.into_iter().take(take) {
            if let Some(mut msg) = self.inner.remove(&key) {
                let eff_score = msg.effective_score(current_epoch);
                msg.score    = eff_score;
                msg.priority = classify_priority(eff_score);
                result.push(msg);
            }
        }
        result
    }

    /// Peek at the message with highest effective score without removing it.
    pub fn peek_top(&self, current_epoch: u64) -> Option<&PendingMessage> {
        self.inner.values()
            .max_by_key(|msg| (msg.effective_score(current_epoch), u64::MAX - msg.message_id))
    }

    /// Discard all messages whose TTL has expired at current_epoch.
    pub fn discard_expired(&mut self, current_epoch: u64) -> usize {
        let before = self.inner.len();
        self.inner.retain(|_, msg| !msg.is_expired(current_epoch));
        before - self.inner.len()
    }
}

impl Default for GossipPriorityQueue {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── compute_score / classify_priority ─────────────────────────────────────

    #[test]
    fn score_formula_no_elapsed() {
        // ttl=10, urgency=5, fanout=4, elapsed=0 → 10*5*4/(0+1) = 200
        assert_eq!(compute_score(10, 5, 4, 0), 200);
    }

    #[test]
    fn score_decays_with_elapsed() {
        // ttl=10, urgency=5, fanout=4, elapsed=3 → 200/(3+1) = 50
        assert_eq!(compute_score(10, 5, 4, 3), 50);
    }

    #[test]
    fn score_clips_inputs() {
        // urgency=20 clipped to 10, fanout=20 clipped to 8, ttl=20 clipped to 15
        let capped = compute_score(20, 20, 20, 0);
        let normal = compute_score(15, 10, 8, 0);
        assert_eq!(capped, normal);
    }

    #[test]
    fn priority_thresholds() {
        assert_eq!(classify_priority(1000), MessagePriority::Urgent);
        assert_eq!(classify_priority(999),  MessagePriority::High);
        assert_eq!(classify_priority(500),  MessagePriority::High);
        assert_eq!(classify_priority(499),  MessagePriority::Normal);
        assert_eq!(classify_priority(100),  MessagePriority::Normal);
        assert_eq!(classify_priority(99),   MessagePriority::Low);
        assert_eq!(classify_priority(0),    MessagePriority::Low);
    }

    // ── PendingMessage ────────────────────────────────────────────────────────

    #[test]
    fn is_expired_when_elapsed_exceeds_ttl() {
        let msg = PendingMessage {
            message_id: 0, node_id: 1, sequence: 1,
            ttl_remaining: 3, urgency: 5, fanout: 3,
            enqueue_epoch: 10, score: 100, priority: MessagePriority::Normal,
        };
        assert!(!msg.is_expired(12)); // elapsed=2 ≤ ttl=3
        assert!(msg.is_expired(14));  // elapsed=4 > ttl=3
    }

    #[test]
    fn effective_score_decays() {
        let msg = PendingMessage {
            message_id: 0, node_id: 1, sequence: 1,
            ttl_remaining: 10, urgency: 5, fanout: 4,
            enqueue_epoch: 0, score: 200, priority: MessagePriority::Normal,
        };
        assert_eq!(msg.effective_score(0), 200);
        assert_eq!(msg.effective_score(3), 50); // 200 / 4
    }

    // ── GossipPriorityQueue ───────────────────────────────────────────────────

    #[test]
    fn new_queue_empty() {
        let q = GossipPriorityQueue::new();
        assert!(q.is_empty());
        assert_eq!(q.len(), 0);
    }

    #[test]
    fn enqueue_increases_len() {
        let mut q = GossipPriorityQueue::new();
        q.enqueue(1, 1, 5, 5, 3, 1);
        q.enqueue(2, 2, 3, 3, 2, 1);
        assert_eq!(q.len(), 2);
    }

    #[test]
    fn dequeue_batch_highest_score_first() {
        let mut q = GossipPriorityQueue::new();
        q.enqueue(1, 1, 15, 10, 8, 0); // high score: 15*10*8/1=1200 → Urgent
        q.enqueue(2, 1, 1,  1,  1, 0); // low score: 1/1=1 → Low
        let batch = q.dequeue_batch(0, 2);
        assert_eq!(batch.len(), 2);
        assert!(batch[0].score >= batch[1].score);
        assert_eq!(batch[0].node_id, 1); // high-score message first
    }

    #[test]
    fn dequeue_removes_from_queue() {
        let mut q = GossipPriorityQueue::new();
        q.enqueue(1, 1, 5, 5, 3, 0);
        q.enqueue(2, 1, 5, 5, 3, 0);
        let batch = q.dequeue_batch(0, 1);
        assert_eq!(batch.len(), 1);
        assert_eq!(q.len(), 1);
    }

    #[test]
    fn dequeue_batch_zero_returns_empty() {
        let mut q = GossipPriorityQueue::new();
        q.enqueue(1, 1, 5, 5, 3, 0);
        let batch = q.dequeue_batch(0, 0);
        assert!(batch.is_empty());
        assert_eq!(q.len(), 1);
    }

    #[test]
    fn discard_expired_removes_correct_messages() {
        let mut q = GossipPriorityQueue::new();
        q.enqueue(1, 1, 2, 5, 3, 0); // ttl=2, enqueued at epoch 0
        q.enqueue(2, 2, 10, 5, 3, 0); // ttl=10
        let discarded = q.discard_expired(3); // epoch 3: elapsed=3 > ttl=2 for first
        assert_eq!(discarded, 1);
        assert_eq!(q.len(), 1);
    }

    #[test]
    fn peek_top_returns_highest_score() {
        let mut q = GossipPriorityQueue::new();
        q.enqueue(1, 1, 15, 10, 8, 0); // Urgent
        q.enqueue(2, 2, 1,  1,  1, 0); // Low
        let top = q.peek_top(0).unwrap();
        assert_eq!(top.node_id, 1);
    }

    #[test]
    fn message_ids_monotone() {
        let mut q = GossipPriorityQueue::new();
        let id1 = q.enqueue(1, 1, 5, 5, 3, 0);
        let id2 = q.enqueue(1, 2, 5, 5, 3, 0);
        assert!(id2 > id1);
    }
}
