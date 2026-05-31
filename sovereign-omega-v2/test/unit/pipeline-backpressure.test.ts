// ============================================================
// SOVEREIGN OMEGA — Pipeline Backpressure Controller tests
// EPISTEMIC TIER: T0
//
// Tests for pipeline/backpressure.ts:
//   BackpressureController — enqueue, dequeue, getBackpressureState,
//   HIGH/LOW watermark thresholds, hysteresis, event callbacks
// ============================================================

import { describe, it, expect, vi } from 'vitest'
import {
  BackpressureController,
  HIGH_WATER_MARK,
  LOW_WATER_MARK,
} from '../../src/pipeline/backpressure.js'
import { EventType as ET } from '../../src/core/types.js'

// ── Constants ─────────────────────────────────────────────

describe('BackpressureController constants', () => {
  it('HIGH_WATER_MARK is 1000', () => {
    expect(HIGH_WATER_MARK).toBe(1000)
  })

  it('LOW_WATER_MARK is 100', () => {
    expect(LOW_WATER_MARK).toBe(100)
  })
})

// ── Initial state ─────────────────────────────────────────

describe('BackpressureController initial state', () => {
  it('starts with engaged=false and queueDepth=0', () => {
    const ctrl = new BackpressureController(vi.fn())
    const state = ctrl.getBackpressureState()
    expect(state.engaged).toBe(false)
    expect(state.queueDepth).toBe(0)
  })

  it('getBackpressureState returns a frozen object', () => {
    const ctrl = new BackpressureController(vi.fn())
    expect(Object.isFrozen(ctrl.getBackpressureState())).toBe(true)
  })
})

// ── enqueue ───────────────────────────────────────────────

describe('BackpressureController.enqueue', () => {
  it('increases queueDepth by the enqueued count', () => {
    const ctrl = new BackpressureController(vi.fn())
    ctrl.enqueue(10)
    expect(ctrl.getBackpressureState().queueDepth).toBe(10)
  })

  it('defaults count to 1 when called without argument', () => {
    const ctrl = new BackpressureController(vi.fn())
    ctrl.enqueue()
    expect(ctrl.getBackpressureState().queueDepth).toBe(1)
  })

  it('does not emit event when depth stays below HIGH_WATER_MARK', () => {
    const onEvent = vi.fn()
    const ctrl = new BackpressureController(onEvent)
    ctrl.enqueue(HIGH_WATER_MARK - 1)
    expect(onEvent).not.toHaveBeenCalled()
  })

  it('emits BACKPRESSURE_ENGAGED when depth reaches HIGH_WATER_MARK', () => {
    const onEvent = vi.fn()
    const ctrl = new BackpressureController(onEvent)
    ctrl.enqueue(HIGH_WATER_MARK)
    expect(onEvent).toHaveBeenCalledOnce()
    expect(onEvent).toHaveBeenCalledWith(ET.BACKPRESSURE_ENGAGED)
    expect(ctrl.getBackpressureState().engaged).toBe(true)
  })

  it('emits BACKPRESSURE_ENGAGED exactly once even when depth exceeds HIGH_WATER_MARK', () => {
    const onEvent = vi.fn()
    const ctrl = new BackpressureController(onEvent)
    ctrl.enqueue(HIGH_WATER_MARK)
    ctrl.enqueue(500)  // already engaged
    expect(onEvent).toHaveBeenCalledOnce()
  })
})

// ── dequeue ───────────────────────────────────────────────

describe('BackpressureController.dequeue', () => {
  it('decreases queueDepth by the dequeued count', () => {
    const ctrl = new BackpressureController(vi.fn())
    ctrl.enqueue(200)
    ctrl.dequeue(50)
    expect(ctrl.getBackpressureState().queueDepth).toBe(150)
  })

  it('defaults count to 1 when called without argument', () => {
    const ctrl = new BackpressureController(vi.fn())
    ctrl.enqueue(5)
    ctrl.dequeue()
    expect(ctrl.getBackpressureState().queueDepth).toBe(4)
  })

  it('does not go below 0 (clamped at 0)', () => {
    const ctrl = new BackpressureController(vi.fn())
    ctrl.enqueue(5)
    ctrl.dequeue(100)
    expect(ctrl.getBackpressureState().queueDepth).toBe(0)
  })

  it('emits BACKPRESSURE_RELEASED when depth drops below LOW_WATER_MARK after engagement', () => {
    const onEvent = vi.fn()
    const ctrl = new BackpressureController(onEvent)
    ctrl.enqueue(HIGH_WATER_MARK)           // engage
    ctrl.dequeue(HIGH_WATER_MARK - LOW_WATER_MARK + 1)  // drop below LOW_WATER_MARK
    expect(onEvent).toHaveBeenCalledTimes(2)
    expect(onEvent).toHaveBeenNthCalledWith(2, ET.BACKPRESSURE_RELEASED)
    expect(ctrl.getBackpressureState().engaged).toBe(false)
  })

  it('does not emit BACKPRESSURE_RELEASED when not engaged', () => {
    const onEvent = vi.fn()
    const ctrl = new BackpressureController(onEvent)
    ctrl.enqueue(50)
    ctrl.dequeue(50)
    expect(onEvent).not.toHaveBeenCalled()
  })

  it('does not emit BACKPRESSURE_RELEASED when engaged but depth stays at LOW_WATER_MARK', () => {
    const onEvent = vi.fn()
    const ctrl = new BackpressureController(onEvent)
    ctrl.enqueue(HIGH_WATER_MARK)
    // Dequeue to exactly LOW_WATER_MARK — condition is < LOW_WATER_MARK so no release
    ctrl.dequeue(HIGH_WATER_MARK - LOW_WATER_MARK)
    expect(ctrl.getBackpressureState().queueDepth).toBe(LOW_WATER_MARK)
    expect(onEvent).toHaveBeenCalledOnce()  // only ENGAGED, not RELEASED
  })
})

// ── Hysteresis ────────────────────────────────────────────

describe('BackpressureController hysteresis', () => {
  it('re-engages after being released when depth climbs back above HIGH_WATER_MARK', () => {
    const onEvent = vi.fn()
    const ctrl = new BackpressureController(onEvent)
    ctrl.enqueue(HIGH_WATER_MARK)           // engage
    ctrl.dequeue(HIGH_WATER_MARK)           // release (depth=0, below LOW_WATER_MARK)
    ctrl.enqueue(HIGH_WATER_MARK)           // engage again
    expect(onEvent).toHaveBeenCalledTimes(3)
    expect(onEvent).toHaveBeenNthCalledWith(1, ET.BACKPRESSURE_ENGAGED)
    expect(onEvent).toHaveBeenNthCalledWith(2, ET.BACKPRESSURE_RELEASED)
    expect(onEvent).toHaveBeenNthCalledWith(3, ET.BACKPRESSURE_ENGAGED)
  })
})
