//! Gate 308 — Gossip Message Acknowledgment Tracker: per-message delivery confirmation (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks acknowledgment status for sent gossip messages. Each message sent to a
//! peer is either Acked (delivery confirmed) or Unacked (pending or timed out).
//! A message is considered timed out when the current epoch exceeds sent_at_epoch +
//! ACK_TIMEOUT_EPOCHS. Acks are recorded as hash-chained AckRecords.
//!
//! Constants:
//!   ACK_TIMEOUT_EPOCHS: u64 = 5   (epochs before an unacked message is considered lost)
//!   MAX_PENDING_PER_PEER: usize = 128  (max unacked messages tracked per peer)
//!
//! AckStatus: Pending | Acked | TimedOut
//!
//! AckRecord:
//!   peer_id, message_id: u64, sent_at_epoch: u64, acked_at_epoch: Option<u64>, status
//!   record_hash = SHA-256(prev ‖ peer_be4 ‖ msg_be8 ‖ sent_be8 ‖ acked_be8_or_zero ‖ status_byte)
//!   prev_hash
//!
//! AckLog: hash-chained AckRecords (global).
//!   push(), acked_count(), timed_out_count(), verify_chain().
//!
//! PendingEntry: message_id, sent_at_epoch (internal state)
//!
//! MessageAckTracker:
//!   send(peer_id, message_id, epoch) → Result<(), AckError>   (tracks message as Pending)
//!   ack(peer_id, message_id, epoch) → bool                    (marks as Acked)
//!   expire_timeouts(current_epoch)   — marks TimedOut, removes from pending
//!   pending_count(peer_id) → usize
//!   delivery_rate_pct(peer_id) → u8  (acked*100 / (acked+timed_out), 0 if no completed)
//!   get_log() → &AckLog

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const ACK_TIMEOUT_EPOCHS:    u64   = 5;
pub const MAX_PENDING_PER_PEER:  usize = 128;

// ─── Ack status ───────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AckStatus {
    Pending   = 0,
    Acked     = 1,
    TimedOut  = 2,
}

impl AckStatus {
    pub fn status_byte(self) -> u8 { self as u8 }
}

// ─── Ack record ───────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct AckRecord {
    pub peer_id:        u32,
    pub message_id:     u64,
    pub sent_at_epoch:  u64,
    pub acked_at_epoch: Option<u64>,
    pub status:         AckStatus,
    pub record_hash:    [u8; 32],
    pub prev_hash:      [u8; 32],
}

pub const ACK_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_ack_hash(
    peer_id:        u32,
    message_id:     u64,
    sent_at_epoch:  u64,
    acked_at_epoch: Option<u64>,
    status:         AckStatus,
    prev:           &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(message_id.to_be_bytes());
    h.update(sent_at_epoch.to_be_bytes());
    h.update(acked_at_epoch.unwrap_or(0).to_be_bytes());
    h.update([status.status_byte()]);
    h.finalize().into()
}

pub fn build_ack_record(
    peer_id:        u32,
    message_id:     u64,
    sent_at_epoch:  u64,
    acked_at_epoch: Option<u64>,
    status:         AckStatus,
    prev_hash:      &[u8; 32],
) -> AckRecord {
    let record_hash = compute_ack_hash(peer_id, message_id, sent_at_epoch, acked_at_epoch, status, prev_hash);
    AckRecord { peer_id, message_id, sent_at_epoch, acked_at_epoch, status, record_hash, prev_hash: *prev_hash }
}

// ─── Ack log ──────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct AckLog {
    records: Vec<AckRecord>,
}

impl AckLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[AckRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(ACK_GENESIS_HASH)
    }

    pub fn push(
        &mut self,
        peer_id:        u32,
        message_id:     u64,
        sent_at_epoch:  u64,
        acked_at_epoch: Option<u64>,
        status:         AckStatus,
    ) -> &AckRecord {
        let prev = self.last_hash();
        let r = build_ack_record(peer_id, message_id, sent_at_epoch, acked_at_epoch, status, &prev);
        self.records.push(r);
        self.records.last().unwrap()
    }

    pub fn acked_count(&self) -> usize {
        self.records.iter().filter(|r| r.status == AckStatus::Acked).count()
    }

    pub fn timed_out_count(&self) -> usize {
        self.records.iter().filter(|r| r.status == AckStatus::TimedOut).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = ACK_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_ack_hash(r.peer_id, r.message_id, r.sent_at_epoch, r.acked_at_epoch, r.status, &r.prev_hash);
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for AckLog {
    fn default() -> Self { Self::new() }
}

// ─── Pending entry ────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
struct PendingEntry {
    sent_at_epoch: u64,
}

// ─── Per-peer state ───────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
struct PeerAckState {
    pending:       BTreeMap<u64, PendingEntry>, // message_id → entry
    acked_count:   u64,
    timeout_count: u64,
}

impl PeerAckState {
    fn new() -> Self {
        Self { pending: BTreeMap::new(), acked_count: 0, timeout_count: 0 }
    }
}

// ─── Errors ───────────────────────────────────────────────────────────────────

#[derive(Debug)]
pub enum AckError {
    AlreadyPending,
    PendingLimitReached,
}

// ─── MessageAckTracker ────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct MessageAckTracker {
    peers: BTreeMap<u32, PeerAckState>,
    pub log: AckLog,
}

impl MessageAckTracker {
    pub fn new() -> Self { Self { peers: BTreeMap::new(), log: AckLog::new() } }

    fn ensure_peer(&mut self, peer_id: u32) {
        self.peers.entry(peer_id).or_insert_with(PeerAckState::new);
    }

    /// Track a new message as Pending.
    pub fn send(&mut self, peer_id: u32, message_id: u64, epoch: u64) -> Result<(), AckError> {
        self.ensure_peer(peer_id);
        let state = self.peers.get_mut(&peer_id).unwrap();
        if state.pending.contains_key(&message_id) { return Err(AckError::AlreadyPending); }
        if state.pending.len() >= MAX_PENDING_PER_PEER { return Err(AckError::PendingLimitReached); }
        state.pending.insert(message_id, PendingEntry { sent_at_epoch: epoch });
        self.log.push(peer_id, message_id, epoch, None, AckStatus::Pending);
        Ok(())
    }

    /// Mark a pending message as Acked. Returns true if the message was pending.
    pub fn ack(&mut self, peer_id: u32, message_id: u64, epoch: u64) -> bool {
        if let Some(state) = self.peers.get_mut(&peer_id) {
            if let Some(entry) = state.pending.remove(&message_id) {
                state.acked_count += 1;
                self.log.push(peer_id, message_id, entry.sent_at_epoch, Some(epoch), AckStatus::Acked);
                return true;
            }
        }
        false
    }

    /// Expire all pending messages that have timed out, recording TimedOut entries.
    pub fn expire_timeouts(&mut self, current_epoch: u64) {
        // Collect all expired entries before mutating (avoids borrow conflict with self.log)
        let mut to_expire: Vec<(u32, u64, u64)> = Vec::new();
        for (&peer_id, state) in self.peers.iter() {
            for (&mid, entry) in state.pending.iter() {
                if current_epoch >= entry.sent_at_epoch.saturating_add(ACK_TIMEOUT_EPOCHS) {
                    to_expire.push((peer_id, mid, entry.sent_at_epoch));
                }
            }
        }
        for (peer_id, mid, sent) in to_expire {
            if let Some(state) = self.peers.get_mut(&peer_id) {
                state.pending.remove(&mid);
                state.timeout_count += 1;
            }
            self.log.push(peer_id, mid, sent, None, AckStatus::TimedOut);
        }
    }

    pub fn pending_count(&self, peer_id: u32) -> usize {
        self.peers.get(&peer_id).map(|s| s.pending.len()).unwrap_or(0)
    }

    /// acked * 100 / (acked + timed_out). Returns 0 if no completed messages.
    pub fn delivery_rate_pct(&self, peer_id: u32) -> u8 {
        if let Some(state) = self.peers.get(&peer_id) {
            let total = state.acked_count + state.timeout_count;
            if total == 0 { return 0; }
            ((state.acked_count * 100) / total) as u8
        } else {
            0
        }
    }

    pub fn get_log(&self) -> &AckLog { &self.log }
}

impl Default for MessageAckTracker {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── AckStatus ─────────────────────────────────────────────────────────────

    #[test]
    fn status_bytes() {
        assert_eq!(AckStatus::Pending.status_byte(),  0);
        assert_eq!(AckStatus::Acked.status_byte(),    1);
        assert_eq!(AckStatus::TimedOut.status_byte(), 2);
    }

    // ── build_ack_record ──────────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let r = build_ack_record(1, 100, 5, None, AckStatus::Pending, &ACK_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_ack_record(1, 100, 5, Some(7), AckStatus::Acked, &ACK_GENESIS_HASH);
        let r2 = build_ack_record(1, 100, 5, Some(7), AckStatus::Acked, &ACK_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    // ── AckLog ────────────────────────────────────────────────────────────────

    #[test]
    fn log_counts_statuses() {
        let mut l = AckLog::new();
        l.push(1, 10, 1, None, AckStatus::Pending);
        l.push(1, 10, 1, Some(2), AckStatus::Acked);
        l.push(1, 11, 1, None, AckStatus::TimedOut);
        assert_eq!(l.acked_count(), 1);
        assert_eq!(l.timed_out_count(), 1);
    }

    #[test]
    fn log_chain_links() {
        let mut l = AckLog::new();
        l.push(1, 10, 1, None, AckStatus::Pending);
        l.push(1, 11, 1, Some(3), AckStatus::Acked);
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    #[test]
    fn log_verify_chain_valid() {
        let mut l = AckLog::new();
        for i in 0..5u64 {
            l.push(1, i * 10, i, Some(i + 1), AckStatus::Acked);
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    // ── MessageAckTracker ─────────────────────────────────────────────────────

    #[test]
    fn send_and_pending() {
        let mut t = MessageAckTracker::new();
        t.send(1, 100, 1).unwrap();
        assert_eq!(t.pending_count(1), 1);
    }

    #[test]
    fn ack_removes_from_pending() {
        let mut t = MessageAckTracker::new();
        t.send(1, 100, 1).unwrap();
        assert!(t.ack(1, 100, 2));
        assert_eq!(t.pending_count(1), 0);
        assert_eq!(t.log.acked_count(), 1);
    }

    #[test]
    fn ack_not_pending_returns_false() {
        let mut t = MessageAckTracker::new();
        assert!(!t.ack(1, 999, 2));
    }

    #[test]
    fn duplicate_send_errors() {
        let mut t = MessageAckTracker::new();
        t.send(1, 100, 1).unwrap();
        assert!(matches!(t.send(1, 100, 2), Err(AckError::AlreadyPending)));
    }

    #[test]
    fn delivery_rate_all_acked() {
        let mut t = MessageAckTracker::new();
        t.send(1, 1, 1).unwrap();
        t.send(1, 2, 1).unwrap();
        t.ack(1, 1, 2);
        t.ack(1, 2, 2);
        // 2 acked, 0 timed out → 100%
        assert_eq!(t.delivery_rate_pct(1), 100);
    }

    #[test]
    fn delivery_rate_no_completed() {
        let mut t = MessageAckTracker::new();
        t.send(1, 1, 1).unwrap();
        assert_eq!(t.delivery_rate_pct(1), 0); // still pending
    }
}
