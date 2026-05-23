//! Integration tests for AEGIS-Ω CL-Ψ
//! EPISTEMIC TIER: T2

use aegis_cl_psi::orchestrator::Phase1Orchestrator;
use aegis_cl_psi::orchestrator_phase6::Phase6Orchestrator;

#[test]
fn phase1_full_pipeline_10_steps() {
    let mut orch = Phase1Orchestrator::new(1.0, 8, 1, 0.01);
    for i in 0..10 {
        let activations: Vec<f32> = (0..8).map(|j| (i + j) as f32 * 0.05).collect();
        let out = orch.step(&activations);
        assert_eq!(out.step, i + 1);
        assert!(out.audit_hash.len() == 64);
    }
    let (valid, _) = orch.audit.verify_chain();
    assert!(valid, "Audit chain must be valid after 10 steps");
}

#[test]
fn phase6_full_pipeline_5_steps() {
    let mut orch = Phase6Orchestrator::new(8, &[]);
    for i in 0..5 {
        let v: Vec<f32> = (0..8).map(|j| (i + j) as f32 * 0.1).collect();
        let out = orch.step(&v, &v);
        assert_eq!(out.step, i + 1);
    }
    let (valid, _) = orch.audit.verify_chain();
    assert!(valid);
}

#[test]
fn ccil_blocks_specified_indices() {
    use aegis_cl_psi::ccil_lattice::CCILLattice;
    let lattice = CCILLattice::new(8, &[2, 5]);
    let mut logits = vec![1.0f32; 8];
    let report = lattice.apply(&mut logits);
    assert_eq!(report.interventions, 2);
    assert_eq!(logits[2], lattice.safety_floor);
    assert_eq!(logits[5], lattice.safety_floor);
    assert_eq!(logits[0], 1.0); // unblocked
}

#[test]
fn local_resolver_convergence() {
    use aegis_cl_psi::local_resolver::LocalResolver;
    let resolver = LocalResolver::new(0.3, 0.1, 0.01);
    let mut branches = vec![vec![1.0f32, 0.0], vec![0.9, 0.1]];
    let result = resolver.resolve(&mut branches);
    assert!(result.resolved);
}
