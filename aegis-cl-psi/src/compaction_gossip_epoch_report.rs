//! Gate 362 — Compaction Gossip Epoch Report (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Per-epoch summary unifying the three gossip health axes. Mirrors Gate 340
//! (Compaction Epoch Report) for the gossip subsystem.
//!
//!   • GossipHealthVector   (Gate 360) — GossipJointCondition + grade
//!   • GossipMomentumRecord (Gate 361) — directional trend
//!   • Telemetry percentages (Gate 359) — red/yellow/green pct
//!
//! GossipEpochReport:
//!   epoch:           u64
//!   joint_condition: GossipJointCondition
//!   gossip_grade:    GossipHealthGrade
//!   total_delivered: u64
//!   chains_valid:    bool
//!   direction:       GossipMomentumDir
//!   momentum_int:    i16
//!   window_size:     usize
//!   red_pct:         u8
//!   yellow_pct:      u8
//!   green_pct:       u8
//!   report_hash:     [u8;32]
//!   prev_hash:       [u8;32]
//!
//! report_hash = SHA-256(prev[32] ‖ epoch_be8 ‖ joint_byte ‖ grade_byte
//!                        ‖ total_delivered_be8 ‖ chains_valid_byte
//!                        ‖ dir_byte ‖ momentum_int_be2 ‖ window_size_be2
//!                        ‖ red_pct ‖ yellow_pct ‖ green_pct)
//!
//! GossipEpochReportLog: append(), latest(), verify_chain(),
//!   critical_epochs(), optimal_epochs(), declining_epochs().

use sha2::{Sha256, Digest};
use crate::compaction_gossip_health_aggregator::{
    GossipHealthGrade, GossipJointCondition, GossipHealthVector,
};
use crate::compaction_gossip_momentum_tracker::{
    GossipMomentumDir, GossipMomentumRecord,
};

pub const GOSSIP_EPOCH_REPORT_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── GossipEpochReport ────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipEpochReport {
    pub epoch:           u64,
    pub joint_condition: GossipJointCondition,
    pub gossip_grade:    GossipHealthGrade,
    pub total_delivered: u64,
    pub chains_valid:    bool,
    pub direction:       GossipMomentumDir,
    pub momentum_int:    i16,
    pub window_size:     usize,
    pub red_pct:         u8,
    pub yellow_pct:      u8,
    pub green_pct:       u8,
    pub report_hash:     [u8; 32],
    pub prev_hash:       [u8; 32],
}

fn compute_report_hash(
    prev:            &[u8; 32],
    epoch:           u64,
    joint:           GossipJointCondition,
    grade:           GossipHealthGrade,
    total_delivered: u64,
    chains_valid:    bool,
    dir:             GossipMomentumDir,
    momentum_int:    i16,
    window_size:     usize,
    red_pct:         u8,
    yellow_pct:      u8,
    green_pct:       u8,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update([joint.as_u8(), grade.as_u8()]);
    h.update(total_delivered.to_be_bytes());
    h.update([chains_valid as u8]);
    h.update([dir.as_u8()]);
    h.update(momentum_int.to_be_bytes());
    h.update((window_size as u16).to_be_bytes());
    h.update([red_pct, yellow_pct, green_pct]);
    h.finalize().into()
}

// ─── GossipEpochReportLog ─────────────────────────────────────────────────────

pub struct GossipEpochReportLog {
    reports: Vec<GossipEpochReport>,
}

impl GossipEpochReportLog {
    pub fn new() -> Self { Self { reports: Vec::new() } }

    pub fn len(&self)      -> usize { self.reports.len() }
    pub fn is_empty(&self) -> bool  { self.reports.is_empty() }
    pub fn reports(&self)  -> &[GossipEpochReport] { &self.reports }
    pub fn latest(&self)   -> Option<&GossipEpochReport> { self.reports.last() }

    pub fn append(
        &mut self,
        health:    &GossipHealthVector,
        momentum:  &GossipMomentumRecord,
        red_pct:   u8,
        yellow_pct: u8,
        green_pct: u8,
    ) -> &GossipEpochReport {
        let prev = self.reports.last()
            .map(|r| r.report_hash)
            .unwrap_or(GOSSIP_EPOCH_REPORT_GENESIS_HASH);

        let report_hash = compute_report_hash(
            &prev,
            health.epoch,
            health.joint_condition,
            health.gossip_grade,
            health.total_delivered,
            health.chains_valid,
            momentum.direction,
            momentum.momentum_int,
            momentum.window_size as usize,
            red_pct,
            yellow_pct,
            green_pct,
        );

        self.reports.push(GossipEpochReport {
            epoch:           health.epoch,
            joint_condition: health.joint_condition,
            gossip_grade:    health.gossip_grade,
            total_delivered: health.total_delivered,
            chains_valid:    health.chains_valid,
            direction:       momentum.direction,
            momentum_int:    momentum.momentum_int,
            window_size:     momentum.window_size as usize,
            red_pct,
            yellow_pct,
            green_pct,
            report_hash,
            prev_hash: prev,
        });
        self.reports.last().unwrap()
    }

    pub fn critical_epochs(&self) -> usize {
        self.reports.iter().filter(|r| r.joint_condition == GossipJointCondition::Critical).count()
    }

    pub fn optimal_epochs(&self) -> usize {
        self.reports.iter().filter(|r| r.joint_condition == GossipJointCondition::Optimal).count()
    }

    pub fn declining_epochs(&self) -> usize {
        self.reports.iter().filter(|r| r.direction == GossipMomentumDir::Declining).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_EPOCH_REPORT_GENESIS_HASH;
        for (i, r) in self.reports.iter().enumerate() {
            if r.prev_hash != prev { return (false, Some(i)); }
            let expected = compute_report_hash(
                &prev,
                r.epoch,
                r.joint_condition,
                r.gossip_grade,
                r.total_delivered,
                r.chains_valid,
                r.direction,
                r.momentum_int,
                r.window_size,
                r.red_pct,
                r.yellow_pct,
                r.green_pct,
            );
            if r.report_hash != expected { return (false, Some(i)); }
            prev = r.report_hash;
        }
        (true, None)
    }
}

impl Default for GossipEpochReportLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::compaction_gossip_health_aggregator::{
        GossipHealthGrade, GossipJointCondition,
    };
    use crate::compaction_gossip_momentum_tracker::GossipMomentumDir;
    use crate::compaction_gossip_health::CompactionGossipHealthClass;

    fn make_health(epoch: u64, grade: GossipHealthGrade, jc: GossipJointCondition,
                   delivered: u64, chains_valid: bool) -> GossipHealthVector {
        GossipHealthVector {
            epoch,
            gossip_grade:    grade,
            gossip_class:    CompactionGossipHealthClass::Green,
            joint_condition: jc,
            total_delivered: delivered,
            total_missed:    0,
            chains_valid,
            prev_hash:       [0u8; 32],
            vector_hash:     [0u8; 32],
        }
    }

    fn make_momentum(dir: GossipMomentumDir, momentum_int: i16, window_size: u16)
        -> GossipMomentumRecord
    {
        use crate::compaction_gossip_momentum_tracker::GOSSIP_MOMENTUM_GENESIS_HASH;
        GossipMomentumRecord {
            epoch:           1,
            joint_condition: GossipJointCondition::Optimal,
            score:           0,
            direction:       dir,
            momentum_int,
            window_size,
            prev_hash:       GOSSIP_MOMENTUM_GENESIS_HASH,
            record_hash:     [0u8; 32],
        }
    }

    #[test]
    fn log_starts_empty() {
        let l = GossipEpochReportLog::new();
        assert!(l.is_empty());
        assert_eq!(l.len(), 0);
        assert!(l.latest().is_none());
    }

    #[test]
    fn append_single_report() {
        let mut l = GossipEpochReportLog::new();
        let h = make_health(1, GossipHealthGrade::Healthy, GossipJointCondition::Optimal, 100, true);
        let m = make_momentum(GossipMomentumDir::Stable, 0, 1);
        let r = l.append(&h, &m, 5, 20, 75).clone();
        assert_eq!(r.epoch, 1);
        assert_eq!(r.joint_condition, GossipJointCondition::Optimal);
        assert_eq!(r.direction, GossipMomentumDir::Stable);
        assert_eq!(r.red_pct,    5);
        assert_eq!(r.yellow_pct, 20);
        assert_eq!(r.green_pct,  75);
        assert_eq!(l.len(), 1);
    }

    #[test]
    fn fields_from_health_and_momentum() {
        let mut l = GossipEpochReportLog::new();
        let h = make_health(7, GossipHealthGrade::Critical, GossipJointCondition::Critical, 500, false);
        let m = make_momentum(GossipMomentumDir::Declining, 2, 3);
        let r = l.append(&h, &m, 80, 15, 5).clone();
        assert_eq!(r.gossip_grade,    GossipHealthGrade::Critical);
        assert_eq!(r.total_delivered, 500);
        assert!(!r.chains_valid);
        assert_eq!(r.momentum_int, 2);
        assert_eq!(r.window_size, 3);
    }

    #[test]
    fn first_prev_hash_is_genesis() {
        let mut l = GossipEpochReportLog::new();
        let h = make_health(1, GossipHealthGrade::Healthy, GossipJointCondition::Optimal, 0, true);
        let m = make_momentum(GossipMomentumDir::Stable, 0, 1);
        let r = l.append(&h, &m, 0, 0, 100).clone();
        assert_eq!(r.prev_hash, GOSSIP_EPOCH_REPORT_GENESIS_HASH);
    }

    #[test]
    fn prev_hash_links_correctly() {
        let mut l = GossipEpochReportLog::new();
        let h1 = make_health(1, GossipHealthGrade::Healthy, GossipJointCondition::Optimal, 100, true);
        let m1 = make_momentum(GossipMomentumDir::Stable, 0, 1);
        let r1 = l.append(&h1, &m1, 0, 10, 90).clone();
        let h2 = make_health(2, GossipHealthGrade::Nominal, GossipJointCondition::Nominal, 200, true);
        let m2 = make_momentum(GossipMomentumDir::Improving, -1, 2);
        let r2 = l.append(&h2, &m2, 5, 15, 80).clone();
        assert_eq!(r2.prev_hash, r1.report_hash);
    }

    #[test]
    fn report_hash_deterministic() {
        let mut l1 = GossipEpochReportLog::new();
        let mut l2 = GossipEpochReportLog::new();
        let h = make_health(3, GossipHealthGrade::Elevated, GossipJointCondition::Degraded, 800, false);
        let m = make_momentum(GossipMomentumDir::Declining, 1, 2);
        let r1 = l1.append(&h, &m, 30, 40, 30).clone();
        let r2 = l2.append(&h, &m, 30, 40, 30).clone();
        assert_eq!(r1.report_hash, r2.report_hash);
    }

    #[test]
    fn different_pct_different_hash() {
        let mut l1 = GossipEpochReportLog::new();
        let mut l2 = GossipEpochReportLog::new();
        let h = make_health(1, GossipHealthGrade::Healthy, GossipJointCondition::Optimal, 100, true);
        let m = make_momentum(GossipMomentumDir::Stable, 0, 1);
        let r1 = l1.append(&h, &m, 5, 20, 75).clone();
        let r2 = l2.append(&h, &m, 10, 20, 70).clone();
        assert_ne!(r1.report_hash, r2.report_hash);
    }

    #[test]
    fn critical_epochs_count() {
        let mut l = GossipEpochReportLog::new();
        let hc = make_health(1, GossipHealthGrade::Critical, GossipJointCondition::Critical, 0, false);
        let ho = make_health(2, GossipHealthGrade::Healthy, GossipJointCondition::Optimal, 100, true);
        let m  = make_momentum(GossipMomentumDir::Stable, 0, 1);
        l.append(&hc, &m, 0, 0, 0);
        l.append(&ho, &m, 0, 0, 100);
        l.append(&hc, &m, 0, 0, 0);
        assert_eq!(l.critical_epochs(), 2);
        assert_eq!(l.optimal_epochs(), 1);
    }

    #[test]
    fn declining_epochs_count() {
        let mut l = GossipEpochReportLog::new();
        let h = make_health(1, GossipHealthGrade::Healthy, GossipJointCondition::Optimal, 100, true);
        let md = make_momentum(GossipMomentumDir::Declining, 1, 2);
        let ms = make_momentum(GossipMomentumDir::Stable, 0, 2);
        l.append(&h, &md, 0, 10, 90);
        l.append(&h, &ms, 0, 5, 95);
        l.append(&h, &md, 0, 20, 80);
        assert_eq!(l.declining_epochs(), 2);
    }

    #[test]
    fn verify_chain_three_ok() {
        let mut l = GossipEpochReportLog::new();
        let h = make_health(1, GossipHealthGrade::Healthy, GossipJointCondition::Optimal, 100, true);
        let m = make_momentum(GossipMomentumDir::Stable, 0, 1);
        for _ in 0..3 { l.append(&h, &m, 10, 20, 70); }
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut l = GossipEpochReportLog::new();
        let h = make_health(1, GossipHealthGrade::Healthy, GossipJointCondition::Optimal, 100, true);
        let m = make_momentum(GossipMomentumDir::Stable, 0, 1);
        l.append(&h, &m, 10, 20, 70);
        l.append(&h, &m, 5,  25, 70);
        l.reports[0].report_hash[0] ^= 0xFF;
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn report_hash_nonzero() {
        let mut l = GossipEpochReportLog::new();
        let h = make_health(1, GossipHealthGrade::Healthy, GossipJointCondition::Optimal, 100, true);
        let m = make_momentum(GossipMomentumDir::Stable, 0, 1);
        let r = l.append(&h, &m, 10, 20, 70).clone();
        assert_ne!(r.report_hash, [0u8; 32]);
    }
}
