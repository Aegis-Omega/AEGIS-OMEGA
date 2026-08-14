import { spawn } from 'node:child_process'
import path from 'node:path'
import process from 'node:process'
import { sha256Hex } from '../core/hashing.js'
import type { ProofCarryingWorkOrder, VerifiedWorkOrder, WorkOrderVerifier } from './frontier-inference-gateway.js'

const SHA256_HEX = /^[a-f0-9]{64}$/

export interface Automaton3Decision {
  readonly outcome?: string
  readonly authority_receipt_root?: string
  readonly denial_codes?: readonly string[]
  readonly [key: string]: unknown
}

export interface Automaton3EnvelopeFactory {
  create(workOrder: ProofCarryingWorkOrder): Promise<unknown>
}

export interface Automaton3Runner {
  evaluate(payload: unknown): Promise<Automaton3Decision>
}

export class Automaton3VerifierError extends Error {
  constructor(
    readonly code: 'ENVIRONMENT_INVALID' | 'RUNNER_FAILED' | 'OUTPUT_INVALID',
    message: string,
  ) {
    super(message)
    this.name = 'Automaton3VerifierError'
  }
}

export class Automaton3WorkOrderVerifier implements WorkOrderVerifier {
  private readonly authorityRoots = new Map<string, string>()

  constructor(
    private readonly envelopeFactory: Automaton3EnvelopeFactory,
    private readonly runner: Automaton3Runner,
  ) {}

  async verify(workOrder: ProofCarryingWorkOrder): Promise<VerifiedWorkOrder> {
    const digest = await frontierWorkOrderDigest(workOrder)
    const envelope = await this.envelopeFactory.create(workOrder)
    const decision = await this.runner.evaluate(envelope)
    const root = decision.authority_receipt_root
    if (decision.outcome !== 'ADMITTED' || typeof root !== 'string' || !SHA256_HEX.test(root)) {
      this.authorityRoots.delete(workOrder.workOrderId)
      return { valid: false, digest }
    }
    this.authorityRoots.set(workOrder.workOrderId, root)
    return { valid: true, digest }
  }

  authorityReceiptRoot(workOrderId: string): string | undefined {
    return this.authorityRoots.get(workOrderId)
  }
}

export class EnvironmentAutomaton3EnvelopeFactory implements Automaton3EnvelopeFactory {
  async create(workOrder: ProofCarryingWorkOrder): Promise<unknown> {
    const identity = readJsonEnvironment('AEGIS_EXECUTION_IDENTITY_JSON', true)
    const workspace = readJsonEnvironment('AEGIS_WORKSPACE_OBSERVATION_JSON', false) ?? {}
    const approval = readJsonEnvironment('AEGIS_APPROVAL_GRANT_JSON', false)
    const currentGenerationRaw = process.env.AEGIS_CURRENT_LEASE_GENERATION ?? '0'
    const currentGeneration = Number(currentGenerationRaw)
    if (!Number.isSafeInteger(currentGeneration) || currentGeneration < 0) {
      throw new Automaton3VerifierError('ENVIRONMENT_INVALID', 'AEGIS_CURRENT_LEASE_GENERATION must be a non-negative integer')
    }

    const action = {
      kind: 'frontier-provider-inference',
      work_order: workOrderPayload(workOrder),
    }
    const request = {
      action_class: workOrder.consequenceClass,
      authority_domain: `frontier-provider:${workOrder.provider}`,
      requested_capability: workOrder.capability,
      tool: workOrder.provider,
      target: workOrder.target,
      workspace_mode: workOrder.consequenceClass === 'D0' ? 'READ_ONLY' : 'REPOSITORY',
      current_generation: currentGeneration,
      idempotency_key: workOrder.idempotencyKey,
      rollback_reference: 'NONE',
      compensation_reference: 'NONE',
    }

    return approval === undefined
      ? { identity, workspace, action, request }
      : { identity, workspace, action, request, approval }
  }
}

export interface CliAutomaton3RunnerOptions {
  readonly repositoryRoot: string
  readonly pythonExecutable?: string | undefined
  readonly scriptPath?: string | undefined
  readonly timeoutMs?: number | undefined
  readonly maxOutputBytes?: number | undefined
}

export class CliAutomaton3Runner implements Automaton3Runner {
  private readonly pythonExecutable: string
  private readonly scriptPath: string
  private readonly timeoutMs: number
  private readonly maxOutputBytes: number

  constructor(private readonly options: CliAutomaton3RunnerOptions) {
    if (!options.repositoryRoot) {
      throw new Automaton3VerifierError('ENVIRONMENT_INVALID', 'repositoryRoot is required')
    }
    this.pythonExecutable = options.pythonExecutable ?? process.env.PYTHON ?? 'python3'
    this.scriptPath = options.scriptPath ?? path.join(options.repositoryRoot, 'scripts', 'automaton3-authority.py')
    this.timeoutMs = options.timeoutMs ?? 30_000
    this.maxOutputBytes = options.maxOutputBytes ?? 2 * 1024 * 1024
    if (this.timeoutMs <= 0 || this.maxOutputBytes <= 0) {
      throw new Automaton3VerifierError('ENVIRONMENT_INVALID', 'Automaton-3 runner limits must be positive')
    }
  }

  async evaluate(payload: unknown): Promise<Automaton3Decision> {
    let input: string
    try {
      input = JSON.stringify(payload)
    } catch {
      throw new Automaton3VerifierError('OUTPUT_INVALID', 'Automaton-3 input envelope is not JSON serializable')
    }

    return new Promise<Automaton3Decision>((resolve, reject) => {
      const child = spawn(
        this.pythonExecutable,
        [this.scriptPath, 'evaluate', '--input', '-', '--output', '-'],
        {
          cwd: this.options.repositoryRoot,
          env: process.env,
          stdio: ['pipe', 'pipe', 'pipe'],
        },
      )
      let stdout = ''
      let stderrBytes = 0
      let settled = false

      const fail = (error: Automaton3VerifierError): void => {
        if (settled) return
        settled = true
        clearTimeout(timer)
        child.kill('SIGKILL')
        reject(error)
      }

      const timer = setTimeout(() => {
        fail(new Automaton3VerifierError('RUNNER_FAILED', 'Automaton-3 authority evaluation timed out'))
      }, this.timeoutMs)

      child.stdout.setEncoding('utf8')
      child.stdout.on('data', (chunk: string) => {
        stdout += chunk
        if (Buffer.byteLength(stdout, 'utf8') > this.maxOutputBytes) {
          fail(new Automaton3VerifierError('OUTPUT_INVALID', 'Automaton-3 output exceeded the configured byte ceiling'))
        }
      })
      child.stderr.on('data', (chunk: Buffer) => {
        stderrBytes += chunk.length
        if (stderrBytes > this.maxOutputBytes) {
          fail(new Automaton3VerifierError('OUTPUT_INVALID', 'Automaton-3 stderr exceeded the configured byte ceiling'))
        }
      })
      child.on('error', () => fail(new Automaton3VerifierError('RUNNER_FAILED', 'Automaton-3 process could not be started')))
      child.on('close', code => {
        if (settled) return
        clearTimeout(timer)
        if (code !== 0 && code !== 3) {
          settled = true
          reject(new Automaton3VerifierError('RUNNER_FAILED', 'Automaton-3 process exited unexpectedly'))
          return
        }
        let decoded: unknown
        try {
          decoded = JSON.parse(stdout)
        } catch {
          settled = true
          reject(new Automaton3VerifierError('OUTPUT_INVALID', 'Automaton-3 output was not valid JSON'))
          return
        }
        if (!isRecord(decoded)) {
          settled = true
          reject(new Automaton3VerifierError('OUTPUT_INVALID', 'Automaton-3 output must be a JSON object'))
          return
        }
        settled = true
        resolve(decoded as Automaton3Decision)
      })

      child.stdin.end(input)
    })
  }
}

export async function frontierWorkOrderDigest(workOrder: ProofCarryingWorkOrder): Promise<string> {
  const serialized = JSON.stringify(sortRecursively(workOrderPayload(workOrder)))
  return sha256Hex(new TextEncoder().encode(serialized))
}

function workOrderPayload(workOrder: ProofCarryingWorkOrder): Record<string, unknown> {
  const secretReferences = readOptionalSecretReferences(workOrder)
  return {
    schema_version: workOrder.schemaVersion,
    work_order_id: workOrder.workOrderId,
    request_id: workOrder.requestId,
    provider: workOrder.provider,
    capability: workOrder.capability,
    target: workOrder.target,
    consequence_class: workOrder.consequenceClass,
    arguments_digest: workOrder.argumentsDigest,
    expected_parent_state_root: workOrder.expectedParentStateRoot,
    idempotency_key: workOrder.idempotencyKey,
    max_cost_microusd: workOrder.maxCostMicroUsd,
    max_input_tokens: workOrder.maxInputTokens,
    max_output_tokens: workOrder.maxOutputTokens,
    evidence_references: [...workOrder.evidenceReferences],
    operator_approval_reference: workOrder.operatorApprovalReference ?? null,
    secret_references: secretReferences,
    issued_sequence: workOrder.issuedSequence,
  }
}

function readOptionalSecretReferences(workOrder: ProofCarryingWorkOrder): readonly string[] {
  const candidate = workOrder as ProofCarryingWorkOrder & { readonly secretReferences?: readonly string[] }
  return candidate.secretReferences === undefined ? [] : [...candidate.secretReferences]
}

function sortRecursively(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortRecursively)
  if (!isRecord(value)) return value
  const sorted: Record<string, unknown> = {}
  for (const key of Object.keys(value).sort()) sorted[key] = sortRecursively(value[key])
  return sorted
}

function readJsonEnvironment(name: string, required: boolean): unknown {
  const raw = process.env[name]
  if (!raw) {
    if (required) throw new Automaton3VerifierError('ENVIRONMENT_INVALID', `${name} is required`)
    return undefined
  }
  try {
    return JSON.parse(raw)
  } catch {
    throw new Automaton3VerifierError('ENVIRONMENT_INVALID', `${name} is malformed JSON`)
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
