//! Gate 311 — Gossip Message Retry Scheduler: exponential-backoff retry tracking (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Schedules retries for unacknowledged gossip messages using a capped exponential
//! backoff. Each retry doubles the interval (in epochs) starting from BASE_RETRY_EPOCHS,
//! capped at MAX_RETRY_EPOCHS. After MAX_RETRIES attempts, the message is abandoned.
//! Retry events are hash-chained for audit.
//!
//! Constants:
//!   BASE_RETRY_EPOCHS: u64 = 2   (first retry interval)
//!   MAX_RETRY_EPOCHS:  u64 = 32  (cap — 2, 4, 8, 16, 32, 32, ...)
//!   MAX_RETRIES:       u8  = 5   (after this many retries, message is Abandoned)
//!
//! RetryStatus: Scheduled | Retried | Abandoned | Succeeded
//!
//! RetryRecord:
//!   peer_id, message_id: u64, attempt: u8, next_retry_epoch: u64, status
//!   record_hash = SHA-256(prev ‖ peer_be4 ‖ msg_be8 ‖ attempt ‖ next_epoch_be8 ‖ status_byte)
//!   prev_hash
//!
//! RetryLog: hash-chained RetryRecords (global).
//!   push(), retried_count(), abandoned_count(), succeeded_count(), verify_chain().
//!
//! RetryEntry: peer_id, message_id, sent_at_epoch, attempt_count, next_retry_epoch (internal)
//!
//! MessageRetryScheduler:
//!   schedule(peer_id, message_id, epoch) → Result<(), RetryError>   (Scheduled)
//!   succeed(peer_id, message_id, epoch) → bool   (marks Succeeded; removes entry)
//!   tick(current_epoch) → Vec<(u32, u64)>        (returns (peer_id, message_id) due for retry)
//!     For each due message: increments attempt, computes next backoff, logs Retried or Abandoned.
//!   pending_count() → usize
//!   abandoned_count_total() → u64

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const BASE_RETRY_EPOCHS: u64 = 2;
pub const MAX_RETRY_EPOCHS:  u64 = 32;
pub const MAX_RETRIES:       u8  = 5;

// ─── Retry status ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RetryStatus {
    Scheduled = 0,
    Retried   = 1,
    Abandoned = 2,
    Succeeded = 3,
}

impl RetryStatus {
    pub fn status_byte(self) -> u8 { self as u8 }
}

// ─── Retry record ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct RetryRecord {
    pub peer_id:         u32,
    pub message_id:      u64,
    pub attempt:         u8,
    pub next_retry_epoch: u64,
    pub status:          RetryStatus,
    pub record_hash:     [u8; 32],
    pub prev_hash:       [u8; 32],
}

pub const RETRY_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_retry_hash(
    peer_id:          u32,
    message_id:       u64,
    attempt:          u8,
    next_retry_epoch: u64,
    status:           RetryStatus,
    prev:             &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(message_id.to_be_bytes());
    h.update([attempt]);
    h.update(next_retry_epoch.to_be_bytes());
    h.update([status.status_byte()]);
    h.finalize().into()
}

pub fn build_retry_record(
    peer_id:          u32,
    message_id:       u64,
    attempt:          u8,
    next_retry_epoch: u64,
    status:           RetryStatus,
    prev_hash:        &[u8; 32],
) -> RetryRecord {
    let record_hash = compute_retry_hash(peer_id, message_id, attempt, next_retry_epoch, status, prev_hash);
    RetryRecord { peer_id, message_id, attempt, next_retry_epoch, status, record_hash, prev_hash: *prev_hash }
}

// ─── Retry log ────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct RetryLog {
    records: Vec<RetryRecord>,
}

impl RetryLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[RetryRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(RETRY_GENESIS_HASH)
    }

    pub fn push(
        &mut self,
        peer_id:          u32,
        message_id:       u64,
        attempt:          u8,
        next_retry_epoch: u64,
        status:           RetryStatus,
    ) -> &RetryRecord {
        let prev = self.last_hash();
        let r = build_retry_record(peer_id, message_id, attempt, next_retry_epoch, status, &prev);
        self.records.push(r);
        self.records.last().unwrap()
    }

    pub fn retried_count(&self) -> usize {
        self.records.iter().filter(|r| r.status == RetryStatus::Retried).count()
    }

    pub fn abandoned_count(&self) -> usize {
        self.records.iter().filter(|r| r.status == RetryStatus::Abandoned).count()
    }

    pub fn succeeded_count(&self) -> usize {
        self.records.iter().filter(|r| r.status == RetryStatus::Succeeded).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = RETRY_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_retry_hash(r.peer_id, r.message_id, r.attempt, r.next_retry_epoch, r.status, &r.prev_hash);
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for RetryLog {
    fn default() -> Self { Self::new() }
}

// ─── Retry entry (internal state) ────────────────────────────────────────────

#[derive(Debug, Clone)]
struct RetryEntry {
    attempt_count:    u8,
    next_retry_epoch: u64,
}

// ─── Errors ───────────────────────────────────────────────────────────────────

#[derive(Debug)]
pub enum RetryError {
    AlreadyScheduled,
}

// ─── MessageRetryScheduler ───────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct MessageRetryScheduler {
    // BTreeMap<(peer_id, message_id), RetryEntry>
    pending:          BTreeMap<(u32, u64), RetryEntry>,
    abandoned_total:  u64,
    pub log: RetryLog,
}

/// Compute next retry epoch using capped exponential backoff.
/// interval = min(BASE_RETRY_EPOCHS * 2^attempt_count, MAX_RETRY_EPOCHS)
fn backoff_interval(attempt_count: u8) -> u64 {
    let shift = attempt_count.min(5) as u64; // cap shift to avoid overflow; 2^5=32=MAX
    let multiplier = 1u64 << shift;
    BASE_RETRY_EPOCHS.saturating_mul(multiplier).min(MAX_RETRY_EPOCHS)
}

impl MessageRetryScheduler {
    pub fn new() -> Self {
        Self { pending: BTreeMap::new(), abandoned_total: 0, log: RetryLog::new() }
    }

    /// Register a message for retry tracking. First retry due at epoch + BASE_RETRY_EPOCHS.
    pub fn schedule(&mut self, peer_id: u32, message_id: u64, epoch: u64) -> Result<(), RetryError> {
        let key = (peer_id, message_id);
        if self.pending.contains_key(&key) { return Err(RetryError::AlreadyScheduled); }
        let next = epoch.saturating_add(backoff_interval(0));
        self.pending.insert(key, RetryEntry { attempt_count: 0, next_retry_epoch: next });
        self.log.push(peer_id, message_id, 0, next, RetryStatus::Scheduled);
        Ok(())
    }

    /// Mark a message as succeeded; removes from pending. Returns true if it was pending.
    pub fn succeed(&mut self, peer_id: u32, message_id: u64, epoch: u64) -> bool {
        if self.pending.remove(&(peer_id, message_id)).is_some() {
            self.log.push(peer_id, message_id, 0, epoch, RetryStatus::Succeeded);
            true
        } else {
            false
        }
    }

    /// Advance clock to current_epoch. Returns list of (peer_id, message_id) due for retry.
    /// Messages reaching MAX_RETRIES are marked Abandoned and removed.
    pub fn tick(&mut self, current_epoch: u64) -> Vec<(u32, u64)> {
        // Collect due entries first
        let due: Vec<(u32, u64, u8)> = self.pending.iter()
            .filter(|(_, e)| current_epoch >= e.next_retry_epoch)
            .map(|(&(pid, mid), e)| (pid, mid, e.attempt_count))
            .collect();

        let mut ready = Vec::new();
        for (pid, mid, attempt) in due {
            let new_attempt = attempt.saturating_add(1);
            if new_attempt >= MAX_RETRIES {
                self.pending.remove(&(pid, mid));
                self.abandoned_total += 1;
                self.log.push(pid, mid, new_attempt, current_epoch, RetryStatus::Abandoned);
            } else {
                let next = current_epoch.saturating_add(backoff_interval(new_attempt));
                if let Some(entry) = self.pending.get_mut(&(pid, mid)) {
                    entry.attempt_count = new_attempt;
                    entry.next_retry_epoch = next;
                }
                self.log.push(pid, mid, new_attempt, next, RetryStatus::Retried);
                ready.push((pid, mid));
            }
        }
        ready
    }

    pub fn pending_count(&self) -> usize { self.pending.len() }
    pub fn abandoned_count_total(&self) -> u64 { self.abandoned_total }
}

impl Default for MessageRetryScheduler {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── RetryStatus ───────────────────────────────────────────────────────────

    #[test]
    fn status_bytes() {
        assert_eq!(RetryStatus::Scheduled.status_byte(), 0);
        assert_eq!(RetryStatus::Retried.status_byte(),   1);
        assert_eq!(RetryStatus::Abandoned.status_byte(), 2);
        assert_eq!(RetryStatus::Succeeded.status_byte(), 3);
    }

    // ── backoff_interval ──────────────────────────────────────────────────────

    #[test]
    fn backoff_grows_and_caps() {
        assert_eq!(backoff_interval(0), 2);  // BASE_RETRY_EPOCHS * 2^0 = 2
        assert_eq!(backoff_interval(1), 4);  // 2 * 2^1 = 4
        assert_eq!(backoff_interval(2), 8);
        assert_eq!(backoff_interval(3), 16);
        assert_eq!(backoff_interval(4), 32); // capped at MAX_RETRY_EPOCHS
        assert_eq!(backoff_interval(5), 32); // still capped
        assert_eq!(backoff_interval(10), 32);
    }

    // ── build_retry_record ────────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let r = build_retry_record(1, 100, 0, 5, RetryStatus::Scheduled, &RETRY_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_retry_record(1, 100, 1, 8, RetryStatus::Retried, &RETRY_GENESIS_HASH);
        let r2 = build_retry_record(1, 100, 1, 8, RetryStatus::Retried, &RETRY_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    // ── RetryLog ──────────────────────────────────────────────────────────────

    #[test]
    fn log_counts() {
        let mut l = RetryLog::new();
        l.push(1, 10, 0, 2, RetryStatus::Scheduled);
        l.push(1, 10, 1, 4, RetryStatus::Retried);
        l.push(1, 10, 5, 0, RetryStatus::Abandoned);
        assert_eq!(l.retried_count(), 1);
        assert_eq!(l.abandoned_count(), 1);
        assert_eq!(l.succeeded_count(), 0);
    }

    #[test]
    fn log_chain_links() {
        let mut l = RetryLog::new();
        l.push(1, 10, 0, 2, RetryStatus::Scheduled);
        l.push(1, 10, 1, 4, RetryStatus::Retried);
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    #[test]
    fn log_verify_chain_valid() {
        let mut l = RetryLog::new();
        for i in 0..5u8 {
            l.push(1, i as u64 * 10, i, i as u64 * 5, RetryStatus::Retried);
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    // ── MessageRetryScheduler ─────────────────────────────────────────────────

    #[test]
    fn schedule_and_pending() {
        let mut s = MessageRetryScheduler::new();
        s.schedule(1, 100, 1).unwrap();
        assert_eq!(s.pending_count(), 1);
        assert_eq!(s.log.records()[0].status, RetryStatus::Scheduled);
    }

    #[test]
    fn duplicate_schedule_errors() {
        let mut s = MessageRetryScheduler::new();
        s.schedule(1, 100, 1).unwrap();
        assert!(matches!(s.schedule(1, 100, 1), Err(RetryError::AlreadyScheduled)));
    }

    #[test]
    fn succeed_removes_pending() {
        let mut s = MessageRetryScheduler::new();
        s.schedule(1, 100, 1).unwrap();
        assert!(s.succeed(1, 100, 3));
        assert_eq!(s.pending_count(), 0);
        assert_eq!(s.log.succeeded_count(), 1);
    }

    #[test]
    fn tick_returns_due_messages() {
        let mut s = MessageRetryScheduler::new();
        s.schedule(1, 100, 1).unwrap(); // next_retry = 1 + 2 = 3
        let due = s.tick(3);            // epoch 3 >= 3
        assert_eq!(due, vec![(1, 100)]);
        assert_eq!(s.log.retried_count(), 1);
    }

    #[test]
    fn tick_not_yet_due() {
        let mut s = MessageRetryScheduler::new();
        s.schedule(1, 100, 1).unwrap(); // next_retry = 3
        let due = s.tick(2);            // epoch 2 < 3
        assert!(due.is_empty());
    }

    #[test]
    fn tick_abandons_at_max_retries() {
        let mut s = MessageRetryScheduler::new();
        s.schedule(1, 100, 0).unwrap(); // next = 2
        // Exhaust all retries: MAX_RETRIES=5
        // attempt 0→1 at epoch 2: next=epoch+4=6
        // attempt 1→2 at epoch 6: next=epoch+8=14
        // attempt 2→3 at epoch 14: next=epoch+16=30
        // attempt 3→4 at epoch 30: next=epoch+32=62
        // attempt 4→5 at epoch 62: abandoned (5 >= MAX_RETRIES=5)
        let epochs = [2u64, 6, 14, 30, 62];
        let mut last_due = Vec::new();
        for &ep in &epochs {
            last_due = s.tick(ep);
        }
        assert!(last_due.is_empty()); // abandoned, not retried
        assert_eq!(s.pending_count(), 0);
        assert_eq!(s.abandoned_count_total(), 1);
        assert_eq!(s.log.abandoned_count(), 1);
    }
}
