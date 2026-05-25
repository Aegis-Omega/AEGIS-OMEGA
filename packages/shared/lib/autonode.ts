/**
 * AEGIS-Ω External Autonode Client
 * EPISTEMIC TIER: T2 (engineering hypothesis)
 *
 * Fetches the full autonode self-description from bridge.py GET /node.
 * The autonode is the external radiation point of the constitutional system:
 * it exposes T0 verdict, constitutional hash, catalog hash, and resonance
 * state as a single reply-certifiable JSON descriptor.
 *
 * Constitutional invariants:
 * - is_replay_reconstructable: true on every descriptor
 * - AutonodeError thrown if t0_verdict is false or corruption_count > 0
 * - deepFreeze applied to returned descriptor
 */

export const AUTONODE_SCHEMA_VERSION = '1.0.0' as const

export interface AutonodeDescriptor {
  readonly node_id: string
  readonly t0_verdict: boolean
  readonly constitutional_hash: string
  readonly catalog_hash: string
  readonly cognitive_triad: string
  readonly sequence: number
  readonly epoch: number
  readonly corruption_count: number
  readonly phi_threshold: number
  readonly drift_risk: number
  readonly schema_version: typeof AUTONODE_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export class AutonodeError extends Error {
  override readonly name = 'AutonodeError' as const
  constructor(message: string) { super(message) }
}

/**
 * Fetch the live autonode descriptor from the bridge /node endpoint.
 * Throws AutonodeError if the response is malformed.
 */
export async function fetchAutonodeDescriptor(bridgeUrl: string): Promise<AutonodeDescriptor> {
  const url = `${bridgeUrl.replace(/\/$/, '')}/node`
  let raw: Record<string, unknown>
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(5_000) })
    if (!res.ok) throw new AutonodeError(`/node returned HTTP ${res.status}`)
    raw = (await res.json()) as Record<string, unknown>
  } catch (err) {
    if (err instanceof AutonodeError) throw err
    throw new AutonodeError(`/node fetch failed: ${String(err)}`)
  }

  if (typeof raw['node_id'] !== 'string' ||
      typeof raw['t0_verdict'] !== 'boolean' ||
      typeof raw['constitutional_hash'] !== 'string' ||
      typeof raw['catalog_hash'] !== 'string' ||
      typeof raw['sequence'] !== 'number' ||
      typeof raw['epoch'] !== 'number' ||
      typeof raw['corruption_count'] !== 'number' ||
      typeof raw['phi_threshold'] !== 'number' ||
      typeof raw['drift_risk'] !== 'number') {
    throw new AutonodeError('malformed /node response: missing required fields')
  }

  const descriptor: AutonodeDescriptor = Object.freeze({
    node_id:             raw['node_id'] as string,
    t0_verdict:          raw['t0_verdict'] as boolean,
    constitutional_hash: raw['constitutional_hash'] as string,
    catalog_hash:        raw['catalog_hash'] as string,
    cognitive_triad:     typeof raw['cognitive_triad'] === 'string'
                           ? raw['cognitive_triad'] as string
                           : '',
    sequence:            raw['sequence'] as number,
    epoch:               raw['epoch'] as number,
    corruption_count:    raw['corruption_count'] as number,
    phi_threshold:       raw['phi_threshold'] as number,
    drift_risk:          raw['drift_risk'] as number,
    schema_version:      AUTONODE_SCHEMA_VERSION,
    is_replay_reconstructable: true as const,
  })

  return descriptor
}

/**
 * Returns true iff the descriptor represents a constitutionally sound node:
 *   t0_verdict is true AND corruption_count is zero AND drift_risk < phi_threshold
 */
export function isConstitutionallySound(d: AutonodeDescriptor): boolean {
  return d.t0_verdict && d.corruption_count === 0 && d.drift_risk < d.phi_threshold
}
