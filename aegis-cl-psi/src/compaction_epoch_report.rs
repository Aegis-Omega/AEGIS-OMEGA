//! Gate 340 — Compaction Epoch Report (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Per-epoch summary record unifying the three compaction health axes:
//!   • CompactionHealthVector  (Gate 338) — JointCondition + grade
//!   • CompactionMomentumRecord (Gate 339) — directional trend
//!   • Telemetry summary fields  (Gate 337) — spsf/health/res percentages
//!
//! CompactionEpochReport:
//!   epoch:            u64
//!   joint_condition:  JointCondition         — from health vector
//!   compaction_grade: CompactionHealthGrade  — from health vector
//!   total_pruned:     u64                    — from health vector
//!   chains_valid:     bool                   — from health vector
//!   direction:        CompactionMomentumDir  — from momentum record
//!   momentum_int:     i16                    — signed delta
//!   window_size:      usize                  — observations in momentum window
//!   spsf_pct:         u8                     — spsf share (0-100)
//!   health_pct:       u8                     — health share (0-100)
//!   res_pct:          u8                     — resonance share (0-100)
//!   report_hash:      [u8;32]
//!   prev_hash:        [u8;32]
//!
//! report_hash = SHA-256(prev[32] ‖ epoch_be8 ‖ joint_byte ‖ grade_byte
//!                        ‖ total_pruned_be8 ‖ chains_valid_byte
//!                        ‖ dir_byte ‖ momentum_int_be2 ‖ window_size_be2
//!                        ‖ spsf_pct ‖ health_pct ‖ res_pct)
//!
//! CompactionEpochReportLog: append(), latest(), verify_chain(),
//!   critical_epochs(), optimal_epochs(), declining_epochs().

use sha2::{Sha256, Digest};
use crate::compaction_health_aggregator::{
    CompactionHealthGrade, JointCondition, CompactionHealthVector,
};
use crate::compaction_momentum_tracker::{
    CompactionMomentumDir, CompactionMomentumRecord,
};

pub const EPOCH_REPORT_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── CompactionEpochReport ────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct CompactionEpochReport {
    pub epoch:            u64,
    pub joint_condition:  JointCondition,
    pub compaction_grade: CompactionHealthGrade,
    pub total_pruned:     u64,
    pub chains_valid:     bool,
    pub direction:        CompactionMomentumDir,
    pub momentum_int:     i16,
    pub window_size:      usize,
    pub spsf_pct:         u8,
    pub health_pct:       u8,
    pub res_pct:          u8,
    pub report_hash:      [u8; 32],
    pub prev_hash:        [u8; 32],
}

fn compute_report_hash(
    prev:         &[u8; 32],
    epoch:        u64,
    joint:        JointCondition,
    grade:        CompactionHealthGrade,
    total_pruned: u64,
    chains_valid: bool,
    dir:          CompactionMomentumDir,
    momentum_int: i16,
    window_size:  usize,
    spsf_pct:     u8,
    health_pct:   u8,
    res_pct:      u8,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update([joint.as_u8(), grade.as_u8()]);
    h.update(total_pruned.to_be_bytes());
    h.update([chains_valid as u8]);
    h.update([dir.as_u8()]);
    h.update(momentum_int.to_be_bytes());
    h.update((window_size as u16).to_be_bytes());
    h.update([spsf_pct, health_pct, res_pct]);
    h.finalize().into()
}

// ─── CompactionEpochReportLog ─────────────────────────────────────────────────

pub struct CompactionEpochReportLog {
    reports: Vec<CompactionEpochReport>,
}

impl CompactionEpochReportLog {
    pub fn new() -> Self { Self { reports: Vec::new() } }

    pub fn len(&self)      -> usize { self.reports.len() }
    pub fn is_empty(&self) -> bool  { self.reports.is_empty() }
    pub fn reports(&self)  -> &[CompactionEpochReport] { &self.reports }
    pub fn latest(&self)   -> Option<&CompactionEpochReport> { self.reports.last() }

    /// Build a report from a health vector + momentum record + telemetry percentages.
    ///
    /// `spsf_pct`, `health_pct`, `res_pct` should come from the telemetry frame for
    /// the same epoch (via `CompactionTelemetryFrame::spsf_pct()` etc.).
    pub fn append(
        &mut self,
        health:     &CompactionHealthVector,
        momentum:   &CompactionMomentumRecord,
        spsf_pct:   u8,
        health_pct: u8,
        res_pct:    u8,
    ) -> &CompactionEpochReport {
        let prev = self.reports.last()
            .map(|r| r.report_hash)
            .unwrap_or(EPOCH_REPORT_GENESIS_HASH);

        let report_hash = compute_report_hash(
            &prev,
            health.epoch,
            health.joint_condition,
            health.compaction_grade,
            health.total_pruned_this_epoch,
            health.chains_valid,
            momentum.direction,
            momentum.momentum_int,
            momentum.window_size,
            spsf_pct,
            health_pct,
            res_pct,
        );

        self.reports.push(CompactionEpochReport {
            epoch:            health.epoch,
            joint_condition:  health.joint_condition,
            compaction_grade: health.compaction_grade,
            total_pruned:     health.total_pruned_this_epoch,
            chains_valid:     health.chains_valid,
            direction:        momentum.direction,
            momentum_int:     momentum.momentum_int,
            window_size:      momentum.window_size,
            spsf_pct,
            health_pct,
            res_pct,
            report_hash,
            prev_hash: prev,
        });
        self.reports.last().unwrap()
    }

    pub fn critical_epochs(&self) -> usize {
        self.reports.iter().filter(|r| r.joint_condition == JointCondition::Critical).count()
    }

    pub fn optimal_epochs(&self) -> usize {
        self.reports.iter().filter(|r| r.joint_condition == JointCondition::Optimal).count()
    }

    pub fn declining_epochs(&self) -> usize {
        self.reports.iter().filter(|r| r.direction == CompactionMomentumDir::Declining).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = EPOCH_REPORT_GENESIS_HASH;
        for (i, r) in self.reports.iter().enumerate() {
            if r.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_report_hash(
                &prev,
                r.epoch,
                r.joint_condition,
                r.compaction_grade,
                r.total_pruned,
                r.chains_valid,
                r.direction,
                r.momentum_int,
                r.window_size,
                r.spsf_pct,
                r.health_pct,
                r.res_pct,
            );
            if r.report_hash != expected {
                return (false, Some(i));
            }
            prev = r.report_hash;
        }
        (true, None)
    }
}

impl Default for CompactionEpochReportLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::compaction_health_aggregator::{
        CompactionHealthGrade, JointCondition, CompactionHealthVector,
    };
    use crate::compaction_momentum_tracker::{
        CompactionMomentumDir, CompactionMomentumRecord, MOMENTUM_GENESIS_HASH,
    };

    fn make_health(epoch: u64, grade: CompactionHealthGrade, jc: JointCondition,
                   total_pruned: u64, chains_valid: bool) -> CompactionHealthVector {
        CompactionHealthVector {
            epoch,
            compaction_grade:        grade,
            constitutional_cond:     crate::health_aggregator::OverallCondition::Optimal,
            joint_condition:         jc,
            total_pruned_this_epoch: total_pruned,
            chains_valid,
            vector_hash:             [0u8; 32],
            prev_hash:               [0u8; 32],
        }
    }

    fn make_momentum(epoch: u64, dir: CompactionMomentumDir,
                     momentum_int: i16, window_size: usize) -> CompactionMomentumRecord {
        CompactionMomentumRecord {
            epoch,
            joint_condition: JointCondition::Optimal,
            score:           0,
            direction:       dir,
            momentum_int,
            window_size,
            record_hash:     [0u8; 32],
            prev_hash:       MOMENTUM_GENESIS_HASH,
        }
    }

    // ── Basic append ─────────────────────────────────────────────────────────

    #[test]
    fn log_starts_empty() {
        let l = CompactionEpochReportLog::new();
        assert!(l.is_empty());
        assert_eq!(l.len(), 0);
        assert!(l.latest().is_none());
    }

    #[test]
    fn append_single_report() {
        let mut l = CompactionEpochReportLog::new();
        let h = make_health(1, CompactionHealthGrade::Healthy, JointCondition::Optimal, 100, true);
        let m = make_momentum(1, CompactionMomentumDir::Stable, 0, 1);
        let r = l.append(&h, &m, 60, 30, 10).clone();
        assert_eq!(r.epoch, 1);
        assert_eq!(r.joint_condition, JointCondition::Optimal);
        assert_eq!(r.direction, CompactionMomentumDir::Stable);
        assert_eq!(r.spsf_pct, 60);
        assert_eq!(r.health_pct, 30);
        assert_eq!(r.res_pct, 10);
        assert_eq!(l.len(), 1);
    }

    #[test]
    fn report_fields_from_health_and_momentum() {
        let mut l = CompactionEpochReportLog::new();
        let h = make_health(5, CompactionHealthGrade::Critical, JointCondition::Critical, 2000, false);
        let m = make_momentum(5, CompactionMomentumDir::Declining, 2, 3);
        let r = l.append(&h, &m, 50, 40, 10).clone();
        assert_eq!(r.compaction_grade, CompactionHealthGrade::Critical);
        assert_eq!(r.total_pruned, 2000);
        assert!(!r.chains_valid);
        assert_eq!(r.momentum_int, 2);
        assert_eq!(r.window_size, 3);
    }

    // ── Hash chain ────────────────────────────────────────────────────────────

    #[test]
    fn first_prev_hash_is_genesis() {
        let mut l = CompactionEpochReportLog::new();
        let h = make_health(1, CompactionHealthGrade::Healthy, JointCondition::Optimal, 0, true);
        let m = make_momentum(1, CompactionMomentumDir::Stable, 0, 1);
        let r = l.append(&h, &m, 0, 0, 0).clone();
        assert_eq!(r.prev_hash, EPOCH_REPORT_GENESIS_HASH);
    }

    #[test]
    fn prev_hash_links_correctly() {
        let mut l = CompactionEpochReportLog::new();
        let h1 = make_health(1, CompactionHealthGrade::Healthy, JointCondition::Optimal, 0, true);
        let m1 = make_momentum(1, CompactionMomentumDir::Stable, 0, 1);
        let r1 = l.append(&h1, &m1, 0, 0, 0).clone();
        let h2 = make_health(2, CompactionHealthGrade::Nominal, JointCondition::Nominal, 500, true);
        let m2 = make_momentum(2, CompactionMomentumDir::Improving, -1, 2);
        let r2 = l.append(&h2, &m2, 50, 30, 20).clone();
        assert_eq!(r2.prev_hash, r1.report_hash);
    }

    #[test]
    fn report_hash_deterministic() {
        let mut l1 = CompactionEpochReportLog::new();
        let mut l2 = CompactionEpochReportLog::new();
        let h = make_health(3, CompactionHealthGrade::Elevated, JointCondition::Degraded, 800, false);
        let m = make_momentum(3, CompactionMomentumDir::Declining, 1, 2);
        let r1 = l1.append(&h, &m, 55, 33, 12).clone();
        let r2 = l2.append(&h, &m, 55, 33, 12).clone();
        assert_eq!(r1.report_hash, r2.report_hash);
    }

    #[test]
    fn different_pct_different_hash() {
        let mut l1 = CompactionEpochReportLog::new();
        let mut l2 = CompactionEpochReportLog::new();
        let h = make_health(1, CompactionHealthGrade::Healthy, JointCondition::Optimal, 100, true);
        let m = make_momentum(1, CompactionMomentumDir::Stable, 0, 1);
        let r1 = l1.append(&h, &m, 60, 30, 10).clone();
        let r2 = l2.append(&h, &m, 70, 20, 10).clone();
        assert_ne!(r1.report_hash, r2.report_hash);
    }

    // ── Aggregation ───────────────────────────────────────────────────────────

    #[test]
    fn critical_epochs_counted() {
        let mut l = CompactionEpochReportLog::new();
        let h1 = make_health(1, CompactionHealthGrade::Healthy, JointCondition::Optimal, 0, true);
        let h2 = make_health(2, CompactionHealthGrade::Critical, JointCondition::Critical, 2000, false);
        let h3 = make_health(3, CompactionHealthGrade::Critical, JointCondition::Critical, 1500, false);
        let m = make_momentum(1, CompactionMomentumDir::Stable, 0, 1);
        l.append(&h1, &m, 0, 0, 0);
        l.append(&h2, &m, 50, 40, 10);
        l.append(&h3, &m, 50, 40, 10);
        assert_eq!(l.critical_epochs(), 2);
        assert_eq!(l.optimal_epochs(), 1);
    }

    #[test]
    fn declining_epochs_counted() {
        let mut l = CompactionEpochReportLog::new();
        let h = make_health(1, CompactionHealthGrade::Healthy, JointCondition::Optimal, 0, true);
        let m_stable   = make_momentum(1, CompactionMomentumDir::Stable,   0, 1);
        let m_declining = make_momentum(2, CompactionMomentumDir::Declining, 1, 2);
        l.append(&h, &m_stable, 0, 0, 0);
        l.append(&h, &m_declining, 0, 0, 0);
        l.append(&h, &m_declining, 0, 0, 0);
        assert_eq!(l.declining_epochs(), 2);
    }

    // ── verify_chain ──────────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let l = CompactionEpochReportLog::new();
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_five_reports_ok() {
        let mut l = CompactionEpochReportLog::new();
        for i in 1u64..=5 {
            let h = make_health(i, CompactionHealthGrade::Healthy, JointCondition::Optimal, i * 100, true);
            let m = make_momentum(i, CompactionMomentumDir::Stable, 0, 1);
            l.append(&h, &m, 60, 30, 10);
        }
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tampered_hash() {
        let mut l = CompactionEpochReportLog::new();
        let h = make_health(1, CompactionHealthGrade::Healthy, JointCondition::Optimal, 0, true);
        let m = make_momentum(1, CompactionMomentumDir::Stable, 0, 1);
        l.append(&h, &m, 0, 0, 0);
        l.append(&h, &m, 0, 0, 0);
        l.reports[0].report_hash[0] ^= 0xFF;
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn verify_chain_detects_tampered_field() {
        let mut l = CompactionEpochReportLog::new();
        let h = make_health(1, CompactionHealthGrade::Healthy, JointCondition::Optimal, 0, true);
        let m = make_momentum(1, CompactionMomentumDir::Stable, 0, 1);
        l.append(&h, &m, 60, 30, 10);
        l.reports[0].spsf_pct = 99; // tamper
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }
}
