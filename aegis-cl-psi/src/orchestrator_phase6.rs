//! Phase 6 Orchestrator — Full CL-Ψ Stack with Descent Engine
//! EPISTEMIC TIER: T2
//!
//! Integrates all phases:
//! SGM → LUT-KAN → RWKV → Lyapunov → SAHOO → CCIL →
//! Obstruction → Poly-Scheduler → LocalResolver →
//! CechDescent → PostnikovTruncation → GerbeSplitter → Audit

use crate::{
    sgm_gate::SGMGate,
    lut_kan::LUTKANRouter,
    rwkv_state::RWKVStateCache,
    lyapunov::LyapunovMonitor,
    audit::AuditLogger,
    sahoo::SAHOOMonitor,
    devs_scheduler::DEVSScheduler,
    ccil_lattice::CCILLattice,
    obstruction_monitor::MCMObstructionMonitor,
    poly_scheduler::PolyScheduler,
    local_resolver::LocalResolver,
    cech_descent::CechDescentState,
    postnikov_truncation::{PostnikovTruncation, TruncationLevel},
    gerbe_splitter::GerbeSplitter,
};
use serde::Serialize;
use serde_json::json;

#[derive(Serialize, Debug)]
pub struct Phase6Output {
    pub step: u64,
    pub routing_entropy: f32,
    pub lyapunov_stable: bool,
    pub h_d: f32,
    pub obstruction_class: String,
    pub k3_invariant: f32,
    pub resolved: bool,
    pub consensus: Vec<f32>,
    pub audit_hash: String,
}

#[allow(dead_code)]
pub struct Phase6Orchestrator {
    sgm: SGMGate,
    kan: LUTKANRouter,
    cache: RWKVStateCache,
    lyapunov: LyapunovMonitor,
    sahoo: SAHOOMonitor,
    devs: DEVSScheduler,
    ccil: CCILLattice,
    obstruction: MCMObstructionMonitor,
    poly: PolyScheduler,
    resolver: LocalResolver,
    gerbe: GerbeSplitter,
    pub audit: AuditLogger,
    step: u64,
}

impl Phase6Orchestrator {
    pub fn new(vocab_size: usize, blocked: &[usize]) -> Self {
        Self {
            sgm: SGMGate::new(1.0),
            kan: LUTKANRouter::new(vocab_size.max(4), 0.05, 0),
            cache: RWKVStateCache::new(16),
            lyapunov: LyapunovMonitor::new(0.001),
            sahoo: SAHOOMonitor::new(0.3),
            devs: DEVSScheduler::new(3),
            ccil: CCILLattice::new(vocab_size.max(4), blocked),
            obstruction: MCMObstructionMonitor::new(0.1, 0.5, 1.0),
            poly: PolyScheduler::new(5),
            resolver: LocalResolver::new(0.1, 0.05, 0.001),
            gerbe: GerbeSplitter::uniform(2),
            audit: AuditLogger::new(),
            step: 0,
        }
    }

    pub fn step(&mut self, activations: &[f32], observed: &[f32]) -> Phase6Output {
        self.step += 1;

        // Phase 1: SGM → LUT-KAN → RWKV
        let mask = self.sgm.route(activations);
        let mut transformed = self.kan.transform(activations, &mask);

        // Phase 2: CCIL masking
        let ccil_report = self.ccil.apply(&mut transformed);

        // Phase 2: Lyapunov + SAHOO
        let lyap = self.lyapunov.assess(&transformed);
        let sahoo = self.sahoo.assess(&transformed, observed);

        // Phase 3: DEVS tick
        self.devs.tick(lyap.stable, sahoo.rollback_triggered, false, false);

        // Phase 4: Obstruction check (use transformed as two "models" with slight variants)
        let variant: Vec<f32> = transformed.iter().map(|&v| v * 1.01).collect();
        let obs_report = self.obstruction.assess(&[transformed.clone(), variant.clone()]);

        // Phase 5: Poly-scheduler
        use crate::obstruction_monitor::ObstructionClass;
        self.poly.tick(&obs_report.obstruction_class, false, false,
            Some(vec![transformed.clone(), variant.clone()]));

        // Phase 6: Čech descent state
        let cech = CechDescentState::build(
            vec![transformed.clone(), variant.clone()]
        );

        // Postnikov τ≤1 truncation of the mean
        let mean: Vec<f32> = transformed.iter().zip(variant.iter())
            .map(|(&a, &b)| (a + b) / 2.0)
            .collect();
        let truncated = PostnikovTruncation::truncate(&mean, TruncationLevel::Tau1);

        // Gerbe splitting: select dominant branch
        let margins = vec![lyap.v_current.max(0.0), lyap.v_current.max(0.0) * 0.9];
        let consensus = if let Some(split) = self.gerbe.split(
            &[transformed.clone(), variant.clone()], &margins
        ) {
            split.resolved_vector
        } else {
            truncated.retained_components.clone()
        };

        let audit_hash = self.audit.log("PHASE6_STEP", &json!({
            "step": self.step,
            "entropy": mask.entropy,
            "lyapunov_stable": lyap.stable,
            "h_d": sahoo.h_d,
            "k3": cech.k3_invariant,
            "obstruction": format!("{:?}", obs_report.obstruction_class),
            "ccil_interventions": ccil_report.interventions,
        }));

        Phase6Output {
            step: self.step,
            routing_entropy: mask.entropy,
            lyapunov_stable: lyap.stable,
            h_d: sahoo.h_d,
            obstruction_class: format!("{:?}", obs_report.obstruction_class),
            k3_invariant: cech.k3_invariant,
            resolved: obs_report.obstruction_class == ObstructionClass::None,
            consensus,
            audit_hash,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn phase6_runs_one_step() {
        let mut orch = Phase6Orchestrator::new(4, &[]);
        let out = orch.step(&[0.1, 0.2, 0.3, 0.4], &[0.1, 0.2, 0.3, 0.4]);
        assert_eq!(out.step, 1);
        assert_eq!(out.audit_hash.len(), 64);
    }

    #[test]
    fn audit_chain_valid_after_steps() {
        let mut orch = Phase6Orchestrator::new(4, &[]);
        for i in 0..3 {
            orch.step(&[i as f32 * 0.1; 4], &[i as f32 * 0.1; 4]);
        }
        let (valid, _) = orch.audit.verify_chain();
        assert!(valid);
    }

    // 3. Step counter increments correctly
    #[test]
    fn step_counter_increments() {
        let mut orch = Phase6Orchestrator::new(4, &[]);
        for expected in 1u64..=4 {
            let out = orch.step(&[0.1; 4], &[0.1; 4]);
            assert_eq!(out.step, expected);
        }
    }

    // 4. consensus vector is non-empty after a step
    #[test]
    fn consensus_non_empty() {
        let mut orch = Phase6Orchestrator::new(4, &[]);
        let out = orch.step(&[0.2; 4], &[0.2; 4]);
        assert!(!out.consensus.is_empty());
    }

    // 5. audit_hash is a 64-char hex string
    #[test]
    fn audit_hash_64_chars() {
        let mut orch = Phase6Orchestrator::new(4, &[]);
        let out = orch.step(&[0.1, 0.2, 0.3, 0.4], &[0.1, 0.2, 0.3, 0.4]);
        assert_eq!(out.audit_hash.len(), 64);
        assert!(out.audit_hash.chars().all(|c| c.is_ascii_hexdigit()));
    }

    // 6. routing_entropy is non-negative
    #[test]
    fn routing_entropy_nonneg() {
        let mut orch = Phase6Orchestrator::new(4, &[]);
        for _ in 0..4 {
            let out = orch.step(&[0.3; 4], &[0.3; 4]);
            assert!(out.routing_entropy >= 0.0);
        }
    }

    // 7. h_d is non-negative
    #[test]
    fn h_d_nonneg() {
        let mut orch = Phase6Orchestrator::new(4, &[]);
        for _ in 0..4 {
            let out = orch.step(&[0.25; 4], &[0.25; 4]);
            assert!(out.h_d >= 0.0);
        }
    }

    // 8. audit log grows by one entry per step
    #[test]
    fn audit_grows_per_step() {
        let mut orch = Phase6Orchestrator::new(4, &[]);
        for n in 1..=5usize {
            orch.step(&[0.1; 4], &[0.1; 4]);
            assert_eq!(orch.audit.len(), n);
        }
    }

    // 9. Step numbers are strictly increasing across consecutive calls
    #[test]
    fn step_numbers_strictly_increasing() {
        let mut orch = Phase6Orchestrator::new(4, &[]);
        let mut prev = 0u64;
        for _ in 0..5 {
            let out = orch.step(&[0.15; 4], &[0.15; 4]);
            assert!(out.step > prev);
            prev = out.step;
        }
    }

    // 10. Determinism: same inputs produce same step-1 output fields
    #[test]
    fn same_inputs_same_step1_output() {
        let input = [0.1f32, 0.2, 0.3, 0.4];
        let mut a = Phase6Orchestrator::new(4, &[]);
        let mut b = Phase6Orchestrator::new(4, &[]);
        let out_a = a.step(&input, &input);
        let out_b = b.step(&input, &input);
        assert_eq!(out_a.step, out_b.step);
        assert_eq!(out_a.audit_hash, out_b.audit_hash);
        assert_eq!(out_a.lyapunov_stable, out_b.lyapunov_stable);
    }
}
