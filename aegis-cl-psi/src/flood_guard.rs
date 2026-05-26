//! Gate 285 — Gossip Flood Guard: per-source message rate limiting with penalty escalation (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Protects the gossip layer from message floods by tracking per-source message counts
//! per epoch and applying escalating penalty levels using integer arithmetic.
//!
//! FloodLevel (penalty escalation):
//!   Clean     — messages ≤ FLOOD_WARN_THRESHOLD (50)
//!   Warning   — messages > FLOOD_WARN_THRESHOLD (50) and ≤ FLOOD_LIMIT (100)
//!   Blocking  — messages > FLOOD_LIMIT (100) and ≤ FLOOD_BAN_THRESHOLD (500)
//!   Banned    — messages > FLOOD_BAN_THRESHOLD (500)
//!
//! Penalty multiplier (applied to outbound drops for a source in Blocking/Banned):
//!   Clean/Warning → 1 (no drop)
//!   Blocking      → 2 (drop every other message)
//!   Banned        → 0 (drop all)
//!
//! FloodRecord:
//!   source_id      — u32
//!   epoch          — u64
//!   message_count  — u32
//!   dropped_count  — u32
//!   level          — FloodLevel
//!   record_hash    — SHA-256(prev ‖ src_be4 ‖ epoch_be8 ‖ count_be4 ‖ dropped_be4 ‖ level_byte)
//!   prev_hash      — [u8; 32]
//!
//! FloodLog: hash-chained FloodRecords per source.
//!   record(), banned_epoch_count(), total_dropped(), verify_chain().
//!
//! FloodGuard: BTreeMap<source_id, (FloodLog, current_epoch_count, current_dropped)>.
//!   observe_message(source, epoch) → FloodLevel (and increments counters).
//!   seal_epoch(epoch).
//!   sources_at_level(level).

use sha2::{Sha256, Digest};
use std::collections::BTreeMap;

pub const FLOOD_WARN_THRESHOLD:  u32 = 50;
pub const FLOOD_LIMIT:           u32 = 100;
pub const FLOOD_BAN_THRESHOLD:   u32 = 500;

// ─── Flood level ──────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum FloodLevel {
    Clean    = 0,
    Warning  = 1,
    Blocking = 2,
    Banned   = 3,
}

impl FloodLevel {
    pub fn level_byte(self) -> u8 { self as u8 }

    /// Drop fraction: Banned=all, Blocking=every-other, Clean/Warning=none.
    /// Returns (drop_numerator, drop_denominator): drop if (count % denom) < num.
    pub fn should_drop(self, message_count: u32) -> bool {
        match self {
            Self::Banned   => true,
            Self::Blocking => message_count % 2 == 0,
            _              => false,
        }
    }
}

pub fn classify_flood(message_count: u32) -> FloodLevel {
    if message_count > FLOOD_BAN_THRESHOLD   { FloodLevel::Banned }
    else if message_count > FLOOD_LIMIT      { FloodLevel::Blocking }
    else if message_count > FLOOD_WARN_THRESHOLD { FloodLevel::Warning }
    else                                     { FloodLevel::Clean }
}

// ─── Flood record ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct FloodRecord {
    pub source_id:     u32,
    pub epoch:         u64,
    pub message_count: u32,
    pub dropped_count: u32,
    pub level:         FloodLevel,
    pub record_hash:   [u8; 32],
    pub prev_hash:     [u8; 32],
}

pub const FLOOD_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_flood_hash(
    source_id:     u32,
    epoch:         u64,
    message_count: u32,
    dropped_count: u32,
    level:         FloodLevel,
    prev:          &[u8; 32],
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(source_id.to_be_bytes());
    h.update(epoch.to_be_bytes());
    h.update(message_count.to_be_bytes());
    h.update(dropped_count.to_be_bytes());
    h.update([level.level_byte()]);
    h.finalize().into()
}

pub fn build_flood_record(
    source_id:     u32,
    epoch:         u64,
    message_count: u32,
    dropped_count: u32,
    level:         FloodLevel,
    prev_hash:     &[u8; 32],
) -> FloodRecord {
    let record_hash = compute_flood_hash(
        source_id, epoch, message_count, dropped_count, level, prev_hash,
    );
    FloodRecord { source_id, epoch, message_count, dropped_count, level, record_hash, prev_hash: *prev_hash }
}

// ─── Flood log ────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct FloodLog {
    source_id: u32,
    records:   Vec<FloodRecord>,
}

#[derive(Debug)]
pub enum FloodError {
    StaleEpoch,
}

impl FloodLog {
    pub fn new(source_id: u32) -> Self { Self { source_id, records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[FloodRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.record_hash).unwrap_or(FLOOD_GENESIS_HASH)
    }

    pub fn record(
        &mut self,
        epoch:         u64,
        message_count: u32,
        dropped_count: u32,
    ) -> Result<&FloodRecord, FloodError> {
        if let Some(last) = self.records.last() {
            if epoch <= last.epoch { return Err(FloodError::StaleEpoch); }
        }
        let prev = self.last_hash();
        let level = classify_flood(message_count);
        let r = build_flood_record(self.source_id, epoch, message_count, dropped_count, level, &prev);
        self.records.push(r);
        Ok(self.records.last().unwrap())
    }

    pub fn banned_epoch_count(&self) -> usize {
        self.records.iter().filter(|r| r.level == FloodLevel::Banned).count()
    }

    pub fn total_dropped(&self) -> u64 {
        self.records.iter().map(|r| r.dropped_count as u64).sum()
    }

    pub fn worst_level(&self) -> FloodLevel {
        self.records.iter().map(|r| r.level).max().unwrap_or(FloodLevel::Clean)
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut expected_prev = FLOOD_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != expected_prev { return (false, Some(i)); }
            let recomputed = compute_flood_hash(
                r.source_id, r.epoch, r.message_count, r.dropped_count, r.level, &r.prev_hash,
            );
            if recomputed != r.record_hash { return (false, Some(i)); }
            expected_prev = r.record_hash;
        }
        (true, None)
    }
}

// ─── Flood guard ──────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
struct SourceState {
    log:          FloodLog,
    current_epoch: u64,
    msg_count:    u32,
    drop_count:   u32,
}

#[derive(Debug, Clone)]
pub struct FloodGuard {
    sources: BTreeMap<u32, SourceState>,
}

impl FloodGuard {
    pub fn new() -> Self { Self { sources: BTreeMap::new() } }

    pub fn source_count(&self) -> usize { self.sources.len() }

    /// Record an observed message from source_id at epoch.
    /// Returns the current FloodLevel (after this message).
    pub fn observe_message(&mut self, source_id: u32, epoch: u64) -> FloodLevel {
        let state = self.sources.entry(source_id).or_insert_with(|| SourceState {
            log:           FloodLog::new(source_id),
            current_epoch: epoch,
            msg_count:     0,
            drop_count:    0,
        });

        if epoch > state.current_epoch {
            state.current_epoch = epoch;
            state.msg_count     = 0;
            state.drop_count    = 0;
        }

        state.msg_count = state.msg_count.saturating_add(1);
        let level = classify_flood(state.msg_count);
        if level.should_drop(state.msg_count) {
            state.drop_count = state.drop_count.saturating_add(1);
        }
        level
    }

    /// Seal epoch: persist epoch counts to flood log.
    pub fn seal_epoch(&mut self, epoch: u64) {
        for state in self.sources.values_mut() {
            if state.current_epoch == epoch {
                let _ = state.log.record(epoch, state.msg_count, state.drop_count);
            }
        }
    }

    pub fn get_log(&self, source_id: u32) -> Option<&FloodLog> {
        self.sources.get(&source_id).map(|s| &s.log)
    }

    /// All sources currently at or above a given level.
    pub fn sources_at_level(&self, min_level: FloodLevel) -> Vec<u32> {
        self.sources.iter()
            .filter(|(_, s)| classify_flood(s.msg_count) >= min_level)
            .map(|(&id, _)| id)
            .collect()
    }

    pub fn current_msg_count(&self, source_id: u32) -> u32 {
        self.sources.get(&source_id).map(|s| s.msg_count).unwrap_or(0)
    }
}

impl Default for FloodGuard {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── classify_flood ────────────────────────────────────────────────────────

    #[test]
    fn level_thresholds() {
        assert_eq!(classify_flood(0),   FloodLevel::Clean);
        assert_eq!(classify_flood(50),  FloodLevel::Clean);
        assert_eq!(classify_flood(51),  FloodLevel::Warning);
        assert_eq!(classify_flood(100), FloodLevel::Warning);
        assert_eq!(classify_flood(101), FloodLevel::Blocking);
        assert_eq!(classify_flood(500), FloodLevel::Blocking);
        assert_eq!(classify_flood(501), FloodLevel::Banned);
    }

    #[test]
    fn flood_level_ordering() {
        assert!(FloodLevel::Banned   > FloodLevel::Blocking);
        assert!(FloodLevel::Blocking > FloodLevel::Warning);
        assert!(FloodLevel::Warning  > FloodLevel::Clean);
    }

    #[test]
    fn should_drop_banned_always() {
        assert!(FloodLevel::Banned.should_drop(1));
        assert!(FloodLevel::Banned.should_drop(999));
    }

    #[test]
    fn should_drop_blocking_every_other() {
        assert!(FloodLevel::Blocking.should_drop(102)); // even
        assert!(!FloodLevel::Blocking.should_drop(103)); // odd
    }

    #[test]
    fn should_drop_clean_never() {
        assert!(!FloodLevel::Clean.should_drop(25));
        assert!(!FloodLevel::Warning.should_drop(75));
    }

    // ── build_flood_record ────────────────────────────────────────────────────

    #[test]
    fn record_hash_nonzero() {
        let r = build_flood_record(1, 1, 30, 0, FloodLevel::Clean, &FLOOD_GENESIS_HASH);
        assert_ne!(r.record_hash, [0u8; 32]);
    }

    #[test]
    fn record_hash_deterministic() {
        let r1 = build_flood_record(1, 1, 30, 0, FloodLevel::Clean, &FLOOD_GENESIS_HASH);
        let r2 = build_flood_record(1, 1, 30, 0, FloodLevel::Clean, &FLOOD_GENESIS_HASH);
        assert_eq!(r1.record_hash, r2.record_hash);
    }

    // ── FloodLog ──────────────────────────────────────────────────────────────

    #[test]
    fn new_log_empty() {
        let l = FloodLog::new(1);
        assert!(l.is_empty());
        assert_eq!(l.worst_level(), FloodLevel::Clean);
        assert_eq!(l.total_dropped(), 0);
    }

    #[test]
    fn record_levels() {
        let mut l = FloodLog::new(1);
        l.record(1, 30, 0).unwrap();
        l.record(2, 200, 10).unwrap();
        l.record(3, 600, 200).unwrap();
        assert_eq!(l.worst_level(), FloodLevel::Banned);
        assert_eq!(l.banned_epoch_count(), 1);
        assert_eq!(l.total_dropped(), 210);
    }

    #[test]
    fn stale_epoch_rejected() {
        let mut l = FloodLog::new(1);
        l.record(5, 10, 0).unwrap();
        assert!(matches!(l.record(4, 10, 0), Err(FloodError::StaleEpoch)));
    }

    #[test]
    fn chain_links() {
        let mut l = FloodLog::new(1);
        l.record(1, 10, 0).unwrap();
        l.record(2, 20, 0).unwrap();
        assert_eq!(l.records()[1].prev_hash, l.records()[0].record_hash);
    }

    #[test]
    fn verify_chain_valid() {
        let mut l = FloodLog::new(1);
        for e in 1..=5u64 {
            l.record(e, e as u32 * 20, 0).unwrap();
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    // ── FloodGuard ────────────────────────────────────────────────────────────

    #[test]
    fn clean_below_threshold() {
        let mut g = FloodGuard::new();
        for _ in 0..50 {
            let l = g.observe_message(1, 1);
            assert_eq!(l, FloodLevel::Clean);
        }
    }

    #[test]
    fn warning_after_threshold() {
        let mut g = FloodGuard::new();
        for _ in 0..51 { g.observe_message(1, 1); }
        assert_eq!(g.observe_message(1, 1), FloodLevel::Warning);
    }

    #[test]
    fn banned_after_ban_threshold() {
        let mut g = FloodGuard::new();
        for _ in 0..501 { g.observe_message(1, 1); }
        assert_eq!(g.observe_message(1, 1), FloodLevel::Banned);
    }

    #[test]
    fn epoch_reset_clears_count() {
        let mut g = FloodGuard::new();
        for _ in 0..200 { g.observe_message(1, 1); }
        // New epoch: count reset
        let l = g.observe_message(1, 2);
        assert_eq!(l, FloodLevel::Clean);
        assert_eq!(g.current_msg_count(1), 1);
    }

    #[test]
    fn seal_epoch_records_log() {
        let mut g = FloodGuard::new();
        for _ in 0..60 { g.observe_message(1, 1); }
        g.seal_epoch(1);
        let log = g.get_log(1).unwrap();
        assert_eq!(log.len(), 1);
        assert_eq!(log.records()[0].message_count, 60);
        assert_eq!(log.records()[0].level, FloodLevel::Warning);
    }

    #[test]
    fn sources_at_level() {
        let mut g = FloodGuard::new();
        for _ in 0..30 { g.observe_message(1, 1); }  // Clean
        for _ in 0..80 { g.observe_message(2, 1); }  // Warning
        for _ in 0..150 { g.observe_message(3, 1); } // Blocking
        let blocked = g.sources_at_level(FloodLevel::Blocking);
        assert_eq!(blocked, vec![3]);
        let warned = g.sources_at_level(FloodLevel::Warning);
        assert_eq!(warned.len(), 2); // 2 and 3
    }
}
