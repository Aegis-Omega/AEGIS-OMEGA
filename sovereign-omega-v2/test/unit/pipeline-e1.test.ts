// ============================================================
// SOVEREIGN OMEGA — E1 Ambiguity Routing Interface tests
// EPISTEMIC TIER: T2
//
// Tests for pipeline/e1.ts:
//   createInitialDialogueState — initial frozen state
//   assessAmbiguity — all four detection heuristics, cost-benefit,
//     rate limiting, escalation, result shape
//   updateDialogueState — immutable update, flag accumulation,
//     grounding decay, sequence tracking
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  createInitialDialogueState,
  assessAmbiguity,
  updateDialogueState,
} from '../../src/pipeline/e1.js'
import type { DialogueState, AmbiguityFlag, DialogueConstraint } from '../../src/core/types.js'
import type { SequenceNumber, UUIDv7 } from '../../src/core/types.js'
import { AmbiguityType } from '../../src/core/types.js'

const SEQ = (n: number) => BigInt(n) as unknown as SequenceNumber
const SESSION = 'sess-01' as UUIDv7

function emptyState(): Readonly<DialogueState> {
  return createInitialDialogueState(SESSION)
}

function stateWith(overrides: Partial<DialogueState>): Readonly<DialogueState> {
  return Object.freeze({ ...emptyState(), ...overrides })
}

function makeFlag(type: AmbiguityType, resolved = false): AmbiguityFlag {
  return Object.freeze({
    id: `flag-${type}`,
    ambiguity_type: type,
    divergence_score: 0.3,
    introduced_at_sequence: SEQ(1),
    resolved,
  })
}

// ── createInitialDialogueState ────────────────────────────

describe('createInitialDialogueState', () => {
  it('creates a frozen state with correct initial fields', () => {
    const state = createInitialDialogueState(SESSION)
    expect(Object.isFrozen(state)).toBe(true)
    expect(state.session_id).toBe(SESSION)
    expect(state.resolved_referents).toEqual({})
    expect(state.active_constraints).toHaveLength(0)
    expect(state.unresolved_ambiguities).toHaveLength(0)
    expect(state.grounding_confidence).toBe(1.0)
    expect(state.turn_count).toBe(0)
  })
})

// ── assessAmbiguity — clean input ─────────────────────────

describe('assessAmbiguity — clean input', () => {
  it('returns no detected types and zero divergence for unambiguous input', () => {
    const assessment = assessAmbiguity('please summarise the document for me', emptyState(), 'v1')
    expect(assessment.detected_types).toHaveLength(0)
    expect(assessment.divergence_score).toBe(0)
    expect(assessment.requires_clarification).toBe(false)
    expect(assessment.escalate_to_structured_form).toBe(false)
  })

  it('result is frozen', () => {
    const assessment = assessAmbiguity('hello world test input', emptyState(), 'v1')
    expect(Object.isFrozen(assessment)).toBe(true)
    expect(Object.isFrozen(assessment.detected_types)).toBe(true)
  })
})

// ── assessAmbiguity — REFERENTIAL ─────────────────────────

describe('assessAmbiguity — REFERENTIAL detection', () => {
  it('detects REFERENTIAL when input has pronoun and no resolved_referents', () => {
    const assessment = assessAmbiguity('please check it and verify', emptyState(), 'v1')
    expect(assessment.detected_types).toContain(AmbiguityType.REFERENTIAL)
    expect(assessment.divergence_score).toBeGreaterThanOrEqual(0.3)
  })

  it('does not flag REFERENTIAL when resolved_referents are populated', () => {
    const state = stateWith({
      resolved_referents: {
        'doc': { id: 'r1', label: 'doc', introduced_at_sequence: SEQ(1), last_referenced_at_sequence: SEQ(1) },
      },
    })
    const assessment = assessAmbiguity('please check it and verify', state, 'v1')
    expect(assessment.detected_types).not.toContain(AmbiguityType.REFERENTIAL)
  })
})

// ── assessAmbiguity — CONSTRAINT_CONFLICT ─────────────────

describe('assessAmbiguity — CONSTRAINT_CONFLICT detection', () => {
  it('detects CONSTRAINT_CONFLICT and sets requires_clarification when negation matches constraint', () => {
    const constraint: DialogueConstraint = {
      id: 'c1',
      description: 'always use database for storage',
      introduced_at_sequence: SEQ(1),
      is_active: true,
    }
    const state = stateWith({ active_constraints: [constraint] })
    const assessment = assessAmbiguity('not use database here', state, 'v1')
    expect(assessment.detected_types).toContain(AmbiguityType.CONSTRAINT_CONFLICT)
    expect(assessment.requires_clarification).toBe(true)
  })

  it('does not flag CONSTRAINT_CONFLICT with no active_constraints', () => {
    const assessment = assessAmbiguity('never use the database', emptyState(), 'v1')
    expect(assessment.detected_types).not.toContain(AmbiguityType.CONSTRAINT_CONFLICT)
  })
})

// ── assessAmbiguity — DOMAIN_SHIFT ────────────────────────

describe('assessAmbiguity — DOMAIN_SHIFT detection', () => {
  it('detects DOMAIN_SHIFT when caps-term is not in resolved_referents', () => {
    const assessment = assessAmbiguity('implement the REST endpoint now', emptyState(), 'v1')
    expect(assessment.detected_types).toContain(AmbiguityType.DOMAIN_SHIFT)
    expect(assessment.divergence_score).toBeGreaterThanOrEqual(0.2)
  })

  it('does not flag DOMAIN_SHIFT when technical term matches a resolved_referent', () => {
    const state = stateWith({
      resolved_referents: {
        'REST': { id: 'r2', label: 'REST', introduced_at_sequence: SEQ(1), last_referenced_at_sequence: SEQ(1) },
      },
    })
    const assessment = assessAmbiguity('implement the REST endpoint now', state, 'v1')
    expect(assessment.detected_types).not.toContain(AmbiguityType.DOMAIN_SHIFT)
  })
})

// ── assessAmbiguity — INTENT_UNDERSPECIFICATION ───────────

describe('assessAmbiguity — INTENT_UNDERSPECIFICATION detection', () => {
  it('detects INTENT_UNDERSPECIFICATION for vague keyword "anything"', () => {
    const assessment = assessAmbiguity('do anything with the results', emptyState(), 'v1')
    expect(assessment.detected_types).toContain(AmbiguityType.INTENT_UNDERSPECIFICATION)
  })

  it('detects INTENT_UNDERSPECIFICATION for short inputs (< 4 words)', () => {
    const assessment = assessAmbiguity('make it work', emptyState(), 'v1')
    expect(assessment.detected_types).toContain(AmbiguityType.INTENT_UNDERSPECIFICATION)
  })
})

// ── assessAmbiguity — requires_clarification triggers ─────

describe('assessAmbiguity — requires_clarification triggers', () => {
  it('returns requires_clarification=true when grounding_confidence is below floor (0.40)', () => {
    const state = stateWith({ grounding_confidence: 0.35 })
    const assessment = assessAmbiguity('what should we do now', state, 'v1')
    expect(assessment.requires_clarification).toBe(true)
  })

  it('rate limit suppresses requires_clarification when unresolved/turns ≥ 1/3', () => {
    // turn_count=3, 1 unresolved flag → recentClarifications=1, 1/3 is not < 1/3
    const state = stateWith({
      grounding_confidence: 0.35,  // would trigger clarification
      turn_count: 3,
      unresolved_ambiguities: [makeFlag(AmbiguityType.REFERENTIAL)],
    })
    const assessment = assessAmbiguity('what should we do now', state, 'v1')
    expect(assessment.requires_clarification).toBe(false)
  })
})

// ── assessAmbiguity — escalation ──────────────────────────

describe('assessAmbiguity — escalation', () => {
  it('escalate_to_structured_form is true when 3+ unresolved ambiguities', () => {
    const state = stateWith({
      unresolved_ambiguities: [
        makeFlag(AmbiguityType.REFERENTIAL),
        makeFlag(AmbiguityType.DOMAIN_SHIFT),
        makeFlag(AmbiguityType.INTENT_UNDERSPECIFICATION),
      ],
    })
    const assessment = assessAmbiguity('do anything', state, 'v1')
    expect(assessment.escalate_to_structured_form).toBe(true)
  })

  it('escalate_to_structured_form is false with fewer than 3 unresolved', () => {
    const state = stateWith({
      unresolved_ambiguities: [makeFlag(AmbiguityType.REFERENTIAL)],
    })
    const assessment = assessAmbiguity('do anything', state, 'v1')
    expect(assessment.escalate_to_structured_form).toBe(false)
  })

  it('resolved flags do not count toward escalation threshold', () => {
    const state = stateWith({
      unresolved_ambiguities: [
        makeFlag(AmbiguityType.REFERENTIAL, true),   // resolved
        makeFlag(AmbiguityType.DOMAIN_SHIFT, true),  // resolved
        makeFlag(AmbiguityType.INTENT_UNDERSPECIFICATION, false), // 1 unresolved
      ],
    })
    const assessment = assessAmbiguity('please summarise the document for me', state, 'v1')
    expect(assessment.escalate_to_structured_form).toBe(false)
  })
})

// ── updateDialogueState ───────────────────────────────────

describe('updateDialogueState', () => {
  it('increments turn_count and updates sequence', () => {
    const state = emptyState()
    const assessment = assessAmbiguity('hello world text input here', state, 'v1')
    const updated = updateDialogueState(state, 'hello world text input here', assessment, SEQ(5))
    expect(updated.turn_count).toBe(1)
    expect(updated.last_updated_sequence).toBe(SEQ(5))
  })

  it('adds AmbiguityFlag entries for each detected type', () => {
    const state = emptyState()
    // Use short input to trigger INTENT_UNDERSPECIFICATION
    const assessment = assessAmbiguity('do anything', state, 'v1')
    const updated = updateDialogueState(state, 'do anything', assessment, SEQ(2))
    expect(updated.unresolved_ambiguities.some(
      a => a.ambiguity_type === AmbiguityType.INTENT_UNDERSPECIFICATION
    )).toBe(true)
  })

  it('decreases grounding_confidence by divergence_score * 0.1', () => {
    const constraint: DialogueConstraint = {
      id: 'c2', description: 'use cache', introduced_at_sequence: SEQ(1), is_active: true,
    }
    const stateWithConstraint = stateWith({ active_constraints: [constraint] })
    const assessment = assessAmbiguity('not use cache here', stateWithConstraint, 'v1')
    const updated = updateDialogueState(stateWithConstraint, 'not use cache here', assessment, SEQ(3))
    const expectedConfidence = Math.max(0, 1.0 - assessment.divergence_score * 0.1)
    expect(updated.grounding_confidence).toBeCloseTo(expectedConfidence)
  })

  it('returns a frozen state and does not mutate the input', () => {
    const state = emptyState()
    const assessment = assessAmbiguity('hello world text input here', state, 'v1')
    const updated = updateDialogueState(state, 'hello', assessment, SEQ(1))
    expect(Object.isFrozen(updated)).toBe(true)
    // original state unchanged
    expect(state.turn_count).toBe(0)
    expect(state.unresolved_ambiguities).toHaveLength(0)
  })

  it('clean assessment with no detected types adds no new ambiguity flags', () => {
    const state = emptyState()
    const assessment = assessAmbiguity('please summarise the document for me', state, 'v1')
    const updated = updateDialogueState(state, 'please summarise the document for me', assessment, SEQ(1))
    expect(updated.unresolved_ambiguities).toHaveLength(0)
  })
})
