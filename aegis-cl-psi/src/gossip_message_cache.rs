//! Gate 313 — Gossip Message Cache: epoch-scoped content-addressed message store (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Stores recent gossip message payloads keyed by their SHA-256 content hash.
//! Each epoch, messages can be inserted and retrieved by hash. At epoch advance,
//! messages older than CACHE_WINDOW_EPOCHS are evicted. The cache prevents
//! re-processing the same payload within the window.
//!
//! Constants:
//!   CACHE_WINDOW_EPOCHS: u64   = 6    (epochs of retention)
//!   MAX_ENTRIES_PER_EPOCH: usize = 512 (hard cap per epoch slot)
//!
//! CacheDecision: Inserted | AlreadyPresent | EpochFull
//!
//! CacheRecord:
//!   content_hash: [u8;32], inserted_epoch: u64, decision
//!   record_hash = SHA-256(prev ‖ content_hash[32] ‖ epoch_be8 ‖ decision_byte)
//!   prev_hash
//!
//! CacheLog: hash-chained CacheRecords (global).
//!   push(), inserted_count(), already_present_count(), verify_chain().
//!
//! GossipMessageCache:
//!   insert(content_hash, epoch) → CacheDecision
//!   contains(content_hash) → bool   (searches entire window)
//!   advance_epoch(new_epoch)         (evicts old epochs)
//!   window_entry_count() → usize    (total entries in window)
//!   get_log() → &CacheLog

use sha2::{Sha256, Digest};
use std::collections::{BTreeMap, BTreeSet};

pub const CACHE_WINDOW_EPOCHS:    u64   = 6;
pub const MAX_ENTRIES_PER_EPOCH:  usize = 512;

// ─── Cache decision ───────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CacheDecision {
    Inserted       = 0,
    AlreadyPresent = 1,
    EpochFull      = 2,
}

impl CacheDecision {
    pub fn decision_byte(self) -> u8 { self as u8 }
}

// ─── Cache record ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct CacheRecord {
    pub content_hash:    [u8; 32],
    pub inserted_epoch:  u64,
    pub decision:        CacheDecision,
    pub record_hash:     [u8; 32],
    pub prev_hash:       [u8; 32],
}

pub const CACHE_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_cache_hash(
    content_hash:   &[u8; 32],
    inserted_epoch: u64,
    decision:       CacheDecision,
    prev:           &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(content_hash);
    h.update(inserted_epoch.to_be_bytes());
    h.update([decision.decision_byte()]);
    h.finalize().into()
}

pub fn build_cache_record(
    content_hash:   [u8; 32],
    inserted_epoch: u64,
    decision:       CacheDecision,
    prev_hash:      &[u8; 32],
) -> CacheRecord {
    let record_hash = compute_cache_hash(&content_hash, inserted_epoch, decision, prev_hash);
    CacheRecord { content_hash, inserted_epoch, decision, record_hash, prev_hash: *prev_hash }
}

// ─── Cache log ────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct CacheLog {
    records: Vec<CacheRecord>,
}

impl CacheLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)     -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool { self.records.is_empty() }
    pub fn records(&self) -> &[CacheRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(CACHE_GENESIS_HASH)
    }

    pub fn push(
        &mut self,
        content_hash:   [u8; 32],
        inserted_epoch: u64,
        decision:       CacheDecision,
    ) -> &CacheRecord {
        let prev = self.last_hash();
        let r = build_cache_record(content_hash, inserted_epoch, decision, &prev);
        self.records.push(r);
        self.records.last().unwrap()
    }

    pub fn inserted_count(&self) -> usize {
        self.records.iter().filter(|r| r.decision == CacheDecision::Inserted).count()
    }

    pub fn already_present_count(&self) -> usize {
        self.records.iter().filter(|r| r.decision == CacheDecision::AlreadyPresent).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = CACHE_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_cache_hash(&r.content_hash, r.inserted_epoch, r.decision, &r.prev_hash);
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for CacheLog {
    fn default() -> Self { Self::new() }
}

// ─── GossipMessageCache ───────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct GossipMessageCache {
    /// BTreeMap<epoch, BTreeSet<content_hash>>
    window:        BTreeMap<u64, BTreeSet<[u8; 32]>>,
    current_epoch: u64,
    pub log:       CacheLog,
}

impl GossipMessageCache {
    pub fn new(initial_epoch: u64) -> Self {
        Self { window: BTreeMap::new(), current_epoch: initial_epoch, log: CacheLog::new() }
    }

    fn evict_old(&mut self) {
        let cutoff = self.current_epoch.saturating_sub(CACHE_WINDOW_EPOCHS);
        self.window.retain(|&epoch, _| epoch > cutoff);
    }

    pub fn advance_epoch(&mut self, new_epoch: u64) {
        if new_epoch > self.current_epoch {
            self.current_epoch = new_epoch;
            self.evict_old();
        }
    }

    /// Insert a message by content hash. Records the decision in the log.
    pub fn insert(&mut self, content_hash: [u8; 32], epoch: u64) -> CacheDecision {
        if epoch > self.current_epoch {
            self.current_epoch = epoch;
            self.evict_old();
        }

        // Check if already present in any epoch slot in window
        for slot in self.window.values() {
            if slot.contains(&content_hash) {
                self.log.push(content_hash, epoch, CacheDecision::AlreadyPresent);
                return CacheDecision::AlreadyPresent;
            }
        }

        let slot = self.window.entry(epoch).or_insert_with(BTreeSet::new);
        if slot.len() >= MAX_ENTRIES_PER_EPOCH {
            self.log.push(content_hash, epoch, CacheDecision::EpochFull);
            return CacheDecision::EpochFull;
        }

        slot.insert(content_hash);
        self.log.push(content_hash, epoch, CacheDecision::Inserted);
        CacheDecision::Inserted
    }

    /// Check if a content hash is present in the current window.
    pub fn contains(&self, content_hash: &[u8; 32]) -> bool {
        self.window.values().any(|slot| slot.contains(content_hash))
    }

    /// Total entries across all epoch slots in the window.
    pub fn window_entry_count(&self) -> usize {
        self.window.values().map(|s| s.len()).sum()
    }

    pub fn current_epoch(&self) -> u64 { self.current_epoch }
    pub fn get_log(&self) -> &CacheLog { &self.log }
}

impl Default for GossipMessageCache {
    fn default() -> Self { Self::new(0) }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn hash_of(seed: u8) -> [u8; 32] {
        let mut h = [0u8; 32];
        h[0] = seed;
        h[31] = seed.wrapping_mul(7);
        h
    }

    // ── CacheDecision ─────────────────────────────────────────────────────────

    #[test]
    fn decision_bytes() {
        assert_eq!(CacheDecision::Inserted.decision_byte(),       0);
        assert_eq!(CacheDecision::AlreadyPresent.decision_byte(), 1);
        assert_eq!(CacheDecision::EpochFull.decision_byte(),      2);
    }

    // ── build_cache_record ────────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let r = build_cache_record(hash_of(1), 1, CacheDecision::Inserted, &CACHE_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_cache_record(hash_of(1), 1, CacheDecision::Inserted, &CACHE_GENESIS_HASH);
        let r2 = build_cache_record(hash_of(1), 1, CacheDecision::Inserted, &CACHE_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    // ── CacheLog ──────────────────────────────────────────────────────────────

    #[test]
    fn log_counts() {
        let mut l = CacheLog::new();
        l.push(hash_of(1), 1, CacheDecision::Inserted);
        l.push(hash_of(1), 1, CacheDecision::AlreadyPresent);
        l.push(hash_of(2), 1, CacheDecision::Inserted);
        assert_eq!(l.inserted_count(), 2);
        assert_eq!(l.already_present_count(), 1);
    }

    #[test]
    fn log_chain_links() {
        let mut l = CacheLog::new();
        l.push(hash_of(1), 1, CacheDecision::Inserted);
        l.push(hash_of(2), 2, CacheDecision::Inserted);
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    #[test]
    fn log_verify_chain_valid() {
        let mut l = CacheLog::new();
        for i in 0..5u8 {
            l.push(hash_of(i), i as u64, CacheDecision::Inserted);
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    // ── GossipMessageCache ────────────────────────────────────────────────────

    #[test]
    fn first_insert_is_inserted() {
        let mut c = GossipMessageCache::new(1);
        assert_eq!(c.insert(hash_of(1), 1), CacheDecision::Inserted);
        assert!(c.contains(&hash_of(1)));
        assert_eq!(c.window_entry_count(), 1);
    }

    #[test]
    fn duplicate_insert_is_already_present() {
        let mut c = GossipMessageCache::new(1);
        c.insert(hash_of(1), 1);
        assert_eq!(c.insert(hash_of(1), 1), CacheDecision::AlreadyPresent);
    }

    #[test]
    fn old_epoch_evicted() {
        let mut c = GossipMessageCache::new(1);
        c.insert(hash_of(1), 1);
        c.advance_epoch(1 + CACHE_WINDOW_EPOCHS + 1); // epoch 8
        assert!(!c.contains(&hash_of(1)));
        assert_eq!(c.window_entry_count(), 0);
    }

    #[test]
    fn window_covers_multiple_epochs() {
        let mut c = GossipMessageCache::new(1);
        c.insert(hash_of(1), 1);
        c.insert(hash_of(2), 3);
        assert_eq!(c.window_entry_count(), 2);
        // Both still in window at epoch 4
        assert!(c.contains(&hash_of(1)));
        assert!(c.contains(&hash_of(2)));
    }

    #[test]
    fn duplicate_across_epochs_is_already_present() {
        let mut c = GossipMessageCache::new(1);
        c.insert(hash_of(5), 1);
        // Same hash at a later epoch — still present in window
        assert_eq!(c.insert(hash_of(5), 3), CacheDecision::AlreadyPresent);
    }

    #[test]
    fn log_records_all_inserts() {
        let mut c = GossipMessageCache::new(1);
        c.insert(hash_of(1), 1);
        c.insert(hash_of(1), 1); // already present
        assert_eq!(c.log.inserted_count(), 1);
        assert_eq!(c.log.already_present_count(), 1);
        let (valid, _) = c.log.verify_chain();
        assert!(valid);
    }
}
