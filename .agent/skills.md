# SOVEREIGN AGI OS — SKILLS REGISTRY

**Phase:** 1 (static, human-authored baseline)  
**Generated:** 2026-05-31T09:25:24.588371+00:00  
**Docs scanned:** 110  
**Skills:** 40

---

## Domain: `agent_operations`

### SKILL: agent_role_governance
- **Label:** Agent Role Governance
- **Tier:** T1
- **Confidence:** 0.80
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** agent, governance
- **Dependencies:** none
- **Evidence refs:** .agent/rules.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** ORCHESTRATOR / ARCHITECT / BUILDER / RESEARCHER / QA / DEBUG / REVIEWER / PRE-SHIP roles. Each role has constrained tool access. Builder: no web_search. Researcher: authorized web_search.

### SKILL: agent_handoff_protocol
- **Label:** Agent Handoff Protocol
- **Tier:** T1
- **Confidence:** 0.80
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** agent, governance
- **Dependencies:** agent_role_governance
- **Evidence refs:** .agent/rules.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** Mandatory format: [FROM]/[TO]/[TYPE: HANDOFF|REQUEST|BLOCKER|UPDATE]/CONTEXT/MESSAGE/EXPECTED RESPONSE.

### SKILL: cognitive_event_logging
- **Label:** Cognitive Event Logging
- **Tier:** T1
- **Confidence:** 0.80
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** agent, audit
- **Dependencies:** agent_handoff_protocol
- **Evidence refs:** .agent/rules.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** Log via tools/log-action.js: SKILL_CHECK, PLAN_CREATED, PLAN_MUTATED, CONTEXT_ROT, FATAL_BLOCKER, LANE_VIOLATION, MISSING_CAPABILITY, MISSION_REPORT.

### SKILL: three_strike_failsafe
- **Label:** 3-Strike Failsafe Protocol
- **Tier:** T1
- **Confidence:** 0.80
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** agent, constitutional
- **Dependencies:** agent_role_governance
- **Evidence refs:** .agent/rules.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** If VERIFY fails 3× on same approach: STOP, output FATAL_BLOCKER, log to log-action.js, do NOT retry same approach.

## Domain: `commercial_products`

### SKILL: shared_component_library
- **Label:** Shared Component Library (@shared)
- **Tier:** T1
- **Confidence:** 0.80
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** typescript, commercial
- **Dependencies:** none
- **Evidence refs:** CLAUDE.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** @shared alias → packages/shared. DashScope caller, useAsyncForm, ErrorAlert, LoadingSpinner, ScoreBar, ToolkitFooter. All 3 products import from here.

### SKILL: dashscope_qwen_integration
- **Label:** DashScope / Qwen API Integration
- **Tier:** T2
- **Confidence:** 0.65
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** commercial, typescript
- **Dependencies:** shared_component_library
- **Evidence refs:** CLAUDE.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** VITE_DASHSCOPE_API_KEY + VITE_DASHSCOPE_MODEL env vars. @shared/lib/dashscope generic caller. Default model: qwen-plus.

### SKILL: vercel_deployment
- **Label:** Vercel Deployment Pipeline
- **Tier:** T1
- **Confidence:** 0.80
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** deployment, commercial
- **Dependencies:** gate8_deployment_gate
- **Evidence refs:** DEPLOY.md, CLAUDE.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** One Vercel project per product (Root Directory set per product). Gate 8 must pass before any deployment. vercel --prod from product directory.

### SKILL: gumroad_product_pricing
- **Label:** Gumroad Product Pricing
- **Tier:** T1
- **Confidence:** 0.80
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** commercial
- **Dependencies:** vercel_deployment
- **Evidence refs:** docs/GUMROAD_LISTINGS.md, CLAUDE.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** $19/product, $29 any 2, $39 all 3 (Full Creator AI Toolkit). platform-picker + hook-generator + content-calendar.

## Domain: `constitutional_governance`

### SKILL: constitutional_law_enforcement
- **Label:** Constitutional Law Enforcement
- **Tier:** T0
- **Confidence:** 0.95
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** governance, constitutional, replay
- **Dependencies:** none
- **Evidence refs:** sovereign-omega-v2/docs/SOVEREIGN_RUNTIME_HANDOFF_v1.0.md, CONSTITUTIONAL_DECLARATION.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** Enforce Root Constitutional Law: AdaptivePower(T) ≤ ReplayVerifiability(T). Covers constitutional boundary checks, T0_ABORT conditions, and replay sovereignty.

### SKILL: martingale_gating
- **Label:** Martingale Gate Enforcement
- **Tier:** T1
- **Confidence:** 0.80
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** governance, martingale, typescript
- **Dependencies:** constitutional_law_enforcement
- **Evidence refs:** sovereign-omega-v2/docs/SOVEREIGN_RUNTIME_HANDOFF_v1.0.md, sovereign-omega-v2/docs/CONSTITUTIONAL_GOVERNANCE_SURFACE.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** certifyMartingale() + assertMartingaleAnchored() — suspends mutation authority when drift_bounded, is_anchored, or entropy_bounded constraints fail.

### SKILL: epistemic_tier_classification
- **Label:** Epistemic Tier Classification
- **Tier:** T0
- **Confidence:** 0.95
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** governance, audit, constitutional
- **Dependencies:** none
- **Evidence refs:** CLAUDE.md, .sovereign_context/SYSTEM_DIRECTIVES.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** Tag every module T0-T5. T0=mechanically proven; T4/T5 confined to docs/. A file's tier is determined by mechanism, not framing.

### SKILL: ontology_admission
- **Label:** Ontology Admission Enforcement
- **Tier:** T1
- **Confidence:** 0.80
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** governance, typescript, constitutional
- **Dependencies:** epistemic_tier_classification
- **Evidence refs:** sovereign-omega-v2/docs/SOVEREIGN_RUNTIME_HANDOFF_v1.0.md, docs/ONTOLOGY.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** admitAbstraction() blocks T4/T5 constructs. Every abstraction must reduce to six canonical primitives: Event, Transition, Ownership, Entropy, Transport, Verification.

## Domain: `cryptographic_infrastructure`

### SKILL: jcs_canonicalization
- **Label:** JCS RFC 8785 Canonicalization
- **Tier:** T0
- **Confidence:** 0.95
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** cryptograph, hash, typescript
- **Dependencies:** none
- **Evidence refs:** sovereign-omega-v2/docs/SOVEREIGN_RUNTIME_HANDOFF_v1.0.md, CLAUDE.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** canonicalizeJCS() in src/core/canonicalize.ts — RFC 8785 → SHA-256. Only permitted hash path. Never JSON.stringify for integrity.

### SKILL: hash_chain_construction
- **Label:** Hash Chain Construction
- **Tier:** T0
- **Confidence:** 0.95
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** cryptograph, hash, rust, replay
- **Dependencies:** jcs_canonicalization
- **Evidence refs:** sovereign-omega-v2/docs/SOVEREIGN_RUNTIME_HANDOFF_v1.0.md, docs/GATE_201_REFACTORING.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** Every Rust gate module implements verify_chain() → (bool, Option<usize>). All hash inputs use to_be_bytes(). f64 hashed as value.to_bits().to_be_bytes(). Chain starts from *_GENESIS_HASH = [0u8; 32].

### SKILL: genesis_seal_verification
- **Label:** Genesis Seal Verification
- **Tier:** T0
- **Confidence:** 0.95
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** cryptograph, constitutional, rust
- **Dependencies:** hash_chain_construction
- **Evidence refs:** docs/GATE_201_REFACTORING.md, docs/GATE_202_HARNESS_SDK.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** Verify T0 genesis seals in Planner and Evaluator. SHA-256 of empty payload = e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.

## Domain: `gate_progression`

### SKILL: gate_progression_system
- **Label:** Gate Progression System
- **Tier:** T1
- **Confidence:** 0.80
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** governance, audit
- **Dependencies:** constitutional_law_enforcement
- **Evidence refs:** docs/GATE_201_REFACTORING.md, docs/GATE_202_HARNESS_SDK.md, docs/GATE_203_SOVEREIGN_AUTOMATON.md, docs/GATE_204_ECCF_SECURITY_ALIGNMENT.md, docs/GATE_205_MESH_DEPLOYMENT.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** Gate 201 (refactoring) → 202 (harness SDK) → 203 (sovereign automaton) → 204 (ECCF security) → 205 (mesh deployment) → 210 (evaluator verdict correction). Each gate: complete → status COMPLETE + epistemic tier declaration.

### SKILL: sovereign_mesh_deployment
- **Label:** Sovereign Mesh Deployment
- **Tier:** T2
- **Confidence:** 0.65
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** deployment, governance, orchestrat
- **Dependencies:** vercel_deployment, gate_progression_system
- **Evidence refs:** docs/GATE_205_MESH_DEPLOYMENT.md, sovereign-omega-v2/docs/SOVEREIGN_OMEGA_INTEGRATED_SPEC_v2.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** Fractal Sovereign Mesh: Node α (Architect/Planner), Node β (Artisan/Generator), Node γ (Auditor/Evaluator). Alibaba Cloud FC / ACK targets.

## Domain: `harness_sdk`

### SKILL: khatt_loop_execution
- **Label:** Khatt Loop Execution
- **Tier:** T2
- **Confidence:** 0.65
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** khatt, gcce, harness, orchestrat
- **Dependencies:** planner_module, generator_module, evaluator_module
- **Evidence refs:** docs/GATE_202_HARNESS_SDK.md, docs/GCCE_ARCHITECTURE.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** 5-phase loop: Nuqta (inscribe truth) → Alif (hard constraints) → Rasm (continuous flow) → Tashkeel (uncertainty metadata) → Tanasub (fractal scaling).

### SKILL: planner_module
- **Label:** Planner Module (Node α)
- **Tier:** T2
- **Confidence:** 0.65
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** harness, orchestrat, python
- **Dependencies:** hash_chain_construction, genesis_seal_verification
- **Evidence refs:** docs/GATE_202_HARNESS_SDK.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** Receives directives, decomposes into CausalChain with Nuqta/Alif constraints. harness/sdk/planner/__init__.py — Node α (Architect) in Fractal Sovereign Mesh.

### SKILL: generator_module
- **Label:** Generator Module (Node β)
- **Tier:** T2
- **Confidence:** 0.65
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** harness, python
- **Dependencies:** planner_module
- **Evidence refs:** docs/GATE_202_HARNESS_SDK.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** Executes sprint work maintaining Rasm continuity. harness/sdk/generator/__init__.py — Node β (Artisan) in Fractal Sovereign Mesh.

### SKILL: evaluator_module
- **Label:** Evaluator Module (Node γ)
- **Tier:** T2
- **Confidence:** 0.65
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** harness, audit, python
- **Dependencies:** generator_module
- **Evidence refs:** docs/GATE_202_HARNESS_SDK.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** QA via Playwright, Tashkeel confidence validation, Tanasub fractal scaling check. Verdicts: PASS / PASS_WITH_WARNINGS / FAIL / REJECT_REROLL.

## Domain: `python_bridge`

### SKILL: python_bridge_development
- **Label:** Python Bridge Development
- **Tier:** T1
- **Confidence:** 0.80
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** python, telemetry, governance
- **Dependencies:** constitutional_law_enforcement
- **Evidence refs:** CLAUDE.md, sovereign-omega-v2/docs/SOVEREIGN_RUNTIME_HANDOFF_v1.0.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** HTTP server on port 7890 exposing /telemetry /event /gate_signal /health /claude /node. No time.time() in determinism-critical paths. PGCS must pass before TGCS is valid.

### SKILL: frozen_file_protection
- **Label:** Frozen Constitutional File Protection
- **Tier:** T0
- **Confidence:** 0.95
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** constitutional, cryptograph, audit
- **Dependencies:** genesis_seal_verification
- **Evidence refs:** CLAUDE.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** gate.py / dna.py / router.py are FROZEN. Verify SHA-256 before every session via node scripts/verify-hashes.mjs. Never modify without /guardian APPROVED verdict.

### SKILL: telemetry_streaming
- **Label:** Telemetry Streaming (Python)
- **Tier:** T2
- **Confidence:** 0.65
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** telemetry, python, governance
- **Dependencies:** python_bridge_development
- **Evidence refs:** CLAUDE.md, docs/TELEMETRY_SPEC.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** 5-second poll from cockpit + sovereign-omega-v2 dashboard to /telemetry. corruption_count must equal 0. bit-shifted integer arithmetic throughout.

## Domain: `rust_systems`

### SKILL: rust_gate_module_development
- **Label:** Rust Gate Module Development
- **Tier:** T0
- **Confidence:** 0.95
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** rust, hash, audit
- **Dependencies:** hash_chain_construction, deterministic_data_structures
- **Evidence refs:** CLAUDE.md, sovereign-omega-v2/docs/CL_PSI_SPECIFICATION.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** Implement aegis-cl-psi gate modules: public struct with verify_chain(), BTreeMap/BTreeSet only, saturating arithmetic, to_be_bytes() big-endian.

### SKILL: deterministic_data_structures
- **Label:** Deterministic Data Structures (Rust)
- **Tier:** T0
- **Confidence:** 0.95
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** rust, replay, constitutional
- **Dependencies:** none
- **Evidence refs:** CLAUDE.md, .sovereign_context/SYSTEM_DIRECTIVES.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** BTreeMap / BTreeSet only — never HashMap/HashSet in Rust. Iteration order must be deterministic for cross-platform replay.

### SKILL: safe_arithmetic
- **Label:** Safe Arithmetic (Rust)
- **Tier:** T0
- **Confidence:** 0.95
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** rust, constitutional
- **Dependencies:** none
- **Evidence refs:** CLAUDE.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** saturating_add / saturating_mul — no silent overflow. No f64 in consensus/threshold logic — use integer arithmetic.

### SKILL: cargo_build_and_test
- **Label:** Cargo Build & Test Lifecycle
- **Tier:** T1
- **Confidence:** 0.80
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** rust, deployment
- **Dependencies:** rust_gate_module_development
- **Evidence refs:** CLAUDE.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** cargo test (plain, never --all-features — hip/rocblas require ROCm hardware). cargo build --release for native. 5114 tests in aegis-cl-psi; 96 in aegis-runtime.

## Domain: `security_audit`

### SKILL: audit_trail_management
- **Label:** Audit Trail Management
- **Tier:** T1
- **Confidence:** 0.80
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** audit, replay, constitutional
- **Dependencies:** hash_chain_construction
- **Evidence refs:** docs/AUDIT_FINDINGS.md, docs/TRACEABILITY.md, sovereign-omega-v2/docs/TRACEABILITY.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** Immutable audit logs, full evolution traceability, is_replay_reconstructable: true on every record. directive_hash on all outputs.

### SKILL: eccf_security_alignment
- **Label:** ECCF Security Alignment
- **Tier:** T2
- **Confidence:** 0.65
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** eccf, audit, governance
- **Dependencies:** constitutional_law_enforcement
- **Evidence refs:** docs/GATE_204_ECCF_SECURITY_ALIGNMENT.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** Gate 204 security model. EU AI Act compliance audit chain. 385-gate Rust inference crate (aegis-cl-psi) tagged T2.

### SKILL: replay_sovereignty
- **Label:** Replay Sovereignty
- **Tier:** T0
- **Confidence:** 0.95
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** replay, constitutional, cryptograph
- **Dependencies:** hash_chain_construction, constitutional_law_enforcement
- **Evidence refs:** sovereign-omega-v2/docs/SOVEREIGN_RUNTIME_HANDOFF_v1.0.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** replay(genesis, events) → identical topology hash across Linux/macOS/Docker/WASM/ARM/x86. Replay determinism supersedes runtime convenience, orchestration flexibility, adaptive velocity.

## Domain: `skill_harness`

### SKILL: skill_tree_construction
- **Label:** Skill Tree Construction (Phase 1)
- **Tier:** T2
- **Confidence:** 0.65
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** skill, harness
- **Dependencies:** epistemic_tier_classification
- **Evidence refs:** sovereign-omega-v2/docs/SKILL_HARNESS_SPECIFICATION.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** Phase 1: static, human-authored, inspectable skill trees. Each skill is a probabilistic competency object with confidence, validated_runs, failure_rate, recency_score, domain_affinity, dependencies.

### SKILL: probabilistic_competency_modeling
- **Label:** Probabilistic Competency Modeling
- **Tier:** T2
- **Confidence:** 0.65
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** skill, harness, governance
- **Dependencies:** skill_tree_construction
- **Evidence refs:** sovereign-omega-v2/docs/SKILL_HARNESS_SPECIFICATION.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** Skills are NOT booleans. Required attributes: skill_id, confidence, validated_runs, failure_rate, recency_score, domain_affinity, dependencies, evidence_refs.

### SKILL: skill_event_sourcing
- **Label:** Skill Event Sourcing
- **Tier:** T2
- **Confidence:** 0.65
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** skill, harness, replay
- **Dependencies:** probabilistic_competency_modeling, typescript_event_ledger
- **Evidence refs:** sovereign-omega-v2/docs/SKILL_HARNESS_SPECIFICATION.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** Store evolution history, not snapshots. Events: SKILL_VALIDATED, SKILL_DEGRADED, SKILL_DECAYED, SKILL_SPECIALIZED, SKILL_REJECTED, SKILL_REINFORCED, SKILL_TRANSFERRED, SKILL_MERGED, SKILL_SPLIT.

### SKILL: orchestration_routing
- **Label:** Orchestration Routing via Skills
- **Tier:** T2
- **Confidence:** 0.65
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** skill, orchestrat, agent
- **Dependencies:** probabilistic_competency_modeling, bft_swarm_consensus
- **Evidence refs:** sovereign-omega-v2/docs/SKILL_HARNESS_SPECIFICATION.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** Route tasks to best-qualified agent using: competency confidence, specialization domain, failure history, domain affinity, recency score.

## Domain: `typescript_governance`

### SKILL: typescript_event_ledger
- **Label:** TypeScript Event Ledger
- **Tier:** T0
- **Confidence:** 0.95
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** typescript, replay, constitutional
- **Dependencies:** jcs_canonicalization
- **Evidence refs:** sovereign-omega-v2/docs/SOVEREIGN_RUNTIME_HANDOFF_v1.0.md, CLAUDE.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** Append-only canonical event log. No Date.now() except src/event/uuid.ts. No array.length for sequence numbers — use IndexedDBSequenceAllocator. deepFreeze every state object after construction.

### SKILL: bft_swarm_consensus
- **Label:** BFT Swarm Consensus
- **Tier:** T2
- **Confidence:** 0.65
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** consensus, bft, typescript, governance
- **Dependencies:** typescript_event_ledger, constitutional_law_enforcement
- **Evidence refs:** sovereign-omega-v2/docs/AGENT_COORDINATION_MODEL.md, CLAUDE.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** tallyVotes() → SwarmConvergenceRecord at 1/φ ≈ 0.618 quorum. Bernstein bounds (not Hoeffding). src/consensus/swarm.ts.

### SKILL: ralph_loop_execution
- **Label:** RALPH Loop Execution
- **Tier:** T1
- **Confidence:** 0.80
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** agent, typescript, orchestrat
- **Dependencies:** typescript_event_ledger
- **Evidence refs:** sovereign-omega-v2/handoff/RALPH_LOOP_OMEGA2_INTEGRATION_AUDIT.md, sovereign-omega-v2/handoff/RALPH_LOOP_OMEGA_EXECUTION_SYNTHESIS.md, CLAUDE.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** Fibonacci-paced R→A→L→P→H loops. src/agents/executor/loop.ts. Corpus knowledge enters through 5-phase loop only — no raw narrative propagation.

### SKILL: adaptive_lineage_tracking
- **Label:** Adaptive Lineage Tracking
- **Tier:** T1
- **Confidence:** 0.80
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** typescript, hash, governance
- **Dependencies:** hash_chain_construction, typescript_event_ledger
- **Evidence refs:** CLAUDE.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** Hash-chained capability evolution events. src/frame/adaptive-lineage.ts.

### SKILL: gate8_deployment_gate
- **Label:** Gate 8 — Pre-Commit Deployment Gate
- **Tier:** T0
- **Confidence:** 0.95
- **Validated runs:** 0
- **Failure rate:** 0.00
- **Recency score:** 1.00
- **Domain affinity:** deployment, typescript, governance
- **Dependencies:** typescript_event_ledger
- **Evidence refs:** CLAUDE.md
- **Last validated:** 2026-05-31T09:25:24.588371+00:00
- **Description:** npm run test && npm run typecheck && npm run build must pass in sovereign-omega-v2 before any commit. Mandatory — no exceptions.

---

## Format

```
### SKILL: <skill_id>
- **Tier:** T0-T3
- **Confidence:** 0.0–1.0 (T0=0.95 seed, T1=0.80, T2=0.65, T3=0.40)
- **Validated runs:** incremented by telemetry in Phase 2
- **Failure rate:** 0.0 in Phase 1 (no telemetry yet)
```

_Skills evolve via SKILL_VALIDATED / SKILL_DEGRADED / SKILL_DECAYED events in Phase 2._