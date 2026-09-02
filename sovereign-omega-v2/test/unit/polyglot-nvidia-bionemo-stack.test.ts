import { describe, expect, it } from 'vitest'
import {
  admitNvidiaConnector,
  buildNvidiaDetectionSpec,
  buildNvidiaScientificSubstrateReceipt,
  type NvidiaConnectorEvidence,
  type NvidiaConnectorId,
  type NvidiaDetectionObservation,
} from '../../src/polyglot/nvidia'

const SHA_A = 'a'.repeat(64)
const SHA_B = 'b'.repeat(64)

function evidence(connector_id: NvidiaConnectorId): NvidiaConnectorEvidence {
  const observation: NvidiaDetectionObservation = {
    schema_version: 'AEGIS-NVIDIA-DETECTION-OBSERVATION-V1',
    connector_id,
    detected: true,
    connector_version: `${connector_id}-test`,
    executable_digest_sha256: SHA_A,
    capability_receipt_digest: SHA_B,
    authority_class: 'NONE',
    authority_effect: 'NONE',
  }
  return admitNvidiaConnector(observation)
}

describe('NVIDIA BioNeMo stack', () => {
  it('catalogues BioNeMo Framework separately from BioNeMo Inference Runtime', () => {
    const framework = buildNvidiaDetectionSpec('bionemo-framework')
    const inference = buildNvidiaDetectionSpec('bionemo-ir')

    expect(framework.capability_kind).toBe('BIOMOLECULAR_TRAINING')
    expect(framework.probe_locator).toBe('python:bionemo.fw')
    expect(framework.version_probe).toEqual(['package-version', 'bionemo-fw'])
    expect(inference.capability_kind).toBe('BIOMOLECULAR_AI')
    expect(inference.probe_locator).toBe('python:bionemo_ir')
    expect(framework.authority_effect).toBe('NONE')
  })

  it('establishes current agentic BioNeMo inference readiness only from NeMo Platform + Fabric + BioIR', async () => {
    const receipt = await buildNvidiaScientificSubstrateReceipt({
      task_id: 'bionemo-current-stack',
      evidence: [
        evidence('nemo-platform'),
        evidence('nemo-fabric'),
        evidence('bionemo-ir'),
      ],
    })

    expect(receipt.bionemo_stack.agentic_inference).toEqual({
      state: 'READY',
      required_connectors: ['nemo-platform', 'nemo-fabric', 'bionemo-ir'],
      missing_connectors: [],
      gpu_execution: 'NOT_ESTABLISHED',
      agent_execution: 'NOT_ESTABLISHED',
      authority_scope: 'EXECUTION_EVIDENCE_ONLY',
    })
    expect(receipt.bionemo_stack.framework.state).toBe('NOT_ESTABLISHED')
  })

  it('tracks BioNeMo Framework readiness independently from inference readiness', async () => {
    const receipt = await buildNvidiaScientificSubstrateReceipt({
      task_id: 'bionemo-framework-only',
      evidence: [evidence('bionemo-framework')],
    })

    expect(receipt.bionemo_stack.framework).toEqual({
      state: 'READY',
      required_connector: 'bionemo-framework',
      execution: 'NOT_ESTABLISHED',
      authority_scope: 'EXECUTION_EVIDENCE_ONLY',
    })
    expect(receipt.bionemo_stack.agentic_inference.state).toBe('NOT_ESTABLISHED')
    expect(receipt.bionemo_stack.agentic_inference.missing_connectors).toEqual([
      'nemo-platform',
      'nemo-fabric',
      'bionemo-ir',
    ])
  })

  it('does not infer BioIR readiness from BioNeMo Framework presence', async () => {
    const receipt = await buildNvidiaScientificSubstrateReceipt({
      task_id: 'bionemo-no-laundering',
      evidence: [
        evidence('bionemo-framework'),
        evidence('nemo-platform'),
        evidence('nemo-fabric'),
      ],
    })

    expect(receipt.bionemo_stack.framework.state).toBe('READY')
    expect(receipt.bionemo_stack.agentic_inference.state).toBe('NOT_ESTABLISHED')
    expect(receipt.bionemo_stack.agentic_inference.missing_connectors).toEqual(['bionemo-ir'])
  })
})
