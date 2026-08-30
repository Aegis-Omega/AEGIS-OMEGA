//! Poly-Model Scheduler — DEVS-Ψ Extension for Superposition States
//! EPISTEMIC TIER: T2

use serde::Serialize;
use crate::obstruction_monitor::ObstructionClass;

#[derive(Clone, Copy, PartialEq, Debug, Serialize)]
pub enum PolyState {
    /// Single model, deterministic execution.
    LocalInference,
    /// Multiple divergent models held in superposition.
    Superposition,
    /// Superposition resolving via CCIL constitutional projection.
    Collapsing,
    /// Stable post-collapse single model.
    Resolved,
    /// Persistent H³ — cloud verification required.
    CloudVerify,
    /// Budget exhausted or critical failure.
    Rollback,
}

#[derive(Serialize, Debug, Clone)]
pub struct PolyTransition {
    pub from: PolyState,
    pub to: PolyState,
    pub reason: String,
    pub step: u64,
}

pub struct PolyScheduler {
    pub state: PolyState,
    pub step: u64,
    pub superposition_streak: u32,
    pub max_superposition_steps: u32,
    pub transitions: Vec<PolyTransition>,
    /// Held model outputs during superposition.
    pub superposition_branches: Vec<Vec<f32>>,
}

impl PolyScheduler {
    pub fn new(max_superposition_steps: u32) -> Self {
        Self {
            state: PolyState::LocalInference,
            step: 0,
            superposition_streak: 0,
            max_superposition_steps,
            transitions: Vec::new(),
            superposition_branches: Vec::new(),
        }
    }

    fn transition(&mut self, to: PolyState, reason: &str) {
        if self.state != to {
            self.transitions.push(PolyTransition {
                from: self.state, to,
                reason: reason.to_string(),
                step: self.step,
            });
            self.state = to;
        }
    }

    pub fn tick(
        &mut self,
        obstruction: &ObstructionClass,
        budget_exhausted: bool,
        collapse_ready: bool,
        branches: Option<Vec<Vec<f32>>>,
    ) {
        self.step += 1;

        if budget_exhausted {
            self.transition(PolyState::Rollback, "budget_exhausted");
            return;
        }

        match self.state {
            PolyState::LocalInference | PolyState::Resolved => {
                if obstruction != &ObstructionClass::None {
                    if let Some(b) = branches { self.superposition_branches = b; }
                    self.superposition_streak = 0;
                    self.transition(PolyState::Superposition, "obstruction_detected");
                }
            }
            PolyState::Superposition => {
                self.superposition_streak += 1;
                if self.superposition_streak >= self.max_superposition_steps {
                    self.transition(PolyState::CloudVerify, "superposition_timeout");
                } else if obstruction == &ObstructionClass::None {
                    self.transition(PolyState::Collapsing, "obstruction_resolved");
                }
            }
            PolyState::Collapsing => {
                if collapse_ready {
                    self.superposition_branches.clear();
                    self.superposition_streak = 0;
                    self.transition(PolyState::Resolved, "collapse_complete");
                }
            }
            PolyState::CloudVerify => {
                if collapse_ready {
                    self.superposition_branches.clear();
                    self.transition(PolyState::Resolved, "cloud_verified");
                }
            }
            PolyState::Rollback => {}
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn enters_superposition_on_obstruction() {
        let mut sched = PolyScheduler::new(5);
        sched.tick(&ObstructionClass::EnhancementDivergence, false, false, None);
        assert_eq!(sched.state, PolyState::Superposition);
    }

    #[test]
    fn collapses_when_obstruction_clears() {
        let mut sched = PolyScheduler::new(10);
        sched.tick(&ObstructionClass::EnhancementDivergence, false, false, None);
        sched.tick(&ObstructionClass::None, false, false, None); // → Collapsing
        sched.tick(&ObstructionClass::None, false, true, None);  // → Resolved
        assert_eq!(sched.state, PolyState::Resolved);
    }

    #[test]
    fn timeout_sends_to_cloud_verify() {
        let mut sched = PolyScheduler::new(2);
        sched.tick(&ObstructionClass::NoGlobalComparison, false, false, None);
        sched.tick(&ObstructionClass::NoGlobalComparison, false, false, None);
        sched.tick(&ObstructionClass::NoGlobalComparison, false, false, None);
        assert_eq!(sched.state, PolyState::CloudVerify);
    }

    // 4. Starts in LocalInference
    #[test]
    fn starts_in_local_inference() {
        let sched = PolyScheduler::new(5);
        assert_eq!(sched.state, PolyState::LocalInference);
    }

    // 5. Budget exhausted from any state → Rollback
    #[test]
    fn budget_exhausted_triggers_rollback() {
        let mut sched = PolyScheduler::new(5);
        sched.tick(&ObstructionClass::None, true, false, None);
        assert_eq!(sched.state, PolyState::Rollback);
    }

    // 6. State transitions are logged
    #[test]
    fn transitions_logged_on_state_change() {
        let mut sched = PolyScheduler::new(5);
        assert_eq!(sched.transitions.len(), 0);
        sched.tick(&ObstructionClass::EnhancementDivergence, false, false, None);
        assert_eq!(sched.transitions.len(), 1);
        assert_eq!(sched.transitions[0].from, PolyState::LocalInference);
        assert_eq!(sched.transitions[0].to, PolyState::Superposition);
    }

    // 7. No transition logged on stable no-obstruction ticks
    #[test]
    fn no_transition_on_no_obstruction() {
        let mut sched = PolyScheduler::new(5);
        sched.tick(&ObstructionClass::None, false, false, None);
        sched.tick(&ObstructionClass::None, false, false, None);
        assert_eq!(sched.transitions.len(), 0);
    }

    // 8. Branches are stored when entering superposition
    #[test]
    fn branches_stored_on_superposition() {
        let mut sched = PolyScheduler::new(5);
        let b = vec![vec![1.0f32, 2.0], vec![3.0, 4.0]];
        sched.tick(&ObstructionClass::EnhancementDivergence, false, false, Some(b.clone()));
        assert_eq!(sched.superposition_branches, b);
    }

    // 9. CloudVerify resolves to Resolved when collapse_ready
    #[test]
    fn cloud_verify_resolves_on_collapse_ready() {
        let mut sched = PolyScheduler::new(1);
        sched.tick(&ObstructionClass::NoGlobalComparison, false, false, None); // → Superposition
        sched.tick(&ObstructionClass::NoGlobalComparison, false, false, None); // streak=1 → CloudVerify
        sched.tick(&ObstructionClass::None, false, true, None); // cloud verified → Resolved
        assert_eq!(sched.state, PolyState::Resolved);
    }

    // 10. Step counter increments on every tick
    #[test]
    fn step_increments_on_tick() {
        let mut sched = PolyScheduler::new(5);
        assert_eq!(sched.step, 0);
        sched.tick(&ObstructionClass::None, false, false, None);
        assert_eq!(sched.step, 1);
        sched.tick(&ObstructionClass::None, false, false, None);
        assert_eq!(sched.step, 2);
    }
}
