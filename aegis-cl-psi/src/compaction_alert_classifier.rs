//! Gate 341 — Compaction Alert Classifier (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Translates CompactionEpochReport signals (Gate 340) into a three-level alert
//! state, with hysteresis to suppress transient flapping.
//!
//! AlertLevel:
//!   Green  — joint_condition ≤ Nominal AND direction ≠ Declining
//!   Amber  — joint_condition == Degraded OR (direction == Declining AND consecutive_declining ≥ 2)
//!   Red    — joint_condition == Critical OR consecutive_declining ≥ ALERT_DECLINING_THRESHOLD
//!
//! ALERT_DECLINING_THRESHOLD = 3 (three consecutive declining epochs triggers Red regardless)
//!
//! CompactionAlertRecord:
//!   epoch:                 u64
//!   alert_level:           AlertLevel
//!   joint_condition:       JointCondition
//!   direction:             CompactionMomentumDir
//!   consecutive_declining: u32   — streak length (reset to 0 on non-declining)
//!   alert_hash:            [u8;32]
//!   prev_hash:             [u8;32]
//!
//! alert_hash = SHA-256(prev[32] ‖ epoch_be8 ‖ alert_byte ‖ joint_byte
//!                        ‖ dir_byte ‖ consecutive_be4)
//!
//! CompactionAlertLog: append(report), latest(), red_count(), amber_count(),
//!   green_count(), max_consecutive_declining(), verify_chain().

use sha2::{Sha256, Digest};
use crate::compaction_health_aggregator::JointCondition;
use crate::compaction_momentum_tracker::CompactionMomentumDir;
use crate::compaction_epoch_report::CompactionEpochReport;

pub const ALERT_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const ALERT_DECLINING_THRESHOLD: u32 = 3;

// ─── AlertLevel ───────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
#[repr(u8)]
pub enum AlertLevel {
    Green = 0,
    Amber = 1,
    Red   = 2,
}

impl AlertLevel {
    pub fn as_u8(self) -> u8 { self as u8 }

    fn classify(
        jc:                   JointCondition,
        dir:                  CompactionMomentumDir,
        consecutive_declining: u32,
    ) -> Self {
        // Red: Critical condition or prolonged decline
        if jc == JointCondition::Critical || consecutive_declining >= ALERT_DECLINING_THRESHOLD {
            return Self::Red;
        }
        // Amber: Degraded condition or sustained decline onset
        if jc == JointCondition::Degraded
            || (dir == CompactionMomentumDir::Declining && consecutive_declining >= 2)
        {
            return Self::Amber;
        }
        // Green: everything else
        Self::Green
    }
}

// ─── CompactionAlertRecord ────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct CompactionAlertRecord {
    pub epoch:                 u64,
    pub alert_level:           AlertLevel,
    pub joint_condition:       JointCondition,
    pub direction:             CompactionMomentumDir,
    pub consecutive_declining: u32,
    pub alert_hash:            [u8; 32],
    pub prev_hash:             [u8; 32],
}

fn compute_alert_hash(
    prev:                 &[u8; 32],
    epoch:                u64,
    alert:                AlertLevel,
    joint:                JointCondition,
    dir:                  CompactionMomentumDir,
    consecutive_declining: u32,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update([alert.as_u8(), joint.as_u8(), dir.as_u8()]);
    h.update(consecutive_declining.to_be_bytes());
    h.finalize().into()
}

// ─── CompactionAlertLog ───────────────────────────────────────────────────────

pub struct CompactionAlertLog {
    records:              Vec<CompactionAlertRecord>,
    consecutive_declining: u32,
}

impl CompactionAlertLog {
    pub fn new() -> Self {
        Self {
            records:               Vec::new(),
            consecutive_declining: 0,
        }
    }

    pub fn len(&self)     -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool { self.records.is_empty() }
    pub fn records(&self)  -> &[CompactionAlertRecord] { &self.records }
    pub fn latest(&self)   -> Option<&CompactionAlertRecord> { self.records.last() }

    pub fn append(&mut self, report: &CompactionEpochReport) -> &CompactionAlertRecord {
        // Update streak counter
        if report.direction == CompactionMomentumDir::Declining {
            self.consecutive_declining = self.consecutive_declining.saturating_add(1);
        } else {
            self.consecutive_declining = 0;
        }
        let streak = self.consecutive_declining;

        let alert_level = AlertLevel::classify(report.joint_condition, report.direction, streak);

        let prev = self.records.last()
            .map(|r| r.alert_hash)
            .unwrap_or(ALERT_GENESIS_HASH);

        let alert_hash = compute_alert_hash(
            &prev,
            report.epoch,
            alert_level,
            report.joint_condition,
            report.direction,
            streak,
        );

        self.records.push(CompactionAlertRecord {
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
        self.records.iter().filter(|r| r.alert_level == AlertLevel::Red).count()
    }

    pub fn amber_count(&self) -> usize {
        self.records.iter().filter(|r| r.alert_level == AlertLevel::Amber).count()
    }

    pub fn green_count(&self) -> usize {
        self.records.iter().filter(|r| r.alert_level == AlertLevel::Green).count()
    }

    pub fn max_consecutive_declining(&self) -> u32 {
        self.records.iter().map(|r| r.consecutive_declining).max().unwrap_or(0)
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = ALERT_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_alert_hash(
                &prev,
                r.epoch,
                r.alert_level,
                r.joint_condition,
                r.direction,
                r.consecutive_declining,
            );
            if r.alert_hash != expected {
                return (false, Some(i));
            }
            prev = r.alert_hash;
        }
        (true, None)
    }
}

impl Default for CompactionAlertLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::compaction_health_aggregator::{
        CompactionHealthGrade, JointCondition,
    };
    use crate::compaction_momentum_tracker::{CompactionMomentumDir, MOMENTUM_GENESIS_HASH};

    fn make_report(
        epoch:      u64,
        jc:         JointCondition,
        dir:        CompactionMomentumDir,
    ) -> CompactionEpochReport {
        CompactionEpochReport {
            epoch,
            joint_condition:  jc,
            compaction_grade: CompactionHealthGrade::Healthy,
            total_pruned:     0,
            chains_valid:     true,
            direction:        dir,
            momentum_int:     0,
            window_size:      1,
            spsf_pct:         0,
            health_pct:       0,
            res_pct:          0,
            report_hash:      [0u8; 32],
            prev_hash:        [0u8; 32],
        }
    }

    // ── AlertLevel classification ──────────────────────────────────────────────

    #[test]
    fn green_on_optimal_stable() {
        let level = AlertLevel::classify(JointCondition::Optimal, CompactionMomentumDir::Stable, 0);
        assert_eq!(level, AlertLevel::Green);
    }

    #[test]
    fn green_on_nominal_improving() {
        let level = AlertLevel::classify(JointCondition::Nominal, CompactionMomentumDir::Improving, 0);
        assert_eq!(level, AlertLevel::Green);
    }

    #[test]
    fn amber_on_degraded() {
        let level = AlertLevel::classify(JointCondition::Degraded, CompactionMomentumDir::Stable, 0);
        assert_eq!(level, AlertLevel::Amber);
    }

    #[test]
    fn amber_on_declining_streak_2() {
        let level = AlertLevel::classify(JointCondition::Nominal, CompactionMomentumDir::Declining, 2);
        assert_eq!(level, AlertLevel::Amber);
    }

    #[test]
    fn green_on_declining_streak_1() {
        let level = AlertLevel::classify(JointCondition::Nominal, CompactionMomentumDir::Declining, 1);
        assert_eq!(level, AlertLevel::Green);
    }

    #[test]
    fn red_on_critical() {
        let level = AlertLevel::classify(JointCondition::Critical, CompactionMomentumDir::Stable, 0);
        assert_eq!(level, AlertLevel::Red);
    }

    #[test]
    fn red_on_threshold_consecutive_declining() {
        let level = AlertLevel::classify(
            JointCondition::Nominal,
            CompactionMomentumDir::Declining,
            ALERT_DECLINING_THRESHOLD,
        );
        assert_eq!(level, AlertLevel::Red);
    }

    // ── Streak tracking ───────────────────────────────────────────────────────

    #[test]
    fn streak_resets_on_non_declining() {
        let mut l = CompactionAlertLog::new();
        l.append(&make_report(1, JointCondition::Nominal, CompactionMomentumDir::Declining));
        l.append(&make_report(2, JointCondition::Nominal, CompactionMomentumDir::Declining));
        l.append(&make_report(3, JointCondition::Nominal, CompactionMomentumDir::Stable));
        let r = l.latest().unwrap();
        assert_eq!(r.consecutive_declining, 0);
    }

    #[test]
    fn streak_accumulates_correctly() {
        let mut l = CompactionAlertLog::new();
        for i in 1u64..=4 {
            l.append(&make_report(i, JointCondition::Nominal, CompactionMomentumDir::Declining));
        }
        assert_eq!(l.latest().unwrap().consecutive_declining, 4);
    }

    #[test]
    fn amber_triggers_at_streak_2() {
        let mut l = CompactionAlertLog::new();
        l.append(&make_report(1, JointCondition::Nominal, CompactionMomentumDir::Declining));
        assert_eq!(l.latest().unwrap().alert_level, AlertLevel::Green); // streak=1
        l.append(&make_report(2, JointCondition::Nominal, CompactionMomentumDir::Declining));
        assert_eq!(l.latest().unwrap().alert_level, AlertLevel::Amber); // streak=2
    }

    #[test]
    fn red_triggers_at_threshold() {
        let mut l = CompactionAlertLog::new();
        for i in 1u64..=(ALERT_DECLINING_THRESHOLD as u64) {
            l.append(&make_report(i, JointCondition::Nominal, CompactionMomentumDir::Declining));
        }
        assert_eq!(l.latest().unwrap().alert_level, AlertLevel::Red);
    }

    // ── Log aggregation ───────────────────────────────────────────────────────

    #[test]
    fn counts_by_level() {
        let mut l = CompactionAlertLog::new();
        l.append(&make_report(1, JointCondition::Optimal,  CompactionMomentumDir::Stable));    // green
        l.append(&make_report(2, JointCondition::Degraded, CompactionMomentumDir::Stable));   // amber
        l.append(&make_report(3, JointCondition::Critical, CompactionMomentumDir::Stable));   // red
        assert_eq!(l.green_count(), 1);
        assert_eq!(l.amber_count(), 1);
        assert_eq!(l.red_count(), 1);
    }

    #[test]
    fn max_consecutive_declining_tracked() {
        let mut l = CompactionAlertLog::new();
        l.append(&make_report(1, JointCondition::Nominal, CompactionMomentumDir::Declining)); // 1
        l.append(&make_report(2, JointCondition::Nominal, CompactionMomentumDir::Declining)); // 2
        l.append(&make_report(3, JointCondition::Nominal, CompactionMomentumDir::Stable));    // 0
        l.append(&make_report(4, JointCondition::Nominal, CompactionMomentumDir::Declining)); // 1
        assert_eq!(l.max_consecutive_declining(), 2);
    }

    // ── Chain integrity ───────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let l = CompactionAlertLog::new();
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_five_records_ok() {
        let mut l = CompactionAlertLog::new();
        let dirs = [
            CompactionMomentumDir::Stable,
            CompactionMomentumDir::Declining,
            CompactionMomentumDir::Declining,
            CompactionMomentumDir::Improving,
            CompactionMomentumDir::Stable,
        ];
        for (i, &dir) in dirs.iter().enumerate() {
            l.append(&make_report(i as u64 + 1, JointCondition::Nominal, dir));
        }
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut l = CompactionAlertLog::new();
        l.append(&make_report(1, JointCondition::Optimal, CompactionMomentumDir::Stable));
        l.append(&make_report(2, JointCondition::Nominal, CompactionMomentumDir::Stable));
        l.records[0].alert_hash[0] ^= 0xFF;
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn alert_hash_deterministic() {
        let mut l1 = CompactionAlertLog::new();
        let mut l2 = CompactionAlertLog::new();
        l1.append(&make_report(5, JointCondition::Degraded, CompactionMomentumDir::Declining));
        l2.append(&make_report(5, JointCondition::Degraded, CompactionMomentumDir::Declining));
        assert_eq!(l1.records[0].alert_hash, l2.records[0].alert_hash);
    }

    #[test]
    fn prev_hash_links_correctly() {
        let mut l = CompactionAlertLog::new();
        l.append(&make_report(1, JointCondition::Optimal, CompactionMomentumDir::Stable));
        let h1 = l.records[0].alert_hash;
        l.append(&make_report(2, JointCondition::Nominal, CompactionMomentumDir::Stable));
        assert_eq!(l.records[1].prev_hash, h1);
    }
}
