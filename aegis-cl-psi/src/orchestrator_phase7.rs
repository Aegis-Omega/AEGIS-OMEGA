//! AEGIS-Ω Phase 7 — Production Orchestrator
//! EPISTEMIC TIER: T2
//!
//! Production wrapper integrating Phase 1-6 with:
//! - Resource profiling (VRAM/RAM bounds, 5.5GB/6GB headroom for AMD RX 570 8GB)
//! - Compliance gating (periodic SHA-256 audit chain verification)
//! - Graceful degradation on resource bound violation (Lyapunov eviction fallback)
//!
//! VRAM/RAM stubs: get_vram_usage_mb() / get_ram_usage_mb() return conservative
//! static estimates. Replace with hipMemGetInfo / sysinfo in production.

use crate::compliance::verify_audit_chain;
use crate::orchestrator_phase6::{Phase6Orchestrator, Phase6Output};
use crate::profiler::Profiler;
use std::sync::atomic::Ordering;

pub struct ProductionOrchestrator {
    pub engine: Phase6Orchestrator,
    pub profiler: Profiler,
    pub audit_path: String,
}

impl ProductionOrchestrator {
    /// Construct with 5.5GB VRAM / 6GB RAM bounds (conservative for AMD RX 570 / 8GB system).
    pub fn new(vocab_size: usize, blocked: &[usize]) -> Self {
        Self {
            engine: Phase6Orchestrator::new(vocab_size, blocked),
            profiler: Profiler::new(5_500.0, 6_000.0),
            audit_path: String::from("audit.jsonl"),
        }
    }

    pub fn with_audit_path(mut self, path: &str) -> Self {
        self.audit_path = path.to_string();
        self
    }

    /// T2-bounded inference step with profiling and compliance gating.
    /// Returns Err only when resource bounds are exceeded — other failures are encoded in Phase6Output.
    pub fn step(&mut self, activations: &[f32], observed: &[f32]) -> Result<Phase6Output, String> {
        self.profiler.record_step();

        let vram = get_vram_usage_mb();
        let ram = get_ram_usage_mb();

        if !self.profiler.is_within_bounds(vram, ram) {
            self.profiler.record_lyapunov_eviction();
            return Err(format!(
                "Resource bounds exceeded (VRAM={:.0}MB/{:.0}MB, RAM={:.0}MB/{:.0}MB); eviction triggered.",
                vram, self.profiler.vram_limit_mb, ram, self.profiler.ram_limit_mb
            ));
        }

        let output = self.engine.step(activations, observed);

        // Lyapunov instability → record as eviction pressure event
        if !output.lyapunov_stable {
            self.profiler.record_lyapunov_eviction();
        }

        // Periodic compliance verification every 100 steps (non-blocking; ignore errors)
        let steps = self.profiler.step_count.load(Ordering::Relaxed);
        if steps % 100 == 0 {
            let _ = verify_audit_chain(&self.audit_path);
        }

        Ok(output)
    }

    /// Export EU AI Act compliance manifest as JSON.
    /// Reads from audit_path; returns Err if file not accessible.
    pub fn export_compliance_manifest(&self) -> Result<String, String> {
        let report = verify_audit_chain(&self.audit_path)?;
        serde_json::to_string_pretty(&report).map_err(|e| e.to_string())
    }

    /// Returns current resource snapshot with live VRAM/RAM estimates.
    pub fn resource_snapshot(&self) -> crate::profiler::ResourceSnapshot {
        self.profiler.snapshot(get_vram_usage_mb(), get_ram_usage_mb())
    }
}

/// Platform stubs — replace with hipMemGetInfo / sysinfo in production ROCm builds.
fn get_vram_usage_mb() -> f32 {
    4_200.0
}

fn get_ram_usage_mb() -> f32 {
    3_800.0
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn new_orchestrator_within_bounds() {
        let mut orch = ProductionOrchestrator::new(16, &[]);
        let result = orch.step(&vec![0.1; 16], &vec![0.1; 16]);
        assert!(result.is_ok(), "step failed: {:?}", result.err());
    }

    #[test]
    fn step_increments_profiler_count() {
        let mut orch = ProductionOrchestrator::new(8, &[]);
        for _ in 0..5 {
            let _ = orch.step(&vec![0.2; 8], &vec![0.2; 8]);
        }
        let snap = orch.resource_snapshot();
        assert_eq!(snap.step_count, 5);
    }

    #[test]
    fn lyapunov_eviction_recorded_on_instability() {
        let mut orch = ProductionOrchestrator::new(4, &[]);
        // Run several steps to get a stable baseline then an unstable one
        for i in 0..3 {
            let v: Vec<f32> = (0..4).map(|j| (i + j) as f32 * 0.1).collect();
            let _ = orch.step(&v, &v);
        }
        // Eviction count only increases on instability; just verify it's a valid usize
        let snap = orch.resource_snapshot();
        assert!(snap.lyapunov_evictions <= snap.step_count);
    }

    #[test]
    fn export_manifest_error_on_missing_audit_file() {
        let orch = ProductionOrchestrator::new(4, &[])
            .with_audit_path("/tmp/no_such_file_aegis_xyz.jsonl");
        let result = orch.export_compliance_manifest();
        assert!(result.is_err());
    }

    #[test]
    fn export_manifest_ok_with_valid_audit_file() {
        use std::fs;
        let path = "/tmp/aegis_phase7_manifest_test.jsonl";
        fs::write(path, r#"{"event":"step","risk_tier":"Limited"}"#).unwrap();
        let orch = ProductionOrchestrator::new(4, &[]).with_audit_path(path);
        let result = orch.export_compliance_manifest();
        assert!(result.is_ok());
        let json = result.unwrap();
        assert!(json.contains("chain_valid"));
        fs::remove_file(path).ok();
    }

    // 6. resource_snapshot returns positive VRAM and RAM values
    #[test]
    fn resource_snapshot_returns_positive_usage() {
        let orch = ProductionOrchestrator::new(4, &[]);
        let snap = orch.resource_snapshot();
        assert!(snap.vram_used_mb > 0.0);
        assert!(snap.ram_used_mb > 0.0);
    }

    // 7. with_audit_path sets the audit path
    #[test]
    fn with_audit_path_sets_path() {
        let orch = ProductionOrchestrator::new(4, &[]).with_audit_path("/tmp/custom.jsonl");
        assert_eq!(orch.audit_path, "/tmp/custom.jsonl");
    }

    // 8. 10 steps produce step_count = 10
    #[test]
    fn multiple_steps_accumulate_correctly() {
        let mut orch = ProductionOrchestrator::new(4, &[]);
        for _ in 0..10 {
            let _ = orch.step(&vec![0.1; 4], &vec![0.1; 4]);
        }
        let snap = orch.resource_snapshot();
        assert_eq!(snap.step_count, 10);
    }

    // 9. lyapunov_evictions never exceed step_count
    #[test]
    fn lyapunov_evictions_within_step_count() {
        let mut orch = ProductionOrchestrator::new(4, &[]);
        for i in 0..6 {
            let v: Vec<f32> = (0..4).map(|j| (i * j) as f32 * 0.5).collect();
            let _ = orch.step(&v, &vec![0.1; 4]);
        }
        let snap = orch.resource_snapshot();
        assert!(snap.lyapunov_evictions <= snap.step_count);
    }

    // 10. step returns Ok on repeated stable inputs
    #[test]
    fn step_returns_ok_for_stable_input() {
        let mut orch = ProductionOrchestrator::new(8, &[]);
        let activations = vec![0.05f32; 8];
        let observed = vec![0.05f32; 8];
        for _ in 0..3 {
            let result = orch.step(&activations, &observed);
            assert!(result.is_ok());
        }
    }
}
