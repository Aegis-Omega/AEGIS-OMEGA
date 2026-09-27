/**
 * Repo API transport drift guard.
 * EPISTEMIC TIER: T1 source-bound regression.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const ROOT = fileURLToPath(new URL('../../../', import.meta.url))

function read(relativePath: string): string {
  return readFileSync(join(ROOT, relativePath), 'utf8')
}

describe('Supabase Edge outbound transport census', () => {
  it('routes every Edge Function outbound fetch through _shared/http.ts', () => {
    const functionsRoot = join(ROOT, 'supabase/functions')
    const offenders: string[] = []

    for (const entry of readdirSync(functionsRoot)) {
      const dir = join(functionsRoot, entry)
      if (!statSync(dir).isDirectory() || entry === '_shared') continue

      const indexPath = join(dir, 'index.ts')
      try {
        const source = readFileSync(indexPath, 'utf8')
        if (/\bfetch\s*\(/.test(source)) offenders.push(entry)
      } catch {
        // Functions without index.ts are outside this contract.
      }
    }

    expect(offenders).toEqual([])
  })

  it('keeps the raw fetch primitive isolated to the shared transport helper', () => {
    const source = read('supabase/functions/_shared/http.ts')
    expect(source).toContain('return await fetch(input, { ...init, signal: controller.signal })')
    expect(source).toContain('const timer = setTimeout(() => controller.abort(), boundedTimeoutMs)')
    expect(source).toContain("callerSignal.addEventListener('abort', onCallerAbort, { once: true })")
  })
})

describe('inference routing regression guards', () => {
  it('does not implicitly enable CL-Ψ with an unconditional branch', () => {
    const source = read('packages/shared/lib/inference-router.ts')
    expect(source).not.toContain('VITE_BRIDGE_URL || true')
    expect(source).toContain("import.meta.env.VITE_ENABLE_CL_PSI === 'true'")
  })

  it('skips backend functions absent from configuredBackends()', () => {
    const source = read('packages/shared/lib/inference-router.ts')
    expect(source).toContain('if (!configured.has(backend)) continue')
  })
})

describe('non-idempotent retry guard', () => {
  it('keeps Google Sheets POST calls single-attempt unless an idempotency contract is added', () => {
    const source = read('clients/sheets/Code.gs')
    expect(source).toContain("const retryable = normalizedMethod === 'get'")
    expect(source).toContain('const maxAttempts = retryable ? 3 : 1')
  })
})
