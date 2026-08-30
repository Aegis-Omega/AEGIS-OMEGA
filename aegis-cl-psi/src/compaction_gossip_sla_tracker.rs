//! Gate 365 — Compaction Gossip SLA Tracker (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks per-epoch SLA compliance for the gossip subsystem. Mirrors Gate 343.
//! An epoch is SLA-compliant iff ALL three conditions hold:
//!   1. joint_condition ≤ Nominal
//!   2. alert_level ≤ Amber
//!   3. chains_valid == true
//!
//! GossipSlaRecord:
//!   epoch:          u64
//!   compliant:      bool
//!   joint_ok:       bool  — joint_condition ≤ Nominal
//!   alert_ok:       bool  — alert_level ≤ Amber
//!   chains_ok:      bool  — chains_valid == true
//!   violation_mask: u8    — bit0=!joint_ok, bit1=!alert_ok, bit2=!chains_ok
//!   sla_hash:       [u8;32]
//!   prev_hash:      [u8;32]
//!
//! sla_hash = SHA-256(prev[32] ‖ epoch_be8 ‖ compliant_byte ‖ violation_mask)
//!
//! GossipSlaTrackerLog: append(alert, report), compliance_rate() → u32 per-mille,
//!   compliant_count(), violation_count(), streak_compliant(), verify_chain().

use sha2::{Sha256, Digest};
use crate::compaction_gossip_health_aggregator::GossipJointCondition;
use crate::compaction_gossip_alert_classifier::{GossipAlertLevel, GossipAlertRecord};
use crate::compaction_gossip_epoch_report::GossipEpochReport;

pub const GOSSIP_SLA_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── GossipSlaRecord ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipSlaRecord {
    pub epoch:          u64,
    pub compliant:      bool,
    pub joint_ok:       bool,
    pub alert_ok:       bool,
    pub chains_ok:      bool,
    pub violation_mask: u8,
    pub sla_hash:       [u8; 32],
    pub prev_hash:      [u8; 32],
}

fn compute_sla_hash(
    prev:           &[u8; 32],
    epoch:          u64,
    compliant:      bool,
    violation_mask: u8,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update([compliant as u8, violation_mask]);
    h.finalize().into()
}

// ─── GossipSlaTrackerLog ──────────────────────────────────────────────────────

pub struct GossipSlaTrackerLog {
    records: Vec<GossipSlaRecord>,
}

impl GossipSlaTrackerLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[GossipSlaRecord] { &self.records }
    pub fn latest(&self)   -> Option<&GossipSlaRecord> { self.records.last() }

    pub fn append(
        &mut self,
        alert:  &GossipAlertRecord,
        report: &GossipEpochReport,
    ) -> &GossipSlaRecord {
        let joint_ok  = report.joint_condition <= GossipJointCondition::Nominal;
        let alert_ok  = alert.alert_level      <= GossipAlertLevel::Amber;
        let chains_ok = report.chains_valid;
        let compliant = joint_ok && alert_ok && chains_ok;

        let violation_mask: u8 = (!joint_ok  as u8)
                                | ((!alert_ok  as u8) << 1)
                                | ((!chains_ok as u8) << 2);

        let prev = self.records.last()
            .map(|r| r.sla_hash)
            .unwrap_or(GOSSIP_SLA_GENESIS_HASH);

        let sla_hash = compute_sla_hash(&prev, report.epoch, compliant, violation_mask);

        self.records.push(GossipSlaRecord {
            epoch: report.epoch,
            compliant,
            joint_ok,
            alert_ok,
            chains_ok,
            violation_mask,
            sla_hash,
            prev_hash: prev,
        });
        self.records.last().unwrap()
    }

    pub fn compliant_count(&self) -> usize {
        self.records.iter().filter(|r| r.compliant).count()
    }

    pub fn violation_count(&self) -> usize {
        self.records.iter().filter(|r| !r.compliant).count()
    }

    /// Compliance rate in per-mille (0..=1000). 1000 = 100%.
    pub fn compliance_rate(&self) -> u32 {
        if self.records.is_empty() { return 1000; }
        (self.compliant_count() as u32 * 1_000) / (self.records.len() as u32)
    }

    /// Length of trailing compliant streak.
    pub fn streak_compliant(&self) -> usize {
        self.records.iter().rev().take_while(|r| r.compliant).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_SLA_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != prev { return (false, Some(i)); }
            let expected = compute_sla_hash(&prev, r.epoch, r.compliant, r.violation_mask);
            if r.sla_hash != expected { return (false, Some(i)); }
            prev = r.sla_hash;
        }
        (true, None)
    }
}

impl Default for GossipSlaTrackerLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::compaction_gossip_health_aggregator::{GossipHealthGrade, GossipJointCondition};
    use crate::compaction_gossip_alert_classifier::{GossipAlertLevel, GOSSIP_ALERT_GENESIS_HASH};
    use crate::compaction_gossip_momentum_tracker::GossipMomentumDir;

    fn make_alert(level: GossipAlertLevel) -> GossipAlertRecord {
        GossipAlertRecord {
            epoch:                 1,
            alert_level:           level,
            joint_condition:       GossipJointCondition::Nominal,
            direction:             GossipMomentumDir::Stable,
            consecutive_declining: 0,
            alert_hash:            [0u8; 32],
            prev_hash:             GOSSIP_ALERT_GENESIS_HASH,
        }
    }

    fn make_report(epoch: u64, jc: GossipJointCondition, chains_valid: bool) -> GossipEpochReport {
        GossipEpochReport {
            epoch,
            joint_condition: jc,
            gossip_grade:    GossipHealthGrade::Healthy,
            total_delivered: 100,
            chains_valid,
            direction:       GossipMomentumDir::Stable,
            momentum_int:    0,
            window_size:     1,
            red_pct:         0,
            yellow_pct:      0,
            green_pct:       100,
            report_hash:     [0u8; 32],
            prev_hash:       [0u8; 32],
        }
    }

    // ── Compliance classification ─────────────────────────────────────────────

    #[test]
    fn compliant_when_all_ok() {
        let mut l = GossipSlaTrackerLog::new();
        let r = l.append(&make_alert(GossipAlertLevel::Green),
                         &make_report(1, GossipJointCondition::Optimal, true)).clone();
        assert!(r.compliant);
        assert!(r.joint_ok && r.alert_ok && r.chains_ok);
        assert_eq!(r.violation_mask, 0);
    }

    #[test]
    fn violation_on_critical_joint() {
        let mut l = GossipSlaTrackerLog::new();
        let r = l.append(&make_alert(GossipAlertLevel::Green),
                         &make_report(1, GossipJointCondition::Critical, true)).clone();
        assert!(!r.compliant);
        assert!(!r.joint_ok);
        assert_eq!(r.violation_mask & 0x01, 1);
    }

    #[test]
    fn violation_on_red_alert() {
        let mut l = GossipSlaTrackerLog::new();
        let r = l.append(&make_alert(GossipAlertLevel::Red),
                         &make_report(1, GossipJointCondition::Nominal, true)).clone();
        assert!(!r.compliant);
        assert!(!r.alert_ok);
        assert_eq!(r.violation_mask & 0x02, 2);
    }

    #[test]
    fn violation_on_broken_chains() {
        let mut l = GossipSlaTrackerLog::new();
        let r = l.append(&make_alert(GossipAlertLevel::Green),
                         &make_report(1, GossipJointCondition::Optimal, false)).clone();
        assert!(!r.compliant);
        assert!(!r.chains_ok);
        assert_eq!(r.violation_mask & 0x04, 4);
    }

    #[test]
    fn nominal_joint_is_compliant() {
        let mut l = GossipSlaTrackerLog::new();
        let r = l.append(&make_alert(GossipAlertLevel::Green),
                         &make_report(1, GossipJointCondition::Nominal, true)).clone();
        assert!(r.compliant);
    }

    #[test]
    fn degraded_joint_is_violation() {
        let mut l = GossipSlaTrackerLog::new();
        let r = l.append(&make_alert(GossipAlertLevel::Amber),
                         &make_report(1, GossipJointCondition::Degraded, true)).clone();
        assert!(!r.compliant);
    }

    #[test]
    fn amber_alert_is_compliant() {
        let mut l = GossipSlaTrackerLog::new();
        let r = l.append(&make_alert(GossipAlertLevel::Amber),
                         &make_report(1, GossipJointCondition::Nominal, true)).clone();
        assert!(r.compliant);
    }

    #[test]
    fn all_violations_set_mask() {
        let mut l = GossipSlaTrackerLog::new();
        let r = l.append(&make_alert(GossipAlertLevel::Red),
                         &make_report(1, GossipJointCondition::Critical, false)).clone();
        assert_eq!(r.violation_mask, 0x07);
    }

    // ── Aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn compliance_rate_empty_is_1000() {
        assert_eq!(GossipSlaTrackerLog::new().compliance_rate(), 1000);
    }

    #[test]
    fn compliance_rate_all_compliant() {
        let mut l = GossipSlaTrackerLog::new();
        for i in 1u64..=4 {
            l.append(&make_alert(GossipAlertLevel::Green), &make_report(i, GossipJointCondition::Optimal, true));
        }
        assert_eq!(l.compliance_rate(), 1000);
    }

    #[test]
    fn compliance_rate_half() {
        let mut l = GossipSlaTrackerLog::new();
        l.append(&make_alert(GossipAlertLevel::Green), &make_report(1, GossipJointCondition::Optimal, true));
        l.append(&make_alert(GossipAlertLevel::Red),   &make_report(2, GossipJointCondition::Critical, false));
        assert_eq!(l.compliance_rate(), 500);
    }

    #[test]
    fn streak_compliant_tracks_tail() {
        let mut l = GossipSlaTrackerLog::new();
        l.append(&make_alert(GossipAlertLevel::Red),   &make_report(1, GossipJointCondition::Critical, false));
        l.append(&make_alert(GossipAlertLevel::Green), &make_report(2, GossipJointCondition::Optimal, true));
        l.append(&make_alert(GossipAlertLevel::Green), &make_report(3, GossipJointCondition::Optimal, true));
        assert_eq!(l.streak_compliant(), 2);
    }

    #[test]
    fn streak_resets_on_violation() {
        let mut l = GossipSlaTrackerLog::new();
        l.append(&make_alert(GossipAlertLevel::Green), &make_report(1, GossipJointCondition::Optimal, true));
        l.append(&make_alert(GossipAlertLevel::Green), &make_report(2, GossipJointCondition::Optimal, true));
        l.append(&make_alert(GossipAlertLevel::Red),   &make_report(3, GossipJointCondition::Critical, false));
        assert_eq!(l.streak_compliant(), 0);
    }

    // ── Chain integrity ───────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let (ok, idx) = GossipSlaTrackerLog::new().verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_five_records_ok() {
        let mut l = GossipSlaTrackerLog::new();
        for i in 1u64..=5 {
            l.append(&make_alert(GossipAlertLevel::Green), &make_report(i, GossipJointCondition::Optimal, true));
        }
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut l = GossipSlaTrackerLog::new();
        l.append(&make_alert(GossipAlertLevel::Green), &make_report(1, GossipJointCondition::Optimal, true));
        l.append(&make_alert(GossipAlertLevel::Green), &make_report(2, GossipJointCondition::Optimal, true));
        l.records[0].sla_hash[0] ^= 0xFF;
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn sla_hash_deterministic() {
        let mut l1 = GossipSlaTrackerLog::new();
        let mut l2 = GossipSlaTrackerLog::new();
        l1.append(&make_alert(GossipAlertLevel::Amber), &make_report(3, GossipJointCondition::Nominal, true));
        l2.append(&make_alert(GossipAlertLevel::Amber), &make_report(3, GossipJointCondition::Nominal, true));
        assert_eq!(l1.records[0].sla_hash, l2.records[0].sla_hash);
    }
}
