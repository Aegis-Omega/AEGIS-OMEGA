// ============================================================
// SOVEREIGN OMEGA — Pipeline Backpressure Controller
// EPISTEMIC TIER: T0 (flow control, no calibration semantics)
// HIGH_WATER_MARK: queue depth at which backpressure engages.
// LOW_WATER_MARK:  queue depth at which backpressure releases.
// Hysteresis gap prevents oscillation at the boundary.
// ============================================================

import { EventType as ET } from '../core/types.js'

export const HIGH_WATER_MARK = 1000
export const LOW_WATER_MARK = 100

export type BackpressureEvent = ET.BACKPRESSURE_ENGAGED | ET.BACKPRESSURE_RELEASED

export interface BackpressureState {
  readonly engaged: boolean
  readonly queueDepth: number
}

/**
 * Pipeline backpressure controller.
 * Tracks queue depth and emits state-change events when the depth
 * crosses the HIGH_WATER_MARK (engage) or LOW_WATER_MARK (release).
 *
 * Event callbacks receive the event type — callers decide how to
 * route the event into the event substrate. No Date.now() here:
 * timestamp_ms must come from the event substrate.
 */
export class BackpressureController {
  private queueDepth = 0
  private engaged = false
  private readonly onEvent: (event: BackpressureEvent) => void

  constructor(onEvent: (event: BackpressureEvent) => void) {
    this.onEvent = onEvent
  }

  /**
   * Record that `count` items have been enqueued.
   * Emits BACKPRESSURE_ENGAGED if depth crosses HIGH_WATER_MARK.
   */
  enqueue(count = 1): void {
    this.queueDepth += count
    if (!this.engaged && this.queueDepth >= HIGH_WATER_MARK) {
      this.engaged = true
      this.onEvent(ET.BACKPRESSURE_ENGAGED)
    }
  }

  /**
   * Record that `count` items have been dequeued.
   * Emits BACKPRESSURE_RELEASED if depth drops below LOW_WATER_MARK.
   */
  dequeue(count = 1): void {
    this.queueDepth = Math.max(0, this.queueDepth - count)
    if (this.engaged && this.queueDepth < LOW_WATER_MARK) {
      this.engaged = false
      this.onEvent(ET.BACKPRESSURE_RELEASED)
    }
  }

  /**
   * Returns a frozen snapshot of the current backpressure state.
   * Safe to call at any time; no side effects.
   */
  getBackpressureState(): BackpressureState {
    return Object.freeze({ engaged: this.engaged, queueDepth: this.queueDepth })
  }
}
