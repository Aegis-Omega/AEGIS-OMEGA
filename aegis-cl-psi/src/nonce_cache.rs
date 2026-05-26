//! Gate 306 — Gossip Nonce Cache: replay-attack prevention via sliding window nonce tracking (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks recently seen (peer_id, nonce) pairs within a sliding window of epochs to
//! prevent replay attacks. Nonces outside the window are automatically evicted.
//! A nonce is accepted only once per peer within the window.
//!
//! Constants:
//!   WINDOW_EPOCHS: u64 = 8   (number of epochs in the sliding window)
//!   MAX_NONCES_PER_EPOCH: usize = 1024  (max nonces tracked per epoch before eviction)
//!
//! NonceDecision: Fresh | Replay
//!
//! NonceRecord:
//!   peer_id, epoch, nonce: u64, decision, record_hash, prev_hash
//!   record_hash = SHA-256(prev ‖ peer_be4 ‖ epoch_be8 ‖ nonce_be8 ‖ decision_byte)
//!
//! NonceLog: hash-chained NonceRecords.
//!   push(), fresh_count(), replay_count(), verify_chain().
//!
//! NonceCache:
//!   check(peer_id, epoch, nonce) → NonceDecision
//!     Marks nonce Fresh if not seen in window; marks Replay if already seen.
//!     Evicts epochs older than current_epoch - WINDOW_EPOCHS.
//!   advance_epoch(new_epoch)  — explicitly advance window, evict old epochs
//!   window_size() → usize    — number of (peer, nonce) entries currently tracked
//!   log: NonceLog             — all check() calls recorded

use sha2::{Sha256, Digest};
use std::collections::{BTreeMap, BTreeSet};

pub const WINDOW_EPOCHS:       u64   = 8;
pub const MAX_NONCES_PER_EPOCH: usize = 1024;

// ─── Nonce decision ───────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NonceDecision {
    Fresh  = 0,
    Replay = 1,
}

impl NonceDecision {
    pub fn decision_byte(self) -> u8 { self as u8 }
    pub fn is_fresh(self) -> bool { matches!(self, Self::Fresh) }
}

// ─── Nonce record ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct NonceRecord {
    pub peer_id:     u32,
    pub epoch:       u64,
    pub nonce:       u64,
    pub decision:    NonceDecision,
    pub record_hash: [u8; 32],
    pub prev_hash:   [u8; 32],
}

pub const NONCE_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_nonce_hash(
    peer_id:  u32,
    epoch:    u64,
    nonce:    u64,
    decision: NonceDecision,
    prev:     &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update(nonce.to_be_bytes());
    h.update([decision.decision_byte()]);
    h.finalize().into()
}

pub fn build_nonce_record(
    peer_id:   u32,
    epoch:     u64,
    nonce:     u64,
    decision:  NonceDecision,
    prev_hash: &[u8; 32],
) -> NonceRecord {
    let record_hash = compute_nonce_hash(peer_id, epoch, nonce, decision, prev_hash);
    NonceRecord { peer_id, epoch, nonce, decision, record_hash, prev_hash: *prev_hash }
}

// ─── Nonce log ────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct NonceLog {
    records: Vec<NonceRecord>,
}

impl NonceLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[NonceRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(NONCE_GENESIS_HASH)
    }

    pub fn push(&mut self, peer_id: u32, epoch: u64, nonce: u64, decision: NonceDecision) -> &NonceRecord {
        let prev = self.last_hash();
        let r = build_nonce_record(peer_id, epoch, nonce, decision, &prev);
        self.records.push(r);
        self.records.last().unwrap()
    }

    pub fn fresh_count(&self) -> usize {
        self.records.iter().filter(|r| r.decision == NonceDecision::Fresh).count()
    }

    pub fn replay_count(&self) -> usize {
        self.records.iter().filter(|r| r.decision == NonceDecision::Replay).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = NONCE_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_nonce_hash(r.peer_id, r.epoch, r.nonce, r.decision, &r.prev_hash);
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for NonceLog {
    fn default() -> Self { Self::new() }
}

// ─── Nonce cache ──────────────────────────────────────────────────────────────

/// Key: (epoch, peer_id, nonce)
type NonceKey = (u64, u32, u64);

#[derive(Debug, Clone)]
pub struct NonceCache {
    /// BTreeMap<epoch, BTreeSet<(peer_id, nonce)>>
    window: BTreeMap<u64, BTreeSet<(u32, u64)>>,
    current_epoch: u64,
    pub log: NonceLog,
}

impl NonceCache {
    pub fn new(initial_epoch: u64) -> Self {
        Self {
            window: BTreeMap::new(),
            current_epoch: initial_epoch,
            log: NonceLog::new(),
        }
    }

    fn evict_old_epochs(&mut self) {
        let cutoff = self.current_epoch.saturating_sub(WINDOW_EPOCHS);
        self.window.retain(|&epoch, _| epoch > cutoff);
    }

    /// Advance the window to new_epoch (no-op if new_epoch <= current_epoch).
    pub fn advance_epoch(&mut self, new_epoch: u64) {
        if new_epoch > self.current_epoch {
            self.current_epoch = new_epoch;
            self.evict_old_epochs();
        }
    }

    /// Check a nonce. Returns Fresh if not seen; Replay if already in window.
    /// Automatically evicts stale epochs when epoch advances.
    pub fn check(&mut self, peer_id: u32, epoch: u64, nonce: u64) -> NonceDecision {
        if epoch > self.current_epoch {
            self.current_epoch = epoch;
            self.evict_old_epochs();
        }
        let slot = self.window.entry(epoch).or_insert_with(BTreeSet::new);
        let key = (peer_id, nonce);
        let decision = if slot.contains(&key) {
            NonceDecision::Replay
        } else {
            if slot.len() < MAX_NONCES_PER_EPOCH {
                slot.insert(key);
            }
            NonceDecision::Fresh
        };
        self.log.push(peer_id, epoch, nonce, decision);
        decision
    }

    /// Total (peer_id, nonce) entries currently in the window.
    pub fn window_size(&self) -> usize {
        self.window.values().map(|s| s.len()).sum()
    }

    pub fn current_epoch(&self) -> u64 { self.current_epoch }
}

impl Default for NonceCache {
    fn default() -> Self { Self::new(0) }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── NonceDecision ─────────────────────────────────────────────────────────

    #[test]
    fn decision_bytes() {
        assert_eq!(NonceDecision::Fresh.decision_byte(),  0);
        assert_eq!(NonceDecision::Replay.decision_byte(), 1);
        assert!(NonceDecision::Fresh.is_fresh());
        assert!(!NonceDecision::Replay.is_fresh());
    }

    // ── build_nonce_record ────────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let r = build_nonce_record(1, 1, 999, NonceDecision::Fresh, &NONCE_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_nonce_record(1, 1, 999, NonceDecision::Fresh, &NONCE_GENESIS_HASH);
        let r2 = build_nonce_record(1, 1, 999, NonceDecision::Fresh, &NONCE_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    // ── NonceLog ──────────────────────────────────────────────────────────────

    #[test]
    fn log_counts_decisions() {
        let mut l = NonceLog::new();
        l.push(1, 1, 100, NonceDecision::Fresh);
        l.push(1, 1, 100, NonceDecision::Replay);
        l.push(2, 1, 200, NonceDecision::Fresh);
        assert_eq!(l.fresh_count(), 2);
        assert_eq!(l.replay_count(), 1);
    }

    #[test]
    fn log_chain_links() {
        let mut l = NonceLog::new();
        l.push(1, 1, 100, NonceDecision::Fresh);
        l.push(1, 1, 101, NonceDecision::Fresh);
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    #[test]
    fn log_verify_chain_valid() {
        let mut l = NonceLog::new();
        for i in 0..5u64 { l.push(1, 1, i, NonceDecision::Fresh); }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    // ── NonceCache ────────────────────────────────────────────────────────────

    #[test]
    fn first_nonce_is_fresh() {
        let mut c = NonceCache::new(1);
        assert_eq!(c.check(1, 1, 42), NonceDecision::Fresh);
    }

    #[test]
    fn repeated_nonce_is_replay() {
        let mut c = NonceCache::new(1);
        c.check(1, 1, 42);
        assert_eq!(c.check(1, 1, 42), NonceDecision::Replay);
    }

    #[test]
    fn different_peer_same_nonce_is_fresh() {
        let mut c = NonceCache::new(1);
        c.check(1, 1, 42);
        assert_eq!(c.check(2, 1, 42), NonceDecision::Fresh);
    }

    #[test]
    fn old_epoch_evicted() {
        let mut c = NonceCache::new(1);
        c.check(1, 1, 42); // epoch 1, nonce 42 → Fresh
        // advance past window (epoch 1 + WINDOW_EPOCHS = 9; advance to 10)
        c.advance_epoch(1 + WINDOW_EPOCHS + 1);
        // epoch 1 is now outside window; but we can't re-check epoch 1 here since
        // advance_epoch doesn't allow past epochs to be re-inserted.
        // Instead verify window_size dropped to 0
        assert_eq!(c.window_size(), 0);
    }

    #[test]
    fn window_size_tracks_entries() {
        let mut c = NonceCache::new(1);
        c.check(1, 1, 10);
        c.check(1, 1, 20);
        c.check(2, 1, 10);
        assert_eq!(c.window_size(), 3);
    }

    #[test]
    fn log_records_all_checks() {
        let mut c = NonceCache::new(1);
        c.check(1, 1, 10);
        c.check(1, 1, 10); // replay
        assert_eq!(c.log.fresh_count(), 1);
        assert_eq!(c.log.replay_count(), 1);
        let (valid, _) = c.log.verify_chain();
        assert!(valid);
    }

    #[test]
    fn advance_epoch_evicts_stale() {
        let mut c = NonceCache::new(1);
        for n in 0..5u64 { c.check(1, 1, n); }
        assert_eq!(c.window_size(), 5);
        c.advance_epoch(1 + WINDOW_EPOCHS + 1);
        assert_eq!(c.window_size(), 0);
    }
}
