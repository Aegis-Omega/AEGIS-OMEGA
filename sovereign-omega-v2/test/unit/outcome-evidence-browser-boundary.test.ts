import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { build } from 'vite'

interface GeneratedOutput {
  readonly output: ReadonlyArray<{
    readonly type: string
    readonly code?: string
  }>
}

describe('outcome evidence browser boundary', () => {
  it('bundles the IndexedDB adapter without Node-only crypto shims', async () => {
    const result = await build({
      configFile: false,
      logLevel: 'silent',
      build: {
        write: false,
        target: 'es2022',
        minify: false,
        lib: {
          entry: resolve('src/metacognition/outcome-evidence-artifact-store.ts'),
          formats: ['es'],
        },
      },
    })
    const outputs = (Array.isArray(result) ? result : [result]) as GeneratedOutput[]
    const code = outputs
      .flatMap(output => output.output)
      .filter(item => item.type === 'chunk')
      .map(item => item.code ?? '')
      .join('\n')

    expect(code).toContain('IndexedDBOutcomeEvidenceArtifactStore')
    expect(code).not.toContain('node:crypto')
    expect(code).not.toContain('__vite-browser-external')
  }, 30_000)
})
