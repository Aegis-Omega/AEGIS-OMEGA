//! Gate 247 — Constitutional Health Aggregator: unified system health vector (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Composes swarm health, resilience, pulse, stability, momentum, and phase signals
//! into a single SystemHealthVector per epoch.
//!
//! SystemHealthVector:
//!   health_verdict     — HealthVerdict (Pass/Warn/Fail)
//!   resilience_verdict — ResilienceVerdict
//!   pulse_verdict      — PulseVerdict (Green/Yellow/Red)
//!   stability_grade    — StabilityGrade (A/B/C/D/F)
//!   momentum_dir       — MomentumDir
//!   phase              — ConstitutionalPhase
//!
//! OverallCondition — derived from vector:
//!   Optimal    — all six signals in their best state
//!   Good       — minor degradation in at most 1 signal
//!   Caution    — 2 signals degraded
//!   Alert      — 3+ signals degraded OR any critical signal
//!   Emergency  — health=Fail OR pulse=Red OR phase=Critical
//!
//! vector_hash = SHA-256(prev ‖ condition_byte ‖ degraded_count_byte ‖ epoch_be8)

use sha2::{Sha256, Digest};
use crate::swarm_health::HealthVerdict;
use crate::resilience_watchdog::ResilienceVerdict;
use crate::constitutional_pulse::PulseVerdict;
use crate::coherence_stability::StabilityGrade;
use crate::momentum_tracker::MomentumDir;
use crate::phase_transition::ConstitutionalPhase;

// ─── Overall condition ────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum OverallCondition {
    Optimal   = 0,
    Good      = 1,
    Caution   = 2,
    Alert     = 3,
    Emergency = 4,
}

impl OverallCondition {
    pub fn as_u8(self) -> u8 { self as u8 }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Optimal   => "optimal",
            Self::Good      => "good",
            Self::Caution   => "caution",
            Self::Alert     => "alert",
            Self::Emergency => "emergency",
        }
    }

    pub fn is_operational(self) -> bool {
        self.as_u8() <= OverallCondition::Caution.as_u8()
    }

    pub fn requires_action(self) -> bool {
        self.as_u8() >= OverallCondition::Alert.as_u8()
    }
}

// ─── System health vector ─────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct SystemHealthVector {
    pub epoch:              u64,
    pub health_verdict:     HealthVerdict,
    pub resilience_verdict: ResilienceVerdict,
    pub pulse_verdict:      PulseVerdict,
    pub stability_grade:    StabilityGrade,
    pub momentum_dir:       MomentumDir,
    pub phase:              ConstitutionalPhase,
    pub degraded_count:     u8,
    pub condition:          OverallCondition,
    pub vector_hash:        [u8; 32],
    pub prev_vector_hash:   [u8; 32],
}

pub const VECTOR_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── Build vector ────────────────────────────────────────────────────────────

pub fn build_vector(
    epoch:              u64,
    health_verdict:     HealthVerdict,
    resilience_verdict: ResilienceVerdict,
    pulse_verdict:      PulseVerdict,
    stability_grade:    StabilityGrade,
    momentum_dir:       MomentumDir,
    phase:              ConstitutionalPhase,
    prev_hash:          &[u8; 32],
) -> SystemHealthVector {
    let mut degraded_count = 0u8;

    if health_verdict != HealthVerdict::Pass     { degraded_count += 1; }
    if !resilience_verdict.is_healthy()          { degraded_count += 1; }
    if pulse_verdict != PulseVerdict::Green       { degraded_count += 1; }
    if !stability_grade.is_passing()             { degraded_count += 1; }
    if momentum_dir == MomentumDir::Declining    { degraded_count += 1; }
    if !phase.is_operational()                   { degraded_count += 1; }

    // Emergency: any critical signal
    let is_emergency = health_verdict == HealthVerdict::Fail
        || pulse_verdict == PulseVerdict::Red
        || phase == ConstitutionalPhase::Critical
        || resilience_verdict.requires_intervention();

    let condition = if is_emergency {
        OverallCondition::Emergency
    } else {
        match degraded_count {
            0     => OverallCondition::Optimal,
            1     => OverallCondition::Good,
            2     => OverallCondition::Caution,
            _     => OverallCondition::Alert,
        }
    };

    let vector_hash = compute_vector_hash(prev_hash, condition, degraded_count, epoch);

    SystemHealthVector {
        epoch,
        health_verdict,
        resilience_verdict,
        pulse_verdict,
        stability_grade,
        momentum_dir,
        phase,
        degraded_count,
        condition,
        vector_hash,
        prev_vector_hash: *prev_hash,
    }
}

fn compute_vector_hash(
    prev:          &[u8; 32],
    condition:     OverallCondition,
    degraded_count:u8,
    epoch:         u64,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update([condition.as_u8()]);
    h.update([degraded_count]);
    h.update(epoch.to_be_bytes());
    h.finalize().into()
}

// ─── Vector history ───────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct VectorHistory {
    vectors: Vec<SystemHealthVector>,
}

#[derive(Debug)]
pub struct VectorError(pub &'static str);

impl VectorHistory {
    pub fn new() -> Self { Self { vectors: Vec::new() } }

    pub fn len(&self) -> usize { self.vectors.len() }
    pub fn is_empty(&self) -> bool { self.vectors.is_empty() }
    pub fn vectors(&self) -> &[SystemHealthVector] { &self.vectors }

    pub fn last_hash(&self) -> [u8; 32] {
        self.vectors.last().map(|v| v.vector_hash).unwrap_or(VECTOR_GENESIS_HASH)
    }

    pub fn current_condition(&self) -> OverallCondition {
        self.vectors.last().map(|v| v.condition).unwrap_or(OverallCondition::Optimal)
    }

    pub fn emergency_count(&self) -> usize {
        self.vectors.iter().filter(|v| v.condition == OverallCondition::Emergency).count()
    }

    pub fn optimal_count(&self) -> usize {
        self.vectors.iter().filter(|v| v.condition == OverallCondition::Optimal).count()
    }

    /// Record a new vector. Epoch must be strictly increasing.
    pub fn record(
        &mut self,
        epoch:              u64,
        health_verdict:     HealthVerdict,
        resilience_verdict: ResilienceVerdict,
        pulse_verdict:      PulseVerdict,
        stability_grade:    StabilityGrade,
        momentum_dir:       MomentumDir,
        phase:              ConstitutionalPhase,
    ) -> Result<&SystemHealthVector, VectorError> {
        if let Some(last) = self.vectors.last() {
            if epoch <= last.epoch {
                return Err(VectorError("epoch must be strictly greater"));
            }
        }
        let prev_hash = self.last_hash();
        let v = build_vector(epoch, health_verdict, resilience_verdict, pulse_verdict,
                              stability_grade, momentum_dir, phase, &prev_hash);
        self.vectors.push(v);
        Ok(self.vectors.last().unwrap())
    }

    /// Verify hash chain integrity.
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = VECTOR_GENESIS_HASH;
        for (i, v) in self.vectors.iter().enumerate() {
            if v.prev_vector_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_vector_hash(&prev, v.condition, v.degraded_count, v.epoch);
            if expected != v.vector_hash {
                return (false, Some(i));
            }
            prev = v.vector_hash;
        }
        (true, None)
    }
}

impl Default for VectorHistory {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn all_optimal(epoch: u64, prev: &[u8; 32]) -> SystemHealthVector {
        build_vector(epoch,
            HealthVerdict::Pass, ResilienceVerdict::Stable,
            PulseVerdict::Green, StabilityGrade::A,
            MomentumDir::Stable, ConstitutionalPhase::Nominal,
            prev)
    }

    fn emergency(epoch: u64, prev: &[u8; 32]) -> SystemHealthVector {
        build_vector(epoch,
            HealthVerdict::Fail, ResilienceVerdict::Oscillating,
            PulseVerdict::Red, StabilityGrade::F,
            MomentumDir::Declining, ConstitutionalPhase::Critical,
            prev)
    }

    // ── OverallCondition ──────────────────────────────────────────────────────

    #[test]
    fn optimal_is_operational() {
        assert!(OverallCondition::Optimal.is_operational());
        assert!(!OverallCondition::Optimal.requires_action());
    }

    #[test]
    fn emergency_requires_action() {
        assert!(OverallCondition::Emergency.requires_action());
        assert!(!OverallCondition::Emergency.is_operational());
    }

    #[test]
    fn caution_is_operational() {
        assert!(OverallCondition::Caution.is_operational());
        assert!(!OverallCondition::Caution.requires_action());
    }

    #[test]
    fn condition_ordering() {
        assert!(OverallCondition::Optimal < OverallCondition::Emergency);
    }

    #[test]
    fn condition_as_u8() {
        assert_eq!(OverallCondition::Optimal.as_u8(), 0);
        assert_eq!(OverallCondition::Emergency.as_u8(), 4);
    }

    // ── build_vector ──────────────────────────────────────────────────────────

    #[test]
    fn all_optimal_gives_optimal_condition() {
        let v = all_optimal(1, &VECTOR_GENESIS_HASH);
        assert_eq!(v.condition, OverallCondition::Optimal);
        assert_eq!(v.degraded_count, 0);
    }

    #[test]
    fn all_critical_gives_emergency() {
        let v = emergency(1, &VECTOR_GENESIS_HASH);
        assert_eq!(v.condition, OverallCondition::Emergency);
    }

    #[test]
    fn health_fail_gives_emergency() {
        let v = build_vector(1,
            HealthVerdict::Fail, ResilienceVerdict::Stable,
            PulseVerdict::Green, StabilityGrade::A,
            MomentumDir::Stable, ConstitutionalPhase::Nominal,
            &VECTOR_GENESIS_HASH);
        assert_eq!(v.condition, OverallCondition::Emergency);
    }

    #[test]
    fn one_degraded_gives_good() {
        let v = build_vector(1,
            HealthVerdict::Warn, ResilienceVerdict::Stable,
            PulseVerdict::Green, StabilityGrade::A,
            MomentumDir::Stable, ConstitutionalPhase::Nominal,
            &VECTOR_GENESIS_HASH);
        assert_eq!(v.condition, OverallCondition::Good);
        assert_eq!(v.degraded_count, 1);
    }

    #[test]
    fn two_degraded_gives_caution() {
        let v = build_vector(1,
            HealthVerdict::Warn, ResilienceVerdict::Stable,
            PulseVerdict::Yellow, StabilityGrade::A,
            MomentumDir::Stable, ConstitutionalPhase::Nominal,
            &VECTOR_GENESIS_HASH);
        assert_eq!(v.condition, OverallCondition::Caution);
        assert_eq!(v.degraded_count, 2);
    }

    #[test]
    fn three_degraded_gives_alert() {
        let v = build_vector(1,
            HealthVerdict::Warn, ResilienceVerdict::Stable,
            PulseVerdict::Yellow, StabilityGrade::D,
            MomentumDir::Stable, ConstitutionalPhase::Nominal,
            &VECTOR_GENESIS_HASH);
        assert_eq!(v.condition, OverallCondition::Alert);
    }

    #[test]
    fn vector_hash_nonzero() {
        let v = all_optimal(1, &VECTOR_GENESIS_HASH);
        assert_ne!(v.vector_hash, [0u8; 32]);
    }

    #[test]
    fn vector_hash_deterministic() {
        let v1 = all_optimal(7, &VECTOR_GENESIS_HASH);
        let v2 = all_optimal(7, &VECTOR_GENESIS_HASH);
        let v3 = all_optimal(7, &VECTOR_GENESIS_HASH);
        assert_eq!(v1.vector_hash, v2.vector_hash);
        assert_eq!(v2.vector_hash, v3.vector_hash);
    }

    #[test]
    fn different_epochs_different_hash() {
        let v1 = all_optimal(1, &VECTOR_GENESIS_HASH);
        let v2 = all_optimal(2, &VECTOR_GENESIS_HASH);
        assert_ne!(v1.vector_hash, v2.vector_hash);
    }

    // ── VectorHistory ─────────────────────────────────────────────────────────

    #[test]
    fn new_history_empty() {
        let h = VectorHistory::new();
        assert!(h.is_empty());
        assert_eq!(h.current_condition(), OverallCondition::Optimal);
    }

    #[test]
    fn record_grows_history() {
        let mut h = VectorHistory::new();
        h.record(1, HealthVerdict::Pass, ResilienceVerdict::Stable, PulseVerdict::Green,
                  StabilityGrade::A, MomentumDir::Stable, ConstitutionalPhase::Nominal).unwrap();
        h.record(2, HealthVerdict::Pass, ResilienceVerdict::Stable, PulseVerdict::Green,
                  StabilityGrade::A, MomentumDir::Stable, ConstitutionalPhase::Nominal).unwrap();
        assert_eq!(h.len(), 2);
    }

    #[test]
    fn duplicate_epoch_is_err() {
        let mut h = VectorHistory::new();
        h.record(5, HealthVerdict::Pass, ResilienceVerdict::Stable, PulseVerdict::Green,
                  StabilityGrade::A, MomentumDir::Stable, ConstitutionalPhase::Nominal).unwrap();
        assert!(h.record(5, HealthVerdict::Pass, ResilienceVerdict::Stable, PulseVerdict::Green,
                          StabilityGrade::A, MomentumDir::Stable, ConstitutionalPhase::Nominal).is_err());
    }

    #[test]
    fn emergency_count_tracked() {
        let mut h = VectorHistory::new();
        h.record(1, HealthVerdict::Fail, ResilienceVerdict::Stable, PulseVerdict::Red,
                  StabilityGrade::F, MomentumDir::Declining, ConstitutionalPhase::Critical).unwrap();
        h.record(2, HealthVerdict::Pass, ResilienceVerdict::Stable, PulseVerdict::Green,
                  StabilityGrade::A, MomentumDir::Stable, ConstitutionalPhase::Nominal).unwrap();
        h.record(3, HealthVerdict::Fail, ResilienceVerdict::Stable, PulseVerdict::Red,
                  StabilityGrade::F, MomentumDir::Declining, ConstitutionalPhase::Critical).unwrap();
        assert_eq!(h.emergency_count(), 2);
        assert_eq!(h.optimal_count(), 1);
    }

    #[test]
    fn hash_chain_links() {
        let mut h = VectorHistory::new();
        h.record(1, HealthVerdict::Pass, ResilienceVerdict::Stable, PulseVerdict::Green,
                  StabilityGrade::A, MomentumDir::Stable, ConstitutionalPhase::Nominal).unwrap();
        h.record(2, HealthVerdict::Pass, ResilienceVerdict::Stable, PulseVerdict::Green,
                  StabilityGrade::A, MomentumDir::Stable, ConstitutionalPhase::Nominal).unwrap();
        assert_eq!(h.vectors()[1].prev_vector_hash, h.vectors()[0].vector_hash);
    }

    #[test]
    fn verify_chain_clean() {
        let mut h = VectorHistory::new();
        for i in 1u64..=5 {
            h.record(i, HealthVerdict::Pass, ResilienceVerdict::Stable, PulseVerdict::Green,
                     StabilityGrade::A, MomentumDir::Stable, ConstitutionalPhase::Nominal).unwrap();
        }
        let (valid, broken) = h.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }
}
