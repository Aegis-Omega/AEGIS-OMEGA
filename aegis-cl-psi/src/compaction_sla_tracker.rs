//! Gate 343 — Compaction SLA Tracker (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Tracks per-epoch SLA compliance for the compaction subsystem.
//! An epoch is SLA-compliant if ALL three conditions hold:
//!   1. joint_condition ≤ Nominal (no Degraded or Critical)
//!   2. alert_level ≤ Amber (no Red alert)
//!   3. chains_valid == true
//!
//! SlaEpochRecord:
//!   epoch:              u64
//!   compliant:          bool
//!   joint_ok:           bool  — joint_condition ≤ Nominal
//!   alert_ok:           bool  — alert_level ≤ Amber
//!   chains_ok:          bool  — chains_valid == true
//!   violation_mask:     u8    — bit0=!joint_ok, bit1=!alert_ok, bit2=!chains_ok
//!   sla_hash:           [u8;32]
//!   prev_hash:          [u8;32]
//!
//! sla_hash = SHA-256(prev[32] ‖ epoch_be8 ‖ compliant_byte ‖ violation_mask)
//!
//! SlaTrackerLog: append(alert, report), compliance_rate() → u32 per-mille (0..1000),
//!   compliant_count(), violation_count(), streak_compliant(), verify_chain().

use sha2::{Sha256, Digest};
use crate::compaction_health_aggregator::JointCondition;
use crate::compaction_alert_classifier::{AlertLevel, CompactionAlertRecord};
use crate::compaction_epoch_report::CompactionEpochReport;

pub const SLA_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── SlaEpochRecord ───────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct SlaEpochRecord {
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

// ─── SlaTrackerLog ────────────────────────────────────────────────────────────

pub struct SlaTrackerLog {
    records: Vec<SlaEpochRecord>,
}

impl SlaTrackerLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self)      -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool  { self.records.is_empty() }
    pub fn records(&self)  -> &[SlaEpochRecord] { &self.records }
    pub fn latest(&self)   -> Option<&SlaEpochRecord> { self.records.last() }

    pub fn append(
        &mut self,
        alert:  &CompactionAlertRecord,
        report: &CompactionEpochReport,
    ) -> &SlaEpochRecord {
        let joint_ok  = report.joint_condition <= JointCondition::Nominal;
        let alert_ok  = alert.alert_level      <= AlertLevel::Amber;
        let chains_ok = report.chains_valid;
        let compliant = joint_ok && alert_ok && chains_ok;

        let violation_mask: u8 = (!joint_ok  as u8)       // bit 0
                                | ((!alert_ok  as u8) << 1) // bit 1
                                | ((!chains_ok as u8) << 2); // bit 2

        let prev = self.records.last()
            .map(|r| r.sla_hash)
            .unwrap_or(SLA_GENESIS_HASH);

        let sla_hash = compute_sla_hash(&prev, report.epoch, compliant, violation_mask);

        self.records.push(SlaEpochRecord {
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

    /// Number of compliant epochs.
    pub fn compliant_count(&self) -> usize {
        self.records.iter().filter(|r| r.compliant).count()
    }

    /// Number of non-compliant epochs.
    pub fn violation_count(&self) -> usize {
        self.records.iter().filter(|r| !r.compliant).count()
    }

    /// Compliance rate in per-mille (0..=1000). 1000 = 100%.
    pub fn compliance_rate(&self) -> u32 {
        if self.records.is_empty() {
            return 1000;
        }
        (self.compliant_count() as u32 * 1_000) / (self.records.len() as u32)
    }

    /// Length of current trailing compliant streak.
    pub fn streak_compliant(&self) -> usize {
        self.records.iter().rev().take_while(|r| r.compliant).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = SLA_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_sla_hash(&prev, r.epoch, r.compliant, r.violation_mask);
            if r.sla_hash != expected {
                return (false, Some(i));
            }
            prev = r.sla_hash;
        }
        (true, None)
    }
}

impl Default for SlaTrackerLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::compaction_health_aggregator::{CompactionHealthGrade, JointCondition};
    use crate::compaction_alert_classifier::{AlertLevel, ALERT_GENESIS_HASH};
    use crate::compaction_momentum_tracker::CompactionMomentumDir;

    fn make_alert(level: AlertLevel) -> CompactionAlertRecord {
        CompactionAlertRecord {
            epoch:                 1,
            alert_level:           level,
            joint_condition:       JointCondition::Nominal,
            direction:             CompactionMomentumDir::Stable,
            consecutive_declining: 0,
            alert_hash:            [0u8; 32],
            prev_hash:             ALERT_GENESIS_HASH,
        }
    }

    fn make_report(epoch: u64, jc: JointCondition, chains_valid: bool) -> CompactionEpochReport {
        CompactionEpochReport {
            epoch,
            joint_condition:  jc,
            compaction_grade: CompactionHealthGrade::Healthy,
            total_pruned:     0,
            chains_valid,
            direction:        CompactionMomentumDir::Stable,
            momentum_int:     0,
            window_size:      1,
            spsf_pct:         0,
            health_pct:       0,
            res_pct:          0,
            report_hash:      [0u8; 32],
            prev_hash:        [0u8; 32],
        }
    }

    // ── Compliance classification ─────────────────────────────────────────────

    #[test]
    fn compliant_when_all_ok() {
        let mut l = SlaTrackerLog::new();
        let r = l.append(&make_alert(AlertLevel::Green), &make_report(1, JointCondition::Optimal, true)).clone();
        assert!(r.compliant);
        assert!(r.joint_ok && r.alert_ok && r.chains_ok);
        assert_eq!(r.violation_mask, 0);
    }

    #[test]
    fn violation_on_critical_joint() {
        let mut l = SlaTrackerLog::new();
        let r = l.append(&make_alert(AlertLevel::Green), &make_report(1, JointCondition::Critical, true)).clone();
        assert!(!r.compliant);
        assert!(!r.joint_ok);
        assert_eq!(r.violation_mask & 0x01, 1);
    }

    #[test]
    fn violation_on_red_alert() {
        let mut l = SlaTrackerLog::new();
        let r = l.append(&make_alert(AlertLevel::Red), &make_report(1, JointCondition::Nominal, true)).clone();
        assert!(!r.compliant);
        assert!(!r.alert_ok);
        assert_eq!(r.violation_mask & 0x02, 2);
    }

    #[test]
    fn violation_on_broken_chains() {
        let mut l = SlaTrackerLog::new();
        let r = l.append(&make_alert(AlertLevel::Green), &make_report(1, JointCondition::Optimal, false)).clone();
        assert!(!r.compliant);
        assert!(!r.chains_ok);
        assert_eq!(r.violation_mask & 0x04, 4);
    }

    #[test]
    fn nominal_joint_is_compliant() {
        let mut l = SlaTrackerLog::new();
        let r = l.append(&make_alert(AlertLevel::Green), &make_report(1, JointCondition::Nominal, true)).clone();
        assert!(r.compliant);
    }

    #[test]
    fn degraded_joint_is_violation() {
        let mut l = SlaTrackerLog::new();
        let r = l.append(&make_alert(AlertLevel::Amber), &make_report(1, JointCondition::Degraded, true)).clone();
        assert!(!r.compliant);
    }

    #[test]
    fn amber_alert_is_compliant() {
        let mut l = SlaTrackerLog::new();
        let r = l.append(&make_alert(AlertLevel::Amber), &make_report(1, JointCondition::Nominal, true)).clone();
        assert!(r.compliant); // Amber is still within SLA
    }

    #[test]
    fn all_violations_set_mask() {
        let mut l = SlaTrackerLog::new();
        let r = l.append(&make_alert(AlertLevel::Red), &make_report(1, JointCondition::Critical, false)).clone();
        assert_eq!(r.violation_mask, 0x07); // bits 0,1,2 all set
    }

    // ── Aggregate stats ───────────────────────────────────────────────────────

    #[test]
    fn compliance_rate_empty_is_1000() {
        let l = SlaTrackerLog::new();
        assert_eq!(l.compliance_rate(), 1000);
    }

    #[test]
    fn compliance_rate_all_compliant() {
        let mut l = SlaTrackerLog::new();
        for i in 1u64..=4 {
            l.append(&make_alert(AlertLevel::Green), &make_report(i, JointCondition::Optimal, true));
        }
        assert_eq!(l.compliance_rate(), 1000);
    }

    #[test]
    fn compliance_rate_half() {
        let mut l = SlaTrackerLog::new();
        l.append(&make_alert(AlertLevel::Green), &make_report(1, JointCondition::Optimal, true));
        l.append(&make_alert(AlertLevel::Red),   &make_report(2, JointCondition::Critical, false));
        assert_eq!(l.compliance_rate(), 500);
    }

    #[test]
    fn streak_compliant_tracks_tail() {
        let mut l = SlaTrackerLog::new();
        l.append(&make_alert(AlertLevel::Red),   &make_report(1, JointCondition::Critical, false)); // violation
        l.append(&make_alert(AlertLevel::Green), &make_report(2, JointCondition::Optimal, true));  // ok
        l.append(&make_alert(AlertLevel::Green), &make_report(3, JointCondition::Optimal, true));  // ok
        assert_eq!(l.streak_compliant(), 2);
    }

    #[test]
    fn streak_resets_on_violation() {
        let mut l = SlaTrackerLog::new();
        l.append(&make_alert(AlertLevel::Green), &make_report(1, JointCondition::Optimal, true));
        l.append(&make_alert(AlertLevel::Green), &make_report(2, JointCondition::Optimal, true));
        l.append(&make_alert(AlertLevel::Red),   &make_report(3, JointCondition::Critical, false));
        assert_eq!(l.streak_compliant(), 0);
    }

    // ── Chain integrity ───────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let l = SlaTrackerLog::new();
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_five_records_ok() {
        let mut l = SlaTrackerLog::new();
        for i in 1u64..=5 {
            l.append(&make_alert(AlertLevel::Green), &make_report(i, JointCondition::Optimal, true));
        }
        let (ok, idx) = l.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut l = SlaTrackerLog::new();
        l.append(&make_alert(AlertLevel::Green), &make_report(1, JointCondition::Optimal, true));
        l.append(&make_alert(AlertLevel::Green), &make_report(2, JointCondition::Optimal, true));
        l.records[0].sla_hash[0] ^= 0xFF;
        let (ok, idx) = l.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn sla_hash_deterministic() {
        let mut l1 = SlaTrackerLog::new();
        let mut l2 = SlaTrackerLog::new();
        l1.append(&make_alert(AlertLevel::Amber), &make_report(3, JointCondition::Nominal, true));
        l2.append(&make_alert(AlertLevel::Amber), &make_report(3, JointCondition::Nominal, true));
        assert_eq!(l1.records[0].sla_hash, l2.records[0].sla_hash);
    }
}
