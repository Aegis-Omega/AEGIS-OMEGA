import { describe, expect, it } from 'vitest'
import { generateKeypair } from '../../src/consensus/crypto.js'
import type { SHA256Hex } from '../../src/core/types.js'
import {
  ScaleOSControlPlaneProjectorV1,
  hashScaleOSEventEnvelopeV1,
  signScaleOSEventEnvelopeV1,
  verifyScaleOSEventEnvelopeV1,
  type ScaleOSEventEnvelopeDraftV1,
  type ScaleOSEventReplayInputV1,
  type ScaleOSEventTypeV1,
  type ScaleOSIdentitySetV1,
  type ScaleOSSignedEventEnvelopeV1,
} from '../../src/scale-os/control-plane.js'

const sourceObject = {
  request_id: 'request-001',
  action: 'repository-merge',
  target: 'Aegis-Omega/AEGIS-OMEGA',
}

const requestIdentity = {
  actor_id: 'request-agent',
  session_id: 'request-session',
  executor_id: 'request-executor',
}

const approvalIdentity = {
  actor_id: 'operator-tarik',
  session_id: 'operator-session',
  executor_id: 'operator-device',
}

const executionIdentity = {
  actor_id: 'github-actions',
  session_id: 'workflow-run-1',
  executor_id: 'ubuntu-runner-1',
}

const verificationIdentity = {
  actor_id: 'independent-verifier',
  session_id: 'verification-session',
  executor_id: 'verification-runner',
}

function identities(
  approval = false,
  execution = false,
  verification = false,
): ScaleOSIdentitySetV1 {
  return {
    request: requestIdentity,
    approval: approval ? approvalIdentity : null,
    execution: execution ? executionIdentity : null,
    verification: verification ? verificationIdentity : null,
  }
}

async function fixture() {
  const seed = new Uint8Array(32).fill(7)
  const keypair = await generateKeypair(seed)
  return { keypair }
}

function draft(
  eventType: ScaleOSEventTypeV1,
  sequence: number,
  previousEventHash: SHA256Hex | null,
  roleIdentities: ScaleOSIdentitySetV1,
  publicKey: string,
  suffix = String(sequence),
): ScaleOSEventEnvelopeDraftV1 {
  return {
    schema_version: '1.0.0',
    event_id: `event-${suffix}`,
    event_type: eventType,
    aggregate_id: 'approval-001',
    sequence: String(sequence),
    previous_event_hash: previousEventHash,
    idempotency_key: `approval-001:${eventType}:${suffix}`,
    correlation_id: 'correlation-001',
    causation_id: sequence === 0 ? null : `event-${sequence - 1}`,
    emitted_at: `2026-07-19T01:00:${String(sequence).padStart(2, '0')}Z`,
    identities: roleIdentities,
    signer_key_id: 'scale-os-test-key',
    signer_public_key: publicKey,
  }
}

async function signed(
  eventType: ScaleOSEventTypeV1,
  sequence: number,
  previousEventHash: SHA256Hex | null,
  roleIdentities: ScaleOSIdentitySetV1,
  publicKey: string,
  privateKey: Uint8Array,
  payload: unknown,
  suffix = String(sequence),
): Promise<ScaleOSEventReplayInputV1> {
  const envelope = await signScaleOSEventEnvelopeV1(
    draft(eventType, sequence, previousEventHash, roleIdentities, publicKey, suffix),
    sourceObject,
    payload,
    privateKey,
  )
  return { envelope, source_object: sourceObject, payload }
}

describe('Scale OS signed control plane v1', () => {
  it('produces byte-deterministic signatures and event hashes', async () => {
    const { keypair } = await fixture()
    const eventDraft = draft('REQUEST_CREATED', 0, null, identities(), keypair.publicKey)
    const payload = { requested_state: 'REQUESTED' }
    const first = await signScaleOSEventEnvelopeV1(eventDraft, sourceObject, payload, keypair.privateKey)
    const second = await signScaleOSEventEnvelopeV1(eventDraft, sourceObject, payload, keypair.privateKey)

    expect(first).toEqual(second)
    expect(await hashScaleOSEventEnvelopeV1(first)).toBe(await hashScaleOSEventEnvelopeV1(second))
    expect(await verifyScaleOSEventEnvelopeV1(first, sourceObject, payload)).toBe(true)
  })

  it('replays the explicit approval path through a terminal verified state', async () => {
    const { keypair } = await fixture()
    const projector = new ScaleOSControlPlaneProjectorV1()
    const entries: ScaleOSEventReplayInputV1[] = []
    let parent: SHA256Hex | null = null

    const path: Array<[ScaleOSEventTypeV1, ScaleOSIdentitySetV1, unknown]> = [
      ['REQUEST_CREATED', identities(), { state: 'REQUESTED' }],
      ['REQUEST_VALIDATED', identities(), { state: 'VALIDATED' }],
      ['APPROVAL_REQUESTED', identities(), { state: 'PENDING_OPERATOR' }],
      ['APPROVAL_GRANTED', identities(true), { state: 'APPROVED' }],
      ['EXECUTION_STARTED', identities(true, true), { state: 'EXECUTING' }],
      ['EXECUTION_SUCCEEDED', identities(true, true), { state: 'SUCCEEDED' }],
      ['VERIFICATION_RECORDED', identities(true, true, true), { verified_state: 'SUCCEEDED' }],
    ]

    for (const [index, [eventType, roleIdentities, payload]] of path.entries()) {
      const entry = await signed(
        eventType,
        index,
        parent,
        roleIdentities,
        keypair.publicKey,
        keypair.privateKey,
        payload,
      )
      entries.push(entry)
      parent = await hashScaleOSEventEnvelopeV1(entry.envelope)
    }

    await projector.replay(entries)
    const projection = projector.getProjection('approval-001')
    expect(projection?.approval_state).toBe('SUCCEEDED')
    expect(projection?.last_event_type).toBe('VERIFICATION_RECORDED')
    expect(projection?.applied_event_count).toBe('7')
  })

  it('treats an exact replay as an idempotent no-op', async () => {
    const { keypair } = await fixture()
    const projector = new ScaleOSControlPlaneProjectorV1()
    const entry = await signed(
      'REQUEST_CREATED',
      0,
      null,
      identities(),
      keypair.publicKey,
      keypair.privateKey,
      { state: 'REQUESTED' },
    )
    expect(await projector.apply(entry)).toBe('APPLIED')
    expect(await projector.apply(entry)).toBe('NO_OP')
    expect(projector.getProjection('approval-001')?.applied_event_count).toBe('1')
  })

  it('rejects conflicting reuse of an idempotency key', async () => {
    const { keypair } = await fixture()
    const projector = new ScaleOSControlPlaneProjectorV1()
    const first = await signed(
      'REQUEST_CREATED',
      0,
      null,
      identities(),
      keypair.publicKey,
      keypair.privateKey,
      { state: 'REQUESTED' },
    )
    await projector.apply(first)

    const conflictingDraft = {
      ...draft('REQUEST_CREATED', 0, null, identities(), keypair.publicKey, 'conflict'),
      idempotency_key: first.envelope.idempotency_key,
    }
    const conflictingEnvelope = await signScaleOSEventEnvelopeV1(
      conflictingDraft,
      sourceObject,
      { state: 'REQUESTED', altered: true },
      keypair.privateKey,
    )
    await expect(projector.apply({
      envelope: conflictingEnvelope,
      source_object: sourceObject,
      payload: { state: 'REQUESTED', altered: true },
    })).rejects.toThrow('idempotency key conflict')
  })

  it('rejects payload, source-object, and signature tampering', async () => {
    const { keypair } = await fixture()
    const entry = await signed(
      'REQUEST_CREATED',
      0,
      null,
      identities(),
      keypair.publicKey,
      keypair.privateKey,
      { state: 'REQUESTED' },
    )
    expect(await verifyScaleOSEventEnvelopeV1(
      entry.envelope,
      sourceObject,
      { state: 'APPROVED' },
    )).toBe(false)
    expect(await verifyScaleOSEventEnvelopeV1(
      entry.envelope,
      { ...sourceObject, target: 'other/repository' },
      entry.payload,
    )).toBe(false)

    const firstNibble = entry.envelope.signature[0] === '0' ? '1' : '0'
    const invalidSignature = `${firstNibble}${entry.envelope.signature.slice(1)}`
    const tamperedEnvelope: ScaleOSSignedEventEnvelopeV1 = {
      ...entry.envelope,
      signature: invalidSignature,
    }
    expect(await verifyScaleOSEventEnvelopeV1(
      tamperedEnvelope,
      sourceObject,
      entry.payload,
    )).toBe(false)
  })

  it('rejects stale sequence and wrong parent hashes', async () => {
    const { keypair } = await fixture()
    const projector = new ScaleOSControlPlaneProjectorV1()
    const first = await signed(
      'REQUEST_CREATED',
      0,
      null,
      identities(),
      keypair.publicKey,
      keypair.privateKey,
      { state: 'REQUESTED' },
    )
    await projector.apply(first)
    const head = await hashScaleOSEventEnvelopeV1(first.envelope)

    const stale = await signed(
      'REQUEST_VALIDATED',
      0,
      null,
      identities(),
      keypair.publicKey,
      keypair.privateKey,
      { state: 'VALIDATED' },
      'stale',
    )
    await expect(projector.apply(stale)).rejects.toThrow('sequence mismatch')

    const wrongParent = await signed(
      'REQUEST_VALIDATED',
      1,
      'f'.repeat(64) as SHA256Hex,
      identities(),
      keypair.publicKey,
      keypair.privateKey,
      { state: 'VALIDATED' },
      'wrong-parent',
    )
    await expect(projector.apply(wrongParent)).rejects.toThrow('previous_event_hash')

    const valid = await signed(
      'REQUEST_VALIDATED',
      1,
      head,
      identities(),
      keypair.publicKey,
      keypair.privateKey,
      { state: 'VALIDATED' },
      'valid',
    )
    expect(await projector.apply(valid)).toBe('APPLIED')
  })

  it('rejects illegal transitions after a terminal denial', async () => {
    const { keypair } = await fixture()
    const projector = new ScaleOSControlPlaneProjectorV1()
    const created = await signed(
      'REQUEST_CREATED',
      0,
      null,
      identities(),
      keypair.publicKey,
      keypair.privateKey,
      { state: 'REQUESTED' },
    )
    await projector.apply(created)
    const createdHash = await hashScaleOSEventEnvelopeV1(created.envelope)

    const denied = await signed(
      'APPROVAL_DENIED',
      1,
      createdHash,
      identities(true),
      keypair.publicKey,
      keypair.privateKey,
      { state: 'DENIED' },
    )
    await projector.apply(denied)
    const deniedHash = await hashScaleOSEventEnvelopeV1(denied.envelope)

    const resurrected = await signed(
      'APPROVAL_GRANTED',
      2,
      deniedHash,
      identities(true),
      keypair.publicKey,
      keypair.privateKey,
      { state: 'APPROVED' },
    )
    await expect(projector.apply(resurrected)).rejects.toThrow('terminal state DENIED')
  })

  it('requires distinct approval, execution, and verification identities', async () => {
    const { keypair } = await fixture()
    await expect(signScaleOSEventEnvelopeV1(
      draft('APPROVAL_GRANTED', 3, 'a'.repeat(64) as SHA256Hex, {
        request: requestIdentity,
        approval: requestIdentity,
        execution: null,
        verification: null,
      }, keypair.publicKey),
      sourceObject,
      { state: 'APPROVED' },
      keypair.privateKey,
    )).rejects.toThrow('must be distinct')

    await expect(signScaleOSEventEnvelopeV1(
      draft('VERIFICATION_RECORDED', 6, 'b'.repeat(64) as SHA256Hex, identities(true, true, false), keypair.publicKey),
      sourceObject,
      { verified_state: 'SUCCEEDED' },
      keypair.privateKey,
    )).rejects.toThrow('requires a verification identity')
  })
})
