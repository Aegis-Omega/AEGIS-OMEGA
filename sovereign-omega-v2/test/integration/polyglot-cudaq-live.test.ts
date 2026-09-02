import { dirname } from 'node:path'
import { mkdirSync, writeFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { admitNvidiaConnector } from '../../src/polyglot/nvidia'
import {
  admitCudaQBackend,
  admitNvidiaQuantumExecution,
} from '../../src/polyglot/nvidia-execution'
import {
  probeCudaQBackend,
  probeNvidiaPythonConnector,
} from '../../src/polyglot/nvidia-probe'
import { executeCudaQSimulatorSmoke } from '../../src/polyglot/nvidia-quantum-smoke'

const describeLive = process.env.AEGIS_CUDAQ_LIVE === '1' ? describe : describe.skip

describeLive('CUDA-Q live qpp-cpu receipt chain', () => {
  it('executes the real local CPU simulator and produces an authority-neutral receipt', async () => {
    const connectorObservation = await probeNvidiaPythonConnector({
      connector_id: 'cudaq',
      python_executable: 'python3',
    })
    expect(connectorObservation.detected).toBe(true)

    const cudaqEvidence = admitNvidiaConnector(connectorObservation)
    const backendObservation = await probeCudaQBackend({
      target_name: 'qpp-cpu',
      python_executable: 'python3',
    })
    expect(backendObservation.backend_kind).toBe('SIMULATOR')
    expect(backendObservation.is_remote).toBe(false)

    const backendReceipt = await admitCudaQBackend({
      observation: backendObservation,
      cudaq_evidence: cudaqEvidence,
    })
    const executionObservation = await executeCudaQSimulatorSmoke({
      task_id: 'cudaq-live-qpp-cpu-bell-v1',
      backend: backendReceipt,
      python_executable: 'python3',
      shots_count: 32,
    })
    const executionReceipt = await admitNvidiaQuantumExecution({
      observation: executionObservation,
      backend: backendReceipt,
      cudaq_evidence: cudaqEvidence,
      cuquantum_evidence: null,
    })

    expect(executionReceipt.status).toBe('EXECUTED')
    expect(executionReceipt.target_name).toBe('qpp-cpu')
    expect(executionReceipt.backend_kind).toBe('SIMULATOR')
    expect(executionReceipt.manifold_binding).toBe('CUDAQ_SIMULATION')
    expect(executionReceipt.qpu_access).toBe('NOT_ESTABLISHED')
    expect(executionReceipt.quantum_advantage).toBe('NOT_ESTABLISHED')
    expect(executionReceipt.authority_scope).toBe('DIAGNOSTIC_ONLY')
    expect(executionReceipt.authority_class).toBe('NONE')
    expect(executionReceipt.authority_effect).toBe('NONE')
    expect(executionReceipt.receipt_digest).toMatch(/^[0-9a-f]{64}$/)

    const receiptPath = process.env.AEGIS_CUDAQ_RECEIPT_PATH
    if (receiptPath) {
      mkdirSync(dirname(receiptPath), { recursive: true })
      writeFileSync(receiptPath, `${JSON.stringify({
        connector_observation: connectorObservation,
        backend_observation: backendObservation,
        backend_receipt: backendReceipt,
        execution_observation: executionObservation,
        execution_receipt: executionReceipt,
      }, null, 2)}\n`, 'utf8')
    }
  })
})
