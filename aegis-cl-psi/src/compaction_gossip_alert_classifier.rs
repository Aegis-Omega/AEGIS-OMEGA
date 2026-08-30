//! Gate 363 — Compaction Gossip Alert Classifier (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Translates GossipEpochReport (Gate 362) signals into a three-level alert
//! state with hysteresis. Mirrors Gate 341 for the gossip subsystem.
//!
//! GossipAlertLevel:
//!   Green — joint_condition ≤ Nominal AND direction ≠ Declining
//!   Amber — joint_condition == Degraded OR (direction == Declining AND consecutive_declining ≥ 2)
//!   Red   — joint_condition == Critical OR consecutive_declining ≥ GOSSIP_ALERT_DECLINING_THRESHOLD
//!
//! GOSSIP_ALERT_DECLINING_THRESHOLD = 3
//!
//! GossipAlertRecord:
//!   epoch:                 u64
//!   alert_level:           GossipAlertLevel
//!   joint_condition:       GossipJointCondition
//!   direction:             GossipMomentumDir
//!   consecutive_declining: u32
//!   alert_hash:            [u8;32]
//!   prev_hash:             [u8;32]
//!
//! alert_hash = SHA-256(prev[32] ‖ epoch_be8 ‖ alert_byte ‖ joint_byte
//!                        ‖ dir_byte ‖ consecutive_be4)
//!
//! GossipAlertLog: append(report), latest(), red_count(), amber_count(),
//!   green_count(), max_consecutive_declining(), verify_chain().

use sha2::{Sha256, Digest};
use crate::compaction_gossip_health_aggregator::GossipJointCondition;
use crate::compaction_gossip_momentum_tracker::GossipMomentumDir;
use crate::compaction_gossip_epoch_report::GossipEpochReport;

pub const GOSSIP_ALERT_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const GOSSIP_ALERT_DECLINING_THRESHOLD: u32 = 3;

// ─── GossipAlertLevel ─────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
#[repr(u8)]
pub enum GossipAlertLevel {
    Green = 0,
    Amber = 1,
    Red   = 2,
}

impl GossipAlertLevel {
    pub fn as_u8(self) -> u8 { self as u8 }

    fn classify(
        jc:                    GossipJointCondition,
        dir:                   GossipMomentumDir,
        consecutive_declining: u32,
    ) -> Self {
        if jc == GossipJointCondition::Critical
            || consecutive_declining >= GOSSIP_ALERT_DECLINING_THRESHOLD
        {
            return Self::Red;
        }
        if jc == GossipJointCondition::Degraded
            || (dir == GossipMomentumDir::Declining && consecutive_declining >= 2)
        {
            return Self::Amber;
        }
        Self::Green
    }
}

// ─── GossipAlertRecord ────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipAlertRecord {
    pub epoch:                 u64,
    pub alert_level:           GossipAlertLevel,
    pub joint_condition:       GossipJointCondition,
    pub direction:             GossipMomentumDir,
    pub consecutive_declining: u32,
    pub alert_hash:            [u8; 32],
    pub prev_hash:             [u8; 32],
}

fn compute_alert_hash(
    prev:                  &[u8; 32],
    epoch:                 u64,
    alert:                 GossipAlertLevel,
    joint:                 GossipJointCondition,
    dir:                   GossipMomentumDir,
    consecutive_declining: u32,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update([alert.as_u8(), joint.as_u8(), dir.as_u8()]);
    h.update(consecutive_declining.to_be_bytes());
    h.finalize().into()
}

// ─── GossipAlertLog ───────────────────────────────────────────────────────────

pub struct GossipAlertLog {
    records:              Vec<GossipAlertRecord>,
    consecutive_declining: u32,
}

impl GossipAlertLog {
    pub fn new() -> Self {
        Self { records: Vec::new(), consecutive_declining: 0 }
    }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[GossipAlertRecord] { &self.records }
    pub fn latest(&self)   -> Option<&GossipAlertRecord> { self.records.last() }

    pub fn append(&mut self, report: &GossipEpochReport) -> &GossipAlertRecord {
        if report.direction == GossipMomentumDir::Declining {
            self.consecutive_declining = self.consecutive_declining.saturating_add(1);
        } else {
            self.consecutive_declining = 0;
        }
        let streak = self.consecutive_declining;

        let alert_level = GossipAlertLevel::classify(report.joint_condition, report.direction, streak);

        let prev = self.records.last()
            .map(|r| r.alert_hash)
            .unwrap_or(GOSSIP_ALERT_GENESIS_HASH);

        let alert_hash = compute_alert_hash(
            &prev, report.epoch, alert_level,
            report.joint_condition, report.direction, streak,
        );

        self.records.push(GossipAlertRecord {
            epoch:                 report.epoch,
            alert_level,
            joint_condition:       report.joint_condition,
            direction:             report.direction,
            consecutive_declining: streak,
            alert_hash,
            prev_hash:             prev,
        });
        self.records.last().unwrap()
    }

    pub fn red_count(&self) -> usize {
        self.records.iter().filter(|r| r.alert_level == GossipAlertLevel::Red).count()
    }

    pub fn amber_count(&self) -> usize {
        self.records.iter().filter(|r| r.alert_level == GossipAlertLevel::Amber).count()
    }

    pub fn green_count(&self) -> usize {
        self.records.iter().filter(|r| r.alert_level == GossipAlertLevel::Green).count()
    }

    pub fn max_consecutive_declining(&self) -> u32 {
        self.records.iter().map(|r| r.consecutive_declining).max().unwrap_or(0)
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_ALERT_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != prev { return (false, Some(i)); }
            let expected = compute_alert_hash(
                &prev, r.epoch, r.alert_level,
                r.joint_condition, r.direction, r.consecutive_declining,
            );
            if r.alert_hash != expected { return (false, Some(i)); }
            prev = r.alert_hash;
        }
        (true, None)
    }
}

impl Default for GossipAlertLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::compaction_gossip_health_aggregator::{GossipHealthGrade, GossipJointCondition};
    use crate::compaction_gossip_momentum_tracker::GossipMomentumDir;

    fn make_report(epoch: u64, jc: GossipJointCondition, dir: GossipMomentumDir)
        -> GossipEpochReport
    {
        GossipEpochReport {
            epoch,
            joint_condition: jc,
            gossip_grade:    GossipHealthGrade::Healthy,
            total_delivered: 0,
            chains_valid:    true,
            direction:       dir,
            momentum_int:    0,
            window_size:     1,
            red_pct:         0,
            yellow_pct:      0,
            green_pct:       100,
            report_hash:     [0u8; 32],
            prev_hash:       [0u8; 32],
        }
    }

    // ── GossipAlertLevel classification ───────────────────────────────────────

    #[test]
    fn green_on_optimal_stable() {
        assert_eq!(
            GossipAlertLevel::classify(GossipJointCondition::Optimal, GossipMomentumDir::Stable, 0),
            GossipAlertLevel::Green
        );
    }

    #[test]
    fn green_on_nominal_improving() {
        assert_eq!(
            GossipAlertLevel::classify(GossipJointCondition::Nominal, GossipMomentumDir::Improving, 0),
            GossipAlertLevel::Green
        );
    }

    #[test]
    fn amber_on_degraded() {
        assert_eq!(
            GossipAlertLevel::classify(GossipJointCondition::Degraded, GossipMomentumDir::Stable, 0),
            GossipAlertLevel::Amber
        );
    }

    #[test]
    fn amber_on_declining_streak_2() {
        assert_eq!(
            GossipAlertLevel::classify(GossipJointCondition::Nominal, GossipMomentumDir::Declining, 2),
            GossipAlertLevel::Amber
        );
    }

    #[test]
    fn green_on_declining_streak_1() {
        assert_eq!(
            GossipAlertLevel::classify(GossipJointCondition::Nominal, GossipMomentumDir::Declining, 1),
            GossipAlertLevel::Green
        );
    }

    #[test]
    fn red_on_critical() {
        assert_eq!(
            GossipAlertLevel::classify(GossipJointCondition::Critical, GossipMomentumDir::Stable, 0),
            GossipAlertLevel::Red
        );
    }

    #[test]
    fn red_on_threshold_consecutive_declining() {
        assert_eq!(
            GossipAlertLevel::classify(
                GossipJointCondition::Nominal,
                GossipMomentumDir::Declining,
                GOSSIP_ALERT_DECLINING_THRESHOLD,
            ),
            GossipAlertLevel::Red
        );
    }

    // ── Streak tracking ───────────────────────────────────────────────────────

    #[test]
    fn streak_resets_on_non_declining() {
        let mut l = GossipAlertLog::new();
        l.append(&make_report(1, GossipJointCondition::Nominal, GossipMomentumDir::Declining));
        l.append(&make_report(2, GossipJointCondition::Nominal, GossipMomentumDir::Declining));
        l.append(&make_report(3, GossipJointCondition::Nominal, GossipMomentumDir::Stable));
        assert_eq!(l.latest().unwrap().consecutive_declining, 0);
    }

    #[test]
    fn streak_accumulates_correctly() {
        let mut l = GossipAlertLog::new();
        for i in 1u64..=4 {
            l.append(&make_report(i, GossipJointCondition::Nominal, GossipMomentumDir::Declining));
        }
        assert_eq!(l.latest().unwrap().consecutive_declining, 4);
    }

    #[test]
    fn amber_triggers_at_streak_2() {
        let mut l = GossipAlertLog::new();
        l.append(&make_report(1, GossipJointCondition::Nominal, GossipMomentumDir::Declining));
        assert_eq!(l.latest().unwrap().alert_level, GossipAlertLevel::Green); // streak=1
        l.append(&make_report(2, GossipJointCondition::Nominal, GossipMomentumDir::Declining));
        assert_eq!(l.latest().unwrap().alert_level, GossipAlertLevel::Amber); // streak=2
    }

    #[test]
    fn red_triggers_at_threshold() {
        let mut l = GossipAlertLog::new();
        for i in 1u64..=(GOSSIP_ALERT_DECLINING_THRESHOLD as u64) {
            l.append(&make_report(i, GossipJointCondition::Nominal, GossipMomentumDir::Declining));
        }
        assert_eq!(l.latest().unwrap().alert_level, GossipAlertLevel::Red);
    }

    // ── Log aggregation ───────────────────────────────────────────────────────

    #[test]
    fn counts_by_level() {
        let mut l = GossipAlertLog::new();
        l.append(&make_report(1, GossipJointCondition::Optimal,  GossipMomentumDir::Stable));
        l.append(&make_report(2, GossipJointCondition::Degraded, GossipMomentumDir::Stable));
        l.append(&make_report(3, GossipJointCondition::Critical, GossipMomentumDir::Stable));
        assert_eq!(l.green_count(), 1);
        assert_eq!(l.amber_count(), 1);
        assert_eq!(l.red_count(),   1);
    }

    #[test]
    fn max_consecutive_declining_tracked() {
        let mut l = GossipAlertLog::new();
        l.append(&make_report(1, GossipJointCondition::Nominal, GossipMomentumDir::Declining)); // 1
        l.append(&make_report(2, GossipJointCondition::Nominal, GossipMomentumDir::Declining)); // 2
        l.append(&make_report(3, GossipJointCondition::Nominal, GossipMomentumDir::Stable));    // 0
        l.append(&make_report(4, GossipJointCondition::Nominal, GossipMomentumDir::Declining)); // 1
        assert_eq!(l.max_consecutive_declining(), 2);
    }

    // ── Chain integrity ───────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let l = GossipAlertLog::new();
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_five_records_ok() {
        let mut l = GossipAlertLog::new();
        let dirs = [
            GossipMomentumDir::Stable,
            GossipMomentumDir::Declining,
            GossipMomentumDir::Declining,
            GossipMomentumDir::Improving,
            GossipMomentumDir::Stable,
        ];
        for (i, &dir) in dirs.iter().enumerate() {
            l.append(&make_report(i as u64 + 1, GossipJointCondition::Nominal, dir));
        }
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut l = GossipAlertLog::new();
        l.append(&make_report(1, GossipJointCondition::Optimal, GossipMomentumDir::Stable));
        l.append(&make_report(2, GossipJointCondition::Nominal, GossipMomentumDir::Stable));
        l.records[0].alert_hash[0] ^= 0xFF;
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn alert_hash_deterministic() {
        let mut l1 = GossipAlertLog::new();
        let mut l2 = GossipAlertLog::new();
        l1.append(&make_report(5, GossipJointCondition::Degraded, GossipMomentumDir::Declining));
        l2.append(&make_report(5, GossipJointCondition::Degraded, GossipMomentumDir::Declining));
        assert_eq!(l1.records[0].alert_hash, l2.records[0].alert_hash);
    }

    #[test]
    fn prev_hash_links_correctly() {
        let mut l = GossipAlertLog::new();
        l.append(&make_report(1, GossipJointCondition::Optimal, GossipMomentumDir::Stable));
        let h1 = l.records[0].alert_hash;
        l.append(&make_report(2, GossipJointCondition::Nominal, GossipMomentumDir::Stable));
        assert_eq!(l.records[1].prev_hash, h1);
    }
}
