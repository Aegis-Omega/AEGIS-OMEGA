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
}
