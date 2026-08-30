// AEGIS-Ω Phase 7 — Load, Eviction, and Compliance Integration Tests
// EPISTEMIC TIER: T2

use aegis_cl_psi::compliance::{verify_audit_chain, RiskTier};
use aegis_cl_psi::orchestrator_phase7::ProductionOrchestrator;
use aegis_cl_psi::profiler::Profiler;
use std::fs;

fn tmp(name: &str) -> String {
    format!("/tmp/aegis_phase7_load_{}.jsonl", name)
}

// ─── Profiler tests ──────────────────────────────────────────────────────────

#[test]
fn profiler_bounds_enforcement_pass() {
    let p = Profiler::new(5500.0, 6000.0);
    assert!(p.is_within_bounds(4000.0, 4000.0));
}

#[test]
fn profiler_bounds_vram_exceeded() {
    let p = Profiler::new(5500.0, 6000.0);
    assert!(!p.is_within_bounds(6000.0, 4000.0));
}

#[test]
fn profiler_bounds_ram_exceeded() {
    let p = Profiler::new(5500.0, 6000.0);
    assert!(!p.is_within_bounds(4000.0, 7000.0));
}

#[test]
fn eviction_stress_1000_ops() {
    let p = Profiler::new(100.0, 100.0);
    for _ in 0..1000 {
        p.record_lyapunov_eviction();
        p.record_step();
    }
    let snap = p.snapshot(50.0, 50.0);
    assert_eq!(snap.lyapunov_evictions, 1000);
    assert_eq!(snap.step_count, 1000);
}

#[test]
fn cache_efficiency_metrics() {
    let p = Profiler::new(5500.0, 6000.0);
    for _ in 0..80 { p.record_cache_hit(); }
    for _ in 0..20 { p.record_cache_miss(); }
    let snap = p.snapshot(1000.0, 1000.0);
    assert!((snap.cache_hit_rate() - 0.8).abs() < 1e-4);
}

// ─── Compliance / Audit chain tests ──────────────────────────────────────────

#[test]
fn audit_chain_single_entry_valid() {
    let path = tmp("single");
    fs::write(&path, r#"{"timestamp":1,"risk_tier":"Limited"}"#).unwrap();
    let report = verify_audit_chain(&path).unwrap();
    assert!(report.chain_valid);
    assert_eq!(report.audit_entries, 1);
    fs::remove_file(&path).ok();
}

#[test]
fn audit_chain_multiple_entries_valid() {
    let path = tmp("multi");
    let lines = vec![
        r#"{"step":1,"risk_tier":"Limited"}"#,
        r#"{"step":2,"risk_tier":"Limited"}"#,
        r#"{"step":3,"risk_tier":"High"}"#,
    ].join("\n");
    fs::write(&path, lines).unwrap();
    let report = verify_audit_chain(&path).unwrap();
    assert!(report.chain_valid);
    assert_eq!(report.audit_entries, 3);
    fs::remove_file(&path).ok();
}

#[test]
fn audit_chain_risk_transitions_logged() {
    let path = tmp("risk");
    let lines = vec![
        r#"{"risk_tier":"Limited"}"#,
        r#"{"risk_tier":"High"}"#,
        r#"{"risk_tier":"Critical"}"#,
        r#"{"risk_tier":"Degraded"}"#,
    ].join("\n");
    fs::write(&path, lines).unwrap();
    let report = verify_audit_chain(&path).unwrap();
    assert_eq!(report.risk_transitions.len(), 3);
    assert_eq!(report.risk_transitions[0].2, RiskTier::High);
    assert_eq!(report.risk_transitions[1].2, RiskTier::Critical);
    assert_eq!(report.risk_transitions[2].2, RiskTier::Degraded);
    fs::remove_file(&path).ok();
}

#[test]
fn audit_chain_terminal_hash_deterministic() {
    let path = tmp("deterministic");
    fs::write(&path, r#"{"event":"test"}"#).unwrap();
    let r1 = verify_audit_chain(&path).unwrap();
    let r2 = verify_audit_chain(&path).unwrap();
    let r3 = verify_audit_chain(&path).unwrap();
    assert_eq!(r1.terminal_chain_hash, r2.terminal_chain_hash);
    assert_eq!(r2.terminal_chain_hash, r3.terminal_chain_hash);
    fs::remove_file(&path).ok();
}

#[test]
fn audit_chain_oversight_hook_ready_on_valid() {
    let path = tmp("oversight");
    fs::write(&path, r#"{"event":"step"}"#).unwrap();
    let report = verify_audit_chain(&path).unwrap();
    assert!(report.oversight_hook_ready);
    fs::remove_file(&path).ok();
}

// ─── ProductionOrchestrator throughput / integration tests ───────────────────

#[test]
fn production_orchestrator_10_step_throughput() {
    let mut orch = ProductionOrchestrator::new(8, &[]);
    for i in 0..10 {
        let activations: Vec<f32> = (0..8).map(|j| (i + j) as f32 * 0.05 + 0.1).collect();
        let result = orch.step(&activations, &activations);
        assert!(result.is_ok(), "Step {} failed: {:?}", i, result.err());
    }
    let snap = orch.resource_snapshot();
    assert_eq!(snap.step_count, 10);
}

#[test]
fn production_orchestrator_compliance_manifest_valid_json() {
    let path = tmp("prod_manifest");
    fs::write(&path, r#"{"event":"step","risk_tier":"Limited"}"#).unwrap();
    let orch = ProductionOrchestrator::new(4, &[]).with_audit_path(&path);
    let manifest = orch.export_compliance_manifest().unwrap();
    // Must be valid JSON containing expected fields
    let parsed: serde_json::Value = serde_json::from_str(&manifest).unwrap();
    assert!(parsed["chain_valid"].is_boolean());
    assert!(parsed["audit_entries"].is_number());
    assert!(parsed["oversight_hook_ready"].is_boolean());
    fs::remove_file(&path).ok();
}

#[test]
fn production_orchestrator_output_has_audit_hash() {
    let mut orch = ProductionOrchestrator::new(4, &[]);
    let result = orch.step(&[0.1, 0.2, 0.3, 0.4], &[0.1, 0.2, 0.3, 0.4]).unwrap();
    assert_eq!(result.audit_hash.len(), 64);
    assert!(result.audit_hash.chars().all(|c| c.is_ascii_hexdigit()));
}

#[test]
fn production_orchestrator_lyapunov_stable_on_smooth_input() {
    let mut orch = ProductionOrchestrator::new(4, &[]);
    // Smooth, low-magnitude input should not trigger instability
    let smooth: Vec<f32> = vec![0.1, 0.1, 0.1, 0.1];
    let result = orch.step(&smooth, &smooth).unwrap();
    // First step is always stable (no previous state to compare)
    assert!(result.lyapunov_stable);
}
