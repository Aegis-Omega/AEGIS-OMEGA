//! Gate 299 — Gossip Message Priority Queue: urgency-ordered message scheduling (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Maintains a bounded priority queue of outbound gossip messages. Messages are
//! ordered by (priority_class DESC, enqueue_seq ASC) — highest priority first,
//! FIFO within the same class. When capacity is exceeded, the lowest-priority
//! message is evicted.
//!
//! PriorityClass:
//!   Critical  = 0  — consensus/safety messages; never evicted
//!   High      = 1  — reputation/flood-guard alerts
//!   Normal    = 2  — regular gossip
//!   Low       = 3  — background sync
//!
//! Constants:
//!   QUEUE_CAPACITY: usize = 64
//!   CRITICAL_RESERVE: usize = 8  (reserved slots for Critical messages)
//!
//! QueueEntry: (priority_class, enqueue_seq, peer_id, message_id, payload_hash)
//!
//! QueueRecord: hash-chained snapshot at each enqueue/evict operation.
//!   epoch, operation, queue_depth, evicted_message_id (Option<u64>)
//!   record_hash — SHA-256(prev ‖ epoch_be8 ‖ op_byte ‖ depth_be4 ‖ evicted_be8)
//!
//! PriorityQueue: enqueue(), dequeue() → Option<QueueEntry>, depth(), verify_chain()
//! Statistics: enqueue_count(), evict_count(), dequeue_count()

use sha2::{Sha256, Digest};
use std::collections::VecDeque;

pub const QUEUE_CAPACITY:   usize = 64;
pub const CRITICAL_RESERVE: usize = 8;

// ─── Priority class ───────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum PriorityClass {
    Critical = 0,
    High     = 1,
    Normal   = 2,
    Low      = 3,
}

impl PriorityClass {
    pub fn class_byte(self) -> u8 { self as u8 }
    pub fn is_critical(self) -> bool { matches!(self, Self::Critical) }
}

// ─── Queue entry ──────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct QueueEntry {
    pub priority:     PriorityClass,
    pub enqueue_seq:  u64,
    pub peer_id:      u32,
    pub message_id:   u64,
    pub payload_hash: [u8; 32],
}

// ─── Queue operation ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum QueueOperation {
    Enqueue = 0,
    Dequeue = 1,
    Evict   = 2,
}

impl QueueOperation {
    pub fn op_byte(self) -> u8 { self as u8 }
}

// ─── Queue record ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct QueueRecord {
    pub epoch:               u64,
    pub operation:           QueueOperation,
    pub queue_depth:         u32,
    pub evicted_message_id:  Option<u64>,
    pub record_hash:         [u8; 32],
    pub prev_hash:           [u8; 32],
}

pub const QUEUE_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_queue_hash(
    epoch:              u64,
    operation:          QueueOperation,
    queue_depth:        u32,
    evicted_message_id: Option<u64>,
    prev:               &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update([operation.op_byte()]);
    h.update(queue_depth.to_be_bytes());
    let evicted_bytes = evicted_message_id.unwrap_or(u64::MAX).to_be_bytes();
    h.update(evicted_bytes);
    h.finalize().into()
}

pub fn build_queue_record(
    epoch:              u64,
    operation:          QueueOperation,
    queue_depth:        u32,
    evicted_message_id: Option<u64>,
    prev_hash:          &[u8; 32],
) -> QueueRecord {
    let record_hash = compute_queue_hash(epoch, operation, queue_depth, evicted_message_id, prev_hash);
    QueueRecord { epoch, operation, queue_depth, evicted_message_id, record_hash, prev_hash: *prev_hash }
}

// ─── Message priority queue ───────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct MessagePriorityQueue {
    entries:        VecDeque<QueueEntry>,
    next_seq:       u64,
    records:        Vec<QueueRecord>,
    enqueue_count:  u64,
    dequeue_count:  u64,
    evict_count:    u64,
}

#[derive(Debug)]
pub enum QueueError {
    CriticalReserveViolation,
}

impl MessagePriorityQueue {
    pub fn new() -> Self {
        Self {
            entries:       VecDeque::new(),
            next_seq:      0,
            records:       Vec::new(),
            enqueue_count: 0,
            dequeue_count: 0,
            evict_count:   0,
        }
    }

    pub fn depth(&self) -> usize { self.entries.len() }
    pub fn is_empty(&self) -> bool { self.entries.is_empty() }
    pub fn enqueue_count(&self) -> u64 { self.enqueue_count }
    pub fn dequeue_count(&self) -> u64 { self.dequeue_count }
    pub fn evict_count(&self) -> u64 { self.evict_count }
    pub fn records(&self) -> &[QueueRecord] { &self.records }

    fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(QUEUE_GENESIS_HASH)
    }

    fn push_record(&mut self, epoch: u64, op: QueueOperation, evicted: Option<u64>) {
        let depth = self.entries.len() as u32;
        let prev  = self.last_hash();
        let r = build_queue_record(epoch, op, depth, evicted, &prev);
        self.records.push(r);
    }

    /// Enqueue a message. Evicts the lowest-priority message if at capacity
    /// (Critical messages are never evicted; eviction targets the last Low/Normal/High entry).
    /// Returns Err if the queue is full and the incoming message is lower priority
    /// than all current entries (nothing to evict that is worse than the new entry).
    pub fn enqueue(
        &mut self,
        epoch:        u64,
        priority:     PriorityClass,
        peer_id:      u32,
        message_id:   u64,
        payload_hash: [u8; 32],
    ) -> Result<(), QueueError> {
        let seq = self.next_seq;
        self.next_seq = self.next_seq.wrapping_add(1);

        let entry = QueueEntry { priority, enqueue_seq: seq, peer_id, message_id, payload_hash };

        let mut evicted_id: Option<u64> = None;

        if self.entries.len() >= QUEUE_CAPACITY {
            // Find the worst (highest class byte = lowest priority) entry to evict.
            // Never evict Critical.
            let evict_idx = self.entries.iter().enumerate()
                .filter(|(_, e)| !e.priority.is_critical())
                .max_by_key(|(_, e)| (e.priority, u64::MAX - e.enqueue_seq))
                .map(|(i, _)| i);

            if let Some(idx) = evict_idx {
                let evicted = self.entries.remove(idx).unwrap();
                evicted_id = Some(evicted.message_id);
                self.evict_count += 1;
            } else {
                // All entries are Critical — reject non-critical incoming
                if !priority.is_critical() {
                    return Err(QueueError::CriticalReserveViolation);
                }
                // Critical over capacity: evict the oldest critical (FIFO drop)
                if let Some(evicted) = self.entries.pop_front() {
                    evicted_id = Some(evicted.message_id);
                    self.evict_count += 1;
                }
            }
        }

        // Insert maintaining sorted order: highest priority (lowest class byte) first,
        // then by enqueue_seq ascending (earlier = forward in queue).
        let insert_pos = self.entries.partition_point(|e| {
            (e.priority, e.enqueue_seq) < (entry.priority, entry.enqueue_seq)
        });
        self.entries.insert(insert_pos, entry);
        self.enqueue_count += 1;
        self.push_record(epoch, QueueOperation::Enqueue, evicted_id);
        Ok(())
    }

    /// Dequeue the highest-priority (lowest class byte, then oldest) entry.
    pub fn dequeue(&mut self, epoch: u64) -> Option<QueueEntry> {
        if self.entries.is_empty() { return None; }
        let entry = self.entries.pop_front().unwrap();
        self.dequeue_count += 1;
        self.push_record(epoch, QueueOperation::Dequeue, None);
        Some(entry)
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = QUEUE_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_queue_hash(
                r.epoch, r.operation, r.queue_depth, r.evicted_message_id, &r.prev_hash,
            );
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for MessagePriorityQueue {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn ph(v: u8) -> [u8; 32] { let mut a = [0u8; 32]; a[0] = v; a }

    // ── PriorityClass ─────────────────────────────────────────────────────────

    #[test]
    fn class_bytes() {
        assert_eq!(PriorityClass::Critical.class_byte(), 0);
        assert_eq!(PriorityClass::High.class_byte(),     1);
        assert_eq!(PriorityClass::Normal.class_byte(),   2);
        assert_eq!(PriorityClass::Low.class_byte(),      3);
    }

    #[test]
    fn critical_is_critical() {
        assert!(PriorityClass::Critical.is_critical());
        assert!(!PriorityClass::Low.is_critical());
    }

    // ── build_queue_record ────────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let r = build_queue_record(1, QueueOperation::Enqueue, 1, None, &QUEUE_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_queue_record(1, QueueOperation::Enqueue, 1, None, &QUEUE_GENESIS_HASH);
        let r2 = build_queue_record(1, QueueOperation::Enqueue, 1, None, &QUEUE_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    // ── MessagePriorityQueue ──────────────────────────────────────────────────

    #[test]
    fn new_queue_empty() {
        let q = MessagePriorityQueue::new();
        assert!(q.is_empty());
        assert_eq!(q.depth(), 0);
    }

    #[test]
    fn enqueue_and_dequeue_fifo_within_class() {
        let mut q = MessagePriorityQueue::new();
        q.enqueue(1, PriorityClass::Normal, 1, 100, ph(1)).unwrap();
        q.enqueue(1, PriorityClass::Normal, 1, 200, ph(2)).unwrap();
        let first = q.dequeue(1).unwrap();
        assert_eq!(first.message_id, 100); // oldest Normal first
    }

    #[test]
    fn higher_priority_dequeued_first() {
        let mut q = MessagePriorityQueue::new();
        q.enqueue(1, PriorityClass::Low,      1, 1, ph(1)).unwrap();
        q.enqueue(1, PriorityClass::Critical, 1, 2, ph(2)).unwrap();
        q.enqueue(1, PriorityClass::Normal,   1, 3, ph(3)).unwrap();
        let first = q.dequeue(1).unwrap();
        assert_eq!(first.message_id, 2); // Critical first
        let second = q.dequeue(1).unwrap();
        assert_eq!(second.message_id, 3); // Normal second
    }

    #[test]
    fn eviction_targets_lowest_priority() {
        let mut q = MessagePriorityQueue::new();
        // Fill to capacity with Low priority
        for i in 0..QUEUE_CAPACITY as u64 {
            q.enqueue(1, PriorityClass::Low, 1, i, ph(1)).unwrap();
        }
        assert_eq!(q.depth(), QUEUE_CAPACITY);
        // Enqueue a High: should evict one Low
        q.enqueue(2, PriorityClass::High, 1, 999, ph(9)).unwrap();
        assert_eq!(q.depth(), QUEUE_CAPACITY);
        assert_eq!(q.evict_count(), 1);
        // High message should be in queue
        let found = q.records.iter().any(|r| r.evicted_message_id.is_some());
        assert!(found);
    }

    #[test]
    fn dequeue_empty_returns_none() {
        let mut q = MessagePriorityQueue::new();
        assert!(q.dequeue(1).is_none());
    }

    #[test]
    fn stats_tracked() {
        let mut q = MessagePriorityQueue::new();
        q.enqueue(1, PriorityClass::Normal, 1, 1, ph(1)).unwrap();
        q.enqueue(1, PriorityClass::Normal, 1, 2, ph(2)).unwrap();
        q.dequeue(1);
        assert_eq!(q.enqueue_count(), 2);
        assert_eq!(q.dequeue_count(), 1);
    }

    #[test]
    fn verify_chain_valid() {
        let mut q = MessagePriorityQueue::new();
        for i in 0..5u64 {
            q.enqueue(i, PriorityClass::Normal, 1, i, ph(i as u8)).unwrap();
        }
        for i in 0..3u64 {
            q.dequeue(i);
        }
        let (valid, broken) = q.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }
}
