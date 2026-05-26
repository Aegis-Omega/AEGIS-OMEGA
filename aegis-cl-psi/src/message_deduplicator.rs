//! Gate 295 — Gossip Message Deduplicator: epoch-scoped duplicate suppression (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Maintains a per-epoch seen-set of (peer_id, message_id) pairs to detect and
//! suppress duplicate gossip messages. When an epoch boundary is crossed the
//! seen-set for the old epoch is sealed into a DedupRecord and cleared.
//!
//! DedupDecision:
//!   Fresh     — message not seen before this epoch; caller should forward it
//!   Duplicate — message already seen; caller should drop it
//!
//! DedupRecord:
//!   epoch          — u64
//!   seen_count     — u32 (unique messages accepted this epoch)
//!   dup_count      — u32 (duplicates suppressed this epoch)
//!   record_hash    — SHA-256(prev ‖ epoch_be8 ‖ seen_be4 ‖ dup_be4)
//!   prev_hash      — [u8; 32]
//!
//! DedupLog: hash-chained DedupRecords.
//!   record(), total_seen(), total_dups(), dup_rate_pct(), verify_chain().
//!
//! MessageDeduplicator:
//!   observe(peer_id, message_id, epoch) → DedupDecision
//!   seal_epoch(epoch) — persists current seen/dup counts to DedupLog
//!   dup_rate_current() → u32 percentage, seen_count_current() → u32

use sha2::{Sha256, Digest};
use std::collections::BTreeSet;

// ─── Dedup decision ───────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DedupDecision {
    Fresh,
    Duplicate,
}

impl DedupDecision {
    pub fn decision_byte(self) -> u8 {
        match self { Self::Fresh => 0, Self::Duplicate => 1 }
    }
    pub fn is_fresh(self) -> bool { matches!(self, Self::Fresh) }
}

// ─── Dedup record ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct DedupRecord {
    pub epoch:       u64,
    pub seen_count:  u32,
    pub dup_count:   u32,
    pub record_hash: [u8; 32],
    pub prev_hash:   [u8; 32],
}

pub const DEDUP_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_dedup_hash(
    epoch:      u64,
    seen_count: u32,
    dup_count:  u32,
    prev:       &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update(seen_count.to_be_bytes());
    h.update(dup_count.to_be_bytes());
    h.finalize().into()
}

pub fn build_dedup_record(
    epoch:      u64,
    seen_count: u32,
    dup_count:  u32,
    prev_hash:  &[u8; 32],
) -> DedupRecord {
    let record_hash = compute_dedup_hash(epoch, seen_count, dup_count, prev_hash);
    DedupRecord { epoch, seen_count, dup_count, record_hash, prev_hash: *prev_hash }
}

// ─── Dedup log ────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct DedupLog {
    records: Vec<DedupRecord>,
}

#[derive(Debug)]
pub enum DedupError {
    StaleEpoch,
}

impl DedupLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[DedupRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(DEDUP_GENESIS_HASH)
    }

    pub fn record(
        &mut self,
        epoch:      u64,
        seen_count: u32,
        dup_count:  u32,
    ) -> Result<&DedupRecord, DedupError> {
        if let Some(last) = self.records.last() {
            if epoch <= last.epoch { return Err(DedupError::StaleEpoch); }
        }
        let prev = self.last_hash();
        let r = build_dedup_record(epoch, seen_count, dup_count, &prev);
        self.records.push(r);
        Ok(self.records.last().unwrap())
    }

    pub fn total_seen(&self) -> u64 {
        self.records.iter().map(|r| r.seen_count as u64).sum()
    }

    pub fn total_dups(&self) -> u64 {
        self.records.iter().map(|r| r.dup_count as u64).sum()
    }

    /// Integer duplicate rate percentage (0–100).
    pub fn dup_rate_pct(&self) -> u8 {
        let total = self.total_seen() + self.total_dups();
        if total == 0 { return 0; }
        ((self.total_dups() * 100) / total).min(100) as u8
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = DEDUP_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_dedup_hash(r.epoch, r.seen_count, r.dup_count, &r.prev_hash);
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for DedupLog {
    fn default() -> Self { Self::new() }
}

// ─── Message deduplicator ─────────────────────────────────────────────────────

/// A (peer_id, message_id) pair uniquely identifying a gossip message within an epoch.
type MsgKey = (u32, u64);

#[derive(Debug, Clone)]
pub struct MessageDeduplicator {
    current_epoch: u64,
    seen:          BTreeSet<MsgKey>,
    seen_count:    u32,
    dup_count:     u32,
    pub log:       DedupLog,
}

impl MessageDeduplicator {
    pub fn new(initial_epoch: u64) -> Self {
        Self {
            current_epoch: initial_epoch,
            seen:          BTreeSet::new(),
            seen_count:    0,
            dup_count:     0,
            log:           DedupLog::new(),
        }
    }

    /// Observe a message. Rolls epoch forward if `epoch > current_epoch` (implicitly seals).
    pub fn observe(&mut self, peer_id: u32, message_id: u64, epoch: u64) -> DedupDecision {
        if epoch > self.current_epoch {
            self.current_epoch = epoch;
            self.seen.clear();
            self.seen_count = 0;
            self.dup_count  = 0;
        }

        let key = (peer_id, message_id);
        if self.seen.contains(&key) {
            self.dup_count = self.dup_count.saturating_add(1);
            DedupDecision::Duplicate
        } else {
            self.seen.insert(key);
            self.seen_count = self.seen_count.saturating_add(1);
            DedupDecision::Fresh
        }
    }

    /// Seal the current epoch into the log.
    pub fn seal_epoch(&mut self, epoch: u64) {
        if self.current_epoch == epoch {
            let _ = self.log.record(epoch, self.seen_count, self.dup_count);
        }
    }

    pub fn seen_count_current(&self) -> u32  { self.seen_count }
    pub fn dup_count_current(&self)  -> u32  { self.dup_count }

    pub fn dup_rate_current(&self) -> u32 {
        let total = self.seen_count as u64 + self.dup_count as u64;
        if total == 0 { return 0; }
        ((self.dup_count as u64 * 100) / total) as u32
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── DedupDecision ─────────────────────────────────────────────────────────

    #[test]
    fn decision_bytes() {
        assert_eq!(DedupDecision::Fresh.decision_byte(),     0);
        assert_eq!(DedupDecision::Duplicate.decision_byte(), 1);
    }

    #[test]
    fn is_fresh_correct() {
        assert!(DedupDecision::Fresh.is_fresh());
        assert!(!DedupDecision::Duplicate.is_fresh());
    }

    // ── build_dedup_record ────────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let r = build_dedup_record(1, 100, 5, &DEDUP_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_dedup_record(1, 100, 5, &DEDUP_GENESIS_HASH);
        let r2 = build_dedup_record(1, 100, 5, &DEDUP_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    // ── DedupLog ──────────────────────────────────────────────────────────────

    #[test]
    fn new_log_empty() {
        let l = DedupLog::new();
        assert!(l.is_empty());
        assert_eq!(l.total_seen(), 0);
        assert_eq!(l.total_dups(), 0);
        assert_eq!(l.dup_rate_pct(), 0);
    }

    #[test]
    fn log_accumulates_and_rates() {
        let mut l = DedupLog::new();
        l.record(1, 150, 50).unwrap(); // 50/(150+50) = 25%
        l.record(2, 100, 0).unwrap();
        assert_eq!(l.total_seen(), 250);
        assert_eq!(l.total_dups(), 50);
        assert_eq!(l.dup_rate_pct(), 16); // 50/300 = 16.6% → 16
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut l = DedupLog::new();
        l.record(5, 100, 0).unwrap();
        assert!(matches!(l.record(4, 100, 0), Err(DedupError::StaleEpoch)));
        assert!(matches!(l.record(5, 100, 0), Err(DedupError::StaleEpoch)));
    }

    #[test]
    fn chain_links() {
        let mut l = DedupLog::new();
        l.record(1, 100, 5).unwrap();
        l.record(2, 80, 2).unwrap();
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    #[test]
    fn verify_chain_valid() {
        let mut l = DedupLog::new();
        for e in 1..=5u64 {
            l.record(e, e as u32 * 20, 0).unwrap();
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    // ── MessageDeduplicator ───────────────────────────────────────────────────

    #[test]
    fn first_message_is_fresh() {
        let mut d = MessageDeduplicator::new(1);
        assert_eq!(d.observe(1, 100, 1), DedupDecision::Fresh);
    }

    #[test]
    fn duplicate_detected() {
        let mut d = MessageDeduplicator::new(1);
        d.observe(1, 100, 1);
        assert_eq!(d.observe(1, 100, 1), DedupDecision::Duplicate);
        assert_eq!(d.dup_count_current(), 1);
    }

    #[test]
    fn different_peer_same_message_id_fresh() {
        let mut d = MessageDeduplicator::new(1);
        d.observe(1, 100, 1);
        assert_eq!(d.observe(2, 100, 1), DedupDecision::Fresh);
    }

    #[test]
    fn epoch_rollover_clears_seen_set() {
        let mut d = MessageDeduplicator::new(1);
        d.observe(1, 100, 1); // Fresh in epoch 1
        assert_eq!(d.observe(1, 100, 2), DedupDecision::Fresh); // epoch 2 → new set
    }

    #[test]
    fn seen_count_tracks_correctly() {
        let mut d = MessageDeduplicator::new(1);
        d.observe(1, 1, 1);
        d.observe(1, 2, 1);
        d.observe(1, 1, 1); // dup
        assert_eq!(d.seen_count_current(), 2);
        assert_eq!(d.dup_count_current(), 1);
    }

    #[test]
    fn dup_rate_current() {
        let mut d = MessageDeduplicator::new(1);
        for i in 0..3 { d.observe(1, i, 1); } // 3 fresh
        d.observe(1, 0, 1); // 1 dup
        // rate = 1/(3+1) = 25%
        assert_eq!(d.dup_rate_current(), 25);
    }

    #[test]
    fn seal_epoch_persists_to_log() {
        let mut d = MessageDeduplicator::new(1);
        for i in 0..5 { d.observe(1, i, 1); }
        d.observe(1, 0, 1); // dup
        d.seal_epoch(1);
        assert_eq!(d.log.len(), 1);
        assert_eq!(d.log.records()[0].seen_count, 5);
        assert_eq!(d.log.records()[0].dup_count,  1);
    }
}
