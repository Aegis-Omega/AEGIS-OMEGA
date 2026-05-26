//! Gate 339 — Compaction Momentum Tracker (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Rolling directional trend signal for the JointCondition (Gate 338) across
//! a sliding observation window. Mirrors Gate 245 (momentum_tracker) for the
//! compaction health subsystem.
//!
//! MOMENTUM_WINDOW = 4 observations
//!
//! CompactionMomentumDir:
//!   Improving — latest_score < earliest_score (lower ordinal = better)
//!   Stable    — latest_score == earliest_score
//!   Declining — latest_score > earliest_score
//!
//! Score = JointCondition::as_u8() (0=Optimal … 3=Critical)
//! momentum_int = latest_score as i16 - earliest_score as i16 (signed delta)
//!
//! CompactionMomentumRecord:
//!   epoch:           u64
//!   joint_condition: JointCondition
//!   score:           u8           — JointCondition as u8
//!   direction:       CompactionMomentumDir  — trend across current window
//!   momentum_int:    i16          — signed score delta (latest − earliest in window)
//!   window_size:     usize        — number of observations currently in window
//!   record_hash:     [u8;32]
//!   prev_hash:       [u8;32]
//!
//! record_hash = SHA-256(prev[32] ‖ epoch_be8 ‖ score_byte ‖ dir_byte
//!                        ‖ momentum_int_be2 ‖ window_size_be2)
//!
//! CompactionMomentumLog: append(epoch, joint_cond) → record.
//!   direction_count(dir): count records with given direction.
//!   improving_epochs(): count Improving records.
//!   declining_epochs(): count Declining records.
//!   verify_chain().

use sha2::{Sha256, Digest};
use crate::compaction_health_aggregator::JointCondition;

pub const MOMENTUM_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const MOMENTUM_WINDOW: usize = 4;

// ─── CompactionMomentumDir ────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum CompactionMomentumDir {
    Improving = 0,
    Stable    = 1,
    Declining = 2,
}

impl CompactionMomentumDir {
    pub fn as_u8(self) -> u8 { self as u8 }

    fn from_delta(delta: i16) -> Self {
        match delta.cmp(&0) {
            std::cmp::Ordering::Less    => Self::Improving,
            std::cmp::Ordering::Equal   => Self::Stable,
            std::cmp::Ordering::Greater => Self::Declining,
        }
    }
}

// ─── CompactionMomentumRecord ─────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct CompactionMomentumRecord {
    pub epoch:           u64,
    pub joint_condition: JointCondition,
    pub score:           u8,
    pub direction:       CompactionMomentumDir,
    pub momentum_int:    i16,
    pub window_size:     usize,
    pub record_hash:     [u8; 32],
    pub prev_hash:       [u8; 32],
}

fn compute_record_hash(
    prev:         &[u8; 32],
    epoch:        u64,
    score:        u8,
    dir:          CompactionMomentumDir,
    momentum_int: i16,
    window_size:  usize,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update([score, dir.as_u8()]);
    h.update(momentum_int.to_be_bytes());
    h.update((window_size as u16).to_be_bytes());
    h.finalize().into()
}

// ─── CompactionMomentumLog ────────────────────────────────────────────────────

pub struct CompactionMomentumLog {
    records: Vec<CompactionMomentumRecord>,
    /// Circular window of recent scores (MOMENTUM_WINDOW capacity).
    window:  Vec<u8>,
}

impl CompactionMomentumLog {
    pub fn new() -> Self {
        Self {
            records: Vec::new(),
            window:  Vec::with_capacity(MOMENTUM_WINDOW),
        }
    }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[CompactionMomentumRecord] { &self.records }
    pub fn latest(&self)   -> Option<&CompactionMomentumRecord> { self.records.last() }

    pub fn append(&mut self, epoch: u64, joint_condition: JointCondition) -> &CompactionMomentumRecord {
        let score = joint_condition.as_u8();

        // Maintain rolling window of MOMENTUM_WINDOW size
        if self.window.len() == MOMENTUM_WINDOW {
            self.window.remove(0);
        }
        self.window.push(score);

        let window_size = self.window.len();
        let earliest = *self.window.first().unwrap();
        let latest   = *self.window.last().unwrap();
        let momentum_int = latest as i16 - earliest as i16;
        let direction = CompactionMomentumDir::from_delta(momentum_int);

        let prev = self.records.last()
            .map(|r| r.record_hash)
            .unwrap_or(MOMENTUM_GENESIS_HASH);

        let record_hash = compute_record_hash(
            &prev, epoch, score, direction, momentum_int, window_size,
        );

        self.records.push(CompactionMomentumRecord {
            epoch,
            joint_condition,
            score,
            direction,
            momentum_int,
            window_size,
            record_hash,
            prev_hash: prev,
        });
        self.records.last().unwrap()
    }

    pub fn direction_count(&self, dir: CompactionMomentumDir) -> usize {
        self.records.iter().filter(|r| r.direction == dir).count()
    }

    pub fn improving_epochs(&self) -> usize {
        self.direction_count(CompactionMomentumDir::Improving)
    }

    pub fn declining_epochs(&self) -> usize {
        self.direction_count(CompactionMomentumDir::Declining)
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = MOMENTUM_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_record_hash(
                &prev, r.epoch, r.score, r.direction, r.momentum_int, r.window_size,
            );
            if r.record_hash != expected {
                return (false, Some(i));
            }
            prev = r.record_hash;
        }
        (true, None)
    }
}

impl Default for CompactionMomentumLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::compaction_health_aggregator::JointCondition;

    // ── CompactionMomentumDir ─────────────────────────────────────────────────

    #[test]
    fn dir_improving_negative_delta() {
        assert_eq!(CompactionMomentumDir::from_delta(-1), CompactionMomentumDir::Improving);
    }

    #[test]
    fn dir_stable_zero_delta() {
        assert_eq!(CompactionMomentumDir::from_delta(0), CompactionMomentumDir::Stable);
    }

    #[test]
    fn dir_declining_positive_delta() {
        assert_eq!(CompactionMomentumDir::from_delta(1), CompactionMomentumDir::Declining);
    }

    // ── Window and direction logic ────────────────────────────────────────────

    #[test]
    fn single_entry_window_is_stable() {
        let mut l = CompactionMomentumLog::new();
        let r = l.append(1, JointCondition::Optimal).clone();
        assert_eq!(r.window_size, 1);
        assert_eq!(r.direction, CompactionMomentumDir::Stable);
        assert_eq!(r.momentum_int, 0);
    }

    #[test]
    fn improving_when_condition_improves() {
        let mut l = CompactionMomentumLog::new();
        l.append(1, JointCondition::Critical);  // score=3
        l.append(2, JointCondition::Nominal);   // score=1
        let r = l.latest().unwrap().clone();
        assert_eq!(r.direction, CompactionMomentumDir::Improving);
        assert_eq!(r.momentum_int, -2); // 1 - 3 = -2
    }

    #[test]
    fn declining_when_condition_worsens() {
        let mut l = CompactionMomentumLog::new();
        l.append(1, JointCondition::Optimal);   // score=0
        l.append(2, JointCondition::Critical);  // score=3
        let r = l.latest().unwrap().clone();
        assert_eq!(r.direction, CompactionMomentumDir::Declining);
        assert_eq!(r.momentum_int, 3);
    }

    #[test]
    fn stable_across_two_identical() {
        let mut l = CompactionMomentumLog::new();
        l.append(1, JointCondition::Nominal);
        l.append(2, JointCondition::Nominal);
        let r = l.latest().unwrap().clone();
        assert_eq!(r.direction, CompactionMomentumDir::Stable);
        assert_eq!(r.momentum_int, 0);
    }

    #[test]
    fn window_caps_at_momentum_window() {
        let mut l = CompactionMomentumLog::new();
        for i in 1u64..=(MOMENTUM_WINDOW as u64 + 2) {
            l.append(i, JointCondition::Optimal);
        }
        let r = l.latest().unwrap();
        assert_eq!(r.window_size, MOMENTUM_WINDOW);
    }

    #[test]
    fn window_evicts_oldest_entry() {
        let mut l = CompactionMomentumLog::new();
        // Fill window: [Optimal(0), Critical(3), Critical(3), Critical(3)]
        l.append(1, JointCondition::Optimal);
        for i in 2u64..=(MOMENTUM_WINDOW as u64) {
            l.append(i, JointCondition::Critical);
        }
        // Now add one more: evicts Optimal, window = [Critical, Critical, Critical, Nominal]
        l.append(MOMENTUM_WINDOW as u64 + 1, JointCondition::Nominal); // score=1
        let r = l.latest().unwrap();
        // earliest is now Critical(3), latest is Nominal(1) → improving
        assert_eq!(r.direction, CompactionMomentumDir::Improving);
    }

    // ── Log aggregation ───────────────────────────────────────────────────────

    #[test]
    fn direction_count_correct() {
        let mut l = CompactionMomentumLog::new();
        l.append(1, JointCondition::Critical);  // stable (window=[3], delta=0)
        l.append(2, JointCondition::Optimal);   // improving (window=[3,0], delta=-3)
        l.append(3, JointCondition::Optimal);   // improving (window=[3,0,0], earliest=3, latest=0, delta=-3)
        assert_eq!(l.improving_epochs(), 2);
        assert_eq!(l.declining_epochs(), 0);
        assert_eq!(l.direction_count(CompactionMomentumDir::Stable), 1);
    }

    // ── Chain integrity ───────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let l = CompactionMomentumLog::new();
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_five_entries_ok() {
        let mut l = CompactionMomentumLog::new();
        let conds = [
            JointCondition::Optimal,
            JointCondition::Nominal,
            JointCondition::Degraded,
            JointCondition::Nominal,
            JointCondition::Optimal,
        ];
        for (i, c) in conds.iter().enumerate() {
            l.append(i as u64, *c);
        }
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut l = CompactionMomentumLog::new();
        l.append(1, JointCondition::Optimal);
        l.append(2, JointCondition::Nominal);
        l.records[0].record_hash[0] ^= 0xFF;
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn record_hash_deterministic() {
        let mut l1 = CompactionMomentumLog::new();
        let mut l2 = CompactionMomentumLog::new();
        l1.append(7, JointCondition::Degraded);
        l2.append(7, JointCondition::Degraded);
        assert_eq!(l1.records[0].record_hash, l2.records[0].record_hash);
    }

    #[test]
    fn prev_hash_links_correctly() {
        let mut l = CompactionMomentumLog::new();
        l.append(1, JointCondition::Optimal);
        let h1 = l.records[0].record_hash;
        l.append(2, JointCondition::Nominal);
        assert_eq!(l.records[1].prev_hash, h1);
    }
}
