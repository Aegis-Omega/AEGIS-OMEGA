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

export interface AdmittedGovernanceMutation {
  readonly proposalId: string
  readonly sequence: number
  readonly lcb: number
  readonly payload: Uint8Array
  readonly verifier: Uint8Array
  readonly context: Uint8Array
}

export interface MutationTransportFrames {
  readonly gate_signal: Readonly<{
    proposal_id: string
    sequence: number
    accepted: true
    lcb: number
    event_sha256: string
  }>
  readonly event: Readonly<{
    proposal_id: string
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
 * A caller-supplied positive number is NOT proof of an E4 decision.
 *
 * Server code must use mutually distinct secrets for the issuer (/gate_signal)
 * and consumer (/event), and must enforce E4 provenance before invoking this.
 */
export function encodeAdmittedGovernanceMutation(
  source: AdmittedGovernanceMutation
): MutationTransportFrames {
  if (typeof source.proposalId !== 'string' || !PROPOSAL_ID_RE.test(source.proposalId)) {
    throw new RangeError('proposalId is not a canonical proposal identifier')
  }
  if (!Number.isSafeInteger(source.sequence) || source.sequence < 0) {
    throw new RangeError('sequence must be a nonnegative safe integer')
  }
  if (!Number.isFinite(source.lcb) || source.lcb <= 0) {
    throw new RangeError('only a finite strictly positive E4 LCB may be encoded')
  }
  const event_sha256 = governanceEventDigest(
    source.payload, source.verifier, source.context
  )
  return Object.freeze({
    gate_signal: Object.freeze({
      proposal_id: source.proposalId, sequence: source.sequence,
      accepted: true as const, lcb: source.lcb, event_sha256,
    }),
    event: Object.freeze({
      proposal_id: source.proposalId,
      payload_hex: Buffer.from(source.payload).toString('hex'),
      verifier_hex: Buffer.from(source.verifier).toString('hex'),
      context_hex: Buffer.from(source.context).toString('hex'),
    }),
  })
}
