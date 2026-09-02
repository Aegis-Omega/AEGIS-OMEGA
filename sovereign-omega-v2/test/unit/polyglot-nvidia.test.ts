import { describe, expect, it } from 'vitest'
import {
  NVIDIA_CONNECTOR_CATALOG,
  NvidiaConnectorUnavailableError,
  NvidiaSubstrateError,
  admitNvidiaConnector,
  buildNvidiaDetectionSpec,
  buildNvidiaScientificSubstrateReceipt,
  type NvidiaConnectorEvidence,
  type NvidiaConnectorId,
  type NvidiaDetectionObservation,
} from '../../src/polyglot/nvidia'

const SHA_EXEC = '3'.repeat(64)
const SHA_RECEIPT = '4'.repeat(64)

function observation(
  connector_id: NvidiaConnectorId,
  overrides: Partial<NvidiaDetectionObservation> = {},
): NvidiaDetectionObservation {
  return {
    schema_version: 'AEGIS-NVIDIA-DETECTION-OBSERVATION-V1',
    connector_id,
    detected: true,
    connector_version: 'test-1.0.0',
    executable_digest_sha256: SHA_EXEC,
    capability_receipt_digest: SHA_RECEIPT,
    authority_class: 'NONE',
    authority_effect: 'NONE',
    ...overrides,
  }
}

function evidence(connector_id: NvidiaConnectorId): NvidiaConnectorEvidence {
  return admitNvidiaConnector(observation(connector_id))
}

describe('NVIDIA scientific substrate extension', () => {
  it('catalogues Agent Toolkit, NeMo Platform/Fabric, BioNeMo, CUDA-Q and cuQuantum without granting authority', () => {
    expect(NVIDIA_CONNECTOR_CATALOG.map(x => x.connector_id)).toEqual([
      'nvidia-agent-toolkit',
      'nemo-platform',
      'nemo-fabric',
      'bionemo-framework',
      'bionemo-ir',
      'cudaq',
      'cuquantum',
    ])

    expect(new Set(NVIDIA_CONNECTOR_CATALOG.map(x => x.connector_id)).size)
      .toBe(NVIDIA_CONNECTOR_CATALOG.length)

    for (const connector of NVIDIA_CONNECTOR_CATALOG) {
      expect(connector.probe_locator.length).toBeGreaterThan(0)
      expect(connector.version_probe.length).toBeGreaterThan(0)
      expect(connector.digest_algorithm).toBe('SHA-256')
      expect(connector.capability_receipt_required).toBe(true)
      expect(connector.authority_class).toBe('NONE')
      expect(connector.authority_effect).toBe('NONE')
      expect(connector.default_state).toBe('CATALOGUED_NOT_VERIFIED')
    }
  })

  it('binds concrete probe contracts for BioNeMo and NVIDIA Agent Toolkit', () => {
    const bionemo = buildNvidiaDetectionSpec('bionemo-ir')
    const agentToolkit = buildNvidiaDetectionSpec('nvidia-agent-toolkit')

    expect(bionemo.probe_locator).toBe('python:bionemo_ir')
    expect(bionemo.capability_kind).toBe('BIOMOLECULAR_AI')
    expect(agentToolkit.probe_locator).toBe('nat')
    expect(agentToolkit.capability_kind).toBe('AGENT_ORCHESTRATION')
  })

  it('fails closed with TOOLCHAIN_UNAVAILABLE when a connector is absent', () => {
    expect(() => admitNvidiaConnector(observation('bionemo-ir', {
      detected: false,
      connector_version: null,
      executable_digest_sha256: null,
      capability_receipt_digest: null,
    }))).toThrow(NvidiaConnectorUnavailableError)

    try {
      admitNvidiaConnector(observation('bionemo-ir', {
        detected: false,
        connector_version: null,
        executable_digest_sha256: null,
        capability_receipt_digest: null,
      }))
    } catch (error) {
      expect(error).toBeInstanceOf(NvidiaConnectorUnavailableError)
      expect((error as NvidiaConnectorUnavailableError).code).toBe('TOOLCHAIN_UNAVAILABLE')
    }
  })

  it('rejects malformed or authority-bearing connector evidence', () => {
    expect(() => admitNvidiaConnector(observation('cudaq', {
      executable_digest_sha256: 'bad',
    }))).toThrow(NvidiaSubstrateError)

    expect(() => admitNvidiaConnector(observation('cuquantum', {
      capability_receipt_digest: 'bad',
    }))).toThrow(NvidiaSubstrateError)

    expect(() => admitNvidiaConnector(observation('nvidia-agent-toolkit', {
      authority_effect: 'KNOWLEDGE_ADMISSION' as never,
    }))).toThrow(/AUTHORITY/)
  })

  it('establishes the software-level BioNeMo agent fabric and CUDA-Q/cuQuantum quantum manifold only from exact verified evidence', async () => {
    const receipt = await buildNvidiaScientificSubstrateReceipt({
      task_id: 'nvidia-full-substrate',
      evidence: [
        evidence('nvidia-agent-toolkit'),
        evidence('bionemo-ir'),
        evidence('cudaq'),
        evidence('cuquantum'),
      ],
    })

    expect(receipt.verified_connectors).toEqual([
      'nvidia-agent-toolkit',
      'bionemo-ir',
      'cudaq',
      'cuquantum',
    ])
    expect(receipt.biomolecular_agent_fabric.state).toBe('READY')
    expect(receipt.biomolecular_agent_fabric.gpu_execution).toBe('NOT_ESTABLISHED')
    expect(receipt.quantum_manifold.state).toBe('CUDAQ_CUQUANTUM_SIMULATION_READY')
    expect(receipt.quantum_manifold.qpu_access).toBe('NOT_ESTABLISHED')
    expect(receipt.quantum_manifold.quantum_advantage).toBe('NOT_ESTABLISHED')
    expect(receipt.quantum_manifold.authority_scope).toBe('DIAGNOSTIC_ONLY')
    expect(receipt.authority_class).toBe('NONE')
    expect(receipt.authority_effect).toBe('NONE')
    expect(receipt.receipt_digest).toMatch(/^[0-9a-f]{64}$/)
  })

  it('does not launder CUDA-Q alone into an established quantum manifold', async () => {
    const receipt = await buildNvidiaScientificSubstrateReceipt({
      task_id: 'nvidia-partial-quantum',
      evidence: [evidence('cudaq')],
    })

    expect(receipt.quantum_manifold.state).toBe('NOT_ESTABLISHED')
    expect(receipt.quantum_manifold.missing_connectors).toEqual(['cuquantum'])
    expect(receipt.quantum_manifold.qpu_access).toBe('NOT_ESTABLISHED')
    expect(receipt.quantum_manifold.quantum_advantage).toBe('NOT_ESTABLISHED')
  })

  it('does not launder BioNeMo alone into an established biomolecular agent fabric', async () => {
    const receipt = await buildNvidiaScientificSubstrateReceipt({
      task_id: 'nvidia-partial-bio',
      evidence: [evidence('bionemo-ir')],
    })

    expect(receipt.biomolecular_agent_fabric.state).toBe('NOT_ESTABLISHED')
    expect(receipt.biomolecular_agent_fabric.missing_connectors).toEqual(['nvidia-agent-toolkit'])
    expect(receipt.biomolecular_agent_fabric.gpu_execution).toBe('NOT_ESTABLISHED')
  })

  it('is deterministic across three independent receipt constructions', async () => {
    const request = {
      task_id: 'nvidia-replay',
      evidence: [
        evidence('nvidia-agent-toolkit'),
        evidence('bionemo-ir'),
        evidence('cudaq'),
        evidence('cuquantum'),
      ],
    }

    const first = await buildNvidiaScientificSubstrateReceipt(request)
    const second = await buildNvidiaScientificSubstrateReceipt(request)
    const third = await buildNvidiaScientificSubstrateReceipt(request)

    expect(first).toEqual(second)
    expect(second).toEqual(third)
  })

  it('does not expose an executor, shell or command-runner injection seam', () => {
    const source = buildNvidiaScientificSubstrateReceipt.toString()
    expect(source).not.toContain('executor')
    expect(source).not.toContain('commandRunner')
    expect(source).not.toContain('child_process')
  })
})
