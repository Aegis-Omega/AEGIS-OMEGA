//! Gate 290 — Gossip Epoch Rate Limiter: token-bucket rate limiting per source per epoch (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Each source is allocated a token bucket of BUCKET_CAPACITY tokens per epoch.
//! Each gossip message consumes one token. When the bucket is empty, messages are
//! rate-limited (dropped). Buckets auto-refill at epoch boundaries.
//!
//! RateLimitDecision:
//!   Allowed   — token consumed, message accepted
//!   RateLimited — bucket empty, message dropped
//!
//! BucketRecord:
//!   source_id      — u32
//!   epoch          — u64
//!   tokens_used    — u32 (total messages accepted this epoch)
//!   tokens_dropped — u32 (total messages dropped this epoch)
//!   record_hash    — SHA-256(prev ‖ src_be4 ‖ epoch_be8 ‖ used_be4 ‖ dropped_be4)
//!   prev_hash      — [u8; 32]
//!
//! BucketLog: hash-chained BucketRecords per source.
//!   record(), total_allowed(), total_dropped(), drop_rate_pct(), verify_chain().
//!
//! EpochRateLimiter: BTreeMap<source_id, BucketState>.
//!   consume(source_id, epoch) → RateLimitDecision
//!   seal_epoch(epoch) — persists current bucket state to logs
//!   dropped_count(source_id) → u32, sources_over_limit() → Vec<u32>

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const BUCKET_CAPACITY: u32 = 200; // tokens per source per epoch

// ─── Rate limit decision ──────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RateLimitDecision {
    Allowed,
    RateLimited,
}

impl RateLimitDecision {
    pub fn decision_byte(self) -> u8 {
        match self { Self::Allowed => 0, Self::RateLimited => 1 }
    }
    pub fn is_allowed(self) -> bool { matches!(self, Self::Allowed) }
}

// ─── Bucket record ────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct BucketRecord {
    pub source_id:      u32,
    pub epoch:          u64,
    pub tokens_used:    u32,
    pub tokens_dropped: u32,
    pub record_hash:    [u8; 32],
    pub prev_hash:      [u8; 32],
}

pub const BUCKET_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_bucket_hash(
    source_id:      u32,
    epoch:          u64,
    tokens_used:    u32,
    tokens_dropped: u32,
    prev:           &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(source_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update(tokens_used.to_be_bytes());
    h.update(tokens_dropped.to_be_bytes());
    h.finalize().into()
}

pub fn build_bucket_record(
    source_id:      u32,
    epoch:          u64,
    tokens_used:    u32,
    tokens_dropped: u32,
    prev_hash:      &[u8; 32],
) -> BucketRecord {
    let record_hash = compute_bucket_hash(source_id, epoch, tokens_used, tokens_dropped, prev_hash);
    BucketRecord { source_id, epoch, tokens_used, tokens_dropped, record_hash, prev_hash: *prev_hash }
}

// ─── Bucket log ───────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct BucketLog {
    source_id: u32,
    records:   Vec<BucketRecord>,
}

#[derive(Debug)]
pub enum BucketError {
    StaleEpoch,
}

impl BucketLog {
    pub fn new(source_id: u32) -> Self { Self { source_id, records: Vec::new() } }

    pub fn len(&self)     -> usize { self.records.len() }
    pub fn is_empty(&self)-> bool  { self.records.is_empty() }
    pub fn records(&self) -> &[BucketRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(BUCKET_GENESIS_HASH)
    }

    pub fn record(
        &mut self,
        epoch:          u64,
        tokens_used:    u32,
        tokens_dropped: u32,
    ) -> Result<&BucketRecord, BucketError> {
        if let Some(last) = self.records.last() {
            if epoch <= last.epoch { return Err(BucketError::StaleEpoch); }
        }
        let prev = self.last_hash();
        let r = build_bucket_record(self.source_id, epoch, tokens_used, tokens_dropped, &prev);
        self.records.push(r);
        Ok(self.records.last().unwrap())
    }

    pub fn total_allowed(&self) -> u64 {
        self.records.iter().map(|r| r.tokens_used as u64).sum()
    }

    pub fn total_dropped(&self) -> u64 {
        self.records.iter().map(|r| r.tokens_dropped as u64).sum()
    }

    /// Integer drop rate percentage (0–100).
    pub fn drop_rate_pct(&self) -> u8 {
        let total = self.total_allowed() + self.total_dropped();
        if total == 0 { return 0; }
        ((self.total_dropped() * 100) / total).min(100) as u8
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = BUCKET_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_bucket_hash(
                r.source_id, r.epoch, r.tokens_used, r.tokens_dropped, &r.prev_hash,
            );
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

// ─── Epoch rate limiter ────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
struct BucketState {
    log:            BucketLog,
    current_epoch:  u64,
    tokens_used:    u32,
    tokens_dropped: u32,
}

#[derive(Debug, Clone)]
pub struct EpochRateLimiter {
    capacity: u32,
    sources:  BTreeMap<u32, BucketState>,
}

impl EpochRateLimiter {
    pub fn new(capacity: u32) -> Self {
        Self { capacity, sources: BTreeMap::new() }
    }

    pub fn with_default_capacity() -> Self { Self::new(BUCKET_CAPACITY) }

    pub fn source_count(&self) -> usize { self.sources.len() }

    /// Consume one token for a source. Returns Allowed if tokens remain, RateLimited otherwise.
    pub fn consume(&mut self, source_id: u32, epoch: u64) -> RateLimitDecision {
        let cap = self.capacity;
        let state = self.sources.entry(source_id).or_insert_with(|| BucketState {
            log:            BucketLog::new(source_id),
            current_epoch:  epoch,
            tokens_used:    0,
            tokens_dropped: 0,
        });

        if epoch > state.current_epoch {
            state.current_epoch  = epoch;
            state.tokens_used    = 0;
            state.tokens_dropped = 0;
        }

        if state.tokens_used < cap {
            state.tokens_used = state.tokens_used.saturating_add(1);
            RateLimitDecision::Allowed
        } else {
            state.tokens_dropped = state.tokens_dropped.saturating_add(1);
            RateLimitDecision::RateLimited
        }
    }

    /// Seal the current epoch for all sources, persisting counts to their logs.
    pub fn seal_epoch(&mut self, epoch: u64) {
        for state in self.sources.values_mut() {
            if state.current_epoch == epoch {
                let _ = state.log.record(epoch, state.tokens_used, state.tokens_dropped);
            }
        }
    }

    pub fn get_log(&self, source_id: u32) -> Option<&BucketLog> {
        self.sources.get(&source_id).map(|s| &s.log)
    }

    /// Current dropped count for a source in the active epoch.
    pub fn dropped_count(&self, source_id: u32) -> u32 {
        self.sources.get(&source_id).map(|s| s.tokens_dropped).unwrap_or(0)
    }

    /// Sources that have any dropped messages in the current epoch.
    pub fn sources_over_limit(&self) -> Vec<u32> {
        self.sources.iter()
            .filter(|(_, s)| s.tokens_dropped > 0)
            .map(|(&id, _)| id)
            .collect()
    }

    pub fn current_usage(&self, source_id: u32) -> Option<u32> {
        self.sources.get(&source_id).map(|s| s.tokens_used)
    }
}

impl Default for EpochRateLimiter {
    fn default() -> Self { Self::with_default_capacity() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── RateLimitDecision ─────────────────────────────────────────────────────

    #[test]
    fn decision_bytes() {
        assert_eq!(RateLimitDecision::Allowed.decision_byte(),     0);
        assert_eq!(RateLimitDecision::RateLimited.decision_byte(), 1);
    }

    #[test]
    fn is_allowed() {
        assert!(RateLimitDecision::Allowed.is_allowed());
        assert!(!RateLimitDecision::RateLimited.is_allowed());
    }

    // ── BucketRecord ──────────────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let r = build_bucket_record(1, 1, 100, 50, &BUCKET_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_bucket_record(1, 1, 100, 50, &BUCKET_GENESIS_HASH);
        let r2 = build_bucket_record(1, 1, 100, 50, &BUCKET_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    // ── BucketLog ─────────────────────────────────────────────────────────────

    #[test]
    fn new_log_empty() {
        let l = BucketLog::new(1);
        assert!(l.is_empty());
        assert_eq!(l.total_allowed(), 0);
        assert_eq!(l.total_dropped(), 0);
        assert_eq!(l.drop_rate_pct(), 0);
    }

    #[test]
    fn log_accumulates() {
        let mut l = BucketLog::new(1);
        l.record(1, 200, 50).unwrap();
        l.record(2, 180, 0).unwrap();
        assert_eq!(l.total_allowed(), 380);
        assert_eq!(l.total_dropped(), 50);
    }

    #[test]
    fn drop_rate_pct_computed() {
        let mut l = BucketLog::new(1);
        l.record(1, 150, 50).unwrap(); // 50/200 = 25%
        assert_eq!(l.drop_rate_pct(), 25);
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut l = BucketLog::new(1);
        l.record(5, 100, 0).unwrap();
        assert!(matches!(l.record(4, 100, 0), Err(BucketError::StaleEpoch)));
    }

    #[test]
    fn chain_links() {
        let mut l = BucketLog::new(1);
        l.record(1, 100, 0).unwrap();
        l.record(2, 100, 0).unwrap();
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    #[test]
    fn verify_chain_valid() {
        let mut l = BucketLog::new(1);
        for e in 1..=5u64 {
            l.record(e, e as u32 * 30, 0).unwrap();
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    // ── EpochRateLimiter ──────────────────────────────────────────────────────

    #[test]
    fn allowed_within_capacity() {
        let mut rl = EpochRateLimiter::new(5);
        for _ in 0..5 {
            assert_eq!(rl.consume(1, 1), RateLimitDecision::Allowed);
        }
        assert_eq!(rl.current_usage(1), Some(5));
    }

    #[test]
    fn rate_limited_over_capacity() {
        let mut rl = EpochRateLimiter::new(3);
        for _ in 0..3 { rl.consume(1, 1); }
        assert_eq!(rl.consume(1, 1), RateLimitDecision::RateLimited);
        assert_eq!(rl.dropped_count(1), 1);
    }

    #[test]
    fn epoch_reset_refills_bucket() {
        let mut rl = EpochRateLimiter::new(3);
        for _ in 0..3 { rl.consume(1, 1); }
        assert_eq!(rl.consume(1, 1), RateLimitDecision::RateLimited);
        // New epoch
        assert_eq!(rl.consume(1, 2), RateLimitDecision::Allowed);
        assert_eq!(rl.current_usage(1), Some(1));
    }

    #[test]
    fn sources_over_limit_tracked() {
        let mut rl = EpochRateLimiter::new(2);
        rl.consume(1, 1); rl.consume(1, 1); rl.consume(1, 1); // 3rd → limited
        rl.consume(2, 1); rl.consume(2, 1); // within limit
        let over = rl.sources_over_limit();
        assert_eq!(over, vec![1]);
    }

    #[test]
    fn seal_epoch_persists_log() {
        let mut rl = EpochRateLimiter::new(200);
        for _ in 0..80 { rl.consume(1, 1); }
        rl.seal_epoch(1);
        let log = rl.get_log(1).unwrap();
        assert_eq!(log.len(), 1);
        assert_eq!(log.records()[0].tokens_used, 80);
        assert_eq!(log.records()[0].tokens_dropped, 0);
    }

    #[test]
    fn multiple_sources_independent() {
        let mut rl = EpochRateLimiter::new(5);
        rl.consume(1, 1); rl.consume(1, 1);
        rl.consume(2, 1); rl.consume(2, 1); rl.consume(2, 1);
        assert_eq!(rl.current_usage(1), Some(2));
        assert_eq!(rl.current_usage(2), Some(3));
    }

    #[test]
    fn unknown_source_usage_none() {
        let rl = EpochRateLimiter::new(10);
        assert_eq!(rl.current_usage(99), None);
        assert_eq!(rl.dropped_count(99), 0);
    }
}
