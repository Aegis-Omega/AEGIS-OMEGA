//! Lyapunov Monitor — Stability Margin per Forward Pass
//! EPISTEMIC TIER: T1 (empirically validated stability criterion)
//!
//! Enforces ΔV(x) ≤ −ε‖x‖² per step.
//! Violation triggers DEVS rollback + optional cloud verification.

use serde::Serialize;

#[derive(Debug, Serialize, Clone)]
pub struct LyapunovReport {
    pub step: u64,
    pub v_current: f32,
    pub v_previous: f32,
    pub delta_v: f32,
    pub norm_sq: f32,
    pub epsilon: f32,
    pub stable: bool,
    pub rollback_required: bool,
}

pub struct LyapunovMonitor {
    pub epsilon: f32,
    pub v_previous: f32,
    pub step: u64,
}

impl LyapunovMonitor {
    pub fn new(epsilon: f32) -> Self {
        Self { epsilon, v_previous: 0.0, step: 0 }
    }

    /// Compute Lyapunov function value: V(x) = ‖x‖² / 2
    pub fn lyapunov_value(state: &[f32]) -> f32 {
        state.iter().map(|&x| x * x).sum::<f32>() / 2.0
    }

    /// Assess stability for this step's state.
    /// stable = ΔV(x) ≤ −ε‖x‖² (descent condition satisfied)
    pub fn assess(&mut self, state: &[f32]) -> LyapunovReport {
        let v_current = Self::lyapunov_value(state);
        let norm_sq = state.iter().map(|&x| x * x).sum::<f32>();
        let delta_v = v_current - self.v_previous;
        let required_descent = -self.epsilon * norm_sq;
        let stable = delta_v <= required_descent || self.step == 0;
        self.step += 1;
        let report = LyapunovReport {
            step: self.step,
            v_current,
            v_previous: self.v_previous,
            delta_v,
            norm_sq,
            epsilon: self.epsilon,
            stable,
            rollback_required: !stable,
        };
        self.v_previous = v_current;
        report
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn stable_on_first_step() {
        let mut monitor = LyapunovMonitor::new(0.01);
        let report = monitor.assess(&[1.0, 0.0, 0.0]);
        assert!(report.stable);
        assert!(!report.rollback_required);
    }

    #[test]
    fn detects_instability_on_growth() {
        let mut monitor = LyapunovMonitor::new(0.01);
        monitor.assess(&[1.0f32]); // step 0 — always stable
        let report = monitor.assess(&[10.0f32]); // state grew → ΔV > 0 → unstable
        assert!(!report.stable);
        assert!(report.rollback_required);
    }

    #[test]
    fn stable_on_decreasing_state() {
        let mut monitor = LyapunovMonitor::new(0.0); // ε=0: any ΔV ≤ 0 is stable
        monitor.assess(&[2.0f32]);
        let report = monitor.assess(&[1.0f32]); // shrinking → ΔV < 0
        assert!(report.stable);
    }

    // 4. lyapunov_value of empty state is zero
    #[test]
    fn lyapunov_value_empty_is_zero() {
        assert_eq!(LyapunovMonitor::lyapunov_value(&[]), 0.0);
    }

    // 5. lyapunov_value of [2.0] = 2.0 (‖x‖²/2 = 4/2)
    #[test]
    fn lyapunov_value_single_element() {
        assert_eq!(LyapunovMonitor::lyapunov_value(&[2.0f32]), 2.0);
    }

    // 6. delta_v computed correctly between consecutive states
    #[test]
    fn delta_v_computed_correctly() {
        let mut monitor = LyapunovMonitor::new(0.01);
        monitor.assess(&[2.0f32]); // V_prev = 2.0
        let r = monitor.assess(&[1.0f32]); // V_curr = 0.5
        // delta_v = 0.5 - 2.0 = -1.5
        assert!((r.delta_v - (-1.5f32)).abs() < 1e-5);
    }

    // 7. norm_sq = Σ x_i²
    #[test]
    fn norm_sq_computed_correctly() {
        let mut monitor = LyapunovMonitor::new(0.01);
        let r = monitor.assess(&[3.0f32, 4.0f32]);
        assert_eq!(r.norm_sq, 25.0); // 9 + 16
    }

    // 8. step increments on each assess call
    #[test]
    fn step_increments_on_assess() {
        let mut monitor = LyapunovMonitor::new(0.0);
        assert_eq!(monitor.step, 0);
        monitor.assess(&[1.0f32]);
        assert_eq!(monitor.step, 1);
        monitor.assess(&[0.5f32]);
        assert_eq!(monitor.step, 2);
    }

    // 9. rollback_required = !stable always
    #[test]
    fn rollback_required_matches_not_stable() {
        let mut monitor = LyapunovMonitor::new(0.01);
        monitor.assess(&[1.0f32]);
        let r = monitor.assess(&[10.0f32]); // growing → unstable
        assert_eq!(r.rollback_required, !r.stable);
    }

    // 10. Determinism ×3: same sequence → same report
    #[test]
    fn assess_determinism_triple() {
        fn run() -> (bool, f32) {
            let mut m = LyapunovMonitor::new(0.01);
            m.assess(&[1.0f32]);
            let r = m.assess(&[0.5f32]);
            (r.stable, r.delta_v)
        }
        assert_eq!(run(), run());
        assert_eq!(run(), run());
    }
}
