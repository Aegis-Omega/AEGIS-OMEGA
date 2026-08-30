import { describe, expect, it } from 'vitest'
import {
  checkAuthorizationInversion,
  type AAPClaim,
  type AgentSVID,
  type InversionRequest,
  type VerificationOutcome,
} from '../../src/sovereignty/authorization-inversion.js'

const NOW = '2026-07-26T12:00:00.000Z'
const LATER = '2026-07-26T18:00:00.000Z'
const EARLIER = '2026-07-26T06:00:00.000Z'

const svid = (over: Partial<AgentSVID> = {}): AgentSVID => ({
  spiffe_id: 'spiffe://aegisomega.com/agent/holon-1',
  session_id: 'sess-1',
  mutation_operators: ['record.update'],
  k_bound: 4,
  not_after: LATER,
  ...over,
})

const claim = (over: Partial<AAPClaim> = {}): AAPClaim => ({
  claim_id: 'aap-1',
  subject_spiffe_id: 'spiffe://aegisomega.com/agent/holon-1',
  action: 'update-customer-record',
  mutation_operator: 'record.update',
  k_contribution: 2,
  logged: true,
  ...over,
})

const verification = (over: Partial<VerificationOutcome> = {}): VerificationOutcome => ({
  verifier_id: 'verifier-a',
  passed: true,
  evidence_ref: 'sha256:deadbeef',
  ...over,
})

const request = (over: Partial<InversionRequest> = {}): InversionRequest => ({
  svid: svid(),
  claim: claim(),
  verification: verification(),
  requested_operator: 'record.update',
  action: 'update-customer-record',
  now: NOW,
  ...over,
})

describe('checkAuthorizationInversion — the satisfied conjunction', () => {
  it('passes only when all five conjuncts hold', () => {
    const d = checkAuthorizationInversion(request())
    expect(d.verdict).toBe('pass')
    expect(d.failures).toEqual([])
    expect(d.checks).toEqual({
      valid_svid: true,
      in_scope: true,
      within_k_bound: true,
      claim_logged: true,
      verification_pass: true,
    })
  })

  it('is deterministic — same input, byte-identical decision across runs', () => {
    const r = request()
    const a = JSON.stringify(checkAuthorizationInversion(r))
    const b = JSON.stringify(checkAuthorizationInversion(r))
    const c = JSON.stringify(checkAuthorizationInversion(r))
    expect(a).toBe(b)
    expect(b).toBe(c)
  })

  it('reads no ambient clock — the verdict flips with caller-supplied now alone', () => {
    expect(checkAuthorizationInversion(request({ now: EARLIER })).verdict).toBe('pass')
    const expired = checkAuthorizationInversion(request({ now: LATER }))
    expect(expired.verdict).toBe('reject')
    expect(expired.failures).toContain('svid_expired')
  })
})

describe('check 1 — identity', () => {
  it('rejects when no SVID is presented', () => {
    const d = checkAuthorizationInversion(request({ svid: null }))
    expect(d.verdict).toBe('reject')
    expect(d.failures).toContain('svid_missing')
    expect(d.checks.valid_svid).toBe(false)
  })

  it('rejects at the expiry boundary — not_after is exclusive', () => {
    const d = checkAuthorizationInversion(request({ svid: svid({ not_after: NOW }) }))
    expect(d.failures).toContain('svid_expired')
  })

  it('rejects an unparsable validity bound instead of reading it as valid', () => {
    // NaN <= NaN is false, so an unguarded comparison would let this through.
    const d = checkAuthorizationInversion(request({ svid: svid({ not_after: 'never' }) }))
    expect(d.verdict).toBe('reject')
    expect(d.failures).toContain('svid_validity_unparsable')
    expect(d.failures).not.toContain('svid_expired')
  })

  it('rejects a claim issued to a different subject', () => {
    const d = checkAuthorizationInversion(
      request({ claim: claim({ subject_spiffe_id: 'spiffe://aegisomega.com/agent/other' }) }),
    )
    expect(d.verdict).toBe('reject')
    expect(d.failures).toContain('svid_subject_mismatch')
  })
})

describe('check 2 — scope (access is not authority)', () => {
  it('rejects a mutation for a retrieval-only identity', () => {
    // The core inversion: retrieval was authorized, mutation never was.
    const d = checkAuthorizationInversion(request({ svid: svid({ mutation_operators: [] }) }))
    expect(d.verdict).toBe('reject')
    expect(d.failures).toContain('operator_out_of_scope')
    expect(d.checks.in_scope).toBe(false)
  })

  it('rejects an operator the identity never declared', () => {
    const d = checkAuthorizationInversion(
      request({ requested_operator: 'record.delete', claim: claim({ mutation_operator: 'record.delete' }) }),
    )
    expect(d.failures).toContain('operator_out_of_scope')
  })

  it('rejects an empty requested operator as undeclared, never as a no-op', () => {
    const d = checkAuthorizationInversion(request({ requested_operator: '' }))
    expect(d.verdict).toBe('reject')
    expect(d.failures).toContain('operator_undeclared')
  })

  it('rejects when the claim authorizes a different operator than the action invokes', () => {
    const d = checkAuthorizationInversion(request({ claim: claim({ mutation_operator: 'record.read' }) }))
    expect(d.verdict).toBe('reject')
    expect(d.failures).toContain('operator_out_of_scope')
  })
})

describe('check 3 — K-bound (capability is not proportionality)', () => {
  it('admits a contribution equal to the bound', () => {
    const d = checkAuthorizationInversion(request({ claim: claim({ k_contribution: 4 }) }))
    expect(d.verdict).toBe('pass')
    expect(d.checks.within_k_bound).toBe(true)
  })

  it('rejects a contribution above the bound', () => {
    const d = checkAuthorizationInversion(request({ claim: claim({ k_contribution: 5 }) }))
    expect(d.verdict).toBe('reject')
    expect(d.failures).toContain('k_bound_exceeded')
  })

  it('does not report an exceeded bound when there was no bound to compare', () => {
    const d = checkAuthorizationInversion(request({ claim: null }))
    expect(d.verdict).toBe('reject')
    expect(d.checks.within_k_bound).toBe(false)
    expect(d.failures).not.toContain('k_bound_exceeded')
    expect(d.failures).toContain('claim_unlogged')
  })
})

describe('check 4 — claim log', () => {
  it('rejects an authorization that was never durably recorded', () => {
    const d = checkAuthorizationInversion(request({ claim: claim({ logged: false }) }))
    expect(d.verdict).toBe('reject')
    expect(d.failures).toContain('claim_unlogged')
  })

  it('rejects when the logged claim covers a different action', () => {
    const d = checkAuthorizationInversion(request({ claim: claim({ action: 'delete-customer-record' }) }))
    expect(d.verdict).toBe('reject')
    expect(d.failures).toContain('claim_action_mismatch')
  })
})

describe('check 5 — independent verification', () => {
  it('escalates when a verifier has simply not run yet', () => {
    const d = checkAuthorizationInversion(request({ verification: null }))
    expect(d.verdict).toBe('escalate')
    expect(d.failures).toEqual(['verification_absent'])
    expect(d.reason).toContain('awaiting independent verification')
  })

  it('rejects — never escalates — when a verifier ran and said no', () => {
    const d = checkAuthorizationInversion(request({ verification: verification({ passed: false }) }))
    expect(d.verdict).toBe('reject')
    expect(d.failures).toEqual(['verification_failed'])
  })

  it('treats absent verification as absent, not as passing', () => {
    expect(checkAuthorizationInversion(request({ verification: null })).checks.verification_pass).toBe(false)
  })
})

describe('fail-closed composition', () => {
  it('does not escalate when a real constraint also failed', () => {
    const d = checkAuthorizationInversion(
      request({ verification: null, svid: svid({ mutation_operators: [] }) }),
    )
    expect(d.verdict).toBe('reject')
    expect(d.failures).toContain('verification_absent')
    expect(d.failures).toContain('operator_out_of_scope')
  })

  it('reports every independent failure, not just the first', () => {
    const d = checkAuthorizationInversion({
      svid: null,
      claim: null,
      verification: null,
      requested_operator: '',
      action: 'update-customer-record',
      now: NOW,
    })
    expect(d.verdict).toBe('reject')
    expect(d.failures).toEqual([
      'svid_missing',
      'operator_undeclared',
      'claim_unlogged',
      'verification_absent',
    ])
    expect(Object.values(d.checks).every((v) => v === false)).toBe(true)
  })

  it('never returns pass with a failing check — the verdict cannot outrun the evidence', () => {
    const mutations: Array<Partial<InversionRequest>> = [
      { svid: null },
      { claim: null },
      { verification: null },
      { requested_operator: '' },
      { svid: svid({ not_after: EARLIER }) },
      { svid: svid({ mutation_operators: [] }) },
      { svid: svid({ k_bound: 0 }) },
      { claim: claim({ logged: false }) },
      { claim: claim({ action: 'other' }) },
      { verification: verification({ passed: false }) },
    ]
    for (const over of mutations) {
      const d = checkAuthorizationInversion(request(over))
      expect(d.verdict, JSON.stringify(over)).not.toBe('pass')
      if (d.verdict === 'escalate') {
        expect(d.failures).toEqual(['verification_absent'])
      }
    }
  })
})
