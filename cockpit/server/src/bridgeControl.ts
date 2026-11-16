/**
 * Byte-exact, server-side-only encoder for the Python E4 mutation bridge.
 *
 * This module is NOT the E4 policy engine, not an authorization endpoint, and
 * cannot attest that an externally supplied LCB is statistically valid.
 * Only a separately authenticated server E4 executor may call this after
 * its own decision has been independently verified. Do not import from Vite.
 */
import { createHash } from 'node:crypto'

const PROPOSAL_ID_RE = /^[A-Za-z0-9._:-]{1,128}$/
const DIGEST_DOMAIN = Buffer.from('AEGIS_MUTATION_EVENT_V1\x00', 'utf8')
const MAX_GOVERNANCE_PAYLOAD = 65536
const MAX_GOVERNANCE_VERIFIER = 256
const MAX_GOVERNANCE_CONTEXT = 4096

/** Structural transport projection of sovereign-runtime GateDecisionPayload (#817).
 * No independent E4 math engine or duplicate acceptance policy is introduced.
 * Transport validation checks the shape; issuer origin still requires a trusted
 * server executor, not a value typed by a browser or other caller.
 */
export interface E4DecisionEvidence {
  readonly proposal_id: string
  readonly component_id: string
  readonly accepted: boolean
  readonly lcb_value: number
  readonly e_value: number
  readonly risk_spent: number
  readonly sample_size: number
  readonly method: string
}

export interface AdmittedGovernanceMutation {
  readonly decision: E4DecisionEvidence
  readonly capabilityClass: 'SELF_MODIFYING'
  readonly operatorId: string
  readonly sequence: number
  readonly payload: Uint8Array
  readonly verifier: Uint8Array
  readonly context: Uint8Array
}

export interface MutationTransportFrames {
  readonly gate_signal: Readonly<{
    proposal_id: string
    component_id: string
    capability_class: 'SELF_MODIFYING'
    operator_id: string
    sequence: number
    accepted: true
    lcb: number
    e_value: number
    risk_spent: number
    sample_size: number
    method: 'anytime_valid_bernstein'
    event_sha256: string
  }>
  readonly event: Readonly<{
    proposal_id: string
    component_id: string
    capability_class: 'SELF_MODIFYING'
    operator_id: string
    payload_hex: string
    verifier_hex: string
    context_hex: string
  }>
}

function requireBytes(input: unknown, max: number, field: string): Buffer {
  if (!(input instanceof Uint8Array) || input.byteLength > max) {
    throw new TypeError(`${field} must be byte data no longer than ${max}`)
  }
  return Buffer.from(input)
}

/** Versioned SHA-256 over 8-byte BE length-prefixed byte tuples. */
export function governanceEventDigest(
  payload: Uint8Array, verifier: Uint8Array, context: Uint8Array
): string {
  const p = requireBytes(payload, MAX_GOVERNANCE_PAYLOAD, 'payload')
  const v = requireBytes(verifier, MAX_GOVERNANCE_VERIFIER, 'verifier')
  const c = requireBytes(context, MAX_GOVERNANCE_CONTEXT, 'context')
  if (v.byteLength === 0 || v[0] !== 0x00) {
    throw new RangeError('mutations require a nonempty GOVERNANCE verifier (0x00)')
  }
  const hash = createHash('sha256').update(DIGEST_DOMAIN)
  for (const field of [p, v, c]) {
    const length = Buffer.alloc(8)
    length.writeBigUInt64BE(BigInt(field.byteLength))
    hash.update(length).update(field)
  }
  return hash.digest('hex')
}

/**
 * Prepares transport messages but never transmits or grants authorization.
 * A caller-supplied positive number or self-declared decision object is NOT
 * proof of an E4 decision. This codec checks a PR #817 structural projection
 * and never produces an independently authenticated statistical verdict.
 *
 * Server code must use mutually distinct secrets for the issuer (/gate_signal)
 * and consumer (/event), and must enforce E4 provenance before invoking this.
 */
export function encodeAdmittedGovernanceMutation(
  source: AdmittedGovernanceMutation
): MutationTransportFrames {
  const decision = source?.decision
  if (!decision || typeof decision !== 'object') {
    throw new TypeError('E4 decision evidence is required')
  }
  if (typeof decision.proposal_id !== 'string' || !PROPOSAL_ID_RE.test(decision.proposal_id)) {
    throw new RangeError('E4 proposal_id is not canonical')
  }
  // Prevent a routine inference-pipeline verdict from being repackaged as
  // mutation authority. These are required registered-source attributes,
  // not independent proof that the untrusted caller truly owns the registry.
  if (typeof decision.component_id !== 'string' || !PROPOSAL_ID_RE.test(decision.component_id)) {
    throw new RangeError('E4 mutation component_id is not canonical')
  }
  if (source.capabilityClass !== 'SELF_MODIFYING') {
    throw new RangeError('E4 mutation requires a SELF_MODIFYING capacity declaration')
  }
  if (typeof source.operatorId !== 'string' || !PROPOSAL_ID_RE.test(source.operatorId)) {
    throw new RangeError('E4 mutation requires a registered operator identifier')
  }
  if (!Number.isSafeInteger(source.sequence) || source.sequence < 0) {
    throw new RangeError('sequence must be a nonnegative safe integer')
  }
  if (decision.accepted !== true) {
    throw new RangeError('only explicitly accepted E4 decisions can be encoded')
  }
  if (decision.method !== 'anytime_valid_bernstein') {
    throw new RangeError('unexpected E4 statistical method')
  }
  if (!Number.isSafeInteger(decision.sample_size) || decision.sample_size < 1) {
    throw new RangeError('E4 sample_size must be a positive integer')
  }
  if (!Number.isFinite(decision.lcb_value) || decision.lcb_value <= 0) {
    throw new RangeError('E4 decision requires finite positive LCB')
  }
  if (!Number.isFinite(decision.risk_spent) ||
      decision.risk_spent <= 0 || decision.risk_spent >= 1) {
    throw new RangeError('E4 risk_spent must be a finite per-round alpha in (0,1)')
  }
  if (!Number.isFinite(decision.e_value) ||
      decision.e_value < 1 / decision.risk_spent) {
    throw new RangeError('E4 e-process evidence has not crossed its alpha threshold')
  }
  const event_sha256 = governanceEventDigest(
    source.payload, source.verifier, source.context
  )
  return Object.freeze({
    gate_signal: Object.freeze({
      proposal_id: decision.proposal_id,
      component_id: decision.component_id,
      capability_class: 'SELF_MODIFYING' as const,
      operator_id: source.operatorId,
      sequence: source.sequence,
      accepted: true as const, lcb: decision.lcb_value,
      e_value: decision.e_value, risk_spent: decision.risk_spent,
      sample_size: decision.sample_size, method: 'anytime_valid_bernstein' as const,
      event_sha256,
    }),
    event: Object.freeze({
      proposal_id: decision.proposal_id,
      component_id: decision.component_id,
      capability_class: 'SELF_MODIFYING' as const,
      operator_id: source.operatorId,
      payload_hex: Buffer.from(source.payload).toString('hex'),
      verifier_hex: Buffer.from(source.verifier).toString('hex'),
      context_hex: Buffer.from(source.context).toString('hex'),
    }),
  })
}
