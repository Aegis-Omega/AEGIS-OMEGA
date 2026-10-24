import type { Checkpoint, EventEnvelope, SHA256Hex } from '../core/types.js'
import { EventType } from '../core/types.js'
import { canonicalizeJCS, canonicalizeJCSString } from '../core/canonicalize.js'
import { sha256Hex } from '../core/hashing.js'
import {
  SOVEREIGNTY_SCHEMA_VERSION,
  type AuthorityLeaseV1,
  type DurableExecutionRecordV1,
} from '../sovereignty/contracts.js'
import { ConcurrentEventStoreUpdateError, EventStore, EventStoreWriteConditionError } from './store.js'
import { recordWorkflowEvent } from './workflow-recorder.js'
import type { DurableWorkflowEventPayloadV1 } from './workflow.js'

interface LeaseProjection {
  readonly execution_id: string
  readonly lease: AuthorityLeaseV1
}

interface CheckpointProjection {
  readonly execution_id: string
  readonly checkpoint: Checkpoint
}

interface StepProjection {
  readonly execution_id: string
  readonly operation_id: string
  readonly action_digest: SHA256Hex
  readonly result_digest: SHA256Hex
}

export interface LeaseAuthorizationRequestV1 {
  readonly execution_id: string
  readonly authority_domain: string
  readonly holder_actor_id: string
  readonly holder_session_id: string
  readonly executor_id: string
  readonly workspace_id: string
  readonly expected_head: string
  readonly expected_parent_state_root: SHA256Hex
  readonly authorization_hash: SHA256Hex
}

export interface DurableWorkflowProjectionV1 {
  readonly executions: readonly DurableExecutionRecordV1[]
  readonly leases: readonly LeaseProjection[]
  readonly checkpoints: readonly CheckpointProjection[]
  readonly steps: readonly StepProjection[]
}

export class DurableWorkflowError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'DurableWorkflowError'
  }
}

const HASH_PATTERN = /^[0-9a-f]{64}$/
const ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:@/+\-]{0,255}$/
const GIT_OBJECT_PATTERN = /^[0-9a-f]{40,64}$/

function assertIdentifier(field: string, value: string): void {
  if (!ID_PATTERN.test(value)) throw new TypeError(`${field} is not a canonical identifier`)
}

function assertHash(field: string, value: string): asserts value is SHA256Hex {
  if (!HASH_PATTERN.test(value)) throw new TypeError(`${field} must be lowercase SHA-256 hex`)
}

function timestamp(value: number): string {
  if (!Number.isSafeInteger(value)) throw new RangeError('timestamp must be a safe integer')
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) throw new RangeError('timestamp is invalid')
  return date.toISOString()
}

function parsedTimestamp(field: string, value: string): number {
  const parsed = Date.parse(value)
  if (!Number.isFinite(parsed) || timestamp(parsed) !== value) {
    throw new TypeError(`${field} must be a canonical ISO-8601 UTC timestamp`)
  }
  return parsed
}

function replace<T>(items: T[], predicate: (item: T) => boolean, value: T): void {
  const index = items.findIndex(predicate)
  if (index === -1) items.push(value)
  else items[index] = value
}

export function replayDurableWorkflow(
  events: readonly EventEnvelope[],
): DurableWorkflowProjectionV1 {
  const executions: DurableExecutionRecordV1[] = []
  const leases: LeaseProjection[] = []
  const checkpoints: CheckpointProjection[] = []
  const steps: StepProjection[] = []

  for (const envelope of events) {
    if (envelope.event_type !== EventType.DURABLE_WORKFLOW_EVENT) continue
    const event = envelope.payload as DurableWorkflowEventPayloadV1
    switch (event.kind) {
      case 'EXECUTION_REGISTERED':
        {
          const existing = executions.find(item => item.execution_id === event.execution.execution_id)
          if (existing && canonicalizeJCSString(existing) !== canonicalizeJCSString(event.execution)) {
            throw new DurableWorkflowError('EXECUTION_IDENTITY_CHANGED')
          }
          if (!existing) executions.push(event.execution)
        }
        break
      case 'LEASE_ACQUIRED':
      case 'HEARTBEAT':
        {
          const existing = executions.find(item => item.execution_id === event.execution_id)
          if (
            !existing ||
            existing.provider !== event.execution.provider ||
            existing.executor_id !== event.execution.executor_id ||
            existing.workflow_identity_hash !== event.execution.workflow_identity_hash ||
            existing.canonical_state_root !== event.execution.canonical_state_root ||
            existing.registration_time !== event.execution.registration_time ||
            existing.cancellation_endpoint_hash !== event.execution.cancellation_endpoint_hash ||
            event.lease.executor_id !== event.execution.executor_id
          ) {
            throw new DurableWorkflowError('EXECUTION_IDENTITY_CHANGED')
          }
        replace(
          leases,
          item => item.lease.lease_id === event.lease.lease_id,
          { execution_id: event.execution_id, lease: event.lease },
        )
        replace(
          executions,
          item => item.execution_id === event.execution_id,
          event.execution,
        )
        }
        break
      case 'CHECKPOINT_SAVED':
        replace(
          checkpoints,
          item => item.execution_id === event.execution_id,
          { execution_id: event.execution_id, checkpoint: event.checkpoint },
        )
        break
      case 'STEP_APPLIED':
        steps.push({
          execution_id: event.execution_id,
          operation_id: event.operation_id,
          action_digest: event.action_digest,
          result_digest: event.result_digest,
        })
        break
      case 'RESUMED':
      case 'ACTION_DENIED':
        break
    }
  }

  return { executions, leases, checkpoints, steps }
}

/** Appends durable receipts only; it has no tool adapter for external side effects. */
export class DurableWorkflowEngine {
  constructor(
    private readonly store: EventStore,
    private readonly verifyCheckpoint: (checkpoint: Checkpoint) => boolean | Promise<boolean>,
    private readonly verifyAuthorization: (
      request: LeaseAuthorizationRequestV1,
    ) => boolean | Promise<boolean>,
    private readonly trustedNow: () => number,
  ) {}

  async register(
    execution: DurableExecutionRecordV1,
    operationId: string,
    timestampMs: number,
  ): Promise<DurableWorkflowEventPayloadV1> {
    assertIdentifier('operation_id', operationId)
    assertIdentifier('execution_id', execution.execution_id)
    const heartbeatExpiry = parsedTimestamp('heartbeat_expires_at', execution.heartbeat_expires_at)
    assertHash('workflow_identity_hash', execution.workflow_identity_hash)
    assertHash('canonical_state_root', execution.canonical_state_root)
    assertHash('cancellation_endpoint_hash', execution.cancellation_endpoint_hash)
    if (
      execution.schema_version !== SOVEREIGNTY_SCHEMA_VERSION ||
      execution.status !== 'REGISTERED' ||
      execution.held_authority_domains.length !== 0
    ) {
      throw new DurableWorkflowError('EXECUTION_REGISTRATION_INVALID')
    }

    return (await this.commit(
      operationId,
      { kind: 'EXECUTION_REGISTERED', execution },
      timestampMs,
      (requestHash, state) => {
        if (state.executions.some(item => item.execution_id === execution.execution_id)) {
          return this.denied(
            operationId,
            requestHash,
            execution.execution_id,
            'REGISTER',
            'EXECUTION_ALREADY_REGISTERED',
          )
        }
        const nowMs = this.assertTrustedTimestamp(timestampMs)
        const at = timestamp(nowMs)
        if (
          execution.registration_time !== at ||
          execution.last_heartbeat_at !== at ||
          heartbeatExpiry <= nowMs
        ) {
          throw new DurableWorkflowError('EXECUTION_REGISTRATION_INVALID')
        }
        return {
          schema_version: '1.0.0',
          kind: 'EXECUTION_REGISTERED',
          operation_id: operationId,
          request_hash: requestHash,
          execution,
        }
      },
    )).event
  }

  async acquireLease(input: {
    readonly operation_id: string
    readonly execution_id: string
    readonly authority_domain: string
    readonly holder_actor_id: string
    readonly holder_session_id: string
    readonly executor_id: string
    readonly workspace_id: string
    readonly expected_head: string
    readonly expected_parent_state_root: SHA256Hex
    readonly authorization_hash: SHA256Hex
    readonly ttl_ms: number
    readonly timestamp_ms: number
  }): Promise<DurableWorkflowEventPayloadV1> {
    assertIdentifier('operation_id', input.operation_id)
    assertIdentifier('execution_id', input.execution_id)
    assertIdentifier('authority_domain', input.authority_domain)
    assertIdentifier('holder_actor_id', input.holder_actor_id)
    assertIdentifier('holder_session_id', input.holder_session_id)
    assertIdentifier('executor_id', input.executor_id)
    assertIdentifier('workspace_id', input.workspace_id)
    if (!GIT_OBJECT_PATTERN.test(input.expected_head)) throw new TypeError('expected_head is invalid')
    assertHash('expected_parent_state_root', input.expected_parent_state_root)
    assertHash('authorization_hash', input.authorization_hash)
    if (!Number.isSafeInteger(input.ttl_ms) || input.ttl_ms <= 0) throw new RangeError('ttl_ms must be positive')
    const request = {
      operation_id: input.operation_id,
      execution_id: input.execution_id,
      authority_domain: input.authority_domain,
      holder_actor_id: input.holder_actor_id,
      holder_session_id: input.holder_session_id,
      executor_id: input.executor_id,
      workspace_id: input.workspace_id,
      expected_head: input.expected_head,
      expected_parent_state_root: input.expected_parent_state_root,
      authorization_hash: input.authorization_hash,
      ttl_ms: input.ttl_ms,
    }

    return (await this.commit(
      input.operation_id,
      request,
      input.timestamp_ms,
      async (requestHash, state) => {
        const nowMs = this.assertTrustedTimestamp(input.timestamp_ms)
        const issuedAt = timestamp(nowMs)
        const expiresAt = timestamp(nowMs + input.ttl_ms)
        const execution = state.executions.find(item => item.execution_id === input.execution_id)
        const denial = this.executionDenial(state, execution, nowMs)
        if (denial) return this.denied(input.operation_id, requestHash, input.execution_id, 'LEASE_ACQUIRE', denial)
        if (execution!.executor_id !== input.executor_id) {
          return this.denied(
            input.operation_id,
            requestHash,
            input.execution_id,
            'LEASE_ACQUIRE',
            'EXECUTOR_MISMATCH',
          )
        }
        let authorized = false
        try {
          authorized = await this.verifyAuthorization({
            execution_id: input.execution_id,
            authority_domain: input.authority_domain,
            holder_actor_id: input.holder_actor_id,
            holder_session_id: input.holder_session_id,
            executor_id: input.executor_id,
            workspace_id: input.workspace_id,
            expected_head: input.expected_head,
            expected_parent_state_root: input.expected_parent_state_root,
            authorization_hash: input.authorization_hash,
          })
        } catch {
          authorized = false
        }
        if (!authorized) {
          return this.denied(
            input.operation_id,
            requestHash,
            input.execution_id,
            'LEASE_ACQUIRE',
            'AUTHORIZATION_UNVERIFIED',
          )
        }

        const active = state.leases.find(
          item =>
            item.lease.authority_domain === input.authority_domain &&
            item.lease.revoked_at === null &&
            Date.parse(item.lease.expires_at) > nowMs,
        )
        if (active) {
          return this.denied(
            input.operation_id,
            requestHash,
            input.execution_id,
            'LEASE_ACQUIRE',
            'WRITER_ALREADY_ACTIVE',
          )
        }

        const generation = state.leases
          .filter(item => item.lease.authority_domain === input.authority_domain)
          .reduce((maximum, item) => {
            const value = BigInt(item.lease.fencing_token)
            return value > maximum ? value : maximum
          }, 0n) + 1n
        const lease: AuthorityLeaseV1 = {
          schema_version: SOVEREIGNTY_SCHEMA_VERSION,
          lease_id: input.operation_id,
          authority_domain: input.authority_domain,
          holder_actor_id: input.holder_actor_id,
          holder_session_id: input.holder_session_id,
          executor_id: input.executor_id,
          workspace_id: input.workspace_id,
          fencing_token: generation.toString(),
          expected_head: input.expected_head,
          expected_parent_state_root: input.expected_parent_state_root,
          authorization_hash: input.authorization_hash,
          issued_at: issuedAt,
          expires_at: expiresAt,
          revoked_at: null,
        }
        const held = state.leases
          .filter(item => item.execution_id === input.execution_id && Date.parse(item.lease.expires_at) > nowMs && item.lease.revoked_at === null)
          .map(item => item.lease.authority_domain)
        if (!held.includes(input.authority_domain)) held.push(input.authority_domain)
        const updatedExecution: DurableExecutionRecordV1 = {
          ...execution!,
          status: 'RUNNING',
          held_authority_domains: held.sort(),
        }
        return {
          schema_version: '1.0.0',
          kind: 'LEASE_ACQUIRED',
          operation_id: input.operation_id,
          request_hash: requestHash,
          execution_id: input.execution_id,
          lease,
          execution: updatedExecution,
        }
      },
    )).event
  }

  async heartbeat(input: {
    readonly operation_id: string
    readonly execution_id: string
    readonly lease_id: string
    readonly fencing_token: string
    readonly heartbeat_expires_at_ms: number
    readonly timestamp_ms: number
  }): Promise<DurableWorkflowEventPayloadV1> {
    assertIdentifier('operation_id', input.operation_id)
    assertIdentifier('execution_id', input.execution_id)
    assertIdentifier('lease_id', input.lease_id)
    const expiresAt = timestamp(input.heartbeat_expires_at_ms)
    const request = {
      execution_id: input.execution_id,
      lease_id: input.lease_id,
      fencing_token: input.fencing_token,
      heartbeat_expires_at_ms: input.heartbeat_expires_at_ms,
    }

    return (await this.commit(
      input.operation_id,
      request,
      input.timestamp_ms,
      (requestHash, state) => {
        const nowMs = this.assertTrustedTimestamp(input.timestamp_ms)
        const at = timestamp(nowMs)
        const execution = state.executions.find(item => item.execution_id === input.execution_id)
        const denial =
          this.executionDenial(state, execution, nowMs) ??
          this.leaseDenial(state, input.execution_id, input.lease_id, input.fencing_token, nowMs)
        const current = state.leases.find(item => item.lease.lease_id === input.lease_id)
        if (denial || !current) {
          return this.denied(input.operation_id, requestHash, input.execution_id, 'HEARTBEAT', denial ?? 'LEASE_MISSING')
        }
        if (
          input.heartbeat_expires_at_ms <= nowMs ||
          input.heartbeat_expires_at_ms <= Date.parse(current.lease.expires_at) ||
          Date.parse(at) < Date.parse(execution!.last_heartbeat_at)
        ) {
          return this.denied(input.operation_id, requestHash, input.execution_id, 'HEARTBEAT', 'HEARTBEAT_INVALID')
        }
        const lease = { ...current.lease, expires_at: expiresAt }
        const updatedExecution: DurableExecutionRecordV1 = {
          ...execution!,
          status: 'RUNNING',
          last_heartbeat_at: at,
          heartbeat_expires_at: expiresAt,
        }
        return {
          schema_version: '1.0.0',
          kind: 'HEARTBEAT',
          operation_id: input.operation_id,
          request_hash: requestHash,
          execution_id: input.execution_id,
          lease,
          execution: updatedExecution,
        }
      },
    )).event
  }

  async saveCheckpoint(input: {
    readonly operation_id: string
    readonly execution_id: string
    readonly lease_id: string
    readonly fencing_token: string
    readonly checkpoint: Checkpoint
    readonly timestamp_ms: number
  }): Promise<DurableWorkflowEventPayloadV1> {
    assertIdentifier('operation_id', input.operation_id)
    assertIdentifier('execution_id', input.execution_id)
    assertIdentifier('lease_id', input.lease_id)
    const request = {
      execution_id: input.execution_id,
      lease_id: input.lease_id,
      fencing_token: input.fencing_token,
      checkpoint: input.checkpoint,
    }

    return (await this.commit(
      input.operation_id,
      request,
      input.timestamp_ms,
      async (requestHash, state, sequence) => {
        const nowMs = this.assertTrustedTimestamp(input.timestamp_ms)
        const execution = state.executions.find(item => item.execution_id === input.execution_id)
        const denial =
          this.executionDenial(state, execution, nowMs) ??
          this.leaseDenial(state, input.execution_id, input.lease_id, input.fencing_token, nowMs)
        if (denial) {
          return this.denied(input.operation_id, requestHash, input.execution_id, 'CHECKPOINT', denial)
        }
        if (
          !input.checkpoint.checkpoint_id ||
          !input.checkpoint.signature ||
          !input.checkpoint.public_key_id ||
          Number(input.checkpoint.event_index) !== sequence ||
          input.checkpoint.timestamp_ms > nowMs
        ) {
          return this.denied(input.operation_id, requestHash, input.execution_id, 'CHECKPOINT', 'CHECKPOINT_INVALID')
        }
        let verified = false
        try {
          verified = await this.verifyCheckpoint(input.checkpoint)
        } catch {
          verified = false
        }
        if (!verified) {
          return this.denied(
            input.operation_id,
            requestHash,
            input.execution_id,
            'CHECKPOINT',
            'CHECKPOINT_UNVERIFIED',
          )
        }
        return {
          schema_version: '1.0.0',
          kind: 'CHECKPOINT_SAVED',
          operation_id: input.operation_id,
          request_hash: requestHash,
          execution_id: input.execution_id,
          lease_id: input.lease_id,
          fencing_token: input.fencing_token,
          checkpoint: input.checkpoint,
        }
      },
    )).event
  }

  async applyStep(input: {
    readonly operation_id: string
    readonly execution_id: string
    readonly lease_id: string
    readonly fencing_token: string
    readonly checkpoint_id: string
    readonly action_digest: SHA256Hex
    readonly result_digest: SHA256Hex
    readonly timestamp_ms: number
  }): Promise<DurableWorkflowEventPayloadV1> {
    assertIdentifier('operation_id', input.operation_id)
    assertIdentifier('execution_id', input.execution_id)
    assertIdentifier('lease_id', input.lease_id)
    assertHash('action_digest', input.action_digest)
    assertHash('result_digest', input.result_digest)
    const request = {
      execution_id: input.execution_id,
      lease_id: input.lease_id,
      fencing_token: input.fencing_token,
      checkpoint_id: input.checkpoint_id,
      action_digest: input.action_digest,
      result_digest: input.result_digest,
    }

    return (await this.commit(
      input.operation_id,
      request,
      input.timestamp_ms,
      async (requestHash, state) => {
        const nowMs = this.assertTrustedTimestamp(input.timestamp_ms)
        const execution = state.executions.find(item => item.execution_id === input.execution_id)
        const denial =
          this.executionDenial(state, execution, nowMs) ??
          this.leaseDenial(state, input.execution_id, input.lease_id, input.fencing_token, nowMs)
        const checkpoint = state.checkpoints.find(item => item.execution_id === input.execution_id)?.checkpoint
        if (denial || !checkpoint) {
          return this.denied(
            input.operation_id,
            requestHash,
            input.execution_id,
            'STEP',
            denial ?? 'CHECKPOINT_MISSING',
          )
        }
        if (checkpoint.checkpoint_id !== input.checkpoint_id) {
          return this.denied(input.operation_id, requestHash, input.execution_id, 'STEP', 'CHECKPOINT_STALE')
        }
        let verified = false
        try {
          verified = await this.verifyCheckpoint(checkpoint)
        } catch {
          verified = false
        }
        if (!verified) {
          return this.denied(
            input.operation_id,
            requestHash,
            input.execution_id,
            'STEP',
            'CHECKPOINT_UNVERIFIED',
          )
        }
        if (state.steps.some(item => item.execution_id === input.execution_id && item.action_digest === input.action_digest)) {
          return this.denied(input.operation_id, requestHash, input.execution_id, 'STEP', 'ACTION_ALREADY_APPLIED')
        }
        return {
          schema_version: '1.0.0',
          kind: 'STEP_APPLIED',
          operation_id: input.operation_id,
          request_hash: requestHash,
          execution_id: input.execution_id,
          lease_id: input.lease_id,
          fencing_token: input.fencing_token,
          checkpoint_id: input.checkpoint_id,
          action_digest: input.action_digest,
          result_digest: input.result_digest,
        }
      },
    )).event
  }

  async resume(
    executionId: string,
    operationId: string,
    timestampMs: number,
  ): Promise<DurableWorkflowEventPayloadV1> {
    assertIdentifier('execution_id', executionId)
    assertIdentifier('operation_id', operationId)

    return (await this.commit(
      operationId,
      { kind: 'RESUMED', execution_id: executionId },
      timestampMs,
      async (requestHash, state) => {
        const nowMs = this.assertTrustedTimestamp(timestampMs)
        const execution = state.executions.find(item => item.execution_id === executionId)
        const checkpoint = state.checkpoints.find(item => item.execution_id === executionId)?.checkpoint
        const denial = this.executionDenial(state, execution, nowMs)
        if (denial || !checkpoint) {
          return this.denied(
            operationId,
            requestHash,
            executionId,
            'RESUME',
            denial ?? 'CHECKPOINT_MISSING',
          )
        }
        let verified = false
        try {
          verified = await this.verifyCheckpoint(checkpoint)
        } catch {
          verified = false
        }
        if (!verified) return this.denied(operationId, requestHash, executionId, 'RESUME', 'CHECKPOINT_UNVERIFIED')
        return {
          schema_version: '1.0.0',
          kind: 'RESUMED',
          operation_id: operationId,
          request_hash: requestHash,
          execution_id: executionId,
          checkpoint,
        }
      },
    )).event
  }

  private denied(
    operationId: string,
    requestHash: SHA256Hex,
    executionId: string,
    action: string,
    denialCode: string,
  ): DurableWorkflowEventPayloadV1 {
    return {
      schema_version: '1.0.0',
      kind: 'ACTION_DENIED',
      operation_id: operationId,
      request_hash: requestHash,
      execution_id: executionId,
      action,
      denial_code: denialCode,
    }
  }

  private assertTrustedTimestamp(reportedTimestampMs: number): number {
    const trustedTimestampMs = this.trustedNow()
    if (!Number.isSafeInteger(trustedTimestampMs) || reportedTimestampMs !== trustedTimestampMs) {
      throw new DurableWorkflowError('UNTRUSTED_EVENT_TIMESTAMP')
    }
    return trustedTimestampMs
  }

  private precommitDenial(
    state: DurableWorkflowProjectionV1,
    event: DurableWorkflowEventPayloadV1,
    nowMs: number,
  ): DurableWorkflowEventPayloadV1 | null {
    let denial: string | null = null
    let action: string = event.kind
    const executionId =
      event.kind === 'EXECUTION_REGISTERED' ? event.execution.execution_id : event.execution_id
    switch (event.kind) {
      case 'EXECUTION_REGISTERED':
        if (Date.parse(event.execution.heartbeat_expires_at) <= nowMs) denial = 'HEARTBEAT_EXPIRED'
        break
      case 'LEASE_ACQUIRED': {
        action = 'LEASE_ACQUIRE'
        const execution = state.executions.find(item => item.execution_id === event.execution_id)
        denial = this.executionDenial(state, execution, nowMs)
        if (
          !denial &&
          state.leases.some(
            item =>
              item.lease.authority_domain === event.lease.authority_domain &&
              item.lease.revoked_at === null &&
              Date.parse(item.lease.expires_at) > nowMs,
          )
        ) denial = 'WRITER_ALREADY_ACTIVE'
        break
      }
      case 'HEARTBEAT': {
        action = 'HEARTBEAT'
        const execution = state.executions.find(item => item.execution_id === event.execution_id)
        denial =
          this.executionDenial(state, execution, nowMs) ??
          this.leaseDenial(state, event.execution_id, event.lease.lease_id, event.lease.fencing_token, nowMs)
        if (!denial && Date.parse(event.lease.expires_at) <= nowMs) denial = 'HEARTBEAT_INVALID'
        break
      }
      case 'CHECKPOINT_SAVED':
      case 'STEP_APPLIED': {
        action = event.kind === 'CHECKPOINT_SAVED' ? 'CHECKPOINT' : 'STEP'
        const execution = state.executions.find(item => item.execution_id === event.execution_id)
        denial =
          this.executionDenial(state, execution, nowMs) ??
          this.leaseDenial(state, event.execution_id, event.lease_id, event.fencing_token, nowMs)
        break
      }
      case 'RESUMED': {
        action = 'RESUME'
        const execution = state.executions.find(item => item.execution_id === event.execution_id)
        denial = this.executionDenial(state, execution, nowMs)
        break
      }
      case 'ACTION_DENIED':
        return null
    }
    return denial
      ? this.denied(event.operation_id, event.request_hash, executionId, action, denial)
      : null
  }

  private eventExecutionId(event: DurableWorkflowEventPayloadV1): string {
    return event.kind === 'EXECUTION_REGISTERED' ? event.execution.execution_id : event.execution_id
  }

  private eventAction(event: DurableWorkflowEventPayloadV1): string {
    switch (event.kind) {
      case 'EXECUTION_REGISTERED': return 'REGISTER'
      case 'LEASE_ACQUIRED': return 'LEASE_ACQUIRE'
      case 'HEARTBEAT': return 'HEARTBEAT'
      case 'CHECKPOINT_SAVED': return 'CHECKPOINT'
      case 'STEP_APPLIED': return 'STEP'
      case 'RESUMED': return 'RESUME'
      case 'ACTION_DENIED': return event.action
    }
  }

  private executionDenial(
    state: DurableWorkflowProjectionV1,
    execution: DurableExecutionRecordV1 | undefined,
    nowMs: number,
  ): string | null {
    if (!execution) return 'EXECUTION_NOT_REGISTERED'
    if (execution.status !== 'REGISTERED' && execution.status !== 'RUNNING') return 'EXECUTION_NOT_ACTIVE'
    const expiresAt = Date.parse(execution.heartbeat_expires_at)
    if (!Number.isFinite(expiresAt) || expiresAt <= nowMs) return 'HEARTBEAT_EXPIRED'
    if (!state.executions.some(item => item.execution_id === execution.execution_id)) return 'EXECUTION_NOT_REGISTERED'
    return null
  }

  private leaseDenial(
    state: DurableWorkflowProjectionV1,
    executionId: string,
    leaseId: string,
    fencingToken: string,
    nowMs: number,
  ): string | null {
    const current = state.leases.find(item => item.lease.lease_id === leaseId)
    if (!current || current.execution_id !== executionId) return 'LEASE_MISSING'
    const execution = state.executions.find(item => item.execution_id === executionId)
    if (!execution) return 'EXECUTION_NOT_REGISTERED'
    if (current.lease.executor_id !== execution.executor_id) return 'EXECUTOR_MISMATCH'
    if (current.lease.fencing_token !== fencingToken) return 'STALE_FENCING_TOKEN'
    if (current.lease.revoked_at !== null) return 'LEASE_REVOKED'
    const newer = state.leases.some(
      item =>
        item.lease.authority_domain === current.lease.authority_domain &&
        item.lease.revoked_at === null &&
        Date.parse(item.lease.expires_at) > nowMs &&
        BigInt(item.lease.fencing_token) > BigInt(fencingToken),
    )
    if (newer) return 'STALE_FENCING_TOKEN'
    if (Date.parse(current.lease.expires_at) <= nowMs) return 'LEASE_EXPIRED'
    return null
  }

  private async commit(
    operationId: string,
    request: unknown,
    timestampMs: number,
    build: (
      requestHash: SHA256Hex,
      state: DurableWorkflowProjectionV1,
      sequence: number,
    ) => DurableWorkflowEventPayloadV1 | Promise<DurableWorkflowEventPayloadV1>,
  ): Promise<{ event: DurableWorkflowEventPayloadV1; replayed: boolean }> {
    const requestHash = await sha256Hex(canonicalizeJCS(request))
    let conditionRetryPayload: DurableWorkflowEventPayloadV1 | null = null
    for (let attempt = 0; attempt < 8; attempt++) {
      const events = await this.store.getAll()
      const broken = await this.store.verifyChain()
      if (broken) throw new DurableWorkflowError(`EVENT_CHAIN_BROKEN_AT_${broken.broken_at_sequence}`)
      const prior = events.find(
        event =>
          event.event_type === EventType.DURABLE_WORKFLOW_EVENT &&
          (event.payload as DurableWorkflowEventPayloadV1).operation_id === operationId,
      )
      if (prior) {
        const payload = prior.payload as DurableWorkflowEventPayloadV1
        if (payload.request_hash !== requestHash) throw new DurableWorkflowError('IDEMPOTENCY_KEY_REUSED')
        return { event: payload, replayed: true }
      }

      const lastSequence = events.length === 0 ? -1 : Number(events[events.length - 1]!.sequence)
      if (!Number.isSafeInteger(lastSequence)) throw new DurableWorkflowError('EVENT_SEQUENCE_INVALID')
      const state = replayDurableWorkflow(events)
      const payload: DurableWorkflowEventPayloadV1 = conditionRetryPayload
        ? this.precommitDenial(state, conditionRetryPayload, this.trustedNow()) ??
          this.denied(
            conditionRetryPayload.operation_id,
            conditionRetryPayload.request_hash,
            this.eventExecutionId(conditionRetryPayload),
            this.eventAction(conditionRetryPayload),
            'UNTRUSTED_EVENT_TIMESTAMP',
          )
        : await build(requestHash, state, lastSequence)
      conditionRetryPayload = null
      const commitTimestamp = this.trustedNow()
      if (!Number.isSafeInteger(commitTimestamp) || commitTimestamp < timestampMs) {
        throw new DurableWorkflowError('TRUSTED_CLOCK_ROLLBACK')
      }
      const recordedPayload = this.precommitDenial(state, payload, commitTimestamp) ?? payload
      try {
        await recordWorkflowEvent(
          this.store,
          EventType.DURABLE_WORKFLOW_EVENT,
          recordedPayload,
          commitTimestamp,
          lastSequence,
          () => {
            const writeTimestamp = this.trustedNow()
            return (
              Number.isSafeInteger(writeTimestamp) &&
              writeTimestamp >= commitTimestamp &&
              (recordedPayload.kind === 'ACTION_DENIED' ||
                this.precommitDenial(state, payload, writeTimestamp) === null)
            )
          },
        )
        return { event: recordedPayload, replayed: false }
      } catch (error) {
        if (error instanceof EventStoreWriteConditionError) {
          conditionRetryPayload = payload
          continue
        }
        if (
          !(error instanceof ConcurrentEventStoreUpdateError)
        ) {
          throw error
        }
      }
    }
    throw new DurableWorkflowError('EVENT_STREAM_CONTENTION')
  }
}
