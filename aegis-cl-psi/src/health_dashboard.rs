//! Gate 248 — Constitutional Health Dashboard: unified epoch-by-epoch frame (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Wires SystemHealthVector + PhaseObservation + MomentumReport into a single
//! DashboardFrame per epoch. The dashboard is the operator-facing summary of
//! the full constitutional health stack.
//!
//! DashboardFrame:
//!   epoch              — u64
//!   vector             — SystemHealthVector (all 6 signals + OverallCondition)
//!   phase              — ConstitutionalPhase from PhaseObservation
//!   momentum_dir       — MomentumDir from MomentumReport
//!   momentum_int       — i64 from MomentumReport
//!   overall_trend      — OverallTrend derived from condition + momentum + phase
//!   frame_hash         — SHA-256(prev ‖ condition_byte ‖ trend_byte ‖ epoch_be8)
//!   prev_frame_hash    — hash of previous DashboardFrame
//!
//! OverallTrend:
//!   Thriving   — Optimal condition + Improving momentum + operational phase
//!   Stable     — Good/Optimal condition + Stable/Improving momentum
//!   Concerning — Caution OR Declining momentum
//!   Critical   — Alert/Emergency condition OR non-operational phase
//!
//! frame_hash = SHA-256(prev ‖ condition_byte ‖ trend_byte ‖ epoch_be8)

use sha2::{Sha256, Digest};
use crate::health_aggregator::{SystemHealthVector, OverallCondition};
use crate::phase_transition::ConstitutionalPhase;
use crate::momentum_tracker::MomentumDir;

// ─── Overall trend ────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum OverallTrend {
    Thriving   = 0,
    Stable     = 1,
    Concerning = 2,
    Critical   = 3,
}

impl OverallTrend {
    pub fn as_u8(self) -> u8 { self as u8 }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Thriving   => "thriving",
            Self::Stable     => "stable",
            Self::Concerning => "concerning",
            Self::Critical   => "critical",
        }
    }

    pub fn is_positive(self) -> bool {
        matches!(self, Self::Thriving | Self::Stable)
    }

    pub fn derive(
        condition:    OverallCondition,
        momentum_dir: MomentumDir,
        phase:        ConstitutionalPhase,
    ) -> Self {
        // Critical: any hard alarm
        if condition >= OverallCondition::Alert || !phase.is_operational() {
            return Self::Critical;
        }
        // Thriving: best condition + improving + operational
        if condition == OverallCondition::Optimal
            && momentum_dir == MomentumDir::Improving
            && phase.is_operational()
        {
            return Self::Thriving;
        }
        // Concerning: caution OR declining
        if condition == OverallCondition::Caution || momentum_dir == MomentumDir::Declining {
            return Self::Concerning;
        }
        // Otherwise stable
        Self::Stable
    }
}

// ─── Dashboard frame ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct DashboardFrame {
    pub epoch:           u64,
    pub vector:          SystemHealthVector,
    pub phase:           ConstitutionalPhase,
    pub momentum_dir:    MomentumDir,
    pub momentum_int:    i64,
    pub overall_trend:   OverallTrend,
    pub frame_hash:      [u8; 32],
    pub prev_frame_hash: [u8; 32],
}

pub const DASHBOARD_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── Build frame ─────────────────────────────────────────────────────────────

pub fn build_frame(
    epoch:        u64,
    vector:       SystemHealthVector,
    phase:        ConstitutionalPhase,
    momentum_dir: MomentumDir,
    momentum_int: i64,
    prev_hash:    &[u8; 32],
) -> DashboardFrame {
    let overall_trend = OverallTrend::derive(vector.condition, momentum_dir, phase);
    let frame_hash    = compute_frame_hash(prev_hash, vector.condition, overall_trend, epoch);

    DashboardFrame {
        epoch,
        vector,
        phase,
        momentum_dir,
        momentum_int,
        overall_trend,
        frame_hash,
        prev_frame_hash: *prev_hash,
    }
}

fn compute_frame_hash(
    prev:      &[u8; 32],
    condition: OverallCondition,
    trend:     OverallTrend,
    epoch:     u64,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update([condition.as_u8()]);
    h.update([trend.as_u8()]);
    h.update(epoch.to_be_bytes());
    h.finalize().into()
}

// ─── Dashboard history ────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct DashboardHistory {
    frames: Vec<DashboardFrame>,
}

#[derive(Debug)]
pub struct DashboardError(pub &'static str);

impl DashboardHistory {
    pub fn new() -> Self { Self { frames: Vec::new() } }

    pub fn len(&self) -> usize { self.frames.len() }
    pub fn is_empty(&self) -> bool { self.frames.is_empty() }
    pub fn frames(&self) -> &[DashboardFrame] { &self.frames }

    pub fn last_hash(&self) -> [u8; 32] {
        self.frames.last().map(|f| f.frame_hash).unwrap_or(DASHBOARD_GENESIS_HASH)
    }

    pub fn current_trend(&self) -> OverallTrend {
        self.frames.last().map(|f| f.overall_trend).unwrap_or(OverallTrend::Stable)
    }

    pub fn thriving_count(&self) -> usize {
        self.frames.iter().filter(|f| f.overall_trend == OverallTrend::Thriving).count()
    }

    pub fn critical_count(&self) -> usize {
        self.frames.iter().filter(|f| f.overall_trend == OverallTrend::Critical).count()
    }

    /// Record a new frame. Epoch must be strictly increasing.
    pub fn record(
        &mut self,
        epoch:        u64,
        vector:       SystemHealthVector,
        phase:        ConstitutionalPhase,
        momentum_dir: MomentumDir,
        momentum_int: i64,
    ) -> Result<&DashboardFrame, DashboardError> {
        if let Some(last) = self.frames.last() {
            if epoch <= last.epoch {
                return Err(DashboardError("epoch must be strictly greater"));
            }
        }
        let prev_hash = self.last_hash();
        let frame = build_frame(epoch, vector, phase, momentum_dir, momentum_int, &prev_hash);
        self.frames.push(frame);
        Ok(self.frames.last().unwrap())
    }

    /// Verify hash chain integrity.
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = DASHBOARD_GENESIS_HASH;
        for (i, f) in self.frames.iter().enumerate() {
            if f.prev_frame_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_frame_hash(&prev, f.vector.condition, f.overall_trend, f.epoch);
            if expected != f.frame_hash {
                return (false, Some(i));
            }
            prev = f.frame_hash;
        }
        (true, None)
    }
}

impl Default for DashboardHistory {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::health_aggregator::{build_vector, VECTOR_GENESIS_HASH};
    use crate::swarm_health::HealthVerdict;
    use crate::resilience_watchdog::ResilienceVerdict;
    use crate::constitutional_pulse::PulseVerdict;
    use crate::coherence_stability::StabilityGrade;

    fn optimal_vector(epoch: u64) -> SystemHealthVector {
        build_vector(epoch,
            HealthVerdict::Pass, ResilienceVerdict::Stable,
            PulseVerdict::Green, StabilityGrade::A,
            MomentumDir::Stable, ConstitutionalPhase::Nominal,
            &VECTOR_GENESIS_HASH)
    }

    fn emergency_vector(epoch: u64) -> SystemHealthVector {
        build_vector(epoch,
            HealthVerdict::Fail, ResilienceVerdict::Oscillating,
            PulseVerdict::Red, StabilityGrade::F,
            MomentumDir::Declining, ConstitutionalPhase::Critical,
            &VECTOR_GENESIS_HASH)
    }

    // ── OverallTrend ──────────────────────────────────────────────────────────

    #[test]
    fn thriving_when_optimal_improving_nominal() {
        let t = OverallTrend::derive(
            OverallCondition::Optimal, MomentumDir::Improving, ConstitutionalPhase::Nominal);
        assert_eq!(t, OverallTrend::Thriving);
    }

    #[test]
    fn stable_when_good_stable() {
        let t = OverallTrend::derive(
            OverallCondition::Good, MomentumDir::Stable, ConstitutionalPhase::Nominal);
        assert_eq!(t, OverallTrend::Stable);
    }

    #[test]
    fn concerning_when_caution() {
        let t = OverallTrend::derive(
            OverallCondition::Caution, MomentumDir::Stable, ConstitutionalPhase::Nominal);
        assert_eq!(t, OverallTrend::Concerning);
    }

    #[test]
    fn concerning_when_declining_momentum() {
        let t = OverallTrend::derive(
            OverallCondition::Good, MomentumDir::Declining, ConstitutionalPhase::Nominal);
        assert_eq!(t, OverallTrend::Concerning);
    }

    #[test]
    fn critical_when_alert() {
        let t = OverallTrend::derive(
            OverallCondition::Alert, MomentumDir::Stable, ConstitutionalPhase::Nominal);
        assert_eq!(t, OverallTrend::Critical);
    }

    #[test]
    fn critical_when_emergency() {
        let t = OverallTrend::derive(
            OverallCondition::Emergency, MomentumDir::Improving, ConstitutionalPhase::Nominal);
        assert_eq!(t, OverallTrend::Critical);
    }

    #[test]
    fn critical_when_non_operational_phase() {
        let t = OverallTrend::derive(
            OverallCondition::Optimal, MomentumDir::Improving, ConstitutionalPhase::Critical);
        assert_eq!(t, OverallTrend::Critical);
    }

    #[test]
    fn trend_is_positive_for_thriving_and_stable() {
        assert!(OverallTrend::Thriving.is_positive());
        assert!(OverallTrend::Stable.is_positive());
        assert!(!OverallTrend::Concerning.is_positive());
        assert!(!OverallTrend::Critical.is_positive());
    }

    #[test]
    fn trend_ordering() {
        assert!(OverallTrend::Thriving < OverallTrend::Critical);
    }

    #[test]
    fn trend_as_u8() {
        assert_eq!(OverallTrend::Thriving.as_u8(), 0);
        assert_eq!(OverallTrend::Critical.as_u8(), 3);
    }

    #[test]
    fn trend_as_str() {
        assert_eq!(OverallTrend::Thriving.as_str(), "thriving");
        assert_eq!(OverallTrend::Stable.as_str(), "stable");
        assert_eq!(OverallTrend::Concerning.as_str(), "concerning");
        assert_eq!(OverallTrend::Critical.as_str(), "critical");
    }

    // ── build_frame ───────────────────────────────────────────────────────────

    #[test]
    fn optimal_improving_gives_thriving() {
        let v = optimal_vector(1);
        let f = build_frame(1, v, ConstitutionalPhase::Nominal, MomentumDir::Improving, 10,
                            &DASHBOARD_GENESIS_HASH);
        assert_eq!(f.overall_trend, OverallTrend::Thriving);
    }

    #[test]
    fn emergency_vector_gives_critical_trend() {
        let v = emergency_vector(1);
        let f = build_frame(1, v, ConstitutionalPhase::Critical, MomentumDir::Declining, -20,
                            &DASHBOARD_GENESIS_HASH);
        assert_eq!(f.overall_trend, OverallTrend::Critical);
    }

    #[test]
    fn frame_hash_nonzero() {
        let v = optimal_vector(1);
        let f = build_frame(1, v, ConstitutionalPhase::Nominal, MomentumDir::Stable, 0,
                            &DASHBOARD_GENESIS_HASH);
        assert_ne!(f.frame_hash, [0u8; 32]);
    }

    #[test]
    fn frame_hash_deterministic() {
        let v1 = optimal_vector(5);
        let v2 = optimal_vector(5);
        let v3 = optimal_vector(5);
        let f1 = build_frame(5, v1, ConstitutionalPhase::Nominal, MomentumDir::Stable, 0, &DASHBOARD_GENESIS_HASH);
        let f2 = build_frame(5, v2, ConstitutionalPhase::Nominal, MomentumDir::Stable, 0, &DASHBOARD_GENESIS_HASH);
        let f3 = build_frame(5, v3, ConstitutionalPhase::Nominal, MomentumDir::Stable, 0, &DASHBOARD_GENESIS_HASH);
        assert_eq!(f1.frame_hash, f2.frame_hash);
        assert_eq!(f2.frame_hash, f3.frame_hash);
    }

    #[test]
    fn different_epochs_different_frame_hash() {
        let v1 = optimal_vector(1);
        let v2 = optimal_vector(2);
        let f1 = build_frame(1, v1, ConstitutionalPhase::Nominal, MomentumDir::Stable, 0, &DASHBOARD_GENESIS_HASH);
        let f2 = build_frame(2, v2, ConstitutionalPhase::Nominal, MomentumDir::Stable, 0, &DASHBOARD_GENESIS_HASH);
        assert_ne!(f1.frame_hash, f2.frame_hash);
    }

    // ── DashboardHistory ──────────────────────────────────────────────────────

    #[test]
    fn new_history_empty() {
        let h = DashboardHistory::new();
        assert!(h.is_empty());
        assert_eq!(h.current_trend(), OverallTrend::Stable);
    }

    #[test]
    fn record_grows_history() {
        let mut h = DashboardHistory::new();
        h.record(1, optimal_vector(1), ConstitutionalPhase::Nominal, MomentumDir::Stable, 0).unwrap();
        h.record(2, optimal_vector(2), ConstitutionalPhase::Nominal, MomentumDir::Stable, 0).unwrap();
        assert_eq!(h.len(), 2);
    }

    #[test]
    fn duplicate_epoch_is_err() {
        let mut h = DashboardHistory::new();
        h.record(5, optimal_vector(5), ConstitutionalPhase::Nominal, MomentumDir::Stable, 0).unwrap();
        assert!(h.record(5, optimal_vector(5), ConstitutionalPhase::Nominal, MomentumDir::Stable, 0).is_err());
    }

    #[test]
    fn thriving_and_critical_counts_tracked() {
        let mut h = DashboardHistory::new();
        // Thriving
        h.record(1, optimal_vector(1), ConstitutionalPhase::Nominal, MomentumDir::Improving, 5).unwrap();
        // Critical
        h.record(2, emergency_vector(2), ConstitutionalPhase::Critical, MomentumDir::Declining, -10).unwrap();
        // Stable
        h.record(3, optimal_vector(3), ConstitutionalPhase::Nominal, MomentumDir::Stable, 0).unwrap();
        assert_eq!(h.thriving_count(), 1);
        assert_eq!(h.critical_count(), 1);
    }

    #[test]
    fn hash_chain_links() {
        let mut h = DashboardHistory::new();
        h.record(1, optimal_vector(1), ConstitutionalPhase::Nominal, MomentumDir::Stable, 0).unwrap();
        h.record(2, optimal_vector(2), ConstitutionalPhase::Nominal, MomentumDir::Stable, 0).unwrap();
        assert_eq!(h.frames()[1].prev_frame_hash, h.frames()[0].frame_hash);
    }

    #[test]
    fn verify_chain_clean() {
        let mut h = DashboardHistory::new();
        for i in 1u64..=5 {
            h.record(i, optimal_vector(i), ConstitutionalPhase::Nominal, MomentumDir::Stable, 0).unwrap();
        }
        let (valid, broken) = h.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }
}
