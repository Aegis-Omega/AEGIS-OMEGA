//! Phase 1 Orchestrator — SGM → LUT-KAN → RWKV → Lyapunov pipeline
//! EPISTEMIC TIER: T2

use crate::sgm_gate::SGMGate;
use crate::lut_kan::LUTKANRouter;
use crate::rwkv_state::RWKVStateCache;
use crate::lyapunov::LyapunovMonitor;
use crate::audit::AuditLogger;
use serde::Serialize;
use serde_json::json;

#[derive(Serialize, Debug)]
pub struct Phase1Output {
    pub step: u64,
    pub routing_entropy: f32,
    pub active_paths: usize,
    pub stable: bool,
    pub rollback_required: bool,
    pub cache_utilization_pct: f32,
    pub audit_hash: String,
}

pub struct Phase1Orchestrator {
    sgm: SGMGate,
    kan: LUTKANRouter,
    cache: RWKVStateCache,
    lyapunov: LyapunovMonitor,
    pub audit: AuditLogger,
}

impl Phase1Orchestrator {
    pub fn new(
        entropy_threshold: f32,
        num_paths: usize,
        cache_mb: usize,
        lyapunov_epsilon: f32,
    ) -> Self {
        Self {
            sgm: SGMGate::new(entropy_threshold),
            kan: LUTKANRouter::new(num_paths, 0.05, 0),
            cache: RWKVStateCache::new(cache_mb),
            lyapunov: LyapunovMonitor::new(lyapunov_epsilon),
            audit: AuditLogger::new(),
        }
    }

    /// Run one forward step: route → transform → cache → stability check.
    pub fn step(&mut self, activations: &[f32]) -> Phase1Output {
        // 1. Sparse gating
        let mask = self.sgm.route(activations);

        // 2. LUT-KAN transform
        let transformed = self.kan.transform(activations, &mask);

        // 3. Lyapunov stability assessment
        let lyap = self.lyapunov.assess(&transformed);

        // 4. RWKV cache: evict if needed, then store
        let packed = if transformed.len() >= 2 {
            RWKVStateCache::pack_int4(transformed[0], transformed[1])
        } else if !transformed.is_empty() {
            RWKVStateCache::pack_int4(transformed[0], 0.0)
        } else {
            0u8
        };
        if !self.cache.store_slot(packed, if lyap.stable { lyap.v_current } else { 0.0 }) {
            self.cache.evict_least_stable();
            self.cache.store_slot(packed, if lyap.stable { lyap.v_current } else { 0.0 });
        }

        // 5. Audit log
        let audit_hash = self.audit.log("PHASE1_STEP", &json!({
            "step": lyap.step,
            "entropy": mask.entropy,
            "active_paths": mask.active_indices.len(),
            "stable": lyap.stable,
            "delta_v": lyap.delta_v,
        }));

        Phase1Output {
            step: lyap.step,
            routing_entropy: mask.entropy,
            active_paths: mask.active_indices.len(),
            stable: lyap.stable,
            rollback_required: lyap.rollback_required,
            cache_utilization_pct: self.cache.utilization_pct(),
            audit_hash,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn orchestrator_runs_one_step() {
        let mut orch = Phase1Orchestrator::new(1.0, 4, 1, 0.01);
        let out = orch.step(&[0.1, 0.2, 0.3, 0.4]);
        assert_eq!(out.step, 1);
        assert!(out.audit_hash.len() == 64);
        assert!(out.active_paths <= 4);
    }

    #[test]
    fn audit_chain_valid_after_multiple_steps() {
        let mut orch = Phase1Orchestrator::new(1.0, 4, 1, 0.01);
        for i in 0..5 {
            orch.step(&[i as f32 * 0.1; 4]);
        }
        let (valid, _) = orch.audit.verify_chain();
        assert!(valid);
    }

    // 3. step number in output increments correctly
    #[test]
    fn step_count_increments_correctly() {
        let mut orch = Phase1Orchestrator::new(1.0, 4, 1, 0.01);
        for expected in 1u64..=5 {
            let out = orch.step(&[0.1; 4]);
            assert_eq!(out.step, expected);
        }
    }

    // 4. audit log is non-empty after a step
    #[test]
    fn audit_non_empty_after_step() {
        let mut orch = Phase1Orchestrator::new(1.0, 4, 1, 0.01);
        orch.step(&[0.5; 4]);
        assert!(!orch.audit.is_empty());
    }

    // 5. cache_utilization_pct is in [0, 100]
    #[test]
    fn cache_utilization_within_bounds() {
        let mut orch = Phase1Orchestrator::new(1.0, 4, 1, 0.01);
        for _ in 0..10 {
            let out = orch.step(&[0.2; 4]);
            assert!(out.cache_utilization_pct >= 0.0);
            assert!(out.cache_utilization_pct <= 100.0);
        }
    }

    // 6. active_paths never exceeds num_paths
    #[test]
    fn active_paths_within_num_paths() {
        let mut orch = Phase1Orchestrator::new(1.0, 4, 1, 0.01);
        for _ in 0..5 {
            let out = orch.step(&[0.3; 4]);
            assert!(out.active_paths <= 4);
        }
    }

    // 7. audit_hash is a 64-character hex string
    #[test]
    fn audit_hash_is_64_char_hex() {
        let mut orch = Phase1Orchestrator::new(1.0, 4, 1, 0.01);
        let out = orch.step(&[0.1, 0.2, 0.3, 0.4]);
        assert_eq!(out.audit_hash.len(), 64);
        assert!(out.audit_hash.chars().all(|c| c.is_ascii_hexdigit()));
    }

    // 8. rollback_required == !stable invariant
    #[test]
    fn rollback_required_matches_not_stable() {
        let mut orch = Phase1Orchestrator::new(1.0, 4, 1, 0.01);
        for i in 0..4 {
            let out = orch.step(&[i as f32; 4]);
            assert_eq!(out.rollback_required, !out.stable);
        }
    }

    // 9. consecutive outputs have strictly increasing step numbers
    #[test]
    fn step_numbers_strictly_increasing() {
        let mut orch = Phase1Orchestrator::new(1.0, 4, 1, 0.01);
        let mut prev = 0u64;
        for _ in 0..5 {
            let out = orch.step(&[0.1; 4]);
            assert!(out.step > prev);
            prev = out.step;
        }
    }

    // 10. audit entries count matches step count
    #[test]
    fn audit_len_matches_step_count() {
        let mut orch = Phase1Orchestrator::new(1.0, 4, 1, 0.01);
        for n in 1..=6usize {
            orch.step(&[0.05; 4]);
            assert_eq!(orch.audit.len(), n);
        }
    }
}
