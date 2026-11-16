/**
 * Untrusted browser observations, deliberately separate from E3/E4 events.
 *
 * Data in this counter cannot authorize mutations, train calibration gates
 * or promote evidence. Process-local aggregate only, lost on restart.
 */
export interface BrowserObservation {
  readonly type: 'RESPONSE_GENERATED'
  readonly content_length: number
}

export interface ObservationSnapshot {
  readonly trust_class: 'UNVERIFIED_BROWSER_OBSERVATION'
  readonly durability: 'PROCESS_LOCAL'
  readonly response_generated_count: number
  readonly reported_characters: number
}

const MAX_CONTENT_LENGTH = 1_000_000

export function parseBrowserObservation(value: unknown): BrowserObservation | null {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return null
  const record = value as Record<string, unknown>
  const keys = Object.keys(record)
  if (keys.length !== 2 || !keys.includes('type') || !keys.includes('content_length')) return null
  if (record.type !== 'RESPONSE_GENERATED') return null
  if (
    typeof record.content_length !== 'number' ||
    !Number.isSafeInteger(record.content_length) ||
    record.content_length < 0 ||
    record.content_length > MAX_CONTENT_LENGTH
  ) return null
  return Object.freeze({
    type: 'RESPONSE_GENERATED',
    content_length: record.content_length,
  })
}

/** Do not interpret these unauthenticated reports as a trusted event log. */
export class BrowserObservationCounter {
  private count = 0
  private characters = 0

  record(value: unknown): boolean {
    const parsed = parseBrowserObservation(value)
    if (!parsed) return false
    // Saturate counters to prevent unsafe JS integer rollover.
    this.count = Math.min(Number.MAX_SAFE_INTEGER, this.count + 1)
    this.characters = Math.min(Number.MAX_SAFE_INTEGER, this.characters + parsed.content_length)
    return true
  }

  snapshot(): ObservationSnapshot {
    return Object.freeze({
      trust_class: 'UNVERIFIED_BROWSER_OBSERVATION',
      durability: 'PROCESS_LOCAL',
      response_generated_count: this.count,
      reported_characters: this.characters,
    })
  }
}
