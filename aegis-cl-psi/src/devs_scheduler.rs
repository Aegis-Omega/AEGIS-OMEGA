//! DEVS-Ψ Scheduler — Discrete-Event State Machine
//! EPISTEMIC TIER: T2
//!
//! State transitions:
//!   LocalInference → Degraded (on Lyapunov violation or H_d > τ)
//!   Degraded → CloudVerify (on persistent instability)
//!   CloudVerify → LocalInference (on verified stable state)
//!   Any → Rollback (on budget cap or critical H_d)

use serde::Serialize;

#[derive(Clone, Copy, PartialEq, Debug, Serialize)]
pub enum DEVSState {
    LocalInference,
    Degraded,
    CloudVerify,
    Rollback,
}

#[derive(Serialize, Debug, Clone)]
pub struct DEVSTransition {
    pub from: DEVSState,
    pub to: DEVSState,
    pub reason: String,
    pub step: u64,
}

pub struct DEVSScheduler {
    pub state: DEVSState,
    pub step: u64,
    pub degraded_streak: u32,
    pub degraded_threshold: u32,
    pub rollback_buffer: Vec<Vec<u8>>,
    pub transitions: Vec<DEVSTransition>,
}

impl DEVSScheduler {
    pub fn new(degraded_threshold: u32) -> Self {
        Self {
            state: DEVSState::LocalInference,
            step: 0,
            degraded_streak: 0,
            degraded_threshold,
            rollback_buffer: Vec::new(),
            transitions: Vec::new(),
        }
    }

    fn transition(&mut self, to: DEVSState, reason: &str) {
        if self.state != to {
            self.transitions.push(DEVSTransition {
                from: self.state,
                to,
                reason: reason.to_string(),
                step: self.step,
            });
            self.state = to;
        }
    }

    /// Tick the scheduler with current stability signals.
    pub fn tick(
        &mut self,
        lyapunov_stable: bool,
        h_d_rollback: bool,
        cloud_verified: bool,
        budget_exhausted: bool,
    ) {
        self.step += 1;

        if budget_exhausted || (h_d_rollback && self.state == DEVSState::CloudVerify) {
            self.transition(DEVSState::Rollback, "budget_exhausted_or_persistent_h_d");
            return;
        }

        match self.state {
            DEVSState::LocalInference => {
                if !lyapunov_stable || h_d_rollback {
                    self.degraded_streak += 1;
                    self.transition(DEVSState::Degraded, "lyapunov_violation_or_h_d");
                } else {
                    self.degraded_streak = 0;
                }
            }
            DEVSState::Degraded => {
                if lyapunov_stable && !h_d_rollback {
                    self.degraded_streak = 0;
                    self.transition(DEVSState::LocalInference, "stability_restored");
                } else {
                    self.degraded_streak += 1;
                    if self.degraded_streak >= self.degraded_threshold {
                        self.transition(DEVSState::CloudVerify, "persistent_degradation");
                    }
                }
            }
            DEVSState::CloudVerify => {
                if cloud_verified {
                    self.degraded_streak = 0;
                    self.transition(DEVSState::LocalInference, "cloud_verified_stable");
                }
            }
            DEVSState::Rollback => {
                // Terminal state until external reset
            }
        }
    }

    pub fn needs_cloud_verification(&self) -> bool {
        self.state == DEVSState::CloudVerify
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn starts_in_local_inference() {
        let sched = DEVSScheduler::new(3);
        assert_eq!(sched.state, DEVSState::LocalInference);
    }

    #[test]
    fn transitions_to_degraded_on_instability() {
        let mut sched = DEVSScheduler::new(3);
        sched.tick(false, false, false, false);
        assert_eq!(sched.state, DEVSState::Degraded);
    }

    #[test]
    fn transitions_to_cloud_verify_on_streak() {
        let mut sched = DEVSScheduler::new(2);
        sched.tick(false, false, false, false); // → Degraded
        sched.tick(false, false, false, false); // streak=2 → CloudVerify
        assert_eq!(sched.state, DEVSState::CloudVerify);
    }

    #[test]
    fn recovers_to_local_after_cloud_verify() {
        let mut sched = DEVSScheduler::new(1);
        sched.tick(false, false, false, false); // → Degraded streak=1
        sched.tick(false, false, false, false); // → CloudVerify
        sched.tick(true, false, true, false);   // cloud_verified → LocalInference
        assert_eq!(sched.state, DEVSState::LocalInference);
    }

    #[test]
    fn budget_exhaustion_triggers_rollback() {
        let mut sched = DEVSScheduler::new(5);
        sched.tick(true, false, false, true); // budget_exhausted → Rollback
        assert_eq!(sched.state, DEVSState::Rollback);
    }
}
