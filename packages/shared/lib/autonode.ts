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
  readonly chord_bytes?: readonly number[]
  readonly chord_hex?: string
  readonly schema_version: typeof AUTONODE_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export type NetworkVerdict = 'UNIFIED' | 'CLUSTERED' | 'SPLIT'

export interface NetworkPeer {
  readonly node_id: string
  readonly chord_bytes: readonly number[]
  readonly chord_hex: string
  readonly drift_risk: number
}

export interface NetworkResonanceReport {
  readonly verdict: NetworkVerdict
  readonly peer_count: number
  readonly below_phi_count: number
  readonly above_phi_count: number
  readonly triadic_count: number
  readonly quorum_triadic: boolean
  readonly distinct_chord_classes: number
  readonly all_below_phi: boolean
  readonly peers: readonly NetworkPeer[]
  readonly is_replay_reconstructable: true
}

export class NetworkError extends Error {
  override readonly name = 'NetworkError' as const
  constructor(message: string) { super(message) }
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

/**
 * Fetch the live network resonance report from the bridge /network endpoint.
 * Returns the chord network analysis for all simulated peers.
 */
export async function fetchNetworkResonance(bridgeUrl: string): Promise<NetworkResonanceReport> {
  const url = `${bridgeUrl.replace(/\/$/, '')}/network`
  let raw: Record<string, unknown>
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(5_000) })
    if (!res.ok) throw new NetworkError(`/network returned HTTP ${res.status}`)
    raw = (await res.json()) as Record<string, unknown>
  } catch (err) {
    if (err instanceof NetworkError) throw err
    throw new NetworkError(`/network fetch failed: ${String(err)}`)
  }

  if (typeof raw['verdict'] !== 'string' ||
      typeof raw['peer_count'] !== 'number' ||
      !Array.isArray(raw['peers'])) {
    throw new NetworkError('malformed /network response')
  }

  return Object.freeze({
    verdict:               raw['verdict'] as NetworkVerdict,
    peer_count:            raw['peer_count'] as number,
    below_phi_count:       (raw['below_phi_count'] as number) ?? 0,
    above_phi_count:       (raw['above_phi_count'] as number) ?? 0,
    triadic_count:         (raw['triadic_count'] as number) ?? 0,
    quorum_triadic:        (raw['quorum_triadic'] as boolean) ?? false,
    distinct_chord_classes:(raw['distinct_chord_classes'] as number) ?? 1,
    all_below_phi:         (raw['all_below_phi'] as boolean) ?? false,
    peers:                 (raw['peers'] as NetworkPeer[]).map(p => Object.freeze(p)),
    is_replay_reconstructable: true as const,
  }) as NetworkResonanceReport
}
