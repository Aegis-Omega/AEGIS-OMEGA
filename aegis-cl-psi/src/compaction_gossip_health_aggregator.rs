//! Gate 360 — Compaction Gossip Health Aggregator (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Combines gossip telemetry validity (chains_valid, missed rate) with the
//! per-epoch CompactionGossipHealthClass (Gate 355) into a GossipHealthVector.
//! Mirrors Gate 338 (Compaction Health Aggregator) for the gossip subsystem.
//!
//! GossipHealthGrade:
//!   Healthy  — chains_valid AND total_missed < MISSED_ALERT_THRESHOLD
//!   Nominal  — chains_valid AND total_missed >= MISSED_ALERT_THRESHOLD
//!   Elevated — !chains_valid AND total_missed < MISSED_ALERT_THRESHOLD
//!   Critical — !chains_valid AND total_missed >= MISSED_ALERT_THRESHOLD
//!
//! MISSED_ALERT_THRESHOLD = 10 per epoch
//!
//! GossipJointCondition: Optimal / Nominal / Degraded / Critical
//!   Optimal:  grade=Healthy AND class=Green
//!   Nominal:  grade≤Nominal AND class≤Yellow (not Optimal)
//!   Degraded: grade=Elevated OR (class=Yellow AND grade=Healthy)
//!   Critical: grade=Critical OR class=Red
//!
//! vector_hash = SHA-256(prev[32] ‖ epoch_be8 ‖ grade_byte ‖ class_byte
//!                        ‖ joint_byte ‖ total_delivered_be8
//!                        ‖ total_missed_be8 ‖ chains_valid_byte)
//!
//! GossipHealthLog: hash-chained vectors.
//! verify_chain(), critical_count(), optimal_count(), joint_condition_count().

use sha2::{Sha256, Digest};
use crate::compaction_gossip_health::CompactionGossipHealthClass;

pub const GOSSIP_HEALTH_AGGREGATOR_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const MISSED_ALERT_THRESHOLD: u64 = 10;

// ─── GossipHealthGrade ────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
#[repr(u8)]
pub enum GossipHealthGrade {
    Healthy  = 0,
    Nominal  = 1,
    Elevated = 2,
    Critical = 3,
}

impl GossipHealthGrade {
    pub fn as_u8(self) -> u8 { self as u8 }

    pub fn classify(chains_valid: bool, total_missed: u64) -> Self {
        let high = total_missed >= MISSED_ALERT_THRESHOLD;
        match (chains_valid, high) {
            (true,  false) => Self::Healthy,
            (true,  true)  => Self::Nominal,
            (false, false) => Self::Elevated,
            (false, true)  => Self::Critical,
        }
    }
}

// ─── GossipJointCondition ─────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
#[repr(u8)]
pub enum GossipJointCondition {
    Optimal  = 0,
    Nominal  = 1,
    Degraded = 2,
    Critical = 3,
}

impl GossipJointCondition {
    pub fn as_u8(self) -> u8 { self as u8 }

    pub fn classify(grade: GossipHealthGrade, class: CompactionGossipHealthClass) -> Self {
        if grade == GossipHealthGrade::Critical || class == CompactionGossipHealthClass::Red {
            return Self::Critical;
        }
        if grade == GossipHealthGrade::Elevated {
            return Self::Degraded;
        }
        if grade == GossipHealthGrade::Healthy && class == CompactionGossipHealthClass::Green {
            return Self::Optimal;
        }
        // grade=Nominal or class=Yellow (not Critical, not Elevated, not Optimal)
        if class == CompactionGossipHealthClass::Yellow {
            return Self::Degraded;
        }
        Self::Nominal
    }
}

// ─── GossipHealthVector ───────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipHealthVector {
    pub epoch:           u64,
    pub gossip_grade:    GossipHealthGrade,
    pub gossip_class:    CompactionGossipHealthClass,
    pub joint_condition: GossipJointCondition,
    pub total_delivered: u64,
    pub total_missed:    u64,
    pub chains_valid:    bool,
    pub prev_hash:       [u8; 32],
    pub vector_hash:     [u8; 32],
}

fn compute_vector_hash(
    prev:            &[u8; 32],
    epoch:           u64,
    grade:           GossipHealthGrade,
    class:           CompactionGossipHealthClass,
    joint:           GossipJointCondition,
    total_delivered: u64,
    total_missed:    u64,
    chains_valid:    bool,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update([grade.as_u8()]);
    h.update([class.as_u8()]);
    h.update([joint.as_u8()]);
    h.update(total_delivered.to_be_bytes());
    h.update(total_missed.to_be_bytes());
    h.update([chains_valid as u8]);
    h.finalize().into()
}

// ─── GossipHealthLog ──────────────────────────────────────────────────────────

pub struct GossipHealthLog {
    vectors: Vec<GossipHealthVector>,
}

impl GossipHealthLog {
    pub fn new() -> Self { Self { vectors: Vec::new() } }

    pub fn len(&self)     -> usize { self.vectors.len() }
    pub fn is_empty(&self) -> bool { self.vectors.is_empty() }
    pub fn vectors(&self)  -> &[GossipHealthVector] { &self.vectors }
    pub fn latest(&self)   -> Option<&GossipHealthVector> { self.vectors.last() }

    pub fn critical_count(&self) -> usize {
        self.vectors.iter().filter(|v| v.joint_condition == GossipJointCondition::Critical).count()
    }

    pub fn optimal_count(&self) -> usize {
        self.vectors.iter().filter(|v| v.joint_condition == GossipJointCondition::Optimal).count()
    }

    pub fn joint_condition_count(&self, jc: GossipJointCondition) -> usize {
        self.vectors.iter().filter(|v| v.joint_condition == jc).count()
    }

    pub fn record(
        &mut self,
        epoch:           u64,
        gossip_class:    CompactionGossipHealthClass,
        total_delivered: u64,
        total_missed:    u64,
        chains_valid:    bool,
    ) -> &GossipHealthVector {
        let grade = GossipHealthGrade::classify(chains_valid, total_missed);
        let joint = GossipJointCondition::classify(grade, gossip_class);
        let prev  = self.vectors.last().map(|v| v.vector_hash)
            .unwrap_or(GOSSIP_HEALTH_AGGREGATOR_GENESIS_HASH);
        let vector_hash = compute_vector_hash(
            &prev, epoch, grade, gossip_class, joint,
            total_delivered, total_missed, chains_valid,
        );
        self.vectors.push(GossipHealthVector {
            epoch, gossip_grade: grade, gossip_class, joint_condition: joint,
            total_delivered, total_missed, chains_valid,
            prev_hash: prev, vector_hash,
        });
        self.vectors.last().unwrap()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_HEALTH_AGGREGATOR_GENESIS_HASH;
        for (i, v) in self.vectors.iter().enumerate() {
            if v.prev_hash != prev { return (false, Some(i)); }
            let expected = compute_vector_hash(
                &prev, v.epoch, v.gossip_grade, v.gossip_class, v.joint_condition,
                v.total_delivered, v.total_missed, v.chains_valid,
            );
            if v.vector_hash != expected { return (false, Some(i)); }
            prev = v.vector_hash;
        }
        (true, None)
    }
}

impl Default for GossipHealthLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use CompactionGossipHealthClass as Class;

    // ── GossipHealthGrade ─────────────────────────────────────────────────────

    #[test]
    fn grade_healthy_valid_low_missed() {
        assert_eq!(GossipHealthGrade::classify(true, 0), GossipHealthGrade::Healthy);
        assert_eq!(GossipHealthGrade::classify(true, 9), GossipHealthGrade::Healthy);
    }

    #[test]
    fn grade_nominal_valid_high_missed() {
        assert_eq!(GossipHealthGrade::classify(true, 10), GossipHealthGrade::Nominal);
        assert_eq!(GossipHealthGrade::classify(true, 100), GossipHealthGrade::Nominal);
    }

    #[test]
    fn grade_elevated_invalid_low_missed() {
        assert_eq!(GossipHealthGrade::classify(false, 5), GossipHealthGrade::Elevated);
    }

    #[test]
    fn grade_critical_invalid_high_missed() {
        assert_eq!(GossipHealthGrade::classify(false, 10), GossipHealthGrade::Critical);
    }

    // ── GossipJointCondition ──────────────────────────────────────────────────

    #[test]
    fn joint_optimal_healthy_green() {
        assert_eq!(
            GossipJointCondition::classify(GossipHealthGrade::Healthy, Class::Green),
            GossipJointCondition::Optimal
        );
    }

    #[test]
    fn joint_critical_on_red_class() {
        assert_eq!(
            GossipJointCondition::classify(GossipHealthGrade::Healthy, Class::Red),
            GossipJointCondition::Critical
        );
    }

    #[test]
    fn joint_critical_on_critical_grade() {
        assert_eq!(
            GossipJointCondition::classify(GossipHealthGrade::Critical, Class::Green),
            GossipJointCondition::Critical
        );
    }

    #[test]
    fn joint_degraded_on_elevated_grade() {
        assert_eq!(
            GossipJointCondition::classify(GossipHealthGrade::Elevated, Class::Green),
            GossipJointCondition::Degraded
        );
    }

    #[test]
    fn joint_degraded_on_yellow_class() {
        assert_eq!(
            GossipJointCondition::classify(GossipHealthGrade::Healthy, Class::Yellow),
            GossipJointCondition::Degraded
        );
    }

    #[test]
    fn joint_nominal_on_nominal_grade_green_class() {
        assert_eq!(
            GossipJointCondition::classify(GossipHealthGrade::Nominal, Class::Green),
            GossipJointCondition::Nominal
        );
    }

    // ── GossipHealthLog ───────────────────────────────────────────────────────

    #[test]
    fn log_optimal_entry() {
        let mut log = GossipHealthLog::new();
        let v = log.record(1, Class::Green, 100, 0, true);
        assert_eq!(v.joint_condition, GossipJointCondition::Optimal);
        assert_eq!(v.gossip_grade, GossipHealthGrade::Healthy);
    }

    #[test]
    fn log_critical_entry() {
        let mut log = GossipHealthLog::new();
        let v = log.record(1, Class::Red, 0, 50, false);
        assert_eq!(v.joint_condition, GossipJointCondition::Critical);
    }

    #[test]
    fn log_vector_hash_nonzero() {
        let mut log = GossipHealthLog::new();
        let v = log.record(1, Class::Green, 100, 0, true);
        assert_ne!(v.vector_hash, [0u8; 32]);
    }

    #[test]
    fn log_first_prev_is_genesis() {
        let mut log = GossipHealthLog::new();
        let v = log.record(1, Class::Green, 100, 0, true);
        assert_eq!(v.prev_hash, GOSSIP_HEALTH_AGGREGATOR_GENESIS_HASH);
    }

    #[test]
    fn log_critical_and_optimal_counts() {
        let mut log = GossipHealthLog::new();
        log.record(1, Class::Green, 100, 0, true);    // Optimal
        log.record(2, Class::Red,   0,   50, false);  // Critical
        log.record(3, Class::Green, 100, 0, true);    // Optimal
        assert_eq!(log.optimal_count(),  2);
        assert_eq!(log.critical_count(), 1);
    }

    #[test]
    fn log_joint_condition_count() {
        let mut log = GossipHealthLog::new();
        log.record(1, Class::Green, 100, 0, true);   // Optimal
        log.record(2, Class::Yellow, 80, 5, true);   // Degraded
        log.record(3, Class::Yellow, 60, 5, true);   // Degraded
        assert_eq!(log.joint_condition_count(GossipJointCondition::Degraded), 2);
    }

    #[test]
    fn log_vector_hash_deterministic() {
        let mut l1 = GossipHealthLog::new();
        let mut l2 = GossipHealthLog::new();
        let h1 = l1.record(5, Class::Green, 200, 3, true).vector_hash;
        let h2 = l2.record(5, Class::Green, 200, 3, true).vector_hash;
        assert_eq!(h1, h2);
    }

    #[test]
    fn log_verify_chain_three_ok() {
        let mut log = GossipHealthLog::new();
        log.record(1, Class::Green,  100, 0,  true);
        log.record(2, Class::Yellow, 80,  5,  true);
        log.record(3, Class::Red,    0,   20, false);
        let (ok, idx) = log.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn log_verify_chain_detects_tamper() {
        let mut log = GossipHealthLog::new();
        log.record(1, Class::Green, 100, 0, true);
        log.record(2, Class::Green, 100, 0, true);
        log.vectors[0].vector_hash[0] ^= 0xFF;
        let (ok, idx) = log.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }
}
