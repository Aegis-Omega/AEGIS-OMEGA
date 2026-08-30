//! Gate 275 — Message Deduplication Cache: epoch-scoped gossip dedup (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks (node_id, sequence) pairs seen in the current epoch to prevent
//! processing duplicate gossip messages. Supports epoch rotation (evicts
//! all entries from epochs older than the current by more than MAX_EPOCH_LAG).
//!
//! DedupEntry:
//!   node_id   — u32
//!   sequence  — u64
//!   seen_epoch — u64
//!
//! DedupCache:
//!   current_epoch   — u64
//!   entries         — BTreeMap<(u32, u64), u64>  (key=(node_id,seq), value=seen_epoch)
//!   max_epoch_lag   — u64  (entries older than current - lag are evicted on check/insert)
//!   hit_count       — u64  (total duplicate rejections)
//!   insert_count    — u64  (total new messages accepted)
//!
//! Methods:
//!   check_and_insert(node_id, sequence, epoch) → DedupResult
//!   advance_epoch(new_epoch) — evict stale entries and update current epoch
//!   hit_rate_pct() → u8 — hit_count * 100 / (hit_count + insert_count), 0 if empty
//!   entry_count() → usize
//!   evict_stale(current_epoch) — removes entries where seen_epoch < current_epoch - max_epoch_lag

use std::collections::BTreeMap;

pub const DEFAULT_MAX_EPOCH_LAG: u64 = 3;

// ─── Dedup result ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DedupResult {
    /// Message is new — accepted and recorded.
    New,
    /// Message was already seen in the given epoch.
    Duplicate { seen_epoch: u64 },
}

impl DedupResult {
    pub fn is_new(self) -> bool { matches!(self, DedupResult::New) }
    pub fn is_duplicate(self) -> bool { matches!(self, DedupResult::Duplicate { .. }) }
}

// ─── Dedup cache ──────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct DedupCache {
    current_epoch: u64,
    max_epoch_lag: u64,
    entries:       BTreeMap<(u32, u64), u64>, // (node_id, sequence) → seen_epoch
    hit_count:     u64,
    insert_count:  u64,
}

#[derive(Debug)]
pub enum DedupError {
    /// Epoch is older than current_epoch - max_epoch_lag (stale; ignore message).
    EpochTooOld,
    /// Epoch is in the future beyond current + 1 (advance_epoch first).
    EpochTooFuture,
}

impl DedupCache {
    pub fn new(initial_epoch: u64, max_epoch_lag: u64) -> Self {
        Self {
            current_epoch: initial_epoch,
            max_epoch_lag,
            entries: BTreeMap::new(),
            hit_count:    0,
            insert_count: 0,
        }
    }

    pub fn current_epoch(&self) -> u64 { self.current_epoch }
    pub fn entry_count(&self)  -> usize { self.entries.len() }
    pub fn hit_count(&self)    -> u64   { self.hit_count }
    pub fn insert_count(&self) -> u64   { self.insert_count }

    /// hit_count * 100 / (hit_count + insert_count), or 0 if no traffic.
    pub fn hit_rate_pct(&self) -> u8 {
        let total = self.hit_count + self.insert_count;
        if total == 0 { return 0; }
        ((self.hit_count * 100) / total).min(100) as u8
    }

    /// Check if (node_id, sequence) was seen and insert if not.
    /// Returns Err if epoch is outside the acceptable window.
    pub fn check_and_insert(
        &mut self,
        node_id:  u32,
        sequence: u64,
        epoch:    u64,
    ) -> Result<DedupResult, DedupError> {
        // Reject epochs too far in the past
        if epoch + self.max_epoch_lag < self.current_epoch {
            return Err(DedupError::EpochTooOld);
        }
        // Reject epochs more than 1 ahead (must advance_epoch first)
        if epoch > self.current_epoch + 1 {
            return Err(DedupError::EpochTooFuture);
        }

        let key = (node_id, sequence);
        if let Some(&seen_epoch) = self.entries.get(&key) {
            self.hit_count += 1;
            return Ok(DedupResult::Duplicate { seen_epoch });
        }

        self.entries.insert(key, epoch);
        self.insert_count += 1;
        Ok(DedupResult::New)
    }

    /// Advance current epoch, evicting entries older than current - max_epoch_lag.
    pub fn advance_epoch(&mut self, new_epoch: u64) {
        if new_epoch <= self.current_epoch { return; }
        self.current_epoch = new_epoch;
        self.evict_stale();
    }

    /// Remove entries whose seen_epoch is too old.
    fn evict_stale(&mut self) {
        if self.current_epoch < self.max_epoch_lag { return; }
        let threshold = self.current_epoch - self.max_epoch_lag;
        self.entries.retain(|_, &mut seen_epoch| seen_epoch >= threshold);
    }
}

impl Default for DedupCache {
    fn default() -> Self { Self::new(0, DEFAULT_MAX_EPOCH_LAG) }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── DedupResult ───────────────────────────────────────────────────────────

    #[test]
    fn dedup_result_is_new() {
        assert!(DedupResult::New.is_new());
        assert!(!DedupResult::New.is_duplicate());
    }

    #[test]
    fn dedup_result_is_duplicate() {
        let d = DedupResult::Duplicate { seen_epoch: 5 };
        assert!(d.is_duplicate());
        assert!(!d.is_new());
    }

    // ── check_and_insert ──────────────────────────────────────────────────────

    #[test]
    fn new_message_returns_new() {
        let mut c = DedupCache::new(1, 3);
        let r = c.check_and_insert(1, 100, 1).unwrap();
        assert_eq!(r, DedupResult::New);
        assert_eq!(c.insert_count(), 1);
    }

    #[test]
    fn duplicate_message_returns_duplicate() {
        let mut c = DedupCache::new(1, 3);
        c.check_and_insert(1, 100, 1).unwrap();
        let r = c.check_and_insert(1, 100, 1).unwrap();
        assert!(r.is_duplicate());
        assert_eq!(c.hit_count(), 1);
    }

    #[test]
    fn different_sequence_not_duplicate() {
        let mut c = DedupCache::new(1, 3);
        c.check_and_insert(1, 100, 1).unwrap();
        let r = c.check_and_insert(1, 101, 1).unwrap();
        assert_eq!(r, DedupResult::New);
    }

    #[test]
    fn different_node_same_seq_not_duplicate() {
        let mut c = DedupCache::new(1, 3);
        c.check_and_insert(1, 100, 1).unwrap();
        let r = c.check_and_insert(2, 100, 1).unwrap();
        assert_eq!(r, DedupResult::New);
    }

    #[test]
    fn epoch_too_old_returns_error() {
        let mut c = DedupCache::new(10, 3);
        // epoch 6 is 10 - 3 - 1 = too old
        let r = c.check_and_insert(1, 1, 6);
        assert!(matches!(r, Err(DedupError::EpochTooOld)));
    }

    #[test]
    fn epoch_at_boundary_accepted() {
        let mut c = DedupCache::new(10, 3);
        // epoch 7 = 10 - 3 → at boundary (just acceptable)
        let r = c.check_and_insert(1, 1, 7);
        assert!(r.is_ok());
    }

    #[test]
    fn epoch_too_future_returns_error() {
        let mut c = DedupCache::new(5, 3);
        let r = c.check_and_insert(1, 1, 8); // 8 > 5 + 1
        assert!(matches!(r, Err(DedupError::EpochTooFuture)));
    }

    #[test]
    fn next_epoch_plus_one_accepted() {
        let mut c = DedupCache::new(5, 3);
        let r = c.check_and_insert(1, 1, 6); // 6 = current + 1 → OK
        assert!(r.is_ok());
    }

    // ── advance_epoch + eviction ───────────────────────────────────────────────

    #[test]
    fn advance_epoch_evicts_old_entries() {
        let mut c = DedupCache::new(1, 2);
        c.check_and_insert(1, 1, 1).unwrap();
        c.check_and_insert(2, 2, 2).unwrap();
        c.advance_epoch(5); // lag=2 → threshold=3; epoch 1 and 2 evicted
        assert_eq!(c.entry_count(), 0);
    }

    #[test]
    fn advance_epoch_retains_recent_entries() {
        let mut c = DedupCache::new(1, 3);
        c.check_and_insert(1, 1, 1).unwrap();
        c.check_and_insert(2, 2, 2).unwrap();
        c.advance_epoch(4); // threshold=1; epoch 1 still ≥ 1 → retained
        assert_eq!(c.entry_count(), 2);
    }

    #[test]
    fn advance_epoch_noop_if_not_newer() {
        let mut c = DedupCache::new(10, 3);
        c.advance_epoch(5); // no-op
        assert_eq!(c.current_epoch(), 10);
    }

    // ── hit_rate_pct ──────────────────────────────────────────────────────────

    #[test]
    fn hit_rate_zero_when_empty() {
        let c = DedupCache::new(1, 3);
        assert_eq!(c.hit_rate_pct(), 0);
    }

    #[test]
    fn hit_rate_correct() {
        let mut c = DedupCache::new(1, 3);
        c.check_and_insert(1, 1, 1).unwrap(); // New
        c.check_and_insert(1, 1, 1).unwrap(); // Duplicate
        c.check_and_insert(1, 1, 1).unwrap(); // Duplicate
        // 2 hits / 3 total = 66%
        assert_eq!(c.hit_rate_pct(), 66);
    }

    #[test]
    fn entry_count_increments() {
        let mut c = DedupCache::new(1, 3);
        c.check_and_insert(1, 1, 1).unwrap();
        c.check_and_insert(2, 2, 1).unwrap();
        assert_eq!(c.entry_count(), 2);
    }
}
