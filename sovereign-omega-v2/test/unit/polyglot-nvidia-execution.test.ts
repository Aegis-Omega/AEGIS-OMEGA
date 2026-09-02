import { describe, expect, it } from 'vitest'
import {
  admitNvidiaConnector,
  type NvidiaConnectorEvidence,
  type NvidiaConnectorId,
  type NvidiaDetectionObservation,
} from '../../src/polyglot/nvidia'
import {
  NvidiaExecutionError,
  NvidiaGpuEnvironmentUnavailableError,
  admitBioNemoExecution,
  admitCudaQBackend,
  admitNvidiaGpuEnvironment,
  admitNvidiaQuantumExecution,
  type BioNemoExecutionObservation,
  type CudaQBackendObservation,
  type NvidiaGpuEnvironmentObservation,
  type NvidiaQuantumExecutionObservation,
} from '../../src/polyglot/nvidia-execution'

const SHA_A = 'a'.repeat(64)
const SHA_B = 'b'.repeat(64)
const SHA_C = 'c'.repeat(64)
const SHA_D = 'd'.repeat(64)
const SHA_E = 'e'.repeat(64)

function connectorObservation(connector_id: NvidiaConnectorId): NvidiaDetectionObservation {
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

function connectorEvidence(connector_id: NvidiaConnectorId): NvidiaConnectorEvidence {
  return admitNvidiaConnector(connectorObservation(connector_id))
}

function gpuObservation(
  overrides: Partial<NvidiaGpuEnvironmentObservation> = {},
): NvidiaGpuEnvironmentObservation {
  return {
    schema_version: 'AEGIS-NVIDIA-GPU-ENVIRONMENT-OBSERVATION-V1',
    detected: true,
    gpu_count: 1,
    driver_version: '580.65.06',
    cuda_driver_version: '13.0',
    gpu_architectures: ['Hopper'],
    device_inventory_digest_sha256: SHA_C,
    capability_receipt_digest: SHA_D,
    authority_class: 'NONE',
    authority_effect: 'NONE',
    ...overrides,
  }
}

function bioObservation(
  gpu_environment_receipt_digest: string,
  overrides: Partial<BioNemoExecutionObservation> = {},
): BioNemoExecutionObservation {
  return {
    schema_version: 'AEGIS-BIONEMO-EXECUTION-OBSERVATION-V1',
    task_id: 'bio-task-1',
    completed: true,
    gpu_environment_receipt_digest,
    model_id: 'test-biomolecular-model',
    model_artifact_digest_sha256: SHA_A,
    input_digest_sha256: SHA_B,
    output_digest_sha256: SHA_C,
    execution_receipt_digest: SHA_E,
    authority_class: 'NONE',
    authority_effect: 'NONE',
    ...overrides,
  }
}

function cudaQObservation(
  overrides: Partial<CudaQBackendObservation> = {},
): CudaQBackendObservation {
  return {
    schema_version: 'AEGIS-CUDAQ-BACKEND-OBSERVATION-V1',
    target_name: 'nvidia',
    backend_kind: 'SIMULATOR',
    qpu_count: 1,
    is_remote: false,
    is_emulated: false,
    platform_properties_digest_sha256: SHA_C,
    capability_receipt_digest: SHA_D,
    authority_class: 'NONE',
    authority_effect: 'NONE',
    ...overrides,
  }
}

function quantumObservation(
  backend_receipt_digest: string,
  overrides: Partial<NvidiaQuantumExecutionObservation> = {},
): NvidiaQuantumExecutionObservation {
  return {
    schema_version: 'AEGIS-NVIDIA-QUANTUM-EXECUTION-OBSERVATION-V1',
    task_id: 'quantum-task-1',
    completed: true,
    backend_receipt_digest,
    execution_kind: 'SAMPLE',
    kernel_digest_sha256: SHA_A,
    input_digest_sha256: SHA_B,
    output_digest_sha256: SHA_C,
    execution_receipt_digest: SHA_E,
    shots_count: 1024,
    authority_class: 'NONE',
    authority_effect: 'NONE',
    ...overrides,
  }
}

describe('NVIDIA execution receipt boundaries', () => {
  it('fails closed when no NVIDIA GPU environment is detected', async () => {
    await expect(admitNvidiaGpuEnvironment(gpuObservation({
      detected: false,
      gpu_count: 0,
      driver_version: null,
      cuda_driver_version: null,
      gpu_architectures: [],
      device_inventory_digest_sha256: null,
      capability_receipt_digest: null,
    }))).rejects.toThrow(NvidiaGpuEnvironmentUnavailableError)
  })

  it('admits an immutable digest-bound GPU environment without granting execution authority', async () => {
    const first = await admitNvidiaGpuEnvironment(gpuObservation())
    const second = await admitNvidiaGpuEnvironment(gpuObservation())

    expect(first).toEqual(second)
    expect(first.gpu_count).toBe(1)
    expect(first.driver_version).toBe('580.65.06')
    expect(first.bioir_driver_compatible).toBe(true)
    expect(first.authority_class).toBe('NONE')
    expect(first.authority_effect).toBe('NONE')
    expect(first.receipt_digest).toMatch(/^[0-9a-f]{64}$/)
    expect(Object.isFrozen(first)).toBe(true)
  })

  it('refuses BioNeMo execution admission on a GPU driver below the BioIR minimum', async () => {
    const gpu = await admitNvidiaGpuEnvironment(gpuObservation({ driver_version: '570.99' }))

    await expect(admitBioNemoExecution({
      observation: bioObservation(gpu.receipt_digest),
      bionemo_evidence: connectorEvidence('bionemo-ir'),
      gpu_environment: gpu,
    })).rejects.toThrow(/BIOIR_GPU_ENVIRONMENT_UNSUPPORTED/)
  })

  it('establishes only the exact BioNeMo GPU execution bound to the observed environment and artifacts', async () => {
    const gpu = await admitNvidiaGpuEnvironment(gpuObservation())
    const receipt = await admitBioNemoExecution({
      observation: bioObservation(gpu.receipt_digest),
      bionemo_evidence: connectorEvidence('bionemo-ir'),
      gpu_environment: gpu,
    })

    expect(receipt.status).toBe('EXECUTED')
    expect(receipt.gpu_execution).toBe('ESTABLISHED_FOR_THIS_RECEIPT')
    expect(receipt.gpu_environment_receipt_digest).toBe(gpu.receipt_digest)
    expect(receipt.model_artifact_digest_sha256).toBe(SHA_A)
    expect(receipt.output_digest_sha256).toBe(SHA_C)
    expect(receipt.authority_class).toBe('NONE')
    expect(receipt.authority_effect).toBe('NONE')
    expect(receipt.receipt_digest).toMatch(/^[0-9a-f]{64}$/)
  })

  it('rejects BioNeMo receipt splicing across GPU environments', async () => {
    const gpu = await admitNvidiaGpuEnvironment(gpuObservation())

    await expect(admitBioNemoExecution({
      observation: bioObservation(SHA_E),
      bionemo_evidence: connectorEvidence('bionemo-ir'),
      gpu_environment: gpu,
    })).rejects.toThrow(/GPU_ENVIRONMENT_BINDING_MISMATCH/)
  })

  it('keeps a CUDA-Q simulator backend distinct from physical QPU access', async () => {
    const backend = await admitCudaQBackend({
      observation: cudaQObservation(),
      cudaq_evidence: connectorEvidence('cudaq'),
    })

    expect(backend.backend_kind).toBe('SIMULATOR')
    expect(backend.target_name).toBe('nvidia')
    expect(backend.qpu_access).toBe('NOT_ESTABLISHED')
    expect(backend.quantum_advantage).toBe('NOT_ESTABLISHED')
    expect(backend.authority_scope).toBe('DIAGNOSTIC_ONLY')
  })

  it('can attest a specific hardware backend without promoting quantum advantage', async () => {
    const backend = await admitCudaQBackend({
      observation: cudaQObservation({
        target_name: 'remote-hardware-test',
        backend_kind: 'HARDWARE',
        is_remote: true,
      }),
      cudaq_evidence: connectorEvidence('cudaq'),
    })

    expect(backend.backend_kind).toBe('HARDWARE')
    expect(backend.qpu_access).toBe('ESTABLISHED_FOR_THIS_RECEIPT')
    expect(backend.quantum_advantage).toBe('NOT_ESTABLISHED')
  })

  it('requires cuQuantum evidence for an NVIDIA simulator execution to enter the quantum manifold', async () => {
    const backend = await admitCudaQBackend({
      observation: cudaQObservation(),
      cudaq_evidence: connectorEvidence('cudaq'),
    })

    await expect(admitNvidiaQuantumExecution({
      observation: quantumObservation(backend.receipt_digest),
      backend,
      cudaq_evidence: connectorEvidence('cudaq'),
      cuquantum_evidence: null,
    })).rejects.toThrow(/CUQUANTUM_EVIDENCE_REQUIRED/)
  })

  it('admits a digest-bound CUDA-Q/cuQuantum simulator execution without claiming QPU access or advantage', async () => {
    const backend = await admitCudaQBackend({
      observation: cudaQObservation(),
      cudaq_evidence: connectorEvidence('cudaq'),
    })

    const first = await admitNvidiaQuantumExecution({
      observation: quantumObservation(backend.receipt_digest),
      backend,
      cudaq_evidence: connectorEvidence('cudaq'),
      cuquantum_evidence: connectorEvidence('cuquantum'),
    })
    const second = await admitNvidiaQuantumExecution({
      observation: quantumObservation(backend.receipt_digest),
      backend,
      cudaq_evidence: connectorEvidence('cudaq'),
      cuquantum_evidence: connectorEvidence('cuquantum'),
    })

    expect(first).toEqual(second)
    expect(first.status).toBe('EXECUTED')
    expect(first.manifold_binding).toBe('CUDAQ_CUQUANTUM_SIMULATION')
    expect(first.qpu_access).toBe('NOT_ESTABLISHED')
    expect(first.quantum_advantage).toBe('NOT_ESTABLISHED')
    expect(first.authority_class).toBe('NONE')
    expect(first.authority_effect).toBe('NONE')
    expect(first.receipt_digest).toMatch(/^[0-9a-f]{64}$/)
  })

  it('rejects backend receipt splicing and authority-bearing execution observations', async () => {
    const backend = await admitCudaQBackend({
      observation: cudaQObservation(),
      cudaq_evidence: connectorEvidence('cudaq'),
    })

    await expect(admitNvidiaQuantumExecution({
      observation: quantumObservation(SHA_E),
      backend,
      cudaq_evidence: connectorEvidence('cudaq'),
      cuquantum_evidence: connectorEvidence('cuquantum'),
    })).rejects.toThrow(/BACKEND_BINDING_MISMATCH/)

    await expect(admitNvidiaQuantumExecution({
      observation: quantumObservation(backend.receipt_digest, {
        authority_effect: 'KNOWLEDGE_ADMISSION' as never,
      }),
      backend,
      cudaq_evidence: connectorEvidence('cudaq'),
      cuquantum_evidence: connectorEvidence('cuquantum'),
    })).rejects.toThrow(NvidiaExecutionError)
  })
})
