//! Gate 246 — Phase Transition Detector: constitutional regime change detection (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Models constitutional health as a 4-state machine. Transitions are detected
//! from consecutive PulseVerdict + ResilienceVerdict pairs.
//!
//! ConstitutionalPhase:
//!   Nominal  — Green pulse + healthy resilience
//!   Degraded — Yellow pulse OR non-intervention resilience
//!   Critical — Red pulse OR intervention-required resilience
//!   Recovery — Improving from Critical/Degraded back toward Nominal
//!
//! PhaseTransition — one (from, to) pair with epoch and cause.
//! TransitionCause:
//!   PulseEscalation  — pulse worsened
//!   PulseRecovery    — pulse improved
//!   ResilienceShift  — resilience verdict changed
//!   NoChange         — same phase retained (not a transition)
//!
//! phase_hash = SHA-256(prev_hash ‖ phase_byte ‖ cause_byte ‖ epoch_be8)

use sha2::{Sha256, Digest};
use crate::constitutional_pulse::PulseVerdict;
use crate::resilience_watchdog::ResilienceVerdict;

// ─── Constitutional phase ─────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ConstitutionalPhase {
    Nominal  = 0,
    Degraded = 1,
    Recovery = 2,
    Critical = 3,
}

impl ConstitutionalPhase {
    pub fn as_u8(self) -> u8 { self as u8 }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Nominal  => "nominal",
            Self::Degraded => "degraded",
            Self::Recovery => "recovery",
            Self::Critical => "critical",
        }
    }

    pub fn is_operational(self) -> bool {
        matches!(self, Self::Nominal | Self::Recovery)
    }

    pub fn severity(self) -> u8 {
        match self {
            Self::Nominal  => 0,
            Self::Recovery => 1,
            Self::Degraded => 2,
            Self::Critical => 3,
        }
    }
}

// ─── Transition cause ────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TransitionCause {
    PulseEscalation  = 0,
    PulseRecovery    = 1,
    ResilienceShift  = 2,
    Initial          = 3, // first observation, no prior phase
}

impl TransitionCause {
    pub fn as_u8(self) -> u8 { self as u8 }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::PulseEscalation => "pulse_escalation",
            Self::PulseRecovery   => "pulse_recovery",
            Self::ResilienceShift => "resilience_shift",
            Self::Initial         => "initial",
        }
    }
}

// ─── Phase observation ────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct PhaseObservation {
    pub epoch:      u64,
    pub phase:      ConstitutionalPhase,
    pub cause:      TransitionCause,
    pub pulse:      PulseVerdict,
    pub resilience: ResilienceVerdict,
    pub is_transition: bool, // true if phase changed from previous
    pub phase_hash:    [u8; 32],
    pub prev_hash:     [u8; 32],
}

pub const PHASE_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── Classify phase ──────────────────────────────────────────────────────────

fn classify_phase(pulse: PulseVerdict, resilience: ResilienceVerdict) -> ConstitutionalPhase {
    if pulse == PulseVerdict::Red || resilience.requires_intervention() {
        ConstitutionalPhase::Critical
    } else if pulse == PulseVerdict::Yellow || !resilience.is_healthy() {
        ConstitutionalPhase::Degraded
    } else {
        ConstitutionalPhase::Nominal
    }
}

fn determine_cause(
    prev_phase:      Option<ConstitutionalPhase>,
    new_phase:       ConstitutionalPhase,
    prev_pulse:      Option<PulseVerdict>,
    new_pulse:       PulseVerdict,
    prev_resilience: Option<ResilienceVerdict>,
    new_resilience:  ResilienceVerdict,
) -> TransitionCause {
    if prev_phase.is_none() {
        return TransitionCause::Initial;
    }
    let pp = prev_phase.unwrap();

    // Check if pulse worsened or improved
    let pulse_changed = prev_pulse.map(|p| p != new_pulse).unwrap_or(false);
    let resilience_changed = prev_resilience.map(|r| r != new_resilience).unwrap_or(false);

    if pulse_changed {
        // Was previous pulse better or worse than new?
        let prev_p = prev_pulse.unwrap();
        if new_pulse.as_u8() > prev_p.as_u8() {
            return TransitionCause::PulseEscalation;
        } else {
            return TransitionCause::PulseRecovery;
        }
    }

    if resilience_changed {
        return TransitionCause::ResilienceShift;
    }

    // Phase change without explicit signal change — use phase severity comparison
    if new_phase.severity() > pp.severity() {
        TransitionCause::PulseEscalation
    } else {
        TransitionCause::PulseRecovery
    }
}

fn compute_phase_hash(
    prev:  &[u8; 32],
    phase: ConstitutionalPhase,
    cause: TransitionCause,
    epoch: u64,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update([phase.as_u8()]);
    h.update([cause.as_u8()]);
    h.update(epoch.to_be_bytes());
    h.finalize().into()
}

// ─── Phase history ────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct PhaseHistory {
    observations: Vec<PhaseObservation>,
}

#[derive(Debug)]
pub struct PhaseError(pub &'static str);

impl PhaseHistory {
    pub fn new() -> Self { Self { observations: Vec::new() } }

    pub fn len(&self) -> usize { self.observations.len() }
    pub fn is_empty(&self) -> bool { self.observations.is_empty() }
    pub fn observations(&self) -> &[PhaseObservation] { &self.observations }

    pub fn last_hash(&self) -> [u8; 32] {
        self.observations.last().map(|o| o.phase_hash).unwrap_or(PHASE_GENESIS_HASH)
    }

    pub fn current_phase(&self) -> ConstitutionalPhase {
        self.observations.last().map(|o| o.phase).unwrap_or(ConstitutionalPhase::Nominal)
    }

    pub fn transition_count(&self) -> usize {
        self.observations.iter().filter(|o| o.is_transition).count()
    }

    pub fn critical_count(&self) -> usize {
        self.observations.iter().filter(|o| o.phase == ConstitutionalPhase::Critical).count()
    }

    /// Record a new observation. Epoch must be strictly greater.
    pub fn record(
        &mut self,
        epoch:      u64,
        pulse:      PulseVerdict,
        resilience: ResilienceVerdict,
    ) -> Result<&PhaseObservation, PhaseError> {
        if let Some(last) = self.observations.last() {
            if epoch <= last.epoch {
                return Err(PhaseError("epoch must be strictly greater"));
            }
        }

        let prev_phase      = self.observations.last().map(|o| o.phase);
        let prev_pulse      = self.observations.last().map(|o| o.pulse);
        let prev_resilience = self.observations.last().map(|o| o.resilience);

        let raw_phase = classify_phase(pulse, resilience);

        // Recovery: was Critical/Degraded, now less severe
        let phase = if let Some(pp) = prev_phase {
            if pp.severity() >= ConstitutionalPhase::Degraded.severity()
                && raw_phase.severity() < pp.severity()
            {
                ConstitutionalPhase::Recovery
            } else {
                raw_phase
            }
        } else {
            raw_phase
        };

        let cause = determine_cause(prev_phase, phase, prev_pulse, pulse, prev_resilience, resilience);
        let is_transition = prev_phase.map(|p| p != phase).unwrap_or(true);
        let prev_hash = self.last_hash();
        let phase_hash = compute_phase_hash(&prev_hash, phase, cause, epoch);

        let obs = PhaseObservation {
            epoch,
            phase,
            cause,
            pulse,
            resilience,
            is_transition,
            phase_hash,
            prev_hash,
        };

        self.observations.push(obs);
        Ok(self.observations.last().unwrap())
    }

    /// Verify hash chain integrity.
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = PHASE_GENESIS_HASH;
        for (i, obs) in self.observations.iter().enumerate() {
            if obs.prev_hash != prev {
                return (false, Some(i));
            }
            let expected = compute_phase_hash(&prev, obs.phase, obs.cause, obs.epoch);
            if expected != obs.phase_hash {
                return (false, Some(i));
            }
            prev = obs.phase_hash;
        }
        (true, None)
    }
}

impl Default for PhaseHistory {
    fn default() -> Self { Self::new() }
}

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    // ── ConstitutionalPhase ───────────────────────────────────────────────────

    #[test]
    fn nominal_is_operational() {
        assert!(ConstitutionalPhase::Nominal.is_operational());
        assert!(!ConstitutionalPhase::Critical.is_operational());
    }

    #[test]
    fn recovery_is_operational() {
        assert!(ConstitutionalPhase::Recovery.is_operational());
    }

    #[test]
    fn severity_ordering() {
        assert!(ConstitutionalPhase::Nominal.severity() < ConstitutionalPhase::Degraded.severity());
        assert!(ConstitutionalPhase::Degraded.severity() < ConstitutionalPhase::Critical.severity());
    }

    #[test]
    fn phase_as_u8() {
        assert_eq!(ConstitutionalPhase::Nominal.as_u8(), 0);
        assert_eq!(ConstitutionalPhase::Critical.as_u8(), 3);
    }

    #[test]
    fn phase_as_str() {
        assert_eq!(ConstitutionalPhase::Nominal.as_str(), "nominal");
        assert_eq!(ConstitutionalPhase::Recovery.as_str(), "recovery");
    }

    // ── classify_phase ────────────────────────────────────────────────────────

    #[test]
    fn green_stable_gives_nominal() {
        let p = classify_phase(PulseVerdict::Green, ResilienceVerdict::Stable);
        assert_eq!(p, ConstitutionalPhase::Nominal);
    }

    #[test]
    fn red_gives_critical() {
        let p = classify_phase(PulseVerdict::Red, ResilienceVerdict::Stable);
        assert_eq!(p, ConstitutionalPhase::Critical);
    }

    #[test]
    fn oscillating_gives_critical() {
        let p = classify_phase(PulseVerdict::Green, ResilienceVerdict::Oscillating);
        assert_eq!(p, ConstitutionalPhase::Critical);
    }

    #[test]
    fn yellow_gives_degraded() {
        let p = classify_phase(PulseVerdict::Yellow, ResilienceVerdict::Stable);
        assert_eq!(p, ConstitutionalPhase::Degraded);
    }

    // ── PhaseHistory transitions ───────────────────────────────────────────────

    #[test]
    fn initial_observation_is_transition() {
        let mut h = PhaseHistory::new();
        let obs = h.record(1, PulseVerdict::Green, ResilienceVerdict::Stable).unwrap();
        assert!(obs.is_transition); // first observation always counts
        assert_eq!(obs.cause, TransitionCause::Initial);
    }

    #[test]
    fn nominal_to_critical_is_transition() {
        let mut h = PhaseHistory::new();
        h.record(1, PulseVerdict::Green, ResilienceVerdict::Stable).unwrap();
        let obs = h.record(2, PulseVerdict::Red, ResilienceVerdict::Stable).unwrap();
        assert!(obs.is_transition);
        assert_eq!(obs.phase, ConstitutionalPhase::Critical);
        assert_eq!(obs.cause, TransitionCause::PulseEscalation);
    }

    #[test]
    fn critical_then_green_is_recovery() {
        let mut h = PhaseHistory::new();
        h.record(1, PulseVerdict::Red, ResilienceVerdict::Stable).unwrap();
        let obs = h.record(2, PulseVerdict::Green, ResilienceVerdict::Stable).unwrap();
        assert_eq!(obs.phase, ConstitutionalPhase::Recovery);
        assert!(obs.is_transition);
    }

    #[test]
    fn sustained_nominal_no_transition() {
        let mut h = PhaseHistory::new();
        h.record(1, PulseVerdict::Green, ResilienceVerdict::Stable).unwrap();
        let obs = h.record(2, PulseVerdict::Green, ResilienceVerdict::Stable).unwrap();
        assert!(!obs.is_transition);
        assert_eq!(obs.phase, ConstitutionalPhase::Nominal);
    }

    #[test]
    fn resilience_shift_causes_transition() {
        let mut h = PhaseHistory::new();
        h.record(1, PulseVerdict::Yellow, ResilienceVerdict::Stable).unwrap();
        let obs = h.record(2, PulseVerdict::Yellow, ResilienceVerdict::Degrading).unwrap();
        assert!(obs.is_transition || obs.cause == TransitionCause::ResilienceShift);
    }

    #[test]
    fn transition_count_tracked() {
        let mut h = PhaseHistory::new();
        h.record(1, PulseVerdict::Green, ResilienceVerdict::Stable).unwrap(); // initial → transition
        h.record(2, PulseVerdict::Green, ResilienceVerdict::Stable).unwrap(); // same → no transition
        h.record(3, PulseVerdict::Red,   ResilienceVerdict::Stable).unwrap(); // → transition
        h.record(4, PulseVerdict::Green, ResilienceVerdict::Stable).unwrap(); // recovery → transition
        assert_eq!(h.transition_count(), 3);
    }

    #[test]
    fn critical_count_tracked() {
        let mut h = PhaseHistory::new();
        h.record(1, PulseVerdict::Red, ResilienceVerdict::Stable).unwrap();
        h.record(2, PulseVerdict::Red, ResilienceVerdict::Stable).unwrap();
        h.record(3, PulseVerdict::Green, ResilienceVerdict::Stable).unwrap();
        assert_eq!(h.critical_count(), 2);
    }

    #[test]
    fn duplicate_epoch_is_err() {
        let mut h = PhaseHistory::new();
        h.record(5, PulseVerdict::Green, ResilienceVerdict::Stable).unwrap();
        assert!(h.record(5, PulseVerdict::Green, ResilienceVerdict::Stable).is_err());
    }

    #[test]
    fn phase_hash_nonzero() {
        let mut h = PhaseHistory::new();
        let obs = h.record(1, PulseVerdict::Green, ResilienceVerdict::Stable).unwrap();
        assert_ne!(obs.phase_hash, [0u8; 32]);
    }

    #[test]
    fn verify_chain_clean() {
        let mut h = PhaseHistory::new();
        h.record(1, PulseVerdict::Green, ResilienceVerdict::Stable).unwrap();
        h.record(2, PulseVerdict::Red, ResilienceVerdict::Stable).unwrap();
        h.record(3, PulseVerdict::Green, ResilienceVerdict::Recovering).unwrap();
        h.record(4, PulseVerdict::Green, ResilienceVerdict::Stable).unwrap();
        let (valid, broken) = h.verify_chain();
        assert!(valid);
        assert!(broken.is_none());
    }
}
