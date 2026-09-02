import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const cognitiveWorkflowPath = resolve(process.cwd(), '..', '.github', 'workflows', 'cognitive-manifest-refresh.yml')
const contractWorkflowPath = resolve(process.cwd(), '..', '.github', 'workflows', 'polyglot-metacognition.yml')
const liveWorkflowPath = resolve(process.cwd(), '..', '.github', 'workflows', 'polyglot-cudaq-live.yml')
const cognitiveWorkflow = readFileSync(cognitiveWorkflowPath, 'utf8')
const contractWorkflow = readFileSync(contractWorkflowPath, 'utf8')
const liveWorkflow = readFileSync(liveWorkflowPath, 'utf8')

describe('cognitive manifest PR provenance boundary', () => {
  it('is read-only and cannot advance a candidate branch head', () => {
    expect(cognitiveWorkflow).toContain('permissions:\n  contents: read')
    expect(cognitiveWorkflow).not.toContain('contents: write')
    expect(cognitiveWorkflow).not.toContain('git commit -m "chore(manifest): refresh cognitive-state anchors"')
    expect(cognitiveWorkflow).not.toContain('git push origin')
  })

  it('checks out the triggering SHA without retaining write credentials', () => {
    expect(cognitiveWorkflow).toContain('ref: ${{ github.sha }}')
    expect(cognitiveWorkflow).toContain('persist-credentials: false')
  })

  it('emits deterministic expected anchors as evidence instead of mutating the branch', () => {
    expect(cognitiveWorkflow).toContain('--output-dir "$RUNNER_TEMP/cognitive-anchors"')
    expect(cognitiveWorkflow).toContain('actions/upload-artifact@v4')
    expect(cognitiveWorkflow).toContain('name: aegis-cognitive-anchor-preview-${{ github.sha }}')
  })

  it('keeps provenance, contract, and live receipt workflows exact-head coupled', () => {
    expect(contractWorkflow).toContain("- '.github/workflows/cognitive-manifest-refresh.yml'")
    expect(contractWorkflow).toContain("- '.github/workflows/polyglot-cudaq-live.yml'")
    expect(liveWorkflow).toContain("- '.github/workflows/polyglot-metacognition.yml'")
  })
})
