//! Gate 369 — Compaction Gossip Dashboard Aggregator (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Unifies all gossip subsystem signals into a single per-epoch
//! GossipDashboardFrame for operator consumption and higher-level integration.
//! Mirrors Gate 347 for the gossip subsystem.
//!
//! GossipDashboardCondition — overall epoch health:
//!   Thriving   — SLA compliant AND trend Improving AND alert Green
//!   Stable     — SLA compliant AND trend Stable AND alert ≤ Amber
//!   Concerning — SLA non-compliant OR trend Volatile OR alert Amber
//!   Critical   — alert Red OR trend Degrading
//!
//! GossipDashboardFrame:
//!   epoch:              u64
//!   condition:          GossipDashboardCondition
//!   alert_level:        GossipAlertLevel     (from Gate 363)
//!   trend_class:        GossipTrendClass     (from Gate 368)
//!   sla_compliant:      bool                 (from Gate 365)
//!   compliance_rate:    u32                  — per-mille snapshot (0..1000)
//!   improvement_count:  u32                  — within trend window
//!   degradation_count:  u32                  — within trend window
//!   frame_hash:         [u8;32]
//!   prev_hash:          [u8;32]
//!
//! frame_hash = SHA-256(prev[32] ‖ epoch_be8 ‖ condition_byte
//!                        ‖ alert_byte ‖ trend_byte ‖ sla_byte
//!                        ‖ compliance_rate_be4
//!                        ‖ improvement_be4 ‖ degradation_be4)
//!
//! GossipDashboard: record(alert, trend, sla_compliant, compliance_rate,
//!   improvement_count, degradation_count), thriving_count(), stable_count(),
//!   concerning_count(), critical_count(), latest(), verify_chain().

use sha2::{Sha256, Digest};
use crate::compaction_gossip_alert_classifier::GossipAlertLevel;
use crate::compaction_gossip_trend_analyzer::GossipTrendClass;

pub const GOSSIP_DASHBOARD_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── GossipDashboardCondition ─────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
#[repr(u8)]
pub enum GossipDashboardCondition {
    Thriving   = 0,
    Stable     = 1,
    Concerning = 2,
    Critical   = 3,
}

impl GossipDashboardCondition {
    pub fn as_u8(self) -> u8 { self as u8 }

    fn classify(
        alert:         GossipAlertLevel,
        trend:         GossipTrendClass,
        sla_compliant: bool,
    ) -> Self {
        // Critical: Red alert or actively degrading trend
        if alert == GossipAlertLevel::Red || trend == GossipTrendClass::Degrading {
            return Self::Critical;
        }
        // Concerning: SLA violation, volatile trend, or Amber alert
        if !sla_compliant || trend == GossipTrendClass::Volatile || alert == GossipAlertLevel::Amber {
            return Self::Concerning;
        }
        // Thriving: compliant + improving + green
        if sla_compliant && trend == GossipTrendClass::Improving && alert == GossipAlertLevel::Green {
            return Self::Thriving;
        }
        // Stable: compliant, stable trend, green alert
        Self::Stable
    }
}

// ─── GossipDashboardFrame ─────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct GossipDashboardFrame {
    pub epoch:              u64,
    pub condition:          GossipDashboardCondition,
    pub alert_level:        GossipAlertLevel,
    pub trend_class:        GossipTrendClass,
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
    condition:          GossipDashboardCondition,
    alert:              GossipAlertLevel,
    trend:              GossipTrendClass,
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

// ─── GossipDashboard ──────────────────────────────────────────────────────────

pub struct GossipDashboard {
    frames: Vec<GossipDashboardFrame>,
}

impl GossipDashboard {
    pub fn new() -> Self { Self { frames: Vec::new() } }

    pub fn len(&self)      -> usize { self.frames.len() }
    pub fn is_empty(&self) -> bool  { self.frames.is_empty() }
    pub fn frames(&self)   -> &[GossipDashboardFrame] { &self.frames }
    pub fn latest(&self)   -> Option<&GossipDashboardFrame> { self.frames.last() }

    /// Record a new dashboard frame for the given epoch.
    pub fn record(
        &mut self,
        epoch:              u64,
        alert:              GossipAlertLevel,
        trend:              GossipTrendClass,
        sla_compliant:      bool,
        compliance_rate:    u32,
        improvement_count:  u32,
        degradation_count:  u32,
    ) -> &GossipDashboardFrame {
        let condition = GossipDashboardCondition::classify(alert, trend, sla_compliant);

        let prev = self.frames.last()
            .map(|f| f.frame_hash)
            .unwrap_or(GOSSIP_DASHBOARD_GENESIS_HASH);

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

        self.frames.push(GossipDashboardFrame {
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
        self.frames.iter().filter(|f| f.condition == GossipDashboardCondition::Thriving).count()
    }

    pub fn stable_count(&self) -> usize {
        self.frames.iter().filter(|f| f.condition == GossipDashboardCondition::Stable).count()
    }

    pub fn concerning_count(&self) -> usize {
        self.frames.iter().filter(|f| f.condition == GossipDashboardCondition::Concerning).count()
    }

    pub fn critical_count(&self) -> usize {
        self.frames.iter().filter(|f| f.condition == GossipDashboardCondition::Critical).count()
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = GOSSIP_DASHBOARD_GENESIS_HASH;
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

impl Default for GossipDashboard {
    fn default() -> Self { Self::new() }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn rec(
        d: &mut GossipDashboard,
        epoch: u64,
        alert: GossipAlertLevel,
        trend: GossipTrendClass,
        compliant: bool,
    ) -> GossipDashboardFrame {
        d.record(epoch, alert, trend, compliant, 1000, 0, 0).clone()
    }

    // ── GossipDashboardCondition classification ───────────────────────────────

    #[test]
    fn thriving_on_green_improving_compliant() {
        let c = GossipDashboardCondition::classify(
            GossipAlertLevel::Green, GossipTrendClass::Improving, true);
        assert_eq!(c, GossipDashboardCondition::Thriving);
    }

    #[test]
    fn stable_on_green_stable_compliant() {
        let c = GossipDashboardCondition::classify(
            GossipAlertLevel::Green, GossipTrendClass::Stable, true);
        assert_eq!(c, GossipDashboardCondition::Stable);
    }

    #[test]
    fn critical_on_red_alert() {
        let c = GossipDashboardCondition::classify(
            GossipAlertLevel::Red, GossipTrendClass::Stable, true);
        assert_eq!(c, GossipDashboardCondition::Critical);
    }

    #[test]
    fn critical_on_degrading_trend() {
        let c = GossipDashboardCondition::classify(
            GossipAlertLevel::Green, GossipTrendClass::Degrading, true);
        assert_eq!(c, GossipDashboardCondition::Critical);
    }

    #[test]
    fn concerning_on_sla_violation() {
        let c = GossipDashboardCondition::classify(
            GossipAlertLevel::Green, GossipTrendClass::Stable, false);
        assert_eq!(c, GossipDashboardCondition::Concerning);
    }

    #[test]
    fn concerning_on_volatile_trend() {
        let c = GossipDashboardCondition::classify(
            GossipAlertLevel::Green, GossipTrendClass::Volatile, true);
        assert_eq!(c, GossipDashboardCondition::Concerning);
    }

    #[test]
    fn concerning_on_amber_alert() {
        let c = GossipDashboardCondition::classify(
            GossipAlertLevel::Amber, GossipTrendClass::Stable, true);
        assert_eq!(c, GossipDashboardCondition::Concerning);
    }

    #[test]
    fn critical_beats_sla_violation() {
        let c = GossipDashboardCondition::classify(
            GossipAlertLevel::Red, GossipTrendClass::Stable, false);
        assert_eq!(c, GossipDashboardCondition::Critical);
    }

    // ── Dashboard record and aggregate ────────────────────────────────────────

    #[test]
    fn record_thriving_frame() {
        let mut d = GossipDashboard::new();
        let f = rec(&mut d, 1, GossipAlertLevel::Green, GossipTrendClass::Improving, true);
        assert_eq!(f.condition, GossipDashboardCondition::Thriving);
        assert_eq!(f.epoch, 1);
        assert!(f.sla_compliant);
    }

    #[test]
    fn aggregate_counts_correct() {
        let mut d = GossipDashboard::new();
        rec(&mut d, 1, GossipAlertLevel::Green, GossipTrendClass::Improving, true);  // Thriving
        rec(&mut d, 2, GossipAlertLevel::Green, GossipTrendClass::Stable,    true);  // Stable
        rec(&mut d, 3, GossipAlertLevel::Amber, GossipTrendClass::Stable,    true);  // Concerning
        rec(&mut d, 4, GossipAlertLevel::Red,   GossipTrendClass::Stable,    false); // Critical
        assert_eq!(d.thriving_count(), 1);
        assert_eq!(d.stable_count(),   1);
        assert_eq!(d.concerning_count(), 1);
        assert_eq!(d.critical_count(), 1);
    }

    #[test]
    fn compliance_rate_stored() {
        let mut d = GossipDashboard::new();
        d.record(1, GossipAlertLevel::Green, GossipTrendClass::Stable, true, 750, 2, 1);
        assert_eq!(d.latest().unwrap().compliance_rate, 750);
        assert_eq!(d.latest().unwrap().improvement_count, 2);
        assert_eq!(d.latest().unwrap().degradation_count, 1);
    }

    // ── Chain integrity ───────────────────────────────────────────────────────

    #[test]
    fn verify_chain_empty_ok() {
        let d = GossipDashboard::new();
        let (ok, idx) = d.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_five_frames_ok() {
        let mut d = GossipDashboard::new();
        for i in 1u64..=5 {
            rec(&mut d, i, GossipAlertLevel::Green, GossipTrendClass::Stable, true);
        }
        let (ok, idx) = d.verify_chain();
        assert!(ok);
        assert!(idx.is_none());
    }

    #[test]
    fn verify_chain_detects_tamper() {
        let mut d = GossipDashboard::new();
        rec(&mut d, 1, GossipAlertLevel::Green, GossipTrendClass::Stable, true);
        rec(&mut d, 2, GossipAlertLevel::Green, GossipTrendClass::Stable, true);
        d.frames[0].frame_hash[0] ^= 0xFF;
        let (ok, idx) = d.verify_chain();
        assert!(!ok);
        assert_eq!(idx, Some(0));
    }

    #[test]
    fn frame_hash_deterministic() {
        let mut d1 = GossipDashboard::new();
        let mut d2 = GossipDashboard::new();
        rec(&mut d1, 5, GossipAlertLevel::Amber, GossipTrendClass::Volatile, false);
        rec(&mut d2, 5, GossipAlertLevel::Amber, GossipTrendClass::Volatile, false);
        assert_eq!(d1.frames[0].frame_hash, d2.frames[0].frame_hash);
    }

    #[test]
    fn prev_hash_links_correctly() {
        let mut d = GossipDashboard::new();
        rec(&mut d, 1, GossipAlertLevel::Green, GossipTrendClass::Stable, true);
        let h0 = d.frames[0].frame_hash;
        rec(&mut d, 2, GossipAlertLevel::Green, GossipTrendClass::Stable, true);
        assert_eq!(d.frames[1].prev_hash, h0);
    }
}
