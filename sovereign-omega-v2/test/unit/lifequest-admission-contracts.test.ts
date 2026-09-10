import { describe, expect, it } from 'vitest'
import {
  assertLifeQuestEventV1,
  assertLifeQuestTransitionAllowed,
  buildLifeQuestAdmissionCandidateV1,
  canonicalizeLifeQuestEventV1,
  hashLifeQuestEventV1,
  type LifeQuestEventV1,
} from '../../src/integrations/lifequest/contracts.js'

const event = {
  schemaVersion: '1.0.0',
  eventId: 'lqevt_20260802_001',
  questId: 'quest-system-rebuild',
  eventType: 'QUEST_ACTIVATION_REQUESTED',
  actorId: 'operator:tarik',
  occurredAt: '2026-08-02T08:00:00.000Z',
  authorityMode: 'PROPOSAL_ONLY',
  payload: {
    quest: {
      id: 'quest-system-rebuild',
      status: 'DRAFT',
    },
  },
} satisfies LifeQuestEventV1

describe('LifeQuest admission contract v1', () => {
  it('produces the pinned domain-separated event hash', async () => {
    await expect(hashLifeQuestEventV1(event)).resolves.toBe(
      '049a6e15e2b131091c6d609991ea785bbe2544948f27f10d9d28704de5941f59',
    )
  })

  it('is invariant to object insertion order', () => {
    const reordered = {
      payload: {
        quest: {
          status: 'DRAFT',
          id: 'quest-system-rebuild',
        },
      },
      authorityMode: 'PROPOSAL_ONLY',
      occurredAt: '2026-08-02T08:00:00.000Z',
      actorId: 'operator:tarik',
      eventType: 'QUEST_ACTIVATION_REQUESTED',
      questId: 'quest-system-rebuild',
      eventId: 'lqevt_20260802_001',
      schemaVersion: '1.0.0',
    } satisfies LifeQuestEventV1

    expect(canonicalizeLifeQuestEventV1(reordered)).toEqual(canonicalizeLifeQuestEventV1(event))
  })

  it('converts a valid proposal into a non-executable admission candidate', async () => {
    const candidate = await buildLifeQuestAdmissionCandidateV1({
      event,
      expectedQuestStatus: 'DRAFT',
      requestedQuestStatus: 'ACTIVE',
    })

    expect(candidate).toMatchObject({
      authorityDomain: 'lifequest.quest-state',
      requiredApproval: 'OPERATOR_EXPLICIT',
      admissionStatus: 'PENDING_OPERATOR',
      executionAuthorityGranted: false,
      canonicalStateRoot: null,
      authorityLeaseHash: null,
      approvalRecordHash: null,
    })
    expect(candidate.candidateId).toBe(`lifequest-admission:${candidate.sourceEventHash}`)
  })

  it('fails closed on client authority escalation', () => {
    expect(() =>
      assertLifeQuestEventV1({
        ...event,
        authorityMode: 'EXECUTE',
      }),
    ).toThrow('LifeQuest clients may submit proposal-only events')
  })

  it('fails closed on illegal state transitions', () => {
    expect(() => assertLifeQuestTransitionAllowed('DRAFT', 'COMPLETED')).toThrow(
      'illegal LifeQuest transition: DRAFT -> COMPLETED',
    )
    expect(() => assertLifeQuestTransitionAllowed('COMPLETED', 'ACTIVE')).toThrow(
      'illegal LifeQuest transition: COMPLETED -> ACTIVE',
    )
  })

  it('rejects extra fields and shared object aliases', () => {
    expect(() => assertLifeQuestEventV1({ ...event, hiddenAuthority: 'EXECUTE' })).toThrow(
      'LifeQuest event contains missing or unexpected fields',
    )

    const shared = { value: 'same-reference' }
    expect(() =>
      assertLifeQuestEventV1({
        ...event,
        payload: {
          first: shared,
          second: shared,
        },
      }),
    ).toThrow('payload.second contains a cycle or shared object alias')
  })
})
