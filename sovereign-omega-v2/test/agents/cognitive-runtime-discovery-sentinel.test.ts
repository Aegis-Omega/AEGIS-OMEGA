import { describe, it } from 'vitest'

describe('Cycle 3 test discovery sentinel', () => {
  it('ENFORCE_RED_DISCOVERY_SENTINEL', () => {
    throw new Error('ENFORCE_RED_DISCOVERY_SENTINEL')
  })
})
