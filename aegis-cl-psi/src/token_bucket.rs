//! Gate 303 — Gossip Token Bucket: rate-limiting via integer token bucket algorithm (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Classic token bucket: tokens refill at a fixed rate per tick; each message consumes
//! one token. If no tokens are available, the message is rate-limited (dropped/deferred).
//! All arithmetic is integer — no f64.
//!
//! Constants:
//!   DEFAULT_CAPACITY:    u32 = 100  (max tokens)
//!   DEFAULT_REFILL_RATE: u32 = 10   (tokens added per tick)
//!
//! BucketDecision: Allow | RateLimited
//!
//! BucketRecord:
//!   peer_id, epoch, tokens_before, tokens_after, decision,
//!   record_hash = SHA-256(prev ‖ peer_be4 ‖ epoch_be8 ‖ tbefore_be4 ‖ tafter_be4 ‖ dec_byte)
//!   prev_hash
//!
//! BucketLog: hash-chained BucketRecords per peer.
//!   push(), allow_count(), rate_limited_count(), verify_chain().
//!
//! TokenBucket (single peer):
//!   new(capacity, refill_rate), consume() → BucketDecision, tick_refill(), tokens(), is_full()
//!
//! TokenBucketRegistry:
//!   get_or_create(peer_id) → &mut TokenBucket (uses DEFAULT_CAPACITY / DEFAULT_REFILL_RATE)
//!   consume(peer_id, epoch) → BucketDecision  (records to per-peer BucketLog)
//!   tick_refill_all()                          (refill all peer buckets)
//!   tokens(peer_id) → u32
//!   get_log(peer_id) → Option<&BucketLog>

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const DEFAULT_CAPACITY:    u32 = 100;
pub const DEFAULT_REFILL_RATE: u32 = 10;

// ─── Bucket decision ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BucketDecision {
    Allow       = 0,
    RateLimited = 1,
}

impl BucketDecision {
    pub fn decision_byte(self) -> u8 { self as u8 }
    pub fn is_allowed(self) -> bool { matches!(self, Self::Allow) }
}

// ─── Bucket record ────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct BucketRecord {
    pub peer_id:       u32,
    pub epoch:         u64,
    pub tokens_before: u32,
    pub tokens_after:  u32,
    pub decision:      BucketDecision,
    pub record_hash:   [u8; 32],
    pub prev_hash:     [u8; 32],
}

pub const BUCKET_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_bucket_hash(
    peer_id:       u32,
    epoch:         u64,
    tokens_before: u32,
    tokens_after:  u32,
    decision:      BucketDecision,
    prev:          &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(peer_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update(tokens_before.to_be_bytes());
    h.update(tokens_after.to_be_bytes());
    h.update([decision.decision_byte()]);
    h.finalize().into()
}

pub fn build_bucket_record(
    peer_id:       u32,
    epoch:         u64,
    tokens_before: u32,
    tokens_after:  u32,
    decision:      BucketDecision,
    prev_hash:     &[u8; 32],
) -> BucketRecord {
    let record_hash = compute_bucket_hash(
        peer_id, epoch, tokens_before, tokens_after, decision, prev_hash,
    );
    BucketRecord { peer_id, epoch, tokens_before, tokens_after, decision, record_hash, prev_hash: *prev_hash }
}

// ─── Bucket log ───────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct BucketLog {
    peer_id: u32,
    records: Vec<BucketRecord>,
}

impl BucketLog {
    pub fn new(peer_id: u32) -> Self { Self { peer_id, records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[BucketRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(BUCKET_GENESIS_HASH)
    }

    pub fn push(
        &mut self,
        epoch:         u64,
        tokens_before: u32,
        tokens_after:  u32,
        decision:      BucketDecision,
    ) -> &BucketRecord {
        let prev = self.last_hash();
        let r = build_bucket_record(self.peer_id, epoch, tokens_before, tokens_after, decision, &prev);
        self.records.push(r);
        self.records.last().unwrap()
    }

    pub fn allow_count(&self) -> usize {
        self.records.iter().filter(|r| r.decision == BucketDecision::Allow).count()
    }

    pub fn rate_limited_count(&self) -> usize {
        self.records.iter().filter(|r| r.decision == BucketDecision::RateLimited).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = BUCKET_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_bucket_hash(
                r.peer_id, r.epoch, r.tokens_before, r.tokens_after, r.decision, &r.prev_hash,
            );
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

// ─── Token bucket (single peer) ───────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct TokenBucket {
    tokens:      u32,
    capacity:    u32,
    refill_rate: u32,
}

impl TokenBucket {
    pub fn new(capacity: u32, refill_rate: u32) -> Self {
        Self { tokens: capacity, capacity, refill_rate }
    }

    pub fn tokens(&self) -> u32 { self.tokens }
    pub fn is_full(&self) -> bool { self.tokens == self.capacity }

    /// Consume one token. Returns Allow if tokens > 0, RateLimited otherwise.
    pub fn consume(&mut self) -> BucketDecision {
        if self.tokens > 0 {
            self.tokens -= 1;
            BucketDecision::Allow
        } else {
            BucketDecision::RateLimited
        }
    }

    /// Refill tokens by refill_rate, clamped to capacity.
    pub fn tick_refill(&mut self) {
        self.tokens = self.tokens.saturating_add(self.refill_rate).min(self.capacity);
    }
}

// ─── Token bucket registry ────────────────────────────────────────────────────

#[derive(Debug, Clone)]
struct PeerBucketState {
    bucket: TokenBucket,
    log:    BucketLog,
}

#[derive(Debug, Clone)]
pub struct TokenBucketRegistry {
    peers: BTreeMap<u32, PeerBucketState>,
}

impl TokenBucketRegistry {
    pub fn new() -> Self { Self { peers: BTreeMap::new() } }

    fn ensure_peer(&mut self, peer_id: u32) {
        self.peers.entry(peer_id).or_insert_with(|| PeerBucketState {
            bucket: TokenBucket::new(DEFAULT_CAPACITY, DEFAULT_REFILL_RATE),
            log:    BucketLog::new(peer_id),
        });
    }

    /// Consume a token for peer_id, record the decision.
    pub fn consume(&mut self, peer_id: u32, epoch: u64) -> BucketDecision {
        self.ensure_peer(peer_id);
        let state = self.peers.get_mut(&peer_id).unwrap();
        let before = state.bucket.tokens();
        let decision = state.bucket.consume();
        let after = state.bucket.tokens();
        state.log.push(epoch, before, after, decision);
        decision
    }

    /// Refill all tracked peer buckets by their refill_rate.
    pub fn tick_refill_all(&mut self) {
        for state in self.peers.values_mut() {
            state.bucket.tick_refill();
        }
    }

    pub fn tokens(&self, peer_id: u32) -> u32 {
        self.peers.get(&peer_id).map(|s| s.bucket.tokens()).unwrap_or(DEFAULT_CAPACITY)
    }

    pub fn get_log(&self, peer_id: u32) -> Option<&BucketLog> {
        self.peers.get(&peer_id).map(|s| &s.log)
    }

    pub fn peer_count(&self) -> usize { self.peers.len() }
}

impl Default for TokenBucketRegistry {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── BucketDecision ────────────────────────────────────────────────────────

    #[test]
    fn decision_bytes() {
        assert_eq!(BucketDecision::Allow.decision_byte(),       0);
        assert_eq!(BucketDecision::RateLimited.decision_byte(), 1);
        assert!(BucketDecision::Allow.is_allowed());
        assert!(!BucketDecision::RateLimited.is_allowed());
    }

    // ── build_bucket_record ───────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let r = build_bucket_record(1, 1, 10, 9, BucketDecision::Allow, &BUCKET_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_bucket_record(1, 1, 10, 9, BucketDecision::Allow, &BUCKET_GENESIS_HASH);
        let r2 = build_bucket_record(1, 1, 10, 9, BucketDecision::Allow, &BUCKET_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    // ── BucketLog ─────────────────────────────────────────────────────────────

    #[test]
    fn log_counts_decisions() {
        let mut l = BucketLog::new(1);
        l.push(1, 5, 4, BucketDecision::Allow);
        l.push(2, 4, 3, BucketDecision::Allow);
        l.push(3, 0, 0, BucketDecision::RateLimited);
        assert_eq!(l.allow_count(), 2);
        assert_eq!(l.rate_limited_count(), 1);
    }

    #[test]
    fn log_chain_links() {
        let mut l = BucketLog::new(1);
        l.push(1, 10, 9, BucketDecision::Allow);
        l.push(2, 9, 8, BucketDecision::Allow);
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    #[test]
    fn log_verify_chain_valid() {
        let mut l = BucketLog::new(1);
        for e in 1..=5u64 {
            l.push(e, 10, 9, BucketDecision::Allow);
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    // ── TokenBucket ───────────────────────────────────────────────────────────

    #[test]
    fn new_bucket_full() {
        let b = TokenBucket::new(100, 10);
        assert_eq!(b.tokens(), 100);
        assert!(b.is_full());
    }

    #[test]
    fn consume_decrements_tokens() {
        let mut b = TokenBucket::new(5, 1);
        assert_eq!(b.consume(), BucketDecision::Allow);
        assert_eq!(b.tokens(), 4);
    }

    #[test]
    fn empty_bucket_rate_limits() {
        let mut b = TokenBucket::new(1, 1);
        b.consume(); // drains to 0
        assert_eq!(b.consume(), BucketDecision::RateLimited);
        assert_eq!(b.tokens(), 0);
    }

    #[test]
    fn refill_respects_capacity() {
        let mut b = TokenBucket::new(10, 5);
        b.consume(); b.consume(); // tokens = 8
        b.tick_refill();          // tokens = min(8+5, 10) = 10
        assert_eq!(b.tokens(), 10);
        assert!(b.is_full());
    }

    // ── TokenBucketRegistry ───────────────────────────────────────────────────

    #[test]
    fn registry_unknown_peer_full() {
        let r = TokenBucketRegistry::new();
        assert_eq!(r.tokens(99), DEFAULT_CAPACITY);
    }

    #[test]
    fn registry_consume_records_decision() {
        let mut r = TokenBucketRegistry::new();
        let dec = r.consume(1, 1);
        assert_eq!(dec, BucketDecision::Allow);
        assert_eq!(r.tokens(1), DEFAULT_CAPACITY - 1);
        let log = r.get_log(1).unwrap();
        assert_eq!(log.allow_count(), 1);
    }

    #[test]
    fn registry_tick_refill_all() {
        let mut r = TokenBucketRegistry::new();
        for e in 0..DEFAULT_CAPACITY { r.consume(1, e as u64); } // drain completely
        assert_eq!(r.tokens(1), 0);
        r.tick_refill_all();
        assert_eq!(r.tokens(1), DEFAULT_REFILL_RATE);
    }
}
