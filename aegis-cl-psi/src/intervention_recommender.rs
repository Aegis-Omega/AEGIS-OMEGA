//! Gate 251 — Intervention Recommender: ranked constitutional remediation actions (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Given an AlertSeverity + SystemHealthVector, produces a ranked list of
//! InterventionAction items with priority scores (0–100).
//!
//! InterventionKind:
//!   MonitorOnly       — no action, continue observation (severity=None/Info)
//!   TightenThresholds — reduce adaptive thresholds to increase sensitivity
//!   ForceResilient    — trigger resilience watchdog recovery protocol
//!   QuorumRecovery    — restore quorum via node re-admission
//!   PulseReset        — reset constitutional pulse baseline
//!   PhaseRecovery     — force transition back toward Nominal
//!   EmergencyHalt     — suspend adaptive events, freeze mutations
//!
//! InterventionPlan:
//!   epoch          — u64
//!   severity       — AlertSeverity from triggering alert
//!   actions        — Vec<InterventionAction> sorted by priority descending
//!   plan_hash      — SHA-256(prev ‖ severity_byte ‖ top_priority_byte ‖ epoch_be8)
//!   prev_plan_hash — previous plan_hash

use sha2::{Sha256, Digest};
use crate::alert_engine::AlertSeverity;
use crate::health_aggregator::{SystemHealthVector, OverallCondition};
use crate::swarm_health::HealthVerdict;
use crate::resilience_watchdog::ResilienceVerdict;
use crate::constitutional_pulse::PulseVerdict;
use crate::momentum_tracker::MomentumDir;
use crate::phase_transition::ConstitutionalPhase;

// ─── Intervention kind ────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum InterventionKind {
    MonitorOnly       = 0,
    TightenThresholds = 1,
    ForceResilient    = 2,
    QuorumRecovery    = 3,
    PulseReset        = 4,
    PhaseRecovery     = 5,
    EmergencyHalt     = 6,
}

impl InterventionKind {
    pub fn as_u8(self) -> u8 { self as u8 }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::MonitorOnly       => "monitor_only",
            Self::TightenThresholds => "tighten_thresholds",
            Self::ForceResilient    => "force_resilient",
            Self::QuorumRecovery    => "quorum_recovery",
            Self::PulseReset        => "pulse_reset",
            Self::PhaseRecovery     => "phase_recovery",
            Self::EmergencyHalt     => "emergency_halt",
        }
    }

    pub fn is_disruptive(self) -> bool {
        matches!(self, Self::QuorumRecovery | Self::PhaseRecovery | Self::EmergencyHalt)
    }
}

// ─── Intervention action ──────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct InterventionAction {
    pub kind:        InterventionKind,
    pub priority:    u8,   // 0–100, higher = more urgent
    pub rationale:   &'static str,
}

// ─── Intervention plan ────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct InterventionPlan {
    pub epoch:          u64,
    pub severity:       AlertSeverity,
    pub actions:        Vec<InterventionAction>,
    pub plan_hash:      [u8; 32],
    pub prev_plan_hash: [u8; 32],
}

pub const PLAN_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── Build plan ───────────────────────────────────────────────────────────────

pub fn build_plan(
    epoch:     u64,
    severity:  AlertSeverity,
    vector:    &SystemHealthVector,
    prev_hash: &[u8; 32],
) -> InterventionPlan {
    let mut actions = recommend_actions(severity, vector);
    // Sort by priority descending, then kind ascending for determinism on tie
    actions.sort_by(|a, b| b.priority.cmp(&a.priority).then(a.kind.cmp(&b.kind)));

    let top_priority = actions.first().map(|a| a.priority).unwrap_or(0);
    let plan_hash = compute_plan_hash(prev_hash, severity, top_priority, epoch);

    InterventionPlan { epoch, severity, actions, plan_hash, prev_plan_hash: *prev_hash }
}

fn recommend_actions(severity: AlertSeverity, vector: &SystemHealthVector) -> Vec<InterventionAction> {
    let mut actions = Vec::new();

    match severity {
        AlertSeverity::None => {
            actions.push(InterventionAction {
                kind: InterventionKind::MonitorOnly,
                priority: 10,
                rationale: "system nominal — continue observation",
            });
        }
        AlertSeverity::Info => {
            actions.push(InterventionAction {
                kind: InterventionKind::MonitorOnly,
                priority: 20,
                rationale: "minor degradation — increased observation frequency",
            });
            if vector.momentum_dir == MomentumDir::Declining {
                actions.push(InterventionAction {
                    kind: InterventionKind::TightenThresholds,
                    priority: 35,
                    rationale: "declining momentum — tighten alert thresholds preemptively",
                });
            }
        }
        AlertSeverity::Warn => {
            actions.push(InterventionAction {
                kind: InterventionKind::TightenThresholds,
                priority: 55,
                rationale: "degradation warrants threshold tightening",
            });
            if vector.resilience_verdict != ResilienceVerdict::Stable
                && vector.resilience_verdict != ResilienceVerdict::Recovering
            {
                actions.push(InterventionAction {
                    kind: InterventionKind::ForceResilient,
                    priority: 60,
                    rationale: "non-stable resilience — trigger recovery protocol",
                });
            }
            if vector.pulse_verdict != PulseVerdict::Green {
                actions.push(InterventionAction {
                    kind: InterventionKind::PulseReset,
                    priority: 50,
                    rationale: "non-green pulse — reset baseline",
                });
            }
        }
        AlertSeverity::Critical => {
            actions.push(InterventionAction {
                kind: InterventionKind::ForceResilient,
                priority: 75,
                rationale: "critical condition — resilience recovery required",
            });
            if vector.condition == OverallCondition::Emergency
                || vector.health_verdict == HealthVerdict::Fail
            {
                actions.push(InterventionAction {
                    kind: InterventionKind::EmergencyHalt,
                    priority: 90,
                    rationale: "health failure — suspend adaptive events",
                });
            }
            if !vector.phase.is_operational() {
                actions.push(InterventionAction {
                    kind: InterventionKind::PhaseRecovery,
                    priority: 80,
                    rationale: "non-operational phase — force phase recovery",
                });
            }
            actions.push(InterventionAction {
                kind: InterventionKind::QuorumRecovery,
                priority: 65,
                rationale: "critical alert — verify quorum integrity",
            });
        }
        AlertSeverity::Emergency => {
            actions.push(InterventionAction {
                kind: InterventionKind::EmergencyHalt,
                priority: 100,
                rationale: "emergency — immediate halt of adaptive mutations",
            });
            actions.push(InterventionAction {
                kind: InterventionKind::PhaseRecovery,
                priority: 95,
                rationale: "emergency — force phase recovery toward Nominal",
            });
            actions.push(InterventionAction {
                kind: InterventionKind::QuorumRecovery,
                priority: 85,
                rationale: "emergency — quorum re-establishment required",
            });
            actions.push(InterventionAction {
                kind: InterventionKind::ForceResilient,
                priority: 80,
                rationale: "emergency — resilience recovery protocol",
            });
            if vector.pulse_verdict == PulseVerdict::Red {
                actions.push(InterventionAction {
                    kind: InterventionKind::PulseReset,
                    priority: 75,
                    rationale: "red pulse — reset constitutional pulse baseline",
                });
            }
        }
    }

    // Always include monitor if not already present for Warn+ (observation must continue)
    if severity.as_u8() >= AlertSeverity::Warn.as_u8()
        && !actions.iter().any(|a| a.kind == InterventionKind::MonitorOnly)
    {
        actions.push(InterventionAction {
            kind: InterventionKind::MonitorOnly,
            priority: 30,
            rationale: "elevated severity — maintain continuous observation",
        });
    }

    actions
}

fn compute_plan_hash(
    prev:         &[u8; 32],
    severity:     AlertSeverity,
    top_priority: u8,
    epoch:        u64,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update([severity.as_u8()]);
    h.update([top_priority]);
    h.update(epoch.to_be_bytes());
    h.finalize().into()
}

// ─── Plan history ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct PlanHistory {
    plans: Vec<InterventionPlan>,
}

#[derive(Debug)]
pub struct PlanError(pub &'static str);

impl PlanHistory {
    pub fn new() -> Self { Self { plans: Vec::new() } }

    pub fn len(&self) -> usize { self.plans.len() }
    pub fn is_empty(&self) -> bool { self.plans.is_empty() }
    pub fn plans(&self) -> &[InterventionPlan] { &self.plans }

    pub fn last_hash(&self) -> [u8; 32] {
        self.plans.last().map(|p| p.plan_hash).unwrap_or(PLAN_GENESIS_HASH)
    }

    pub fn disruptive_count(&self) -> usize {
        self.plans.iter().flat_map(|p| p.actions.iter())
            .filter(|a| a.kind.is_disruptive())
            .count()
    }

    pub fn record(
        &mut self,
        epoch:    u64,
        severity: AlertSeverity,
        vector:   &SystemHealthVector,
    ) -> Result<&InterventionPlan, PlanError> {
        if let Some(last) = self.plans.last() {
            if epoch <= last.epoch {
                return Err(PlanError("epoch must be strictly greater"));
            }
        }
        let prev_hash = self.last_hash();
        let plan = build_plan(epoch, severity, vector, &prev_hash);
        self.plans.push(plan);
        Ok(self.plans.last().unwrap())
    }

    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = PLAN_GENESIS_HASH;
        for (i, p) in self.plans.iter().enumerate() {
            if p.prev_plan_hash != prev {
                return (false, Some(i));
            }
            let top = p.actions.first().map(|a| a.priority).unwrap_or(0);
            let expected = compute_plan_hash(&prev, p.severity, top, p.epoch);
            if expected != p.plan_hash {
                return (false, Some(i));
            }
            prev = p.plan_hash;
        }
        (true, None)
    }
}

impl Default for PlanHistory {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::health_aggregator::{build_vector, VECTOR_GENESIS_HASH};
    use crate::coherence_stability::StabilityGrade;

    fn nominal_vector() -> SystemHealthVector {
        build_vector(1,
            HealthVerdict::Pass, ResilienceVerdict::Stable,
            PulseVerdict::Green, StabilityGrade::A,
            MomentumDir::Stable, ConstitutionalPhase::Nominal,
            &VECTOR_GENESIS_HASH)
    }

    fn emergency_vector() -> SystemHealthVector {
        build_vector(1,
            HealthVerdict::Fail, ResilienceVerdict::Oscillating,
            PulseVerdict::Red, StabilityGrade::F,
            MomentumDir::Declining, ConstitutionalPhase::Critical,
            &VECTOR_GENESIS_HASH)
    }

    // ── InterventionKind ──────────────────────────────────────────────────────

    #[test]
    fn disruptive_kinds() {
        assert!(InterventionKind::EmergencyHalt.is_disruptive());
        assert!(InterventionKind::PhaseRecovery.is_disruptive());
        assert!(InterventionKind::QuorumRecovery.is_disruptive());
        assert!(!InterventionKind::MonitorOnly.is_disruptive());
        assert!(!InterventionKind::TightenThresholds.is_disruptive());
    }

    #[test]
    fn kind_as_str() {
        assert_eq!(InterventionKind::EmergencyHalt.as_str(), "emergency_halt");
        assert_eq!(InterventionKind::MonitorOnly.as_str(), "monitor_only");
    }

    #[test]
    fn kind_ordering() {
        assert!(InterventionKind::MonitorOnly < InterventionKind::EmergencyHalt);
    }

    // ── build_plan ────────────────────────────────────────────────────────────

    #[test]
    fn none_severity_gives_monitor_only() {
        let v = nominal_vector();
        let p = build_plan(1, AlertSeverity::None, &v, &PLAN_GENESIS_HASH);
        assert!(p.actions.iter().any(|a| a.kind == InterventionKind::MonitorOnly));
        assert_eq!(p.severity, AlertSeverity::None);
    }

    #[test]
    fn emergency_severity_gives_halt_first() {
        let v = emergency_vector();
        let p = build_plan(1, AlertSeverity::Emergency, &v, &PLAN_GENESIS_HASH);
        assert!(!p.actions.is_empty());
        assert_eq!(p.actions[0].kind, InterventionKind::EmergencyHalt);
        assert_eq!(p.actions[0].priority, 100);
    }

    #[test]
    fn emergency_includes_phase_recovery() {
        let v = emergency_vector();
        let p = build_plan(1, AlertSeverity::Emergency, &v, &PLAN_GENESIS_HASH);
        assert!(p.actions.iter().any(|a| a.kind == InterventionKind::PhaseRecovery));
    }

    #[test]
    fn emergency_includes_pulse_reset_when_red() {
        let v = emergency_vector(); // pulse=Red
        let p = build_plan(1, AlertSeverity::Emergency, &v, &PLAN_GENESIS_HASH);
        assert!(p.actions.iter().any(|a| a.kind == InterventionKind::PulseReset));
    }

    #[test]
    fn actions_sorted_by_priority_desc() {
        let v = emergency_vector();
        let p = build_plan(1, AlertSeverity::Emergency, &v, &PLAN_GENESIS_HASH);
        let priorities: Vec<u8> = p.actions.iter().map(|a| a.priority).collect();
        let mut sorted = priorities.clone();
        sorted.sort_by(|a, b| b.cmp(a));
        assert_eq!(priorities, sorted);
    }

    #[test]
    fn plan_hash_nonzero() {
        let v = nominal_vector();
        let p = build_plan(1, AlertSeverity::None, &v, &PLAN_GENESIS_HASH);
        assert_ne!(p.plan_hash, [0u8; 32]);
    }

    #[test]
    fn plan_hash_deterministic() {
        let v1 = nominal_vector();
        let v2 = nominal_vector();
        let v3 = nominal_vector();
        let p1 = build_plan(1, AlertSeverity::None, &v1, &PLAN_GENESIS_HASH);
        let p2 = build_plan(1, AlertSeverity::None, &v2, &PLAN_GENESIS_HASH);
        let p3 = build_plan(1, AlertSeverity::None, &v3, &PLAN_GENESIS_HASH);
        assert_eq!(p1.plan_hash, p2.plan_hash);
        assert_eq!(p2.plan_hash, p3.plan_hash);
    }

    #[test]
    fn different_severity_different_hash() {
        let v1 = nominal_vector();
        let v2 = nominal_vector();
        let p1 = build_plan(1, AlertSeverity::None, &v1, &PLAN_GENESIS_HASH);
        let p2 = build_plan(1, AlertSeverity::Emergency, &v2, &PLAN_GENESIS_HASH);
        assert_ne!(p1.plan_hash, p2.plan_hash);
    }

    #[test]
    fn warn_includes_monitor_only() {
        let v = build_vector(1,
            HealthVerdict::Warn, ResilienceVerdict::Stable,
            PulseVerdict::Yellow, StabilityGrade::C,
            MomentumDir::Stable, ConstitutionalPhase::Nominal,
            &VECTOR_GENESIS_HASH);
        let p = build_plan(1, AlertSeverity::Warn, &v, &PLAN_GENESIS_HASH);
        assert!(p.actions.iter().any(|a| a.kind == InterventionKind::MonitorOnly));
    }

    // ── PlanHistory ───────────────────────────────────────────────────────────

    #[test]
    fn new_history_empty() {
        let h = PlanHistory::new();
        assert!(h.is_empty());
    }

    #[test]
    fn record_grows_history() {
        let mut h = PlanHistory::new();
        let v = nominal_vector();
        h.record(1, AlertSeverity::None, &v).unwrap();
        h.record(2, AlertSeverity::None, &v).unwrap();
        assert_eq!(h.len(), 2);
    }

    #[test]
    fn duplicate_epoch_is_err() {
        let mut h = PlanHistory::new();
        let v = nominal_vector();
        h.record(5, AlertSeverity::None, &v).unwrap();
        assert!(h.record(5, AlertSeverity::None, &v).is_err());
    }

    #[test]
    fn disruptive_count_tracks_emergency_actions() {
        let mut h = PlanHistory::new();
        h.record(1, AlertSeverity::Emergency, &emergency_vector()).unwrap();
        assert!(h.disruptive_count() > 0);
    }

    #[test]
    fn verify_chain_clean() {
        let mut h = PlanHistory::new();
        let v = nominal_vector();
        for i in 1u64..=5 {
            h.record(i, AlertSeverity::None, &v).unwrap();
        }
        let (valid, broken) = h.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }

    #[test]
    fn rationale_non_empty() {
        let v = emergency_vector();
        let p = build_plan(1, AlertSeverity::Emergency, &v, &PLAN_GENESIS_HASH);
        for a in &p.actions {
            assert!(!a.rationale.is_empty(), "action {:?} has empty rationale", a.kind);
        }
    }
}
