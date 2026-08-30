// Projection-only types — no constitutional authority

export type DivergenceClass = 'D0' | 'D1' | 'D2' | 'D3' | 'D4'
export type DeterminismClass = 'strict' | 'bounded' | 'observational'
export type SITRState = 'STABLE' | 'DRIFTING' | 'DIVERGENT' | 'FROZEN'
export type AOIEState = 'SECURE' | 'DEGRADED' | 'CRITICAL'

export interface TelemetrySnapshot {
  pgcs_passes: boolean
  vcg_error: number
  drift_index: number
  corruption_count: number
  epoch_sequence: number
  gate_acceptance_rate: number
  failsafe_state: string
  timestamp_ms: number
}

export interface ReplayEvent {
  sequence: number
  kind: string
  hash: string
  is_replay_reconstructable: boolean
}

export interface TopologyState {
  topology_hash: string
  sitr_state: SITRState
  aoie_global_state: AOIEState
  constitutional_verdict: string
  sequence: number
}

export interface EpochLink {
  sequence: number
  epoch_hash: string
  is_valid: boolean
}

export interface LineageEntry {
  sequence: number
  entry_hash: string
  previous_entry_hash: string
  kind: string
}
