import 'fake-indexeddb/auto'

import { beforeEach, describe, expect, it } from 'vitest'
import type { Checkpoint, SHA256Hex, UUIDv7 } from '../../src/core/types.js'
import { canonicalizeJCSString } from '../../src/core/canonicalize.js'
import { EventType } from '../../src/core/types.js'
import { DurableWorkflowEngine, replayDurableWorkflow } from '../../src/event/durable-workflow.js'
import { EventStore } from '../../src/event/store.js'
import type { DurableWorkflowEventPayloadV1 } from '../../src/event/workflow.js'
import {
  SOVEREIGNTY_SCHEMA_VERSION,
  type DurableExecutionRecordV1,
} from '../../src/sovereignty/contracts.js'

const START = 1_700_000_000_000
const hash = (digit: string): SHA256Hex => digit.repeat(64) as SHA256Hex
let trustedNowMs = START

let streamCounter = 0
function streamId(): UUIDv7 {
  streamCounter++
  return `01900000-0000-7000-8000-${String(streamCounter).padStart(12, '0')}` as UUIDv7
}

function executionRecord(executionId: string, heartbeatExpiresAt = START + 60_000): DurableExecutionRecordV1 {
  const at = new Date(START).toISOString()
  return {
    schema_version: SOVEREIGNTY_SCHEMA_VERSION,
    execution_id: executionId,
    provider: 'test',
    executor_id: 'executor-1',
    workflow_identity_hash: hash('1'),
    canonical_state_root: hash('2'),
    status: 'REGISTERED',
    held_authority_domains: [],
    registration_time: at,
    last_heartbeat_at: at,
    heartbeat_expires_at: new Date(heartbeatExpiresAt).toISOString(),
    cancellation_endpoint_hash: hash('3'),
    terminal_receipt_hash: null,
  }
}

async function openedStore(id: UUIDv7 = streamId()): Promise<EventStore> {
  const store = new EventStore(id)
  await store.open()
  return store
}

function engine(
  store: EventStore,
  verifyCheckpoint: (checkpoint: Checkpoint) => boolean = () => true,
  verifyAuthorization: () => boolean = () => true,
  trustedClock: () => number = () => trustedNowMs,
) {
  return new DurableWorkflowEngine(store, verifyCheckpoint, verifyAuthorization, trustedClock)
}

async function register(
  workflow: DurableWorkflowEngine,
  executionId = 'execution-1',
  operationId = `register-${executionId}`,
): Promise<void> {
  trustedNowMs = START
  const result = await workflow.register(executionRecord(executionId), operationId, START)
  expect(result.kind).toBe('EXECUTION_REGISTERED')
}

function leaseRequest(executionId: string, operationId: string, timestampMs: number, ttlMs = 1_000) {
  trustedNowMs = timestampMs
  return {
    operation_id: operationId,
    execution_id: executionId,
    authority_domain: 'repo:main',
    holder_actor_id: 'agent-1',
    holder_session_id: 'session-1',
    executor_id: 'executor-1',
    workspace_id: 'workspace-1',
    expected_head: 'a'.repeat(40),
    expected_parent_state_root: hash('4'),
    authorization_hash: hash('5'),
    ttl_ms: ttlMs,
    timestamp_ms: timestampMs,
  }
}

function checkpoint(eventIndex: number, timestampMs: number): Checkpoint {
  return {
    checkpoint_id: 'checkpoint-1' as UUIDv7,
    event_index: BigInt(eventIndex) as Checkpoint['event_index'],
    segment_root: hash('6'),
    signature: 'test-signature',
    public_key_id: 'test-key',
    timestamp_ms: timestampMs,
  }
}

async function prepareCheckpoint(workflow: DurableWorkflowEngine): Promise<void> {
  const lease = await workflow.acquireLease(leaseRequest('execution-1', 'lease-1', START + 1))
  expect(lease.kind).toBe('LEASE_ACQUIRED')
  trustedNowMs = START + 2
  const saved = await workflow.saveCheckpoint({
    operation_id: 'checkpoint-save-1',
    execution_id: 'execution-1',
    lease_id: 'lease-1',
    fencing_token: '1',
    checkpoint: checkpoint(1, START + 2),
    timestamp_ms: START + 2,
  })
  expect(saved.kind).toBe('CHECKPOINT_SAVED')
}

describe('durable workflow event-store slice', () => {
  beforeEach(() => {
    trustedNowMs = START
  })

  it('serializes concurrent lease writers and audits the denied writer', async () => {
    const id = streamId()
    const store1 = await openedStore(id)
    const store2 = await openedStore(id)
    const first = engine(store1)
    const second = engine(store2)
    await register(first, 'execution-1')
    await register(first, 'execution-2')

    const [left, right] = await Promise.all([
      first.acquireLease(leaseRequest('execution-1', 'lease-left', START + 1)),
      second.acquireLease(leaseRequest('execution-2', 'lease-right', START + 1)),
    ])
    const outcomes = [left, right]

    expect(outcomes.filter(event => event.kind === 'LEASE_ACQUIRED')).toHaveLength(1)
    expect(outcomes.filter(event => event.kind === 'ACTION_DENIED')).toHaveLength(1)
    expect(outcomes.find(event => event.kind === 'ACTION_DENIED')).toMatchObject({
      denial_code: 'WRITER_ALREADY_ACTIVE',
    })
    expect(replayDurableWorkflow(await store1.getAll()).leases).toHaveLength(1)
  })

  it('fails closed on unverified authority, executor mismatch, and invalid heartbeat timestamps', async () => {
    const store = await openedStore()
    const workflow = engine(store, () => true, () => false)
    await register(workflow)

    expect(await workflow.register(
      { ...executionRecord('execution-1'), executor_id: 'other-executor' },
      'register-replacement',
      START,
    )).toMatchObject({
      kind: 'ACTION_DENIED',
      denial_code: 'EXECUTION_ALREADY_REGISTERED',
    })
    expect(await workflow.acquireLease(leaseRequest('execution-1', 'lease-unverified', START + 1))).toMatchObject({
      kind: 'ACTION_DENIED',
      denial_code: 'AUTHORIZATION_UNVERIFIED',
    })
    expect(await workflow.acquireLease({
      ...leaseRequest('execution-1', 'lease-wrong-executor', START + 1),
      executor_id: 'other-executor',
    })).toMatchObject({
      kind: 'ACTION_DENIED',
      denial_code: 'EXECUTOR_MISMATCH',
    })
    trustedNowMs = START
    await expect(
      workflow.register(
        { ...executionRecord('execution-bad'), heartbeat_expires_at: 'invalid' },
        'register-bad-heartbeat',
        START,
      ),
    ).rejects.toThrow('heartbeat_expires_at must be a canonical ISO-8601 UTC timestamp')
    expect(replayDurableWorkflow(await store.getAll()).executions[0]?.executor_id).toBe('executor-1')
  })

  it('rejects replay events that splice execution identifiers', async () => {
    const store = await openedStore()
    const workflow = engine(store)
    await register(workflow)
    await workflow.acquireLease(leaseRequest('execution-1', 'lease-1', START + 1))
    const events = await store.getAll()

    const wrongOuterId = events.map(event => {
      const payload = event.payload as DurableWorkflowEventPayloadV1
      return payload.kind === 'LEASE_ACQUIRED'
        ? { ...event, payload: { ...payload, execution_id: 'other-execution' } }
        : event
    })
    const wrongRecordId = events.map(event => {
      const payload = event.payload as DurableWorkflowEventPayloadV1
      return payload.kind === 'LEASE_ACQUIRED'
        ? {
            ...event,
            payload: {
              ...payload,
              execution: { ...payload.execution, execution_id: 'other-execution' },
            },
          }
        : event
    })

    expect(() => replayDurableWorkflow(wrongOuterId)).toThrow('EXECUTION_IDENTITY_CHANGED')
    expect(() => replayDurableWorkflow(wrongRecordId)).toThrow('EXECUTION_IDENTITY_CHANGED')
  })

  it('uses increasing fencing tokens and rejects a stale writer after expiry', async () => {
    const store = await openedStore()
    const workflow = engine(store)
    await register(workflow)
    const firstLease = await workflow.acquireLease(leaseRequest('execution-1', 'lease-1', START + 1, 10))
    expect(firstLease.kind).toBe('LEASE_ACQUIRED')

    trustedNowMs = START + 2
    const saved = await workflow.saveCheckpoint({
      operation_id: 'checkpoint-save-1',
      execution_id: 'execution-1',
      lease_id: 'lease-1',
      fencing_token: '1',
      checkpoint: checkpoint(1, START + 2),
      timestamp_ms: START + 2,
    })
    expect(saved.kind).toBe('CHECKPOINT_SAVED')

    const secondLease = await workflow.acquireLease(leaseRequest('execution-1', 'lease-2', START + 12))
    expect(secondLease).toMatchObject({ kind: 'LEASE_ACQUIRED', lease: { fencing_token: '2' } })
    trustedNowMs = START + 13
    const stale = await workflow.applyStep({
      operation_id: 'stale-step',
      execution_id: 'execution-1',
      lease_id: 'lease-1',
      fencing_token: '1',
      checkpoint_id: 'checkpoint-1',
      action_digest: hash('7'),
      result_digest: hash('8'),
      timestamp_ms: START + 13,
    })

    expect(stale).toMatchObject({ kind: 'ACTION_DENIED', denial_code: 'STALE_FENCING_TOKEN' })
    expect((await store.getAll()).some(event =>
      event.event_type === EventType.DURABLE_WORKFLOW_EVENT &&
      (event.payload as DurableWorkflowEventPayloadV1).operation_id === 'stale-step',
    )).toBe(true)
  })

  it('renews heartbeats without changing the active fencing token', async () => {
    const store = await openedStore()
    const workflow = engine(store)
    await register(workflow)
    await workflow.acquireLease(leaseRequest('execution-1', 'lease-1', START + 1, 10))

    trustedNowMs = START + 5
    const renewed = await workflow.heartbeat({
      operation_id: 'heartbeat-1',
      execution_id: 'execution-1',
      lease_id: 'lease-1',
      fencing_token: '1',
      heartbeat_expires_at_ms: START + 50,
      timestamp_ms: START + 5,
    })

    expect(renewed).toMatchObject({
      kind: 'HEARTBEAT',
      lease: { fencing_token: '1', expires_at: new Date(START + 50).toISOString() },
      execution: { last_heartbeat_at: new Date(START + 5).toISOString() },
    })
  })

  it('rejects caller-backdated timestamps instead of renewing an expired lease', async () => {
    const store = await openedStore()
    const workflow = engine(store)
    await register(workflow)
    await workflow.acquireLease(leaseRequest('execution-1', 'lease-1', START + 1, 10))
    trustedNowMs = START + 12

    await expect(workflow.heartbeat({
      operation_id: 'backdated-heartbeat',
      execution_id: 'execution-1',
      lease_id: 'lease-1',
      fencing_token: '1',
      heartbeat_expires_at_ms: START + 100,
      timestamp_ms: START + 5,
    })).rejects.toThrow('UNTRUSTED_EVENT_TIMESTAMP')
    expect(replayDurableWorkflow(await store.getAll()).leases[0]?.lease.expires_at).toBe(
      new Date(START + 11).toISOString(),
    )
  })

  it('rechecks expiry at the IndexedDB write boundary after an async race', async () => {
    const store = await openedStore()
    const setup = engine(store)
    await register(setup)
    await setup.acquireLease(leaseRequest('execution-1', 'lease-1', START + 1, 10))

    let clockReads = 0
    const workflow = engine(store, () => true, () => true, () => {
      clockReads++
      return clockReads >= 3 ? START + 12 : START + 5
    })
    const heartbeat = await workflow.heartbeat({
      operation_id: 'racing-heartbeat',
      execution_id: 'execution-1',
      lease_id: 'lease-1',
      fencing_token: '1',
      heartbeat_expires_at_ms: START + 50,
      timestamp_ms: START + 5,
    })

    expect(heartbeat).toMatchObject({
      kind: 'ACTION_DENIED',
      denial_code: 'LEASE_EXPIRED',
    })
    expect(replayDurableWorkflow(await store.getAll()).leases[0]?.lease.expires_at).toBe(
      new Date(START + 11).toISOString(),
    )
  })

  it('resumes from a persisted checkpoint without duplicating an applied step after restart', async () => {
    const id = streamId()
    const store = await openedStore(id)
    const workflow = engine(store)
    await register(workflow)
    await prepareCheckpoint(workflow)
    const input = {
      operation_id: 'step-1',
      execution_id: 'execution-1',
      lease_id: 'lease-1',
      fencing_token: '1',
      checkpoint_id: 'checkpoint-1',
      action_digest: hash('9'),
      result_digest: hash('a'),
      timestamp_ms: START + 3,
    }
    trustedNowMs = START + 3
    expect((await workflow.applyStep(input)).kind).toBe('STEP_APPLIED')

    const reopened = await openedStore(id)
    const restarted = engine(reopened)
    trustedNowMs = START + 10
    expect((await restarted.applyStep({ ...input, timestamp_ms: START + 10 })).kind).toBe('STEP_APPLIED')
    trustedNowMs = START + 11
    expect((await restarted.resume('execution-1', 'resume-1', START + 11)).kind).toBe('RESUMED')
    expect(replayDurableWorkflow(await reopened.getAll()).steps).toHaveLength(1)
  })

  it('replays idempotently after a crash at each persisted state boundary', async () => {
    const id = streamId()
    let store = await openedStore(id)
    let workflow = engine(store)
    const record = executionRecord('execution-1', START + 10_000)
    await workflow.register(record, 'register-execution', START)

    store = await openedStore(id)
    workflow = engine(store)
    trustedNowMs = START + 100
    expect((await workflow.register(record, 'register-execution', START)).kind).toBe('EXECUTION_REGISTERED')
    const leaseInput = leaseRequest('execution-1', 'lease-1', START + 101)
    expect((await workflow.acquireLease(leaseInput)).kind).toBe('LEASE_ACQUIRED')

    store = await openedStore(id)
    workflow = engine(store)
    trustedNowMs = START + 102
    expect((await workflow.acquireLease(leaseInput)).kind).toBe('LEASE_ACQUIRED')
    const checkpointInput = {
      operation_id: 'checkpoint-save-1',
      execution_id: 'execution-1',
      lease_id: 'lease-1',
      fencing_token: '1',
      checkpoint: checkpoint(1, START + 103),
      timestamp_ms: START + 103,
    }
    trustedNowMs = START + 103
    expect((await workflow.saveCheckpoint(checkpointInput)).kind).toBe('CHECKPOINT_SAVED')

    store = await openedStore(id)
    workflow = engine(store)
    trustedNowMs = START + 104
    expect((await workflow.saveCheckpoint(checkpointInput)).kind).toBe('CHECKPOINT_SAVED')
    const stepInput = {
      operation_id: 'step-1',
      execution_id: 'execution-1',
      lease_id: 'lease-1',
      fencing_token: '1',
      checkpoint_id: 'checkpoint-1',
      action_digest: hash('f'),
      result_digest: hash('e'),
      timestamp_ms: START + 105,
    }
    trustedNowMs = START + 105
    expect((await workflow.applyStep(stepInput)).kind).toBe('STEP_APPLIED')

    store = await openedStore(id)
    workflow = engine(store)
    trustedNowMs = START + 106
    expect((await workflow.applyStep({ ...stepInput, timestamp_ms: START + 106 })).kind).toBe('STEP_APPLIED')
    await expect(workflow.applyStep({
      ...stepInput,
      result_digest: hash('d'),
      timestamp_ms: START + 106,
    })).rejects.toThrow(
      'IDEMPOTENCY_KEY_REUSED',
    )
    const events = await store.getAll()
    expect(events.filter(event =>
      event.event_type === EventType.DURABLE_WORKFLOW_EVENT &&
      (event.payload as DurableWorkflowEventPayloadV1).kind === 'EXECUTION_REGISTERED',
    )).toHaveLength(1)
    expect(replayDurableWorkflow(events).leases).toHaveLength(1)
    expect(replayDurableWorkflow(events).checkpoints).toHaveLength(1)
    expect(replayDurableWorkflow(events).steps).toHaveLength(1)
  })

  it('fails closed and records denial when checkpoint or heartbeat evidence is missing', async () => {
    const store = await openedStore()
    const workflow = engine(store)
    await register(workflow)

    trustedNowMs = START + 1
    const missingCheckpoint = await workflow.resume('execution-1', 'resume-no-checkpoint', START + 1)
    expect(missingCheckpoint).toMatchObject({
      kind: 'ACTION_DENIED',
      denial_code: 'CHECKPOINT_MISSING',
    })
    trustedNowMs = START + 60_000
    const expiredHeartbeat = await workflow.resume('execution-1', 'resume-expired', START + 60_000)
    expect(expiredHeartbeat).toMatchObject({
      kind: 'ACTION_DENIED',
      denial_code: 'HEARTBEAT_EXPIRED',
    })
  })

  it('rejects resuming and applying steps from an unverified checkpoint', async () => {
    const store = await openedStore()
    const trusted = engine(store)
    await register(trusted)
    await prepareCheckpoint(trusted)
    const untrusted = engine(store, () => false)

    trustedNowMs = START + 3
    expect(await untrusted.applyStep({
      operation_id: 'step-unverified-checkpoint',
      execution_id: 'execution-1',
      lease_id: 'lease-1',
      fencing_token: '1',
      checkpoint_id: 'checkpoint-1',
      action_digest: hash('d'),
      result_digest: hash('e'),
      timestamp_ms: START + 3,
    })).toMatchObject({
      kind: 'ACTION_DENIED',
      denial_code: 'CHECKPOINT_UNVERIFIED',
    })
    trustedNowMs = START + 4
    expect(await untrusted.resume('execution-1', 'resume-unverified', START + 4)).toMatchObject({
      kind: 'ACTION_DENIED',
      denial_code: 'CHECKPOINT_UNVERIFIED',
    })
  })

  it('does not persist a checkpoint when its verifier rejects it', async () => {
    const store = await openedStore()
    const workflow = engine(store, () => false)
    await register(workflow)
    await workflow.acquireLease(leaseRequest('execution-1', 'lease-1', START + 1))

    trustedNowMs = START + 2
    expect(await workflow.saveCheckpoint({
      operation_id: 'checkpoint-save-denied',
      execution_id: 'execution-1',
      lease_id: 'lease-1',
      fencing_token: '1',
      checkpoint: checkpoint(1, START + 2),
      timestamp_ms: START + 2,
    })).toMatchObject({
      kind: 'ACTION_DENIED',
      denial_code: 'CHECKPOINT_UNVERIFIED',
    })
    expect(replayDurableWorkflow(await store.getAll()).checkpoints).toHaveLength(0)
  })

  it('replays the same persisted history deterministically more than 1000 times', async () => {
    const store = await openedStore()
    const workflow = engine(store)
    await register(workflow)
    await prepareCheckpoint(workflow)
    trustedNowMs = START + 3
    await workflow.applyStep({
      operation_id: 'step-1',
      execution_id: 'execution-1',
      lease_id: 'lease-1',
      fencing_token: '1',
      checkpoint_id: 'checkpoint-1',
      action_digest: hash('b'),
      result_digest: hash('c'),
      timestamp_ms: START + 3,
    })

    const events = await store.getAll()
    const expected = canonicalizeJCSString(replayDurableWorkflow(events))
    for (let replay = 0; replay < 1_001; replay++) {
      expect(canonicalizeJCSString(replayDurableWorkflow(events))).toBe(expected)
    }
  })
})
