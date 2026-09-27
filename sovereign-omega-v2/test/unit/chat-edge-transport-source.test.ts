/**
 * Supabase chat edge transport source contract.
 * EPISTEMIC TIER: T1 source-bound regression.
 *
 * The Edge Function itself runs under Deno, while the repository's broad unit
 * suite is Vitest/Node. These checks pin the transport controls without
 * pretending to be an executed Deno integration test.
 */
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const CHAT_SOURCE_URL = new URL('../../../supabase/functions/chat/index.ts', import.meta.url)
const source = readFileSync(CHAT_SOURCE_URL, 'utf8')

describe('chat edge transport source contract', () => {
  it('puts every provider fetch behind the common upstream timeout', () => {
    expect(source).toContain("const CHAT_UPSTREAM_TIMEOUT_MS = readPositiveIntEnv('CHAT_UPSTREAM_TIMEOUT_MS', 60_000)")
    expect(source).toContain('signal: AbortSignal.timeout(CHAT_UPSTREAM_TIMEOUT_MS)')
  })

  it('bounds provider error bodies before logging them', () => {
    expect(source).toContain("import { fetchWithTimeout, readTextBounded } from '../_shared/http.ts'")
    expect(source).toContain('const err = await readTextBounded(resp)')
  })

  it('keeps paid provider gates server-side', () => {
    expect(source).toContain("const CHAT_ENABLE_OPENAI = Deno.env.get('CHAT_ENABLE_OPENAI') === 'true'")
    expect(source).toContain("const CHAT_ENABLE_NEBIUS = Deno.env.get('CHAT_ENABLE_NEBIUS') === 'true'")
    expect(source).toContain("const CHAT_ENABLE_AZURE  = Deno.env.get('CHAT_ENABLE_AZURE') === 'true'")
  })

  it('does not introduce an automatic POST retry loop', () => {
    expect(source).toContain('no automatic retry for POST inference')
    expect(source).not.toMatch(/for\s*\([^)]*attempt[^)]*\)/i)
  })
})
