//! Gate 364 — Compaction Gossip Recovery Advisor (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Produces hash-chained recovery recommendations from GossipAlertRecord (363)
//! and GossipEpochReport (362) signals. Mirrors Gate 342 for the gossip subsystem.
//!
//! GossipRecoveryPriority (highest first):
//!   ChainRepair       — chains_valid=false
//!   DeliveryRecovery  — red_pct >= GOSSIP_HIGH_RED_PCT_THRESHOLD
//!   MomentumStabilize — direction=Declining AND consecutive_declining≥2
//!   MonitorOnly       — no acute condition
//!
//! GOSSIP_HIGH_RED_PCT_THRESHOLD = 50
//!
//! reason_code (bit-field):
//!   bit0 = !chains_valid
//!   bit1 = high_red_pct
//!   bit2 = declining_trend (consecutive_declining≥2)
//!
//! GossipRecoveryRecommendation:
//!   RepairChains / RestoreDelivery / StabilizeMomentum / ContinueMonitoring
//!
//! action_hash = SHA-256(prev[32] ‖ epoch_be8 ‖ alert_byte ‖ priority_byte
//!                        ‖ reason_code ‖ recommendation_byte)
//!
//! GossipRecoveryAdvisorLog: append(alert, report), action_count_by(priority),
//!   chain_repair_count(), verify_chain().

use sha2::{Sha256, Digest};
use crate::compaction_gossip_alert_classifier::{GossipAlertLevel, GossipAlertRecord};
use crate::compaction_gossip_epoch_report::GossipEpochReport;
use crate::compaction_gossip_momentum_tracker::GossipMomentumDir;

pub const GOSSIP_RECOVERY_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const GOSSIP_HIGH_RED_PCT_THRESHOLD: u8 = 50;

// ─── GossipRecoveryPriority ───────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
#[repr(u8)]
pub enum GossipRecoveryPriority {
    ChainRepair       = 0,
    DeliveryRecovery  = 1,
    MomentumStabilize = 2,
    MonitorOnly       = 3,
}

impl GossipRecoveryPriority {
    pub fn as_u8(self) -> u8 { self as u8 }
}

// ─── GossipRecoveryRecommendation ─────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum GossipRecoveryRecommendation {
    RepairChains       = 0,
    RestoreDelivery    = 1,
    StabilizeMomentum  = 2,
    ContinueMonitoring = 3,
}

impl GossipRecoveryRecommendation {
    pub fn as_u8(self) -> u8 { self as u8 }
}

// ─── GossipRecoveryAction ─────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipRecoveryAction {
    pub epoch:          u64,
    pub alert_level:    GossipAlertLevel,
    pub priority:       GossipRecoveryPriority,
    pub reason_code:    u8,
    pub recommendation: GossipRecoveryRecommendation,
    pub action_hash:    [u8; 32],
    pub prev_hash:      [u8; 32],
}

fn compute_action_hash(
    prev:           &[u8; 32],
    epoch:          u64,
    alert:          GossipAlertLevel,
    priority:       GossipRecoveryPriority,
    reason_code:    u8,
    recommendation: GossipRecoveryRecommendation,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update([alert.as_u8(), priority.as_u8(), reason_code, recommendation.as_u8()]);
    h.finalize().into()
}

fn advise(alert: &GossipAlertRecord, report: &GossipEpochReport)
    -> (GossipRecoveryPriority, GossipRecoveryRecommendation, u8)
{
    let chain_broken  = !report.chains_valid;
    let high_red      = report.red_pct >= GOSSIP_HIGH_RED_PCT_THRESHOLD;
    let declining     = report.direction == GossipMomentumDir::Declining
                        && alert.consecutive_declining >= 2;

    let reason_code: u8 = (chain_broken as u8)
                        | ((high_red   as u8) << 1)
                        | ((declining  as u8) << 2);

    if chain_broken {
        (GossipRecoveryPriority::ChainRepair, GossipRecoveryRecommendation::RepairChains, reason_code)
    } else if high_red {
        (GossipRecoveryPriority::DeliveryRecovery, GossipRecoveryRecommendation::RestoreDelivery, reason_code)
    } else if declining {
        (GossipRecoveryPriority::MomentumStabilize, GossipRecoveryRecommendation::StabilizeMomentum, reason_code)
    } else {
        (GossipRecoveryPriority::MonitorOnly, GossipRecoveryRecommendation::ContinueMonitoring, reason_code)
    }
}

// ─── GossipRecoveryAdvisorLog ─────────────────────────────────────────────────

pub struct GossipRecoveryAdvisorLog {
    actions: Vec<GossipRecoveryAction>,
}

impl GossipRecoveryAdvisorLog {
    pub fn new() -> Self { Self { actions: Vec::new() } }

    pub fn len(&self)      -> usize { self.actions.len() }
    pub fn is_empty(&self) -> bool  { self.actions.is_empty() }
    pub fn actions(&self)  -> &[GossipRecoveryAction] { &self.actions }
    pub fn latest(&self)   -> Option<&GossipRecoveryAction> { self.actions.last() }

    pub fn append(
        &mut self,
        alert:  &GossipAlertRecord,
        report: &GossipEpochReport,
    ) -> &GossipRecoveryAction {
        let (priority, recommendation, reason_code) = advise(alert, report);

        let prev = self.actions.last()
            .map(|a| a.action_hash)
            .unwrap_or(GOSSIP_RECOVERY_GENESIS_HASH);

        let action_hash = compute_action_hash(
            &prev, report.epoch, alert.alert_level, priority, reason_code, recommendation,
        );

        self.actions.push(GossipRecoveryAction {
            epoch:          report.epoch,
            alert_level:    alert.alert_level,
            priority,
            reason_code,
            recommendation,
            action_hash,
            prev_hash:      prev,
        });
        self.actions.last().unwrap()
    }

    pub fn action_count_by(&self, priority: GossipRecoveryPriority) -> usize {
        self.actions.iter().filter(|a| a.priority == priority).count()
    }

    pub fn chain_repair_count(&self) -> usize {
        self.action_count_by(GossipRecoveryPriority::ChainRepair)
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_RECOVERY_GENESIS_HASH;
        for (i, a) in self.actions.iter().enumerate() {
            if a.prev_hash != prev { return (false, Some(i)); }
            let expected = compute_action_hash(
                &prev, a.epoch, a.alert_level, a.priority, a.reason_code, a.recommendation,
            );
            if a.action_hash != expected { return (false, Some(i)); }
            prev = a.action_hash;
        }
        (true, None)
    }
}

impl Default for GossipRecoveryAdvisorLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::compaction_gossip_health_aggregator::{GossipHealthGrade, GossipJointCondition};
    use crate::compaction_gossip_alert_classifier::GOSSIP_ALERT_GENESIS_HASH;
    use crate::compaction_gossip_momentum_tracker::GossipMomentumDir;

    fn make_alert(epoch: u64, level: GossipAlertLevel, dir: GossipMomentumDir,
                  consecutive: u32) -> GossipAlertRecord
    {
        GossipAlertRecord {
            epoch,
            alert_level:           level,
            joint_condition:       GossipJointCondition::Nominal,
            direction:             dir,
            consecutive_declining: consecutive,
            alert_hash:            [0u8; 32],
            prev_hash:             GOSSIP_ALERT_GENESIS_HASH,
        }
    }

    fn make_report(epoch: u64, chains_valid: bool, red_pct: u8, dir: GossipMomentumDir)
        -> GossipEpochReport
    {
        GossipEpochReport {
            epoch,
            joint_condition: GossipJointCondition::Nominal,
            gossip_grade:    GossipHealthGrade::Healthy,
            total_delivered: 100,
            chains_valid,
            direction:       dir,
            momentum_int:    0,
            window_size:     1,
            red_pct,
            yellow_pct:      10,
            green_pct:       100u8.saturating_sub(red_pct).saturating_sub(10),
            report_hash:     [0u8; 32],
            prev_hash:       [0u8; 32],
        }
    }

    // ── Priority routing ──────────────────────────────────────────────────────

    #[test]
    fn chain_repair_on_broken_chains() {
        let mut l = GossipRecoveryAdvisorLog::new();
        let alert  = make_alert(1, GossipAlertLevel::Red,   GossipMomentumDir::Stable, 0);
        let report = make_report(1, false, 0, GossipMomentumDir::Stable);
        let a = l.append(&alert, &report).clone();
        assert_eq!(a.priority, GossipRecoveryPriority::ChainRepair);
        assert_eq!(a.recommendation, GossipRecoveryRecommendation::RepairChains);
        assert_eq!(a.reason_code & 0x01, 1);
    }

    #[test]
    fn delivery_recovery_on_high_red_pct() {
        let mut l = GossipRecoveryAdvisorLog::new();
        let alert  = make_alert(1, GossipAlertLevel::Amber, GossipMomentumDir::Stable, 0);
        let report = make_report(1, true, GOSSIP_HIGH_RED_PCT_THRESHOLD, GossipMomentumDir::Stable);
        let a = l.append(&alert, &report).clone();
        assert_eq!(a.priority, GossipRecoveryPriority::DeliveryRecovery);
        assert_eq!(a.recommendation, GossipRecoveryRecommendation::RestoreDelivery);
        assert_eq!(a.reason_code & 0x02, 2);
    }

    #[test]
    fn momentum_stabilize_on_declining_streak() {
        let mut l = GossipRecoveryAdvisorLog::new();
        let alert  = make_alert(1, GossipAlertLevel::Amber, GossipMomentumDir::Declining, 2);
        let report = make_report(1, true, 0, GossipMomentumDir::Declining);
        let a = l.append(&alert, &report).clone();
        assert_eq!(a.priority, GossipRecoveryPriority::MomentumStabilize);
        assert_eq!(a.recommendation, GossipRecoveryRecommendation::StabilizeMomentum);
    }

    #[test]
    fn monitor_only_when_all_clear() {
        let mut l = GossipRecoveryAdvisorLog::new();
        let alert  = make_alert(1, GossipAlertLevel::Green, GossipMomentumDir::Stable, 0);
        let report = make_report(1, true, 0, GossipMomentumDir::Stable);
        let a = l.append(&alert, &report).clone();
        assert_eq!(a.priority, GossipRecoveryPriority::MonitorOnly);
        assert_eq!(a.recommendation, GossipRecoveryRecommendation::ContinueMonitoring);
        assert_eq!(a.reason_code, 0);
    }

    #[test]
    fn chain_repair_beats_high_red_pct() {
        let mut l = GossipRecoveryAdvisorLog::new();
        let alert  = make_alert(1, GossipAlertLevel::Red, GossipMomentumDir::Stable, 0);
        let report = make_report(1, false, 100, GossipMomentumDir::Stable);
        let a = l.append(&alert, &report).clone();
        assert_eq!(a.priority, GossipRecoveryPriority::ChainRepair);
        assert_eq!(a.reason_code & 0x03, 0x03);
    }

    #[test]
    fn no_momentum_stabilize_at_streak_1() {
        let mut l = GossipRecoveryAdvisorLog::new();
        let alert  = make_alert(1, GossipAlertLevel::Green, GossipMomentumDir::Declining, 1);
        let report = make_report(1, true, 0, GossipMomentumDir::Declining);
        let a = l.append(&alert, &report).clone();
        assert_eq!(a.priority, GossipRecoveryPriority::MonitorOnly);
    }

    // ── Log aggregation ───────────────────────────────────────────────────────

    #[test]
    fn action_count_by_priority() {
        let mut l = GossipRecoveryAdvisorLog::new();
        let ag = make_alert(1, GossipAlertLevel::Green, GossipMomentumDir::Stable, 0);
        let ar = make_alert(2, GossipAlertLevel::Red,   GossipMomentumDir::Stable, 0);
        l.append(&ag, &make_report(1, true,  0, GossipMomentumDir::Stable));
        l.append(&ar, &make_report(2, false, 0, GossipMomentumDir::Stable));
        l.append(&ar, &make_report(3, false, 0, GossipMomentumDir::Stable));
        assert_eq!(l.chain_repair_count(), 2);
        assert_eq!(l.action_count_by(GossipRecoveryPriority::MonitorOnly), 1);
    }

    // ── Chain integrity ───────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let l = GossipRecoveryAdvisorLog::new();
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_five_actions_ok() {
        let mut l = GossipRecoveryAdvisorLog::new();
        let alert = make_alert(1, GossipAlertLevel::Green, GossipMomentumDir::Stable, 0);
        for i in 1u64..=5 {
            l.append(&alert, &make_report(i, true, 0, GossipMomentumDir::Stable));
        }
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut l = GossipRecoveryAdvisorLog::new();
        let alert = make_alert(1, GossipAlertLevel::Green, GossipMomentumDir::Stable, 0);
        l.append(&alert, &make_report(1, true, 0, GossipMomentumDir::Stable));
        l.append(&alert, &make_report(2, true, 0, GossipMomentumDir::Stable));
        l.actions[0].action_hash[0] ^= 0xFF;
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn action_hash_deterministic() {
        let mut l1 = GossipRecoveryAdvisorLog::new();
        let mut l2 = GossipRecoveryAdvisorLog::new();
        let alert  = make_alert(7, GossipAlertLevel::Amber, GossipMomentumDir::Declining, 2);
        let report = make_report(7, true, 0, GossipMomentumDir::Declining);
        l1.append(&alert, &report);
        l2.append(&alert, &report);
        assert_eq!(l1.actions[0].action_hash, l2.actions[0].action_hash);
    }

    #[test]
    fn prev_hash_links_correctly() {
        let mut l = GossipRecoveryAdvisorLog::new();
        let alert = make_alert(1, GossipAlertLevel::Green, GossipMomentumDir::Stable, 0);
        l.append(&alert, &make_report(1, true, 0, GossipMomentumDir::Stable));
        let h1 = l.actions[0].action_hash;
        l.append(&alert, &make_report(2, true, 0, GossipMomentumDir::Stable));
        assert_eq!(l.actions[1].prev_hash, h1);
    }
}
