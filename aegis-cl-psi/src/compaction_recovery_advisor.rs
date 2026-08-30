//! Gate 342 — Compaction Recovery Advisor (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Produces hash-chained recovery recommendations from CompactionAlertRecord (341)
//! and CompactionEpochReport (340) signals.
//!
//! RecoveryPriority (ordered, highest first):
//!   ChainRepair      — chains_valid=false (structural integrity must be restored first)
//!   PruneReduction   — total_pruned high + direction=Declining (prune load increasing)
//!   MomentumStabilize — direction=Declining + consecutive_declining≥2 (trend intervention)
//!   MonitorOnly      — no acute condition; keep observing
//!
//! RecoveryAction:
//!   epoch:            u64
//!   alert_level:      AlertLevel
//!   priority:         RecoveryPriority
//!   reason_code:      u8              — bit-field: bit0=!chains_valid, bit1=high_prune,
//!                                        bit2=declining_trend
//!   recommendation:   RecoveryRecommendation (enum)
//!   action_hash:      [u8;32]
//!   prev_hash:        [u8;32]
//!
//! action_hash = SHA-256(prev[32] ‖ epoch_be8 ‖ alert_byte ‖ priority_byte
//!                        ‖ reason_code ‖ recommendation_byte)
//!
//! RecoveryRecommendation:
//!   RepairChains / ReducePruneLoad / StabilizeMomentum / ContinueMonitoring
//!
//! RecoveryAdvisorLog: append(alert, report), latest(), action_count_by(priority),
//!   chain_repair_count(), verify_chain().

use sha2::{Sha256, Digest};
use crate::compaction_alert_classifier::{AlertLevel, CompactionAlertRecord};
use crate::compaction_epoch_report::CompactionEpochReport;
use crate::compaction_momentum_tracker::CompactionMomentumDir;

pub const RECOVERY_GENESIS_HASH: [u8; 32] = [0u8; 32];

/// High-prune threshold for PruneReduction recommendation (total_pruned ≥ this per epoch).
pub const HIGH_PRUNE_THRESHOLD: u64 = 500;

// ─── RecoveryPriority ─────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
#[repr(u8)]
pub enum RecoveryPriority {
    ChainRepair       = 0,
    PruneReduction    = 1,
    MomentumStabilize = 2,
    MonitorOnly       = 3,
}

impl RecoveryPriority {
    pub fn as_u8(self) -> u8 { self as u8 }
}

// ─── RecoveryRecommendation ───────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum RecoveryRecommendation {
    RepairChains       = 0,
    ReducePruneLoad    = 1,
    StabilizeMomentum  = 2,
    ContinueMonitoring = 3,
}

impl RecoveryRecommendation {
    pub fn as_u8(self) -> u8 { self as u8 }
}

// ─── RecoveryAction ───────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct RecoveryAction {
    pub epoch:          u64,
    pub alert_level:    AlertLevel,
    pub priority:       RecoveryPriority,
    pub reason_code:    u8,
    pub recommendation: RecoveryRecommendation,
    pub action_hash:    [u8; 32],
    pub prev_hash:      [u8; 32],
}

fn compute_action_hash(
    prev:           &[u8; 32],
    epoch:          u64,
    alert:          AlertLevel,
    priority:       RecoveryPriority,
    reason_code:    u8,
    recommendation: RecoveryRecommendation,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update([alert.as_u8(), priority.as_u8(), reason_code, recommendation.as_u8()]);
    h.finalize().into()
}

fn advise(alert: &CompactionAlertRecord, report: &CompactionEpochReport)
    -> (RecoveryPriority, RecoveryRecommendation, u8)
{
    let chain_broken  = !report.chains_valid;
    let high_prune    = report.total_pruned >= HIGH_PRUNE_THRESHOLD;
    let declining     = report.direction == CompactionMomentumDir::Declining
                        && alert.consecutive_declining >= 2;

    let reason_code: u8 = (chain_broken  as u8)       // bit 0
                        | ((high_prune   as u8) << 1)  // bit 1
                        | ((declining    as u8) << 2); // bit 2

    if chain_broken {
        (RecoveryPriority::ChainRepair, RecoveryRecommendation::RepairChains, reason_code)
    } else if high_prune {
        (RecoveryPriority::PruneReduction, RecoveryRecommendation::ReducePruneLoad, reason_code)
    } else if declining {
        (RecoveryPriority::MomentumStabilize, RecoveryRecommendation::StabilizeMomentum, reason_code)
    } else {
        (RecoveryPriority::MonitorOnly, RecoveryRecommendation::ContinueMonitoring, reason_code)
    }
}

// ─── RecoveryAdvisorLog ───────────────────────────────────────────────────────

pub struct RecoveryAdvisorLog {
    actions: Vec<RecoveryAction>,
}

impl RecoveryAdvisorLog {
    pub fn new() -> Self { Self { actions: Vec::new() } }

    pub fn len(&self)      -> usize { self.actions.len() }
    pub fn is_empty(&self) -> bool  { self.actions.is_empty() }
    pub fn actions(&self)  -> &[RecoveryAction] { &self.actions }
    pub fn latest(&self)   -> Option<&RecoveryAction> { self.actions.last() }

    pub fn append(
        &mut self,
        alert:  &CompactionAlertRecord,
        report: &CompactionEpochReport,
    ) -> &RecoveryAction {
        let (priority, recommendation, reason_code) = advise(alert, report);

        let prev = self.actions.last()
            .map(|a| a.action_hash)
            .unwrap_or(RECOVERY_GENESIS_HASH);

        let action_hash = compute_action_hash(
            &prev,
            report.epoch,
            alert.alert_level,
            priority,
            reason_code,
            recommendation,
        );

        self.actions.push(RecoveryAction {
            epoch: report.epoch,
            alert_level: alert.alert_level,
            priority,
            reason_code,
            recommendation,
            action_hash,
            prev_hash: prev,
        });
        self.actions.last().unwrap()
    }

    pub fn action_count_by(&self, priority: RecoveryPriority) -> usize {
        self.actions.iter().filter(|a| a.priority == priority).count()
    }

    pub fn chain_repair_count(&self) -> usize {
        self.action_count_by(RecoveryPriority::ChainRepair)
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = RECOVERY_GENESIS_HASH;
        for (i, a) in self.actions.iter().enumerate() {
            if a.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_action_hash(
                &prev,
                a.epoch,
                a.alert_level,
                a.priority,
                a.reason_code,
                a.recommendation,
            );
            if a.action_hash != expected {
                return (false, Some(i));
            }
            prev = a.action_hash;
        }
        (true, None)
    }
}

impl Default for RecoveryAdvisorLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::compaction_health_aggregator::{CompactionHealthGrade, JointCondition};
    use crate::compaction_alert_classifier::{AlertLevel, ALERT_GENESIS_HASH};
    use crate::compaction_momentum_tracker::CompactionMomentumDir;

    fn make_alert(epoch: u64, level: AlertLevel, dir: CompactionMomentumDir,
                  jc: JointCondition, consecutive: u32) -> CompactionAlertRecord {
        CompactionAlertRecord {
            epoch,
            alert_level:           level,
            joint_condition:       jc,
            direction:             dir,
            consecutive_declining: consecutive,
            alert_hash:            [0u8; 32],
            prev_hash:             ALERT_GENESIS_HASH,
        }
    }

    fn make_report(epoch: u64, chains_valid: bool, total_pruned: u64,
                   dir: CompactionMomentumDir) -> CompactionEpochReport {
        CompactionEpochReport {
            epoch,
            joint_condition:  JointCondition::Nominal,
            compaction_grade: CompactionHealthGrade::Healthy,
            total_pruned,
            chains_valid,
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

    // ── Priority routing ──────────────────────────────────────────────────────

    #[test]
    fn chain_repair_on_broken_chains() {
        let mut l = RecoveryAdvisorLog::new();
        let alert = make_alert(1, AlertLevel::Red, CompactionMomentumDir::Stable, JointCondition::Nominal, 0);
        let report = make_report(1, false, 0, CompactionMomentumDir::Stable);
        let a = l.append(&alert, &report).clone();
        assert_eq!(a.priority, RecoveryPriority::ChainRepair);
        assert_eq!(a.recommendation, RecoveryRecommendation::RepairChains);
        assert_eq!(a.reason_code & 0x01, 1); // bit 0 set
    }

    #[test]
    fn prune_reduction_on_high_prune() {
        let mut l = RecoveryAdvisorLog::new();
        let alert = make_alert(1, AlertLevel::Amber, CompactionMomentumDir::Stable, JointCondition::Nominal, 0);
        let report = make_report(1, true, HIGH_PRUNE_THRESHOLD, CompactionMomentumDir::Stable);
        let a = l.append(&alert, &report).clone();
        assert_eq!(a.priority, RecoveryPriority::PruneReduction);
        assert_eq!(a.recommendation, RecoveryRecommendation::ReducePruneLoad);
        assert_eq!(a.reason_code & 0x02, 2); // bit 1 set
    }

    #[test]
    fn momentum_stabilize_on_declining_streak() {
        let mut l = RecoveryAdvisorLog::new();
        let alert = make_alert(1, AlertLevel::Amber, CompactionMomentumDir::Declining, JointCondition::Nominal, 2);
        let report = make_report(1, true, 0, CompactionMomentumDir::Declining);
        let a = l.append(&alert, &report).clone();
        assert_eq!(a.priority, RecoveryPriority::MomentumStabilize);
        assert_eq!(a.recommendation, RecoveryRecommendation::StabilizeMomentum);
    }

    #[test]
    fn monitor_only_when_all_clear() {
        let mut l = RecoveryAdvisorLog::new();
        let alert = make_alert(1, AlertLevel::Green, CompactionMomentumDir::Stable, JointCondition::Optimal, 0);
        let report = make_report(1, true, 100, CompactionMomentumDir::Stable);
        let a = l.append(&alert, &report).clone();
        assert_eq!(a.priority, RecoveryPriority::MonitorOnly);
        assert_eq!(a.recommendation, RecoveryRecommendation::ContinueMonitoring);
        assert_eq!(a.reason_code, 0);
    }

    #[test]
    fn chain_repair_beats_high_prune() {
        let mut l = RecoveryAdvisorLog::new();
        let alert = make_alert(1, AlertLevel::Red, CompactionMomentumDir::Stable, JointCondition::Nominal, 0);
        let report = make_report(1, false, HIGH_PRUNE_THRESHOLD + 100, CompactionMomentumDir::Stable);
        let a = l.append(&alert, &report).clone();
        assert_eq!(a.priority, RecoveryPriority::ChainRepair);
        assert_eq!(a.reason_code & 0x03, 0x03); // both bits set
    }

    #[test]
    fn no_momentum_stabilize_at_streak_1() {
        let mut l = RecoveryAdvisorLog::new();
        let alert = make_alert(1, AlertLevel::Green, CompactionMomentumDir::Declining, JointCondition::Nominal, 1);
        let report = make_report(1, true, 0, CompactionMomentumDir::Declining);
        let a = l.append(&alert, &report).clone();
        assert_eq!(a.priority, RecoveryPriority::MonitorOnly);
    }

    // ── Log aggregation ───────────────────────────────────────────────────────

    #[test]
    fn action_count_by_priority() {
        let mut l = RecoveryAdvisorLog::new();
        let alert_green = make_alert(1, AlertLevel::Green, CompactionMomentumDir::Stable, JointCondition::Optimal, 0);
        let alert_red   = make_alert(2, AlertLevel::Red,   CompactionMomentumDir::Stable, JointCondition::Nominal, 0);
        l.append(&alert_green, &make_report(1, true, 0, CompactionMomentumDir::Stable));
        l.append(&alert_red,   &make_report(2, false, 0, CompactionMomentumDir::Stable));
        l.append(&alert_red,   &make_report(3, false, 0, CompactionMomentumDir::Stable));
        assert_eq!(l.chain_repair_count(), 2);
        assert_eq!(l.action_count_by(RecoveryPriority::MonitorOnly), 1);
    }

    // ── Chain integrity ───────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let l = RecoveryAdvisorLog::new();
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_five_actions_ok() {
        let mut l = RecoveryAdvisorLog::new();
        let alert = make_alert(1, AlertLevel::Green, CompactionMomentumDir::Stable, JointCondition::Optimal, 0);
        for i in 1u64..=5 {
            l.append(&alert, &make_report(i, true, 0, CompactionMomentumDir::Stable));
        }
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut l = RecoveryAdvisorLog::new();
        let alert = make_alert(1, AlertLevel::Green, CompactionMomentumDir::Stable, JointCondition::Optimal, 0);
        l.append(&alert, &make_report(1, true, 0, CompactionMomentumDir::Stable));
        l.append(&alert, &make_report(2, true, 0, CompactionMomentumDir::Stable));
        l.actions[0].action_hash[0] ^= 0xFF;
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn action_hash_deterministic() {
        let mut l1 = RecoveryAdvisorLog::new();
        let mut l2 = RecoveryAdvisorLog::new();
        let alert = make_alert(7, AlertLevel::Amber, CompactionMomentumDir::Declining, JointCondition::Degraded, 2);
        let report = make_report(7, true, 0, CompactionMomentumDir::Declining);
        l1.append(&alert, &report);
        l2.append(&alert, &report);
        assert_eq!(l1.actions[0].action_hash, l2.actions[0].action_hash);
    }

    #[test]
    fn prev_hash_links_correctly() {
        let mut l = RecoveryAdvisorLog::new();
        let alert = make_alert(1, AlertLevel::Green, CompactionMomentumDir::Stable, JointCondition::Optimal, 0);
        l.append(&alert, &make_report(1, true, 0, CompactionMomentumDir::Stable));
        let h1 = l.actions[0].action_hash;
        l.append(&alert, &make_report(2, true, 0, CompactionMomentumDir::Stable));
        assert_eq!(l.actions[1].prev_hash, h1);
    }
}
