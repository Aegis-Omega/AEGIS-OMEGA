//! Gate 338 — Compaction Health Aggregator (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Combines compaction telemetry (Gate 337) with constitutional health
//! (Gate 247 OverallCondition) to produce a per-epoch CompactionHealthVector.
//!
//! CompactionHealthGrade:
//!   Healthy   — chains_valid AND total_pruned within expected bounds
//!   Nominal   — chains_valid, moderate pruning activity
//!   Elevated  — !chains_valid OR high pruning (>PRUNE_ALERT_THRESHOLD per epoch)
//!   Critical  — !chains_valid AND high pruning activity
//!
//! PRUNE_ALERT_THRESHOLD = 1_000 entries per epoch tick
//!
//! CompactionHealthVector:
//!   epoch:                u64
//!   compaction_grade:     CompactionHealthGrade
//!   constitutional_cond:  OverallCondition (from Gate 247)
//!   joint_condition:      JointCondition — worst of the two axes
//!   total_pruned_this_epoch: u64
//!   chains_valid:         bool
//!   vector_hash:          [u8;32]
//!   prev_hash:            [u8;32]
//!
//! JointCondition: Optimal / Nominal / Degraded / Critical
//!   Optimal:  constitutional=Optimal AND grade=Healthy
//!   Nominal:  max(grade≤Nominal, cond≤Good)
//!   Degraded: grade=Elevated OR cond=Alert
//!   Critical: grade=Critical OR cond=Emergency
//!
//! vector_hash = SHA-256(prev[32] ‖ epoch_be8 ‖ grade_byte ‖ cond_byte
//!                        ‖ joint_byte ‖ total_pruned_be8 ‖ chains_valid_byte)
//!
//! CompactionHealthLog: hash-chained vectors. verify_chain(), critical_count(),
//! optimal_count(), joint_condition_count(jc).

use sha2::{Sha256, Digest};
use crate::health_aggregator::OverallCondition;

pub const COMPACTION_HEALTH_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const PRUNE_ALERT_THRESHOLD: u64 = 1_000;

// ─── CompactionHealthGrade ────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
#[repr(u8)]
pub enum CompactionHealthGrade {
    Healthy  = 0,
    Nominal  = 1,
    Elevated = 2,
    Critical = 3,
}

impl CompactionHealthGrade {
    pub fn as_u8(self) -> u8 { self as u8 }

    pub fn classify(chains_valid: bool, total_pruned: u64) -> Self {
        let high = total_pruned >= PRUNE_ALERT_THRESHOLD;
        match (chains_valid, high) {
            (true,  false) => Self::Healthy,
            (true,  true)  => Self::Nominal,
            (false, false) => Self::Elevated,
            (false, true)  => Self::Critical,
        }
    }
}

// ─── JointCondition ───────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
#[repr(u8)]
pub enum JointCondition {
    Optimal  = 0,
    Nominal  = 1,
    Degraded = 2,
    Critical = 3,
}

impl JointCondition {
    pub fn as_u8(self) -> u8 { self as u8 }

    pub fn from_axes(grade: CompactionHealthGrade, cond: OverallCondition) -> Self {
        // Critical: grade=Critical OR cond=Emergency
        if grade == CompactionHealthGrade::Critical || cond == OverallCondition::Emergency {
            return Self::Critical;
        }
        // Degraded: grade=Elevated OR cond=Alert
        if grade == CompactionHealthGrade::Elevated || cond == OverallCondition::Alert {
            return Self::Degraded;
        }
        // Optimal: both best
        if grade == CompactionHealthGrade::Healthy && cond == OverallCondition::Optimal {
            return Self::Optimal;
        }
        // Otherwise Nominal
        Self::Nominal
    }
}

// ─── CompactionHealthVector ───────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct CompactionHealthVector {
    pub epoch:                   u64,
    pub compaction_grade:        CompactionHealthGrade,
    pub constitutional_cond:     OverallCondition,
    pub joint_condition:         JointCondition,
    pub total_pruned_this_epoch: u64,
    pub chains_valid:            bool,
    pub vector_hash:             [u8; 32],
    pub prev_hash:               [u8; 32],
}

fn compute_vector_hash(
    prev:          &[u8; 32],
    epoch:         u64,
    grade:         CompactionHealthGrade,
    cond:          OverallCondition,
    joint:         JointCondition,
    total_pruned:  u64,
    chains_valid:  bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update([grade.as_u8(), cond.as_u8(), joint.as_u8()]);
    h.update(total_pruned.to_be_bytes());
    h.update([chains_valid as u8]);
    h.finalize().into()
}

// ─── CompactionHealthLog ──────────────────────────────────────────────────────

pub struct CompactionHealthLog {
    vectors: Vec<CompactionHealthVector>,
}

impl CompactionHealthLog {
    pub fn new() -> Self { Self { vectors: Vec::new() } }

    pub fn len(&self)      -> usize { self.vectors.len() }
    pub fn is_empty(&self) -> bool  { self.vectors.is_empty() }
    pub fn vectors(&self)  -> &[CompactionHealthVector] { &self.vectors }
    pub fn latest(&self)   -> Option<&CompactionHealthVector> { self.vectors.last() }

    /// Record a new health vector.
    pub fn record(
        &mut self,
        epoch:         u64,
        chains_valid:  bool,
        total_pruned:  u64,
        cond:          OverallCondition,
    ) -> &CompactionHealthVector {
        let grade = CompactionHealthGrade::classify(chains_valid, total_pruned);
        let joint = JointCondition::from_axes(grade, cond);
        let prev  = self.vectors.last()
            .map(|v| v.vector_hash)
            .unwrap_or(COMPACTION_HEALTH_GENESIS_HASH);

        let vector_hash = compute_vector_hash(&prev, epoch, grade, cond, joint, total_pruned, chains_valid);

        self.vectors.push(CompactionHealthVector {
            epoch,
            compaction_grade:        grade,
            constitutional_cond:     cond,
            joint_condition:         joint,
            total_pruned_this_epoch: total_pruned,
            chains_valid,
            vector_hash,
            prev_hash:               prev,
        });
        self.vectors.last().unwrap()
    }

    pub fn critical_count(&self) -> usize {
        self.vectors.iter().filter(|v| v.joint_condition == JointCondition::Critical).count()
    }

    pub fn optimal_count(&self) -> usize {
        self.vectors.iter().filter(|v| v.joint_condition == JointCondition::Optimal).count()
    }

    pub fn joint_condition_count(&self, jc: JointCondition) -> usize {
        self.vectors.iter().filter(|v| v.joint_condition == jc).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = COMPACTION_HEALTH_GENESIS_HASH;
        for (i, v) in self.vectors.iter().enumerate() {
            if v.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_vector_hash(
                &prev, v.epoch, v.compaction_grade, v.constitutional_cond,
                v.joint_condition, v.total_pruned_this_epoch, v.chains_valid,
            );
            if v.vector_hash != expected {
                return (false, Some(i));
            }
            prev = v.vector_hash;
        }
        (true, None)
    }
}

impl Default for CompactionHealthLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::health_aggregator::OverallCondition;

    // ── CompactionHealthGrade::classify ──────────────────────────────────────

    #[test]
    fn grade_healthy_when_valid_low_prune() {
        assert_eq!(
            CompactionHealthGrade::classify(true, 0),
            CompactionHealthGrade::Healthy,
        );
    }

    #[test]
    fn grade_nominal_when_valid_high_prune() {
        assert_eq!(
            CompactionHealthGrade::classify(true, PRUNE_ALERT_THRESHOLD),
            CompactionHealthGrade::Nominal,
        );
    }

    #[test]
    fn grade_elevated_when_invalid_low_prune() {
        assert_eq!(
            CompactionHealthGrade::classify(false, 0),
            CompactionHealthGrade::Elevated,
        );
    }

    #[test]
    fn grade_critical_when_invalid_high_prune() {
        assert_eq!(
            CompactionHealthGrade::classify(false, PRUNE_ALERT_THRESHOLD),
            CompactionHealthGrade::Critical,
        );
    }

    // ── JointCondition::from_axes ─────────────────────────────────────────────

    #[test]
    fn joint_optimal_when_both_best() {
        assert_eq!(
            JointCondition::from_axes(CompactionHealthGrade::Healthy, OverallCondition::Optimal),
            JointCondition::Optimal,
        );
    }

    #[test]
    fn joint_nominal_when_healthy_good() {
        assert_eq!(
            JointCondition::from_axes(CompactionHealthGrade::Healthy, OverallCondition::Good),
            JointCondition::Nominal,
        );
    }

    #[test]
    fn joint_nominal_when_nominal_optimal() {
        assert_eq!(
            JointCondition::from_axes(CompactionHealthGrade::Nominal, OverallCondition::Optimal),
            JointCondition::Nominal,
        );
    }

    #[test]
    fn joint_degraded_when_grade_elevated() {
        assert_eq!(
            JointCondition::from_axes(CompactionHealthGrade::Elevated, OverallCondition::Optimal),
            JointCondition::Degraded,
        );
    }

    #[test]
    fn joint_degraded_when_cond_alert() {
        assert_eq!(
            JointCondition::from_axes(CompactionHealthGrade::Healthy, OverallCondition::Alert),
            JointCondition::Degraded,
        );
    }

    #[test]
    fn joint_critical_when_grade_critical() {
        assert_eq!(
            JointCondition::from_axes(CompactionHealthGrade::Critical, OverallCondition::Good),
            JointCondition::Critical,
        );
    }

    #[test]
    fn joint_critical_when_cond_emergency() {
        assert_eq!(
            JointCondition::from_axes(CompactionHealthGrade::Healthy, OverallCondition::Emergency),
            JointCondition::Critical,
        );
    }

    // ── CompactionHealthLog ───────────────────────────────────────────────────

    #[test]
    fn log_starts_empty() {
        let l = CompactionHealthLog::new();
        assert!(l.is_empty());
        assert_eq!(l.critical_count(), 0);
        assert_eq!(l.optimal_count(), 0);
    }

    #[test]
    fn record_sets_grade_and_joint() {
        let mut l = CompactionHealthLog::new();
        let v = l.record(1, true, 0, OverallCondition::Optimal).clone();
        assert_eq!(v.compaction_grade, CompactionHealthGrade::Healthy);
        assert_eq!(v.joint_condition, JointCondition::Optimal);
        assert_eq!(l.optimal_count(), 1);
    }

    #[test]
    fn critical_count_tracks_critical_entries() {
        let mut l = CompactionHealthLog::new();
        l.record(1, true, 0, OverallCondition::Optimal);
        l.record(2, false, PRUNE_ALERT_THRESHOLD, OverallCondition::Good); // Critical grade
        l.record(3, true, 0, OverallCondition::Emergency);                 // Critical via cond
        assert_eq!(l.critical_count(), 2);
    }

    #[test]
    fn verify_chain_empty_ok() {
        let l = CompactionHealthLog::new();
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_five_entries_ok() {
        let mut l = CompactionHealthLog::new();
        for i in 0u64..5 {
            let cond = match i % 3 {
                0 => OverallCondition::Optimal,
                1 => OverallCondition::Good,
                _ => OverallCondition::Caution,
            };
            l.record(i, true, i * 100, cond);
        }
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut l = CompactionHealthLog::new();
        l.record(1, true, 0, OverallCondition::Optimal);
        l.record(2, true, 0, OverallCondition::Good);
        l.vectors[0].vector_hash[0] ^= 0xFF;
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn verify_chain_detects_tampered_grade() {
        let mut l = CompactionHealthLog::new();
        l.record(1, true, 0, OverallCondition::Optimal);
        l.vectors[0].compaction_grade = CompactionHealthGrade::Critical; // tamper
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn prev_hash_links_correctly() {
        let mut l = CompactionHealthLog::new();
        l.record(1, true, 0, OverallCondition::Optimal);
        let h1 = l.vectors[0].vector_hash;
        l.record(2, true, 5, OverallCondition::Good);
        assert_eq!(l.vectors[1].prev_hash, h1);
    }

    #[test]
    fn vector_hash_deterministic() {
        let mut l1 = CompactionHealthLog::new();
        let mut l2 = CompactionHealthLog::new();
        l1.record(5, true, 200, OverallCondition::Caution);
        l2.record(5, true, 200, OverallCondition::Caution);
        assert_eq!(l1.vectors[0].vector_hash, l2.vectors[0].vector_hash);
    }

    #[test]
    fn joint_condition_count_correct() {
        let mut l = CompactionHealthLog::new();
        l.record(1, true, 0, OverallCondition::Optimal);   // Optimal
        l.record(2, true, 0, OverallCondition::Good);       // Nominal
        l.record(3, false, 0, OverallCondition::Good);      // Degraded
        l.record(4, false, PRUNE_ALERT_THRESHOLD, OverallCondition::Good); // Critical
        assert_eq!(l.joint_condition_count(JointCondition::Optimal),  1);
        assert_eq!(l.joint_condition_count(JointCondition::Nominal),  1);
        assert_eq!(l.joint_condition_count(JointCondition::Degraded), 1);
        assert_eq!(l.joint_condition_count(JointCondition::Critical), 1);
    }
}
