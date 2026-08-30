// ============================================================
// Gate 48 — End-to-End RALPH Frame Integration
// ~20 tests: runFrame() constitutional signals feed buildTopology,
//   topology feeds TopologyLineage, epoch chain certifies after
//   multi-frame sequence, determinism across full pipeline,
//   constitutional signals preserved through all layers.
//
// This is the first test that chains ALL constitutional layers
// together in a single execution path:
//
//   runFrame() → constitutional signals (SITR/AOIE/verdict)
//     → buildTopology (binds signals to topology hash)
//       → TopologyLineage (causal chain)
//         → synthesizeEpoch (DFA cert + topology → epoch_hash)
//           → EpochChain (epoch sequence → global chain cert)
//
// Proves the holonic composition invariant: the runtime is not
// just correct at each layer — it is correct across all layers
// simultaneously.
// ============================================================

import { describe, it, expect } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import { SITRRuntime } from '../../src/sitr/runtime.js'
import { ConstitutionalRuntime } from '../../src/constitutional/runtime.js'
import { runFrame } from '../../src/frame/kernel.js'
import { buildTopology } from '../../src/frame/topology.js'
import { TopologyLineage, certifyLineage } from '../../src/frame/lineage.js'
import { initialMachine, transition, certifyExecution } from '../../src/frame/dfa.js'
import { synthesizeEpoch } from '../../src/frame/epoch.js'
import { EpochChain, certifyEpochChain } from '../../src/frame/epoch-chain.js'
import type { CoordinationFrame } from '../../src/agents/types.js'
import type { WorkflowReplayFrame } from '../../src/agents/workflows/types.js'
import type { AgentTelemetrySnapshot } from '../../src/agents/telemetry/agent-telemetry.js'
import type { RuntimeSnapshot as InvariantRuntimeSnapshot } from '../../src/core/invariant-checker.js'
import type { PolicyMutation, EpistemicAssertion } from '../../src/aoie/types.js'

// ─── Frame helpers ─────────────────────────────────────────

function h(c: string): SHA256Hex { return c.padEnd(64, c) as SHA256Hex }
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

const CLEAN_TELEMETRY: AgentTelemetrySnapshot = Object.freeze({
  agent_coordination_stability: 1,
  workflow_replay_integrity: 1,
  workspace_memory_density: 0,
  extension_ecology_entropy: 0,
  mutation_chain_depth: 0,
  orchestration_pressure_index: 0,
})

const CLEAN_INVARIANTS: InvariantRuntimeSnapshot = Object.freeze({
  vcg_error: 0,
  drift_index: 0,
  corruption_count: 0,
  pgcs_passes: true,
  calibrator_passes: true,
  failsafe_state: 'healthy' as const,
  sequence: 1,
  gate_sealed: true,
})

const PANEL_SEQ = Object.freeze([1, 1, 1, 1, 1, 1, 1, 1, 1, 1])

function makeFrame(seq_n: number = 1): CoordinationFrame {
  return Object.freeze({
    frame_id: `f-${seq_n}`,
    sequence: seq_n,
    agent_id: 'agent-001',
    action_type: 'observe' as const,
    mutation_ids: [],
    replay_safe: true,
  })
}

function makeWfFrame(seq_n: number = 1): WorkflowReplayFrame {
  return Object.freeze({
    frame_id: `wf-${seq_n}`,
    workflow_id: 'wflow-001',
    sequence: seq_n,
    step_type: 'gather' as const,
    input_hash: h('a'),
    output_hash: h('b'),
    invariant_satisfied: true,
  })
}

// ─── DFA cert builder (reuses epoch test pattern) ──────────

async function makeDfaCert(s: number) {
  let m = initialMachine(seq(s))
  const hashes: SHA256Hex[] = [h('0'), h('1'), h('2'), h('3'), h('4')]
  const phases = ['READ', 'ASSESS', 'LOCK', 'PROPAGATE', 'HARMONIZE'] as const
  const records = []
  for (let i = 0; i < phases.length; i++) {
    const { machine, record } = await transition(m, phases[i]!, hashes[i]!)
    records.push(record)
    m = machine
  }
  return certifyExecution(records, seq(s))
}

// ─── Full pipeline builder ─────────────────────────────────

async function runFullPipeline(n: number) {
  // Layer 1: Frame execution (RALPH kernel)
  const frameResult = runFrame({
    frames: [makeFrame(n)],
    workflowFrames: [makeWfFrame(n)],
    telemetry: CLEAN_TELEMETRY,
    mutations: [] as PolicyMutation[],
    assertions: [] as EpistemicAssertion[],
    invariantSnapshot: { ...CLEAN_INVARIANTS, sequence: n },
    activeAgentIds: ['agent-001'],
    activeWorkflowIds: ['wflow-001'],
    panelSequenceNumbers: PANEL_SEQ,
    sequence: n,
    decision_id: `d-${n}`,
    sitr: SITRRuntime.empty(),
    constitutional: ConstitutionalRuntime.empty(),
  })

  // Layer 2: Topology (binds constitutional signals to hash)
  const dfaCert = await makeDfaCert(n)
  const topology = await buildTopology({
    sitr_state: frameResult.sitr.currentState(),
    aoie_global_state: frameResult.aoie.global_state,
    constitutional_verdict: frameResult.constitutional.currentVerdict(),
    ledger_root: h('a'),
    consensus_qc_hash: null,
    dfa_certificate_hash: dfaCert.certificate_hash,
    sequence: seq(n),
  })

  // Layer 3: Epoch (binds DFA cert + topology into epoch_hash)
  const epoch = await synthesizeEpoch({
    dfa_certificate: dfaCert,
    topology,
    lineage_terminal_hash: null,
    capsule_attestation_hash: null,
  })

  return { frameResult, topology, dfaCert, epoch }
}

// ─── Signal preservation through layers ───────────────────
// Proves: frame constitutional signals survive into the topology hash.

describe('Constitutional signals preserved through layers', () => {
  it('clean frame → STABLE/SECURE/PERMIT in topology fields', async () => {
    const { topology } = await runFullPipeline(1)
    expect(topology.sitr_state).toBe('STABLE')
    expect(topology.aoie_global_state).toBe('SECURE')
    expect(topology.constitutional_verdict).toBe('PERMIT')
  })

  it('topology_hash reflects constitutional signals: different verdict → different hash', async () => {
    // Build two topologies with different verdicts (manually, since frame always gives PERMIT
    // for clean input — test the topology layer directly for different signal)
    const cert = await makeDfaCert(1)
    const tAllow = await buildTopology({
      sitr_state: 'STABLE', aoie_global_state: 'SECURE',
      constitutional_verdict: 'PERMIT',
      ledger_root: h('a'), consensus_qc_hash: null,
      dfa_certificate_hash: cert.certificate_hash, sequence: seq(1),
    })
    const tDefer = await buildTopology({
      sitr_state: 'STABLE', aoie_global_state: 'SECURE',
      constitutional_verdict: 'DEFER',
      ledger_root: h('a'), consensus_qc_hash: null,
      dfa_certificate_hash: cert.certificate_hash, sequence: seq(1),
    })
    expect(tAllow.topology_hash).not.toBe(tDefer.topology_hash)
  })

  it('epoch_hash encodes topology_hash: different topologies → different epochs', async () => {
    const { epoch: e1 } = await runFullPipeline(1)
    const { epoch: e2 } = await runFullPipeline(2)
    expect(e1.epoch_hash).not.toBe(e2.epoch_hash)
  })

  it('epoch preserves topology_hash from frame pipeline', async () => {
    const { topology, epoch } = await runFullPipeline(1)
    expect(epoch.topology_hash).toBe(topology.topology_hash)
  })

  it('epoch preserves dfa_certificate_hash from frame pipeline', async () => {
    const { dfaCert, epoch } = await runFullPipeline(1)
    expect(epoch.dfa_certificate_hash).toBe(dfaCert.certificate_hash)
  })
})

// ─── Multi-frame lineage chain ─────────────────────────────
// Prove that 10 successive frame executions can be recorded as
// a certifiable TopologyLineage.

describe('Multi-frame TopologyLineage', () => {
  it('10 frames build a valid 10-entry lineage', async () => {
    let lineage = TopologyLineage.empty()
    for (let i = 1; i <= 10; i++) {
      const { topology } = await runFullPipeline(i)
      lineage = await lineage.append(topology)
    }
    expect(lineage.length).toBe(10)
    const cert = await certifyLineage(lineage.getAll())
    expect(cert.is_valid).toBe(true)
    expect(cert.entry_count).toBe(10)
  })

  it('lineage entries carry frame constitutional signals', async () => {
    let lineage = TopologyLineage.empty()
    const topologies = []
    for (let i = 1; i <= 5; i++) {
      const { topology } = await runFullPipeline(i)
      lineage = await lineage.append(topology)
      topologies.push(topology)
    }
    const entries = lineage.getAll()
    for (let i = 0; i < 5; i++) {
      expect(entries[i]!.topology_hash).toBe(topologies[i]!.topology_hash)
    }
  })

  it('lineage certificate is deterministic × 3 after 10 frames', async () => {
    let lineage = TopologyLineage.empty()
    for (let i = 1; i <= 10; i++) {
      const { topology } = await runFullPipeline(i)
      lineage = await lineage.append(topology)
    }
    const entries = lineage.getAll()
    const c1 = await certifyLineage(entries)
    const c2 = await certifyLineage(entries)
    const c3 = await certifyLineage(entries)
    expect(c1.certificate_hash).toBe(c2.certificate_hash)
    expect(c2.certificate_hash).toBe(c3.certificate_hash)
  })
})

// ─── Full epoch chain from frame pipeline ─────────────────
// Prove that 10 frame executions produce a certifiable EpochChain.

describe('Full epoch chain from frame pipeline', () => {
  it('10 frame epochs build a valid 10-entry EpochChain', async () => {
    let chain = EpochChain.empty()
    for (let i = 1; i <= 10; i++) {
      const { epoch } = await runFullPipeline(i)
      const { chain: next } = await chain.append(epoch)
      chain = next
    }
    const cert = await certifyEpochChain(chain.getAll())
    expect(cert.is_valid).toBe(true)
    expect(cert.link_count).toBe(10)
    expect(cert.terminal_hash).toHaveLength(64)
  })

  it('epoch chain certificate is deterministic × 3', async () => {
    let chain = EpochChain.empty()
    for (let i = 1; i <= 5; i++) {
      const { epoch } = await runFullPipeline(i)
      const { chain: next } = await chain.append(epoch)
      chain = next
    }
    const links = chain.getAll()
    const c1 = await certifyEpochChain(links)
    const c2 = await certifyEpochChain(links)
    const c3 = await certifyEpochChain(links)
    expect(c1.certificate_hash).toBe(c2.certificate_hash)
    expect(c2.certificate_hash).toBe(c3.certificate_hash)
  })

  it('distinct frame sequences produce distinct epoch chain certificates', async () => {
    async function buildChain(verdicts: boolean[]): Promise<string> {
      let chain = EpochChain.empty()
      for (let i = 1; i <= verdicts.length; i++) {
        const { epoch } = await runFullPipeline(i)
        const { chain: next } = await chain.append(epoch)
        chain = next
      }
      return (await certifyEpochChain(chain.getAll())).certificate_hash
    }
    const h1 = await buildChain([true, true, true])
    const h2 = await buildChain([true, true, true, true])  // 4 frames vs 3
    expect(h1).not.toBe(h2)
  })
})

// ─── Full pipeline determinism ─────────────────────────────

describe('Full pipeline determinism', () => {
  it('same sequence → same epoch_hash × 3', async () => {
    const r1 = await runFullPipeline(7)
    const r2 = await runFullPipeline(7)
    const r3 = await runFullPipeline(7)
    expect(r1.epoch.epoch_hash).toBe(r2.epoch.epoch_hash)
    expect(r2.epoch.epoch_hash).toBe(r3.epoch.epoch_hash)
  })

  it('pipeline result is fully frozen at every layer', async () => {
    const { frameResult, topology, epoch } = await runFullPipeline(1)
    expect(Object.isFrozen(frameResult)).toBe(true)
    expect(Object.isFrozen(topology)).toBe(true)
    expect(Object.isFrozen(epoch)).toBe(true)
    expect(Object.isFrozen(frameResult.phase_trace)).toBe(true)
  })
})
