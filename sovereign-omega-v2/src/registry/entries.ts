// ============================================================
// SOVEREIGN OMEGA — Semantic Registry Entries
// EPISTEMIC TIER: T0
// Canonical classification of all T0/T1 TypeScript artifacts.
// ============================================================

import type { SemanticNode, AncestryEdge } from './types.js'
import { HolonicScale, MutationAuthority, ProofCoverage } from './types.js'

const MA = MutationAuthority
const PC = ProofCoverage
const HS = HolonicScale

const e = (t: string, r: AncestryEdge['relationship']): AncestryEdge =>
  ({ target_path: t, relationship: r })

const n = (
  path: string, module: string, gate: number | null, tier: 0 | 1,
  auth: MutationAuthority, coverage: readonly ProofCoverage[],
  edges: readonly AncestryEdge[], scale: HolonicScale,
  constitutional: boolean, description: string
): SemanticNode => ({ path, module, gate, tier, mutation_authority: auth,
  proof_coverage: coverage, ancestry_edges: edges, holonic_scale: scale,
  is_constitutional: constitutional, description })

export const REGISTRY_ENTRIES: readonly SemanticNode[] = Object.freeze([
  n('src/core/canonicalize.ts', 'core', 1, 0, MA.GATE_GUARDED,
    [PC.GATE_VERIFIED, PC.COQ_THEOREM],
    [e('formal/theories/Core/Hash.v', 'verified_by'), e('test/unit/jcs.test.ts', 'tested_by')],
    HS.SUBATOMIC, false, 'RFC 8785 JCS canonicalization engine — primary byte-ordering invariant'),

  n('src/core/types.ts', 'core', 1, 0, MA.GATE_GUARDED,
    [PC.GATE_VERIFIED],
    [e('src/event/store.ts', 'grounds'), e('src/gate/hoeffding.ts', 'grounds')],
    HS.ATOMIC, false, 'Branded primitive types and all runtime enumerations'),

  n('src/core/immutable.ts', 'core', 3, 0, MA.GATE_GUARDED,
    [PC.GATE_VERIFIED, PC.COQ_THEOREM],
    [e('formal/theories/Core/Reducer.v', 'verified_by'), e('test/unit/immutable.test.ts', 'tested_by')],
    HS.ATOMIC, false, 'deepFreeze implementation — every state object frozen after construction'),

  n('src/core/hashing.ts', 'core', 1, 0, MA.GATE_GUARDED,
    [PC.GATE_VERIFIED, PC.COQ_THEOREM],
    [e('formal/theories/Core/Hash.v', 'verified_by'), e('src/core/canonicalize.ts', 'depends_on')],
    HS.SUBATOMIC, false, 'SHA-256 byte-level hashing utilities'),

  n('src/core/tier.ts', 'core', null, 0, MA.GATE_GUARDED,
    [PC.GATE_VERIFIED, PC.TEST_COVERED],
    [e('src/core/types.ts', 'depends_on'), e('test/unit/tier.test.ts', 'tested_by')],
    HS.ATOMIC, false,
    'Epistemic tier classification, path ceiling enforcement, migration rule (no T4/T5 → T0–T2)'),

  n('src/core/schema-registry.ts', 'core', null, 0, MA.GATE_GUARDED,
    [PC.GATE_VERIFIED, PC.TEST_COVERED],
    [e('src/core/hashing.ts', 'depends_on'), e('src/core/types.ts', 'depends_on'),
     e('test/unit/schema-registry.test.ts', 'tested_by')],
    HS.ATOMIC, false,
    'SchemaRegistry with seal() — fail closed on unknown schema versions; no fallback validation'),

  n('src/core/fixedpoint.ts', 'core', 6, 0, MA.GATE_GUARDED,
    [PC.GATE_VERIFIED],
    [e('src/gate/hoeffding.ts', 'grounds'), e('test/determinism/bernstein-q32-fuzz.test.ts', 'tested_by')],
    HS.SUBATOMIC, false, 'Q32.32 fixed-point arithmetic for cross-runtime Bernstein bound computation'),

  n('src/core/semantics.ts', 'core', null, 0, MA.GATE_GUARDED,
    [PC.GATE_VERIFIED],
    [e('src/core/canonicalize.ts', 'depends_on'), e('test/determinism/jcs-fuzz.test.ts', 'tested_by')],
    HS.ATOMIC, false,
    'JS semantic particle field — isReplaySafe/assertReplaySafe/ReplaySafetyViolation; formalizes replay-safe value boundary'),

  n('src/event/store.ts', 'event', 2, 0, MA.GATE_GUARDED,
    [PC.GATE_VERIFIED, PC.COQ_THEOREM],
    [e('formal/theories/Core/Event.v', 'verified_by'), e('test/unit/sequence.test.ts', 'tested_by'),
     e('src/core/canonicalize.ts', 'depends_on')],
    HS.CELLULAR, false, 'Three-phase IDB append — E3 cryptographic event substrate'),

  n('src/event/uuid.ts', 'event', 2, 0, MA.GATE_GUARDED,
    [PC.GATE_VERIFIED],
    [e('test/unit/sequence.test.ts', 'tested_by')],
    HS.SUBATOMIC, false, 'UUIDv7 generation — only permitted Date.now() use; overflow guard'),

  n('src/core/wasm-interface.ts', 'core', null, 0, MA.GATE_GUARDED,
    [PC.TEST_COVERED],
    [e('src/core/fixedpoint.ts', 'depends_on'), e('test/determinism/wasm-parity.test.ts', 'tested_by')],
    HS.SUBATOMIC, false,
    'WASM parity harness — assertWasmParity detects JS/WASM divergence; kernel state machine (unloaded until binary compiled)'),

  n('src/event/workflow.ts', 'event', null, 1, MA.STANDARD,
    [PC.TEST_COVERED],
    [e('src/core/types.ts', 'depends_on'), e('src/event/workflow-recorder.ts', 'grounds'),
     e('test/unit/workflow.test.ts', 'tested_by')],
    HS.MOLECULAR, false, 'E5 cognitive workflow payload schemas — 8 AI-mediated development event types'),

  n('src/event/workflow-recorder.ts', 'event', null, 1, MA.STANDARD,
    [PC.TEST_COVERED],
    [e('src/core/semantics.ts', 'depends_on'), e('src/event/workflow.ts', 'depends_on'),
     e('test/unit/workflow.test.ts', 'tested_by')],
    HS.MOLECULAR, false,
    'E5 recorder — assertReplaySafe gate before IDB write; rejects non-E5 types and unsafe payloads'),

  n('src/event/mutation-registry.ts', 'event', null, 0, MA.GATE_GUARDED,
    [PC.TEST_COVERED],
    [e('src/core/types.ts', 'depends_on'), e('src/gate/mutation-governance.ts', 'grounds')],
    HS.MOLECULAR, false, 'Mutation governance registry with seal() and K-bound enforcement'),

  n('src/gate/hoeffding.ts', 'gate', 6, 0, MA.GATE_GUARDED,
    [PC.GATE_VERIFIED],
    [e('test/unit/gate.test.ts', 'tested_by'), e('src/core/fixedpoint.ts', 'depends_on')],
    HS.CELLULAR, false,
    'Bernstein anytime-valid bounds — named hoeffding.ts for legacy reasons (see H-03 annotation)'),

  n('src/gate/risk.ts', 'gate', 6, 0, MA.GATE_GUARDED,
    [PC.GATE_VERIFIED],
    [e('test/unit/gate.test.ts', 'tested_by'), e('src/gate/hoeffding.ts', 'depends_on')],
    HS.CELLULAR, false, 'Risk budget management and harmonic spending schedule'),

  n('src/gate/mutation-governance.ts', 'gate', null, 0, MA.GATE_GUARDED,
    [PC.TEST_COVERED],
    [e('src/core/immutable.ts', 'depends_on'), e('src/core/types.ts', 'depends_on')],
    HS.MOLECULAR, false, 'MutationGovernanceRegistry: capacity declarations and migration paths'),

  n('src/calibration/vcg.ts', 'calibration', 5, 1, MA.GATE_GUARDED,
    [PC.GATE_VERIFIED],
    [e('test/unit/vcg.test.ts', 'tested_by'), e('src/core/types.ts', 'depends_on')],
    HS.CELLULAR, false, 'VCG rolling-window tracker — 500-claim default, 0.35/0.50 alert thresholds'),

  n('src/verifier/registry.ts', 'verifier', 5, 1, MA.GATE_GUARDED,
    [PC.GATE_VERIFIED],
    [e('src/verifier/types.ts', 'depends_on')],
    HS.MOLECULAR, false, 'Verifier registry — V1/V2 full weight, V3 0.5, V4/V5 advisory-excluded'),

  n('src/projection/reducer.ts', 'projection', 4, 1, MA.GATE_GUARDED,
    [PC.GATE_VERIFIED, PC.COQ_THEOREM],
    [e('formal/theories/Core/Reducer.v', 'verified_by'), e('test/unit/reducer.test.ts', 'tested_by')],
    HS.MOLECULAR, false, 'Pure functional reducers over deepFrozen ProjectionState'),

  n('src/pipeline/index.ts', 'pipeline', 7, 1, MA.GATE_GUARDED,
    [PC.GATE_VERIFIED],
    [e('test/integration/pipeline.test.ts', 'tested_by')],
    HS.CELLULAR, false, 'Decision compilation pipeline — full DecisionSchema output'),

  n('src/runtime/projection-machine.ts', 'runtime', 8, 1, MA.GATE_GUARDED,
    [PC.GATE_VERIFIED, PC.TLA_SPEC],
    [e('formal/tlaplus/Omega.tla', 'verified_by')],
    HS.ORGANISM, false, 'RuntimeVersionPin validation — hard abort on any version mismatch'),
])
