// ============================================================
// SHP Extended Tests — shp/types.ts
// Targets uncovered branch:
//   phaseOrdinal: unknown phase → RangeError throw path
// ============================================================

import { describe, it, expect } from 'vitest'
import { phaseOrdinal } from '../../src/shp/types.js'
import type { Phase } from '../../src/shp/types.js'

describe('phaseOrdinal: unknown phase throws RangeError', () => {
  it('throws RangeError for an unrecognised phase string', () => {
    expect(() => phaseOrdinal('UNKNOWN' as Phase)).toThrow(RangeError)
  })

  it('throws RangeError for empty string phase', () => {
    expect(() => phaseOrdinal('' as Phase)).toThrow(RangeError)
  })

  it('RangeError message names the bad phase', () => {
    expect(() => phaseOrdinal('INVALID_PHASE' as Phase)).toThrow('Unknown phase')
  })
})
