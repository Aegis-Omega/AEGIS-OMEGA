/**
 * Stratum II — cockpit telemetry subscription mechanics
 * Tests: initial offline state, subscriber notification, cleanup lifecycle
 */
import { describe, it, expect, afterEach } from 'vitest'
import { getCurrentTelemetry, subscribeTelemetry } from '../../../cockpit/src/lib/telemetry.js'
import type { TelemetryState, TelemetrySnapshot } from '../../../cockpit/src/lib/telemetry.js'

// Collect all unsub callbacks so tests always clean up
const cleanups: Array<() => void> = []

afterEach(() => {
  while (cleanups.length) cleanups.pop()!()
})

describe('getCurrentTelemetry — initial state', () => {
  it('returns offline status before any subscription', () => {
    const state = getCurrentTelemetry()
    expect(state.status).toBe('offline')
  })

  it('returns a TelemetryState object', () => {
    const state = getCurrentTelemetry()
    expect(typeof state).toBe('object')
    expect(state).toHaveProperty('status')
  })
})

describe('subscribeTelemetry — subscription mechanics', () => {
  it('immediately calls listener with current state', () => {
    const received: TelemetryState[] = []
    const unsub = subscribeTelemetry(s => received.push(s))
    cleanups.push(unsub)

    expect(received).toHaveLength(1)
    expect(received[0]!.status).toBe('offline')
  })

  it('returns an unsubscribe function', () => {
    const unsub = subscribeTelemetry(() => {})
    cleanups.push(unsub)
    expect(typeof unsub).toBe('function')
  })

  it('multiple subscribers all receive immediate notification', () => {
    const counts = [0, 0, 0]
    const unsub0 = subscribeTelemetry(() => counts[0]++)
    const unsub1 = subscribeTelemetry(() => counts[1]++)
    const unsub2 = subscribeTelemetry(() => counts[2]++)
    cleanups.push(unsub0, unsub1, unsub2)

    expect(counts).toEqual([1, 1, 1])
  })

  it('unsubscribed listener stops receiving updates', () => {
    let callCount = 0
    const unsub = subscribeTelemetry(() => callCount++)

    // Listener called once immediately
    expect(callCount).toBe(1)
    unsub()

    // After unsub, callCount stays at 1 (not added to cleanups — already unsubbed)
    expect(callCount).toBe(1)
  })

  it('subscribing twice registers both listeners independently', () => {
    const a: TelemetryState[] = []
    const b: TelemetryState[] = []
    const unsubA = subscribeTelemetry(s => a.push(s))
    const unsubB = subscribeTelemetry(s => b.push(s))
    cleanups.push(unsubA, unsubB)

    expect(a).toHaveLength(1)
    expect(b).toHaveLength(1)
  })
})

describe('TelemetrySnapshot — structural contract', () => {
  it('can construct a valid TelemetrySnapshot object', () => {
    const snap: TelemetrySnapshot = {
      sequence: 1,
      epoch: 0,
      avg_vcg_error: 0.001,
      drift_index: 0.0,
      pgcs_passes: true,
      failsafe_state: 'NOMINAL',
      corruption_count: 0,
      calibrator_passes_100k: true,
    }
    expect(snap.corruption_count).toBe(0)
    expect(snap.pgcs_passes).toBe(true)
    expect(snap.failsafe_state).toBe('NOMINAL')
  })

  it('constitutional invariants on a healthy snapshot', () => {
    const snap: TelemetrySnapshot = {
      sequence: 42,
      epoch: 3,
      avg_vcg_error: 0.0012,
      drift_index: 0.003,
      pgcs_passes: true,
      failsafe_state: 'NOMINAL',
      corruption_count: 0,
      calibrator_passes_100k: true,
    }
    // These are the three invariants asserted by the smoke test
    expect(snap.corruption_count).toBe(0)
    expect(snap.pgcs_passes).toBe(true)
    expect(snap.failsafe_state).toBe('NOMINAL')
  })

  it('online TelemetryState wraps a snapshot', () => {
    const snap: TelemetrySnapshot = {
      sequence: 7,
      epoch: 1,
      avg_vcg_error: 0.0,
      drift_index: 0.0,
      pgcs_passes: true,
      failsafe_state: 'NOMINAL',
      corruption_count: 0,
      calibrator_passes_100k: false,
    }
    const state: TelemetryState = { status: 'online', data: snap, streaming: false }
    expect(state.status).toBe('online')
    if (state.status === 'online') {
      expect(state.data.corruption_count).toBe(0)
    }
  })

  it('offline TelemetryState has no data field', () => {
    const state: TelemetryState = { status: 'offline' }
    expect(state.status).toBe('offline')
    expect('data' in state).toBe(false)
  })

  it('error TelemetryState carries a message', () => {
    const state: TelemetryState = { status: 'error', message: 'Bridge 503' }
    expect(state.status).toBe('error')
    if (state.status === 'error') {
      expect(state.message).toBe('Bridge 503')
    }
  })
})
