import { describe, expect, it } from 'vitest'
import {
  NVIDIA_CONNECTOR_CATALOG,
  admitNvidiaConnector,
  buildNvidiaDetectionSpec,
  buildNvidiaScientificSubstrateReceipt,
  type NvidiaConnectorEvidence,
  type NvidiaConnectorId,
  type NvidiaDetectionObservation,
} from '../../src/polyglot/nvidia'

const SHA_A = 'a'.repeat(64)
const SHA_B = 'b'.repeat(64)

function observation(connector_id: NvidiaConnectorId): NvidiaDetectionObservation {
  return {
    schema_version: 'AEGIS-NVIDIA-DETECTION-OBSERVATION-V1',
    connector_id,
    detected: true,
    connector_version: 'test-1.0.0',
    executable_digest_sha256: SHA_A,
    capability_receipt_digest: SHA_B,
    authority_class: 'NONE',
    authority_effect: 'NONE',
  }
}

function evidence(connector_id: NvidiaConnectorId): NvidiaConnectorEvidence {
  return admitNvidiaConnector(observation(connector_id))
}

describe('NVIDIA NeMo Platform substrate', () => {
  it('catalogues current NeMo Platform and NeMo Fabric without replacing legacy NAT', () => {
    expect(NVIDIA_CONNECTOR_CATALOG.map(x => x.connector_id)).toEqual([
      'nvidia-agent-toolkit',
      'nemo-platform',
      'nemo-fabric',
      'bionemo-framework',
      'bionemo-ir',
      'cudaq',
      'cuquantum',
    ])

    const platform = buildNvidiaDetectionSpec('nemo-platform')
    const fabric = buildNvidiaDetectionSpec('nemo-fabric')

    expect(platform.capability_kind).toBe('AGENT_PLATFORM')
    expect(platform.probe_locator).toBe('nemo')
    expect(fabric.capability_kind).toBe('AGENT_RUNTIME_FABRIC')
    expect(fabric.probe_locator).toBe('python:nemo_fabric')
    expect(platform.authority_class).toBe('NONE')
    expect(fabric.authority_effect).toBe('NONE')
  })

  it('establishes NeMo Platform agent readiness only from exact Platform + Fabric evidence', async () => {
    const receipt = await buildNvidiaScientificSubstrateReceipt({
      task_id: 'nvidia-platform-ready',
      evidence: [
        evidence('nemo-platform'),
        evidence('nemo-fabric'),
        evidence('bionemo-ir'),
        evidence('cudaq'),
        evidence('cuquantum'),
      ],
    })

    expect(receipt.agent_platform).toEqual({
      state: 'READY',
      required_connectors: ['nemo-platform', 'nemo-fabric'],
      missing_connectors: [],
      execution: 'NOT_ESTABLISHED',
      authority_scope: 'EXECUTION_EVIDENCE_ONLY',
    })
    expect(receipt.authority_class).toBe('NONE')
    expect(receipt.authority_effect).toBe('NONE')
  })

  it('does not infer NeMo Fabric readiness from the nemo CLI alone', async () => {
    const receipt = await buildNvidiaScientificSubstrateReceipt({
      task_id: 'nvidia-platform-partial',
      evidence: [evidence('nemo-platform')],
    })

    expect(receipt.agent_platform.state).toBe('NOT_ESTABLISHED')
    expect(receipt.agent_platform.missing_connectors).toEqual(['nemo-fabric'])
    expect(receipt.agent_platform.execution).toBe('NOT_ESTABLISHED')
  })
})
