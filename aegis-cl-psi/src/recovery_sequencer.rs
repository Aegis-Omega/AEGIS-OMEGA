//! Gate 252 — Recovery Sequencer: time-ordered step execution with progress hash (T2)
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//!
//! Sequences the top-priority InterventionActions from a set of InterventionPlans
//! into a time-ordered RecoverySequence with StepStatus tracking.
//!
//! RecoveryStep:
//!   step_index   — usize (0-based position in sequence)
//!   epoch        — u64 (epoch when step was scheduled)
//!   kind         — InterventionKind
//!   priority     — u8
//!   status       — StepStatus (Pending/InProgress/Completed/Skipped)
//!   step_hash    — SHA-256(prev ‖ kind_byte ‖ status_byte ‖ epoch_be8)
//!
//! RecoverySequence:
//!   steps            — Vec<RecoveryStep> sorted by priority descending
//!   sequence_hash    — SHA-256(all step_hashes chained)
//!   completed_count  — count of Completed steps
//!   pending_count    — count of Pending steps
//!   is_complete      — all non-Skipped steps are Completed
//!
//! sequence_hash = SHA-256(step0.step_hash ‖ step1.step_hash ‖ ... ‖ epoch_be8)

use sha2::{Sha256, Digest};
use crate::intervention_recommender::{InterventionAction, InterventionKind, InterventionPlan};

// ─── Step status ──────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum StepStatus {
    Pending    = 0,
    InProgress = 1,
    Completed  = 2,
    Skipped    = 3,
}

impl StepStatus {
    pub fn as_u8(self) -> u8 { self as u8 }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::Pending    => "pending",
            Self::InProgress => "in_progress",
            Self::Completed  => "completed",
            Self::Skipped    => "skipped",
        }
    }

    pub fn is_terminal(self) -> bool {
        matches!(self, Self::Completed | Self::Skipped)
    }
}

// ─── Recovery step ────────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct RecoveryStep {
    pub step_index: usize,
    pub epoch:      u64,
    pub kind:       InterventionKind,
    pub priority:   u8,
    pub status:     StepStatus,
    pub step_hash:  [u8; 32],
}

fn compute_step_hash(
    prev:       &[u8; 32],
    kind:       InterventionKind,
    status:     StepStatus,
    epoch:      u64,
) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update([kind.as_u8()]);
    h.update([status.as_u8()]);
    h.update(epoch.to_be_bytes());
    h.finalize().into()
}

// ─── Recovery sequence ────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub struct RecoverySequence {
    pub epoch:           u64,
    pub steps:           Vec<RecoveryStep>,
    pub sequence_hash:   [u8; 32],
    pub completed_count: usize,
    pub pending_count:   usize,
    pub is_complete:     bool,
}

pub const SEQUENCE_GENESIS_HASH: [u8; 32] = [0u8; 32];

// ─── Build sequence ───────────────────────────────────────────────────────────

/// Build a RecoverySequence from the top-priority action of each plan.
/// Plans are deduplicated by InterventionKind (first occurrence wins).
/// Steps are sorted by priority descending, then kind ascending for determinism.
pub fn build_sequence(epoch: u64, plans: &[InterventionPlan]) -> RecoverySequence {
    // Collect unique top actions (deduplicated by kind)
    let mut seen_kinds = [false; 7]; // 7 InterventionKind variants
    let mut unique_actions: Vec<&InterventionAction> = Vec::new();

    for plan in plans {
        for action in &plan.actions {
            let idx = action.kind.as_u8() as usize;
            if !seen_kinds[idx] {
                seen_kinds[idx] = true;
                unique_actions.push(action);
            }
        }
    }

    // Sort by priority descending, then kind ascending for determinism
    unique_actions.sort_by(|a, b| {
        b.priority.cmp(&a.priority).then(a.kind.cmp(&b.kind))
    });

    // Build steps with chained hashes
    let mut prev_hash = SEQUENCE_GENESIS_HASH;
    let steps: Vec<RecoveryStep> = unique_actions.iter().enumerate().map(|(i, action)| {
        let step_hash = compute_step_hash(&prev_hash, action.kind, StepStatus::Pending, epoch);
        let step = RecoveryStep {
            step_index: i,
            epoch,
            kind:       action.kind,
            priority:   action.priority,
            status:     StepStatus::Pending,
            step_hash,
        };
        prev_hash = step_hash;
        step
    }).collect();

    let sequence_hash = compute_sequence_hash(&steps, epoch);
    let completed_count = steps.iter().filter(|s| s.status == StepStatus::Completed).count();
    let pending_count   = steps.iter().filter(|s| s.status == StepStatus::Pending).count();
    let is_complete     = steps.iter()
        .filter(|s| s.status != StepStatus::Skipped)
        .all(|s| s.status == StepStatus::Completed);

    RecoverySequence { epoch, steps, sequence_hash, completed_count, pending_count, is_complete }
}

fn compute_sequence_hash(steps: &[RecoveryStep], epoch: u64) -> [u8; 32] {
    let mut h = Sha256::new();
    for s in steps {
        h.update(s.step_hash);
    }
    h.update(epoch.to_be_bytes());
    h.finalize().into()
}

/// Advance a step to a new status, recomputing affected step_hash.
pub fn advance_step(
    sequence: RecoverySequence,
    step_index: usize,
    new_status: StepStatus,
) -> Result<RecoverySequence, SequenceError> {
    if step_index >= sequence.steps.len() {
        return Err(SequenceError("step_index out of bounds"));
    }
    if sequence.steps[step_index].status.is_terminal() {
        return Err(SequenceError("step is already terminal"));
    }

    let mut steps = sequence.steps.clone();
    let prev_hash = if step_index == 0 {
        SEQUENCE_GENESIS_HASH
    } else {
        steps[step_index - 1].step_hash
    };
    let new_hash = compute_step_hash(&prev_hash, steps[step_index].kind, new_status, sequence.epoch);
    steps[step_index].status    = new_status;
    steps[step_index].step_hash = new_hash;

    // Recompute hashes for all subsequent steps (chain is broken by the change)
    for i in (step_index + 1)..steps.len() {
        let ph = steps[i - 1].step_hash;
        let new_h = compute_step_hash(&ph, steps[i].kind, steps[i].status, sequence.epoch);
        steps[i].step_hash = new_h;
    }

    let sequence_hash   = compute_sequence_hash(&steps, sequence.epoch);
    let completed_count = steps.iter().filter(|s| s.status == StepStatus::Completed).count();
    let pending_count   = steps.iter().filter(|s| s.status == StepStatus::Pending).count();
    let is_complete     = steps.iter()
        .filter(|s| s.status != StepStatus::Skipped)
        .all(|s| s.status == StepStatus::Completed);

    Ok(RecoverySequence { epoch: sequence.epoch, steps, sequence_hash, completed_count, pending_count, is_complete })
}

#[derive(Debug)]
pub struct SequenceError(pub &'static str);

// ─── Tests ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::alert_engine::AlertSeverity;
    use crate::health_aggregator::{build_vector, VECTOR_GENESIS_HASH};
    use crate::intervention_recommender::{build_plan, PLAN_GENESIS_HASH};
    use crate::swarm_health::HealthVerdict;
    use crate::resilience_watchdog::ResilienceVerdict;
    use crate::constitutional_pulse::PulseVerdict;
    use crate::coherence_stability::StabilityGrade;
    use crate::momentum_tracker::MomentumDir;
    use crate::phase_transition::ConstitutionalPhase;

    fn emergency_plan() -> InterventionPlan {
        let v = build_vector(1,
            HealthVerdict::Fail, ResilienceVerdict::Oscillating,
            PulseVerdict::Red, StabilityGrade::F,
            MomentumDir::Declining, ConstitutionalPhase::Critical,
            &VECTOR_GENESIS_HASH);
        build_plan(1, AlertSeverity::Emergency, &v, &PLAN_GENESIS_HASH)
    }

    fn nominal_plan() -> InterventionPlan {
        let v = build_vector(1,
            HealthVerdict::Pass, ResilienceVerdict::Stable,
            PulseVerdict::Green, StabilityGrade::A,
            MomentumDir::Stable, ConstitutionalPhase::Nominal,
            &VECTOR_GENESIS_HASH);
        build_plan(1, AlertSeverity::None, &v, &PLAN_GENESIS_HASH)
    }

    // ── StepStatus ────────────────────────────────────────────────────────────

    #[test]
    fn terminal_statuses() {
        assert!(StepStatus::Completed.is_terminal());
        assert!(StepStatus::Skipped.is_terminal());
        assert!(!StepStatus::Pending.is_terminal());
        assert!(!StepStatus::InProgress.is_terminal());
    }

    #[test]
    fn status_as_str() {
        assert_eq!(StepStatus::Pending.as_str(), "pending");
        assert_eq!(StepStatus::Completed.as_str(), "completed");
    }

    // ── build_sequence ────────────────────────────────────────────────────────

    #[test]
    fn empty_plans_gives_empty_sequence() {
        let seq = build_sequence(1, &[]);
        assert!(seq.steps.is_empty());
        assert!(seq.is_complete); // vacuously true
        assert_eq!(seq.pending_count, 0);
    }

    #[test]
    fn emergency_plan_produces_steps() {
        let plan = emergency_plan();
        let seq = build_sequence(1, &[plan]);
        assert!(!seq.steps.is_empty());
        // First step should be highest priority (EmergencyHalt=100)
        assert_eq!(seq.steps[0].kind, InterventionKind::EmergencyHalt);
        assert_eq!(seq.steps[0].priority, 100);
    }

    #[test]
    fn all_steps_start_pending() {
        let plan = emergency_plan();
        let seq = build_sequence(1, &[plan]);
        assert!(seq.steps.iter().all(|s| s.status == StepStatus::Pending));
    }

    #[test]
    fn pending_count_matches_steps() {
        let plan = emergency_plan();
        let seq = build_sequence(1, &[plan]);
        assert_eq!(seq.pending_count, seq.steps.len());
        assert_eq!(seq.completed_count, 0);
    }

    #[test]
    fn sequence_hash_nonzero() {
        let plan = emergency_plan();
        let seq = build_sequence(1, &[plan]);
        assert_ne!(seq.sequence_hash, [0u8; 32]);
    }

    #[test]
    fn sequence_hash_deterministic() {
        let seq1 = build_sequence(5, &[emergency_plan()]);
        let seq2 = build_sequence(5, &[emergency_plan()]);
        let seq3 = build_sequence(5, &[emergency_plan()]);
        assert_eq!(seq1.sequence_hash, seq2.sequence_hash);
        assert_eq!(seq2.sequence_hash, seq3.sequence_hash);
    }

    #[test]
    fn dedup_by_kind_across_plans() {
        // Two plans that both include EmergencyHalt — should appear only once
        let plan1 = emergency_plan();
        let plan2 = emergency_plan();
        let seq = build_sequence(1, &[plan1, plan2]);
        let halt_count = seq.steps.iter().filter(|s| s.kind == InterventionKind::EmergencyHalt).count();
        assert_eq!(halt_count, 1);
    }

    #[test]
    fn step_indices_are_sequential() {
        let plan = emergency_plan();
        let seq = build_sequence(1, &[plan]);
        for (i, s) in seq.steps.iter().enumerate() {
            assert_eq!(s.step_index, i);
        }
    }

    #[test]
    fn steps_sorted_priority_desc() {
        let plan = emergency_plan();
        let seq = build_sequence(1, &[plan]);
        let priorities: Vec<u8> = seq.steps.iter().map(|s| s.priority).collect();
        let mut sorted = priorities.clone();
        sorted.sort_by(|a, b| b.cmp(a));
        assert_eq!(priorities, sorted);
    }

    // ── advance_step ──────────────────────────────────────────────────────────

    #[test]
    fn advance_first_step_to_in_progress() {
        let plan = emergency_plan();
        let seq = build_sequence(1, &[plan]);
        let advanced = advance_step(seq, 0, StepStatus::InProgress).unwrap();
        assert_eq!(advanced.steps[0].status, StepStatus::InProgress);
    }

    #[test]
    fn advance_to_completed_reduces_pending() {
        let plan = emergency_plan();
        let seq = build_sequence(1, &[plan]);
        let n = seq.steps.len();
        // Complete all steps sequentially
        let mut current = seq;
        for i in 0..n {
            current = advance_step(current, i, StepStatus::Completed).unwrap();
        }
        assert_eq!(current.completed_count, n);
        assert_eq!(current.pending_count, 0);
        assert!(current.is_complete);
    }

    #[test]
    fn advance_out_of_bounds_is_err() {
        let seq = build_sequence(1, &[nominal_plan()]);
        let n = seq.steps.len();
        assert!(advance_step(seq, n + 10, StepStatus::Completed).is_err());
    }

    #[test]
    fn advance_terminal_step_is_err() {
        let plan = emergency_plan();
        let seq = build_sequence(1, &[plan]);
        let advanced = advance_step(seq, 0, StepStatus::Completed).unwrap();
        assert!(advance_step(advanced, 0, StepStatus::InProgress).is_err());
    }

    #[test]
    fn sequence_hash_changes_after_advance() {
        let plan = emergency_plan();
        let seq = build_sequence(1, &[plan]);
        let original_hash = seq.sequence_hash;
        let advanced = advance_step(seq, 0, StepStatus::Completed).unwrap();
        assert_ne!(advanced.sequence_hash, original_hash);
    }

    #[test]
    fn is_complete_false_with_pending_steps() {
        let plan = emergency_plan();
        let seq = build_sequence(1, &[plan]);
        assert!(!seq.is_complete);
    }
}
