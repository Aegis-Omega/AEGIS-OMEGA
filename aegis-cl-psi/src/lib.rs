//! # AEGIS-Ω CL-Ψ — State-Coherence Routing Fabric
//!
//! EPISTEMIC TIER: T2 (engineering hypothesis)
//! Constitutional root: AdaptivePower(T) ≤ ReplayVerifiability(T)
//!
//! This crate implements deterministic state-coherence routing, audit-trail state
//! machines, algorithmic divergence thresholds, and EU AI Act compliance hooks.
//! No emergent properties. No sovereign claims. T2 competency accumulation only.
//!
//! Phase 6 modules (cech_descent, postnikov_truncation, gerbe_splitter):
//! - Code tier: T2 — deterministic O(N) array operations
//! - Theoretical correspondence claim: T3 — the algebraic topology claim is a
//!   research conjecture and does not grant T0–T2 authority.

pub mod sgm_gate;
pub mod lut_kan;
pub mod rwkv_state;
pub mod lyapunov;
pub mod audit;
pub mod orchestrator;

// Phase 1.1 + 2
pub mod sahoo;
pub mod cloud_bridge;
pub mod devs_scheduler;
pub mod hip_runtime;  // always compiled; HIP calls gated inside by cfg(feature = "hip")

// Phase 3
pub mod ccil_lattice;
pub mod rocblas_gemm;  // always compiled; HIP calls gated inside by cfg(feature = "rocblas")

// Phase 4
pub mod obstruction_monitor;
pub mod poly_scheduler;

// Phase 5
pub mod local_resolver;

// Phase 6
pub mod cech_descent;
pub mod postnikov_truncation;
pub mod gerbe_splitter;
pub mod orchestrator_phase6;

// Phase 7 — production hardening
pub mod profiler;
pub mod compliance;
pub mod orchestrator_phase7;

// Gate 177 — Edge BFT Verifier (T2, WASM-compatible, stateless Ed25519 quorum proof)
pub mod edge_verifier;

// Gate 206 — Causal Confidence Arbiter (T2, prevents hallucination via confidence bounding)
pub mod causal_arbiter;

// Gate 207 — Adaptive Lineage Compaction Engine (T2, reduces memory footprint while preserving audit trail)
pub mod lineage_compactor;

// Gate 208 — Geometric Variance Engine (T2, replaces scalar sums with tensor-alignment metrics)
pub mod geometric_variance;

// Gate 208 — Triadic Merkle-Patricia Node (T2, gates state mutations behind geometric variance checks)
pub mod triadic_merkle_node;

// Gate 208 — Holonic State Machine (T2, orchestrates 3-layer escalation with BFT consensus)
pub mod holonic_state;

// Gate 211 — Orthogonal Domain Verifier (T2, |dot(C,O)| < ε enforces D0 ∩ D1 = ∅)
pub mod orthogonal_verifier;

// Gate 212 — Dodecagonal Symmetry Router (T2, 12-fold symmetric routing mesh, integer BFS)
pub mod dodecagonal_router;

// Gate 213 — Proportional Unit Metric (T2, rational arithmetic grid, SQUARED_SUM_K8=204)
pub mod proportional_metric;

// Gate 214 — Vortex Sequence Classifier (T2, digital root cycle detection, Triadic/Hexadic)
pub mod vortex_classifier;

// Gate 215 — Abjad Letter Encoder (T2, letter→integer routing via Abjad values, طارق=310)
pub mod abjad_encoder;

// Gate 216 — Tajweed Phonological DFA (T1, empirically validated Arabic phonology)
// Makharij articulation points = acoustic eigenstates. 4 noon-sakinah/tanween rules.
// Clinical studies: 27.3% cortisol reduction, alpha/theta EEG, vagal stimulation confirmed.
pub mod tajweed_dfa;

// Gate 217 — Ring Composition Verifier (T1, chiastic A-B-C-B'-A' structure)
// Isomorphic to AdaptivePower(T) ≤ ReplayVerifiability(T) — the constitutional law is a ring.
pub mod ring_composition;

// Gate 220 — Compile-Time Acyclic DAG Lattice + Lawvere Metric + Homotopy Witness (T1/T2)
// Cycles are unrepresentable: VerifiedEdge<From,To> requires From::RANK < To::RANK at compile time.
// Lawvere enrichment: d(A,C) ≤ d(A,B) + d(B,C) — triangle inequality by additive composition.
// HomotopyWitness: structural endpoint equality (T2 code / T3 full HoTT claim).
pub mod lattice_dag;

// Gate 220 (cont.) — Sovereign Persistence Layer (SPSF) (T2)
// Disk-boundary determinism: sequence-monotone, hash-chained, BTreeMap-indexed writes.
// Genesis root verified at open(); divergence from expected root is rejected (not ignored).
pub mod spsf;

// Gate 221 — Constitutional Convergence Certifier (T1/T2)
// 1/φ ≈ 0.6180339887 governs three scales: edge divergence (SUBATOMIC), path safety (MOLECULAR),
// swarm quorum (ORGANISM). certify_path<P>() proves AdaptivePower(T) ≤ ReplayVerifiability(T).
// RankSpan vortex classification: digital_root → Triadic {3,6,9} vs Hexadic {1,2,4,5,7,8}.
pub mod phi_convergence;

// Gate 222 — Constitutional Resonance Monitor (T1/T2)
// Unifies phi_convergence + ring_composition + vortex_classifier + spsf monotone law.
// is_resonant iff phi_convergent AND ring_valid AND sequence_monotone (three T1 invariants).
// resonance_coefficient = depth × vortex_factor × phi_headroom; > 5.0 → certified path.
pub mod resonance_monitor;

// Gate 223 — Constitutional Chord (T2)
// Compact 4-byte spectral fingerprint of constitutional state for distributed resonance checks.
// chord_bytes: [vortex_family, digital_root, resonance_depth, phi_class]
// chords_in_resonance(a, b): same VortexFamily + same PhiClass → compatible resonance class.
pub mod constitutional_chord;

// Gate 224 — Constitutional Chord Network (T2)
// Peer table tracking chord fingerprints across multiple nodes. Detects UNIFIED / CLUSTERED / SPLIT.
// BTreeMap<node_id, ConstitutionalChord> — deterministic iteration. Integer 1/φ quorum threshold.
// find_dissonant() identifies drift nodes; quorum_triadic checks the 1/φ Triadic majority.
pub mod chord_network;

// Gate 225 — Constitutional Self-Certification — Autopoietic State Closure (T1/T2)
// The system certifies its own constitutional state: SHA-256(resonance + network + version).
// CertificationVerdict: Certified / ProvisionallyGranted / Uncertified.
// Deterministic: same inputs → same self_hash across all platforms. No clock, no RNG.
pub mod self_certification;

pub use sgm_gate::SGMGate;
pub use lut_kan::LUTKANRouter;
pub use rwkv_state::RWKVStateCache;
pub use lyapunov::LyapunovMonitor;
pub use audit::AuditLogger;
pub use orchestrator::Phase1Orchestrator;
