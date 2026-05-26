//! Gate 347 — Compaction Dashboard Aggregator (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Unifies all compaction subsystem signals into a single per-epoch
//! DashboardFrame for operator consumption and higher-level integration.
//!
//! DashboardCondition — overall epoch health:
//!   Thriving  — SLA compliant AND trend Improving AND alert Green
//!   Stable    — SLA compliant AND trend Stable AND alert ≤ Amber
//!   Concerning — SLA non-compliant OR trend Volatile OR alert Amber
//!   Critical   — alert Red OR trend Degrading
//!
//! DashboardFrame:
//!   epoch:              u64
//!   condition:          DashboardCondition
//!   alert_level:        AlertLevel        (from Gate 341)
//!   trend_class:        TrendClass        (from Gate 346)
//!   sla_compliant:      bool              (from Gate 343)
//!   compliance_rate:    u32               — per-mille snapshot (0..1000)
//!   improvement_count:  u32               — within trend window
//!   degradation_count:  u32               — within trend window
//!   frame_hash:         [u8;32]
//!   prev_hash:          [u8;32]
//!
//! frame_hash = SHA-256(prev[32] ‖ epoch_be8 ‖ condition_byte
//!                        ‖ alert_byte ‖ trend_byte ‖ sla_byte
//!                        ‖ compliance_rate_be4
//!                        ‖ improvement_be4 ‖ degradation_be4)
//!
//! CompactionDashboard: record(alert, trend, sla_record, compliance_rate),
//!   thriving_count(), stable_count(), concerning_count(), critical_count(),
//!   latest(), verify_chain().

use sha2::{Sha256, Digest};
use crate::compaction_alert_classifier::AlertLevel;
use crate::compaction_trend_analyzer::TrendClass;

pub const DASHBOARD_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── DashboardCondition ───────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
#[repr(u8)]
pub enum DashboardCondition {
    Thriving   = 0,
    Stable     = 1,
    Concerning = 2,
    Critical   = 3,
}

impl DashboardCondition {
    pub fn as_u8(self) -> u8 { self as u8 }

    fn classify(
        alert:         AlertLevel,
        trend:         TrendClass,
        sla_compliant: bool,
    ) -> Self {
        // Critical: Red alert or actively degrading trend
        if alert == AlertLevel::Red || trend == TrendClass::Degrading {
            return Self::Critical;
        }
        // Concerning: SLA violation, volatile trend, or Amber alert
        if !sla_compliant || trend == TrendClass::Volatile || alert == AlertLevel::Amber {
            return Self::Concerning;
        }
        // Thriving: compliant + improving + green
        if sla_compliant && trend == TrendClass::Improving && alert == AlertLevel::Green {
            return Self::Thriving;
        }
        // Stable: compliant, stable trend, green alert
        Self::Stable
    }
}

// ─── DashboardFrame ───────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct DashboardFrame {
    pub epoch:              u64,
    pub condition:          DashboardCondition,
    pub alert_level:        AlertLevel,
    pub trend_class:        TrendClass,
    pub sla_compliant:      bool,
    pub compliance_rate:    u32,
    pub improvement_count:  u32,
    pub degradation_count:  u32,
    pub frame_hash:         [u8; 32],
    pub prev_hash:          [u8; 32],
}

fn compute_frame_hash(
    prev:               &[u8; 32],
    epoch:              u64,
    condition:          DashboardCondition,
    alert:              AlertLevel,
    trend:              TrendClass,
    sla_compliant:      bool,
    compliance_rate:    u32,
    improvement_count:  u32,
    degradation_count:  u32,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch.to_be_bytes());
    h.update([condition.as_u8(), alert.as_u8(), trend.as_u8(), sla_compliant as u8]);
    h.update(compliance_rate.to_be_bytes());
    h.update(improvement_count.to_be_bytes());
    h.update(degradation_count.to_be_bytes());
    h.finalize().into()
}

// ─── CompactionDashboard ──────────────────────────────────────────────────────

pub struct CompactionDashboard {
    frames: Vec<DashboardFrame>,
}

impl CompactionDashboard {
    pub fn new() -> Self { Self { frames: Vec::new() } }

    pub fn len(&self)      -> usize { self.frames.len() }
    pub fn is_empty(&self) -> bool  { self.frames.is_empty() }
    pub fn frames(&self)   -> &[DashboardFrame] { &self.frames }
    pub fn latest(&self)   -> Option<&DashboardFrame> { self.frames.last() }

    /// Record a new dashboard frame for the given epoch.
    /// `alert`           — from CompactionAlertLog::latest()
    /// `trend`           — from TrendAnalyzerLog::latest()
    /// `sla_compliant`   — from SlaTrackerLog::latest().compliant
    /// `compliance_rate` — from SlaTrackerLog::compliance_rate()
    /// `improvement_count` / `degradation_count` — from TrendRecord
    pub fn record(
        &mut self,
        epoch:              u64,
        alert:              AlertLevel,
        trend:              TrendClass,
        sla_compliant:      bool,
        compliance_rate:    u32,
        improvement_count:  u32,
        degradation_count:  u32,
    ) -> &DashboardFrame {
        let condition = DashboardCondition::classify(alert, trend, sla_compliant);

        let prev = self.frames.last()
            .map(|f| f.frame_hash)
            .unwrap_or(DASHBOARD_GENESIS_HASH);

        let frame_hash = compute_frame_hash(
            &prev,
            epoch,
            condition,
            alert,
            trend,
            sla_compliant,
            compliance_rate,
            improvement_count,
            degradation_count,
        );

        self.frames.push(DashboardFrame {
            epoch,
            condition,
            alert_level: alert,
            trend_class: trend,
            sla_compliant,
            compliance_rate,
            improvement_count,
            degradation_count,
            frame_hash,
            prev_hash: prev,
        });
        self.frames.last().unwrap()
    }

    pub fn thriving_count(&self) -> usize {
        self.frames.iter().filter(|f| f.condition == DashboardCondition::Thriving).count()
    }

    pub fn stable_count(&self) -> usize {
        self.frames.iter().filter(|f| f.condition == DashboardCondition::Stable).count()
    }

    pub fn concerning_count(&self) -> usize {
        self.frames.iter().filter(|f| f.condition == DashboardCondition::Concerning).count()
    }

    pub fn critical_count(&self) -> usize {
        self.frames.iter().filter(|f| f.condition == DashboardCondition::Critical).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = DASHBOARD_GENESIS_HASH;
        for (i, f) in self.frames.iter().enumerate() {
            if f.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_frame_hash(
                &prev,
                f.epoch,
                f.condition,
                f.alert_level,
                f.trend_class,
                f.sla_compliant,
                f.compliance_rate,
                f.improvement_count,
                f.degradation_count,
            );
            if f.frame_hash != expected {
                return (false, Some(i));
            }
            prev = f.frame_hash;
        }
        (true, None)
    }
}

impl Default for CompactionDashboard {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn record(
        dashboard: &mut CompactionDashboard,
        epoch: u64,
        alert: AlertLevel,
        trend: TrendClass,
        compliant: bool,
    ) -> DashboardFrame {
        dashboard.record(epoch, alert, trend, compliant, 1000, 0, 0).clone()
    }

    // ── DashboardCondition classification ─────────────────────────────────────

    #[test]
    fn thriving_on_green_improving_compliant() {
        let c = DashboardCondition::classify(AlertLevel::Green, TrendClass::Improving, true);
        assert_eq!(c, DashboardCondition::Thriving);
    }

    #[test]
    fn stable_on_green_stable_compliant() {
        let c = DashboardCondition::classify(AlertLevel::Green, TrendClass::Stable, true);
        assert_eq!(c, DashboardCondition::Stable);
    }

    #[test]
    fn critical_on_red_alert() {
        let c = DashboardCondition::classify(AlertLevel::Red, TrendClass::Stable, true);
        assert_eq!(c, DashboardCondition::Critical);
    }

    #[test]
    fn critical_on_degrading_trend() {
        let c = DashboardCondition::classify(AlertLevel::Green, TrendClass::Degrading, true);
        assert_eq!(c, DashboardCondition::Critical);
    }

    #[test]
    fn concerning_on_sla_violation() {
        let c = DashboardCondition::classify(AlertLevel::Green, TrendClass::Stable, false);
        assert_eq!(c, DashboardCondition::Concerning);
    }

    #[test]
    fn concerning_on_volatile_trend() {
        let c = DashboardCondition::classify(AlertLevel::Green, TrendClass::Volatile, true);
        assert_eq!(c, DashboardCondition::Concerning);
    }

    #[test]
    fn concerning_on_amber_alert() {
        let c = DashboardCondition::classify(AlertLevel::Amber, TrendClass::Stable, true);
        assert_eq!(c, DashboardCondition::Concerning);
    }

    #[test]
    fn critical_beats_sla_violation() {
        // Red alert + SLA violation → Critical (not Concerning)
        let c = DashboardCondition::classify(AlertLevel::Red, TrendClass::Stable, false);
        assert_eq!(c, DashboardCondition::Critical);
    }

    // ── Dashboard record and aggregate ────────────────────────────────────────

    #[test]
    fn record_thriving_frame() {
        let mut d = CompactionDashboard::new();
        let f = record(&mut d, 1, AlertLevel::Green, TrendClass::Improving, true);
        assert_eq!(f.condition, DashboardCondition::Thriving);
        assert_eq!(f.epoch, 1);
        assert!(f.sla_compliant);
    }

    #[test]
    fn aggregate_counts_correct() {
        let mut d = CompactionDashboard::new();
        record(&mut d, 1, AlertLevel::Green,  TrendClass::Improving, true);  // Thriving
        record(&mut d, 2, AlertLevel::Green,  TrendClass::Stable,    true);  // Stable
        record(&mut d, 3, AlertLevel::Amber,  TrendClass::Stable,    true);  // Concerning
        record(&mut d, 4, AlertLevel::Red,    TrendClass::Stable,    false); // Critical
        assert_eq!(d.thriving_count(), 1);
        assert_eq!(d.stable_count(), 1);
        assert_eq!(d.concerning_count(), 1);
        assert_eq!(d.critical_count(), 1);
    }

    #[test]
    fn compliance_rate_stored() {
        let mut d = CompactionDashboard::new();
        d.record(1, AlertLevel::Green, TrendClass::Stable, true, 750, 2, 1);
        assert_eq!(d.latest().unwrap().compliance_rate, 750);
        assert_eq!(d.latest().unwrap().improvement_count, 2);
        assert_eq!(d.latest().unwrap().degradation_count, 1);
    }

    // ── Chain integrity ───────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let d = CompactionDashboard::new();
        let (ok, idx) = d.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_five_frames_ok() {
        let mut d = CompactionDashboard::new();
        for i in 1u64..=5 {
            record(&mut d, i, AlertLevel::Green, TrendClass::Stable, true);
        }
        let (ok, idx) = d.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut d = CompactionDashboard::new();
        record(&mut d, 1, AlertLevel::Green, TrendClass::Stable, true);
        record(&mut d, 2, AlertLevel::Green, TrendClass::Stable, true);
        d.frames[0].frame_hash[0] ^= 0xFF;
        let (ok, idx) = d.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn frame_hash_deterministic() {
        let mut d1 = CompactionDashboard::new();
        let mut d2 = CompactionDashboard::new();
        record(&mut d1, 5, AlertLevel::Amber, TrendClass::Volatile, false);
        record(&mut d2, 5, AlertLevel::Amber, TrendClass::Volatile, false);
        assert_eq!(d1.frames[0].frame_hash, d2.frames[0].frame_hash);
    }

    #[test]
    fn prev_hash_links_correctly() {
        let mut d = CompactionDashboard::new();
        record(&mut d, 1, AlertLevel::Green, TrendClass::Stable, true);
        let h0 = d.frames[0].frame_hash;
        record(&mut d, 2, AlertLevel::Green, TrendClass::Stable, true);
        assert_eq!(d.frames[1].prev_hash, h0);
    }
}
