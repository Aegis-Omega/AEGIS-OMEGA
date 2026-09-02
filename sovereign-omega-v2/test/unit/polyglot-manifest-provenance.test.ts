import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const workflowPath = resolve(process.cwd(), '..', '.github', 'workflows', 'cognitive-manifest-refresh.yml')
const workflow = readFileSync(workflowPath, 'utf8')

describe('cognitive manifest PR provenance boundary', () => {
  it('is read-only and cannot advance a candidate branch head', () => {
    expect(workflow).toContain('permissions:\n  contents: read')
    expect(workflow).not.toContain('contents: write')
    expect(workflow).not.toContain('git commit -m "chore(manifest): refresh cognitive-state anchors"')
    expect(workflow).not.toContain('git push origin')
  })

  it('checks out the triggering SHA without retaining write credentials', () => {
    expect(workflow).toContain('ref: ${{ github.sha }}')
    expect(workflow).toContain('persist-credentials: false')
  })

  it('emits deterministic expected anchors as evidence instead of mutating the branch', () => {
    expect(workflow).toContain('--output-dir "$RUNNER_TEMP/cognitive-anchors"')
    expect(workflow).toContain('actions/upload-artifact@v4')
    expect(workflow).toContain('name: aegis-cognitive-anchor-preview-${{ github.sha }}')
  })
})
