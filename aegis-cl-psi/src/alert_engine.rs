//! Gate 250 — Constitutional Alert Engine: severity classification + hash-linked alert log (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Classifies each DashboardFrame into an AlertSeverity and appends to a hash-linked AlertLog.
//!
//! AlertSeverity:
//!   None      — Thriving/Stable, condition ≤ Good
//!   Info      — Concerning trend OR condition = Caution
//!   Warn      — Concerning trend AND condition = Caution, OR Alert condition
//!   Critical  — Critical trend OR Emergency condition
//!   Emergency — Emergency condition AND Critical trend
//!
//! AlertRecord:
//!   epoch          — u64
//!   severity       — AlertSeverity
//!   condition      — OverallCondition (from frame)
//!   trend          — OverallTrend (from frame)
//!   message        — &'static str
//!   alert_hash     — SHA-256(prev ‖ severity_byte ‖ condition_byte ‖ epoch_be8)
//!   prev_alert_hash— previous alert_hash
//!
//! AlertLog: hash-linked record; escalation_count(), suppression_count() for None severity.

use sha2::{Sha256, Digest};
use crate::health_dashboard::{DashboardFrame, OverallTrend};
use crate::health_aggregator::OverallCondition;

// ─── Alert severity ───────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum AlertSeverity {
    None      = 0,
    Info      = 1,
    Warn      = 2,
    Critical  = 3,
    Emergency = 4,
}

impl AlertSeverity {
    pub fn as_u8(self) -> u8 { self as u8 }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::None      => "none",
            Self::Info      => "info",
            Self::Warn      => "warn",
            Self::Critical  => "critical",
            Self::Emergency => "emergency",
        }
    }

    pub fn requires_action(self) -> bool {
        self.as_u8() >= Self::Warn.as_u8()
    }

    pub fn is_silent(self) -> bool { self == Self::None }

    pub fn classify(condition: OverallCondition, trend: OverallTrend) -> Self {
        let is_emergency_cond = condition == OverallCondition::Emergency;
        let is_alert_cond     = condition == OverallCondition::Alert;
        let is_caution_cond   = condition == OverallCondition::Caution;
        let is_critical_trend = trend == OverallTrend::Critical;
        let is_concerning     = trend == OverallTrend::Concerning;

        if is_emergency_cond && is_critical_trend {
            Self::Emergency
        } else if is_emergency_cond || is_critical_trend {
            Self::Critical
        } else if is_alert_cond || (is_concerning && is_caution_cond) {
            Self::Warn
        } else if is_caution_cond || is_concerning {
            Self::Info
        } else {
            Self::None
        }
    }

    fn message(self) -> &'static str {
        match self {
            Self::None      => "system nominal",
            Self::Info      => "minor degradation detected",
            Self::Warn      => "degradation requires attention",
            Self::Critical  => "critical condition — intervention recommended",
            Self::Emergency => "emergency — immediate intervention required",
        }
    }
}

// ─── Alert record ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct AlertRecord {
    pub epoch:           u64,
    pub severity:        AlertSeverity,
    pub condition:       OverallCondition,
    pub trend:           OverallTrend,
    pub message:         &'static str,
    pub alert_hash:      [u8; 32],
    pub prev_alert_hash: [u8; 32],
}

pub const ALERT_GENESIS_HASH: [u8; 32] = [0u8; 32];

fn compute_alert_hash(
    prev:      &[u8; 32],
    severity:  AlertSeverity,
    condition: OverallCondition,
    epoch:     u64,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update([severity.as_u8()]);
    h.update([condition.as_u8()]);
    h.update(epoch.to_be_bytes());
    h.finalize().into()
}

// ─── Alert log ────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct AlertLog {
    records: Vec<AlertRecord>,
}

#[derive(Debug)]
pub struct AlertError(pub &'static str);

impl AlertLog {
    pub fn new() -> Self { Self { records: Vec::new() } }

    pub fn len(&self) -> usize { self.records.len() }
    pub fn is_empty(&self) -> bool { self.records.is_empty() }
    pub fn records(&self) -> &[AlertRecord] { &self.records }

    pub fn last_hash(&self) -> [u8; 32] {
        self.records.last().map(|r| r.alert_hash).unwrap_or(ALERT_GENESIS_HASH)
    }

    pub fn current_severity(&self) -> AlertSeverity {
        self.records.last().map(|r| r.severity).unwrap_or(AlertSeverity::None)
    }

    /// Number of records at Warn or above.
    pub fn escalation_count(&self) -> usize {
        self.records.iter().filter(|r| r.severity.requires_action()).count()
    }

    /// Number of silent (None severity) records.
    pub fn suppression_count(&self) -> usize {
        self.records.iter().filter(|r| r.severity.is_silent()).count()
    }

    /// Highest severity seen across all records.
    pub fn peak_severity(&self) -> AlertSeverity {
        self.records.iter().map(|r| r.severity).max().unwrap_or(AlertSeverity::None)
    }

    /// Classify and record a DashboardFrame. Epoch must be strictly increasing.
    pub fn record(&mut self, frame: &DashboardFrame) -> Result<&AlertRecord, AlertError> {
        if let Some(last) = self.records.last() {
            if frame.epoch <= last.epoch {
                return Err(AlertError("epoch must be strictly greater"));
            }
        }
        let severity   = AlertSeverity::classify(frame.vector.condition, frame.overall_trend);
        let message    = severity.message();
        let prev_hash  = self.last_hash();
        let alert_hash = compute_alert_hash(&prev_hash, severity, frame.vector.condition, frame.epoch);

        let rec = AlertRecord {
            epoch:           frame.epoch,
            severity,
            condition:       frame.vector.condition,
            trend:           frame.overall_trend,
            message,
            alert_hash,
            prev_alert_hash: prev_hash,
        };
        self.records.push(rec);
        Ok(self.records.last().unwrap())
    }

    /// Verify hash chain integrity.
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = ALERT_GENESIS_HASH;
        for (i, r) in self.records.iter().enumerate() {
            if r.prev_alert_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_alert_hash(&prev, r.severity, r.condition, r.epoch);
            if expected != r.alert_hash {
                return (false, Some(i));
            }
            prev = r.alert_hash;
        }
        (true, None)
    }
}

impl Default for AlertLog {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::health_aggregator::{build_vector, VECTOR_GENESIS_HASH};
    use crate::health_dashboard::{build_frame, DASHBOARD_GENESIS_HASH};
    use crate::swarm_health::HealthVerdict;
    use crate::resilience_watchdog::ResilienceVerdict;
    use crate::constitutional_pulse::PulseVerdict;
    use crate::coherence_stability::StabilityGrade;
    use crate::momentum_tracker::MomentumDir;
    use crate::phase_transition::ConstitutionalPhase;

    fn make_frame(epoch: u64, health: HealthVerdict, pulse: PulseVerdict,
                  resilience: ResilienceVerdict, grade: StabilityGrade,
                  dir: MomentumDir, phase: ConstitutionalPhase) -> DashboardFrame {
        let v = build_vector(epoch, health, resilience, pulse, grade, dir, phase,
                             &VECTOR_GENESIS_HASH);
        build_frame(epoch, v, phase, dir, 0, &DASHBOARD_GENESIS_HASH)
    }

    fn good_frame(epoch: u64) -> DashboardFrame {
        make_frame(epoch, HealthVerdict::Pass, PulseVerdict::Green,
                   ResilienceVerdict::Stable, StabilityGrade::A,
                   MomentumDir::Improving, ConstitutionalPhase::Nominal)
    }

    fn emergency_frame(epoch: u64) -> DashboardFrame {
        make_frame(epoch, HealthVerdict::Fail, PulseVerdict::Red,
                   ResilienceVerdict::Oscillating, StabilityGrade::F,
                   MomentumDir::Declining, ConstitutionalPhase::Critical)
    }

    // ── AlertSeverity classification ──────────────────────────────────────────

    #[test]
    fn thriving_stable_gives_none() {
        let s = AlertSeverity::classify(OverallCondition::Optimal, OverallTrend::Thriving);
        assert_eq!(s, AlertSeverity::None);
    }

    #[test]
    fn good_stable_gives_none() {
        let s = AlertSeverity::classify(OverallCondition::Good, OverallTrend::Stable);
        assert_eq!(s, AlertSeverity::None);
    }

    #[test]
    fn caution_stable_gives_info() {
        let s = AlertSeverity::classify(OverallCondition::Caution, OverallTrend::Stable);
        assert_eq!(s, AlertSeverity::Info);
    }

    #[test]
    fn good_concerning_gives_info() {
        let s = AlertSeverity::classify(OverallCondition::Good, OverallTrend::Concerning);
        assert_eq!(s, AlertSeverity::Info);
    }

    #[test]
    fn caution_concerning_gives_warn() {
        let s = AlertSeverity::classify(OverallCondition::Caution, OverallTrend::Concerning);
        assert_eq!(s, AlertSeverity::Warn);
    }

    #[test]
    fn alert_condition_gives_warn() {
        let s = AlertSeverity::classify(OverallCondition::Alert, OverallTrend::Stable);
        assert_eq!(s, AlertSeverity::Warn);
    }

    #[test]
    fn emergency_condition_gives_critical() {
        let s = AlertSeverity::classify(OverallCondition::Emergency, OverallTrend::Stable);
        assert_eq!(s, AlertSeverity::Critical);
    }

    #[test]
    fn critical_trend_gives_critical() {
        let s = AlertSeverity::classify(OverallCondition::Good, OverallTrend::Critical);
        assert_eq!(s, AlertSeverity::Critical);
    }

    #[test]
    fn emergency_plus_critical_gives_emergency_severity() {
        let s = AlertSeverity::classify(OverallCondition::Emergency, OverallTrend::Critical);
        assert_eq!(s, AlertSeverity::Emergency);
    }

    #[test]
    fn severity_requires_action() {
        assert!(!AlertSeverity::None.requires_action());
        assert!(!AlertSeverity::Info.requires_action());
        assert!(AlertSeverity::Warn.requires_action());
        assert!(AlertSeverity::Critical.requires_action());
        assert!(AlertSeverity::Emergency.requires_action());
    }

    #[test]
    fn severity_ordering() {
        assert!(AlertSeverity::None < AlertSeverity::Emergency);
        assert!(AlertSeverity::Info < AlertSeverity::Warn);
    }

    #[test]
    fn severity_as_u8() {
        assert_eq!(AlertSeverity::None.as_u8(), 0);
        assert_eq!(AlertSeverity::Emergency.as_u8(), 4);
    }

    // ── AlertLog ──────────────────────────────────────────────────────────────

    #[test]
    fn new_log_empty() {
        let l = AlertLog::new();
        assert!(l.is_empty());
        assert_eq!(l.current_severity(), AlertSeverity::None);
        assert_eq!(l.peak_severity(), AlertSeverity::None);
    }

    #[test]
    fn record_grows_log() {
        let mut l = AlertLog::new();
        l.record(&good_frame(1)).unwrap();
        l.record(&good_frame(2)).unwrap();
        assert_eq!(l.len(), 2);
    }

    #[test]
    fn duplicate_epoch_is_err() {
        let mut l = AlertLog::new();
        l.record(&good_frame(5)).unwrap();
        assert!(l.record(&good_frame(5)).is_err());
    }

    #[test]
    fn good_frame_gives_none_severity() {
        let mut l = AlertLog::new();
        let r = l.record(&good_frame(1)).unwrap();
        assert_eq!(r.severity, AlertSeverity::None);
    }

    #[test]
    fn emergency_frame_gives_emergency_severity() {
        let mut l = AlertLog::new();
        let r = l.record(&emergency_frame(1)).unwrap();
        assert_eq!(r.severity, AlertSeverity::Emergency);
    }

    #[test]
    fn peak_severity_tracks_worst() {
        let mut l = AlertLog::new();
        l.record(&good_frame(1)).unwrap();      // None
        l.record(&emergency_frame(2)).unwrap(); // Emergency
        l.record(&good_frame(3)).unwrap();      // None
        assert_eq!(l.peak_severity(), AlertSeverity::Emergency);
    }

    #[test]
    fn escalation_and_suppression_count() {
        let mut l = AlertLog::new();
        l.record(&good_frame(1)).unwrap();      // None → suppression
        l.record(&emergency_frame(2)).unwrap(); // Emergency → escalation
        l.record(&good_frame(3)).unwrap();      // None → suppression
        l.record(&emergency_frame(4)).unwrap(); // Emergency → escalation
        assert_eq!(l.escalation_count(), 2);
        assert_eq!(l.suppression_count(), 2);
    }

    #[test]
    fn alert_hash_nonzero() {
        let mut l = AlertLog::new();
        l.record(&good_frame(1)).unwrap();
        assert_ne!(l.last_hash(), [0u8; 32]);
    }

    #[test]
    fn alert_hash_deterministic() {
        let f1 = good_frame(9);
        let f2 = good_frame(9);
        let f3 = good_frame(9);
        let mut l1 = AlertLog::new();
        let mut l2 = AlertLog::new();
        let mut l3 = AlertLog::new();
        l1.record(&f1).unwrap();
        l2.record(&f2).unwrap();
        l3.record(&f3).unwrap();
        assert_eq!(l1.last_hash(), l2.last_hash());
        assert_eq!(l2.last_hash(), l3.last_hash());
    }

    #[test]
    fn hash_chain_links() {
        let mut l = AlertLog::new();
        l.record(&good_frame(1)).unwrap();
        l.record(&good_frame(2)).unwrap();
        assert_eq!(l.records()[1].prev_alert_hash, l.records()[0].alert_hash);
    }

    #[test]
    fn verify_chain_clean() {
        let mut l = AlertLog::new();
        for i in 1u64..=5 {
            l.record(&good_frame(i)).unwrap();
        }
        let (valid, broken) = l.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    #[test]
    fn message_non_empty() {
        let mut l = AlertLog::new();
        let r = l.record(&emergency_frame(1)).unwrap();
        assert!(!r.message.is_empty());
    }
}
