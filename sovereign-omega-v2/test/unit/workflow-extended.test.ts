// ============================================================
// Workflow Engine Extended Tests — agents/workflows/workflow-engine.ts
// Targets uncovered branches:
//   replayIntegrity when some frames have invariant_satisfied=false
//   getExecution returning undefined (not found)
//   completeWorkflow / abortWorkflow on non-matching workflow_id
// ============================================================

import { describe, it, expect } from 'vitest'
import { WorkflowEngine } from '../../src/agents/workflows/workflow-engine.js'
import type { WorkflowReplayFrame } from '../../src/agents/workflows/types.js'
import type { SHA256Hex } from '../../src/core/types.js'

const H = (c: string) => c.padStart(64, '0') as SHA256Hex

function makeFrame(id: string, satisfied: boolean): WorkflowReplayFrame {
  return {
    frame_id: id,
    workflow_id: 'wf-test',
    sequence: parseInt(id.replace(/\D/g, ''), 10) || 1,
    step_type: 'gather',
    input_hash: H('a'),
    output_hash: H('b'),
    invariant_satisfied: satisfied,
  }
}

// ─── replayIntegrity: mixed satisfied/unsatisfied ─────────

describe('WorkflowEngine.replayIntegrity: partial satisfaction', () => {
  it('returns 0.5 when half the frames are satisfied', () => {
    const { engine: e1 } = WorkflowEngine.empty().startWorkflow({
      workflow_id: 'wf-test',
      workflow_type: 'research',
      agent_id: 'a1',
      sequence: 1,
    })
    const e2 = e1
      .recordFrame('wf-test', makeFrame('1', true))
      .recordFrame('wf-test', makeFrame('2', false))
    expect(e2.replayIntegrity()).toBe(0.5)
  })

  it('returns 0 when no frames are satisfied', () => {
    const { engine: e1 } = WorkflowEngine.empty().startWorkflow({
      workflow_id: 'wf-test',
      workflow_type: 'research',
      agent_id: 'a1',
      sequence: 1,
    })
    const e2 = e1
      .recordFrame('wf-test', makeFrame('1', false))
      .recordFrame('wf-test', makeFrame('2', false))
    expect(e2.replayIntegrity()).toBe(0)
  })

  it('returns 1 when all frames are satisfied', () => {
    const { engine: e1 } = WorkflowEngine.empty().startWorkflow({
      workflow_id: 'wf-test',
      workflow_type: 'research',
      agent_id: 'a1',
      sequence: 1,
    })
    const e2 = e1.recordFrame('wf-test', makeFrame('1', true))
    expect(e2.replayIntegrity()).toBe(1)
  })
})

// ─── getExecution: not found → undefined ──────────────────

describe('WorkflowEngine.getExecution: not found', () => {
  it('returns undefined for unregistered workflow_id', () => {
    expect(WorkflowEngine.empty().getExecution('wf-ghost')).toBeUndefined()
  })

  it('returns undefined after different workflow is started', () => {
    const { engine } = WorkflowEngine.empty().startWorkflow({
      workflow_id: 'wf-other',
      workflow_type: 'research',
      agent_id: 'a1',
      sequence: 1,
    })
    expect(engine.getExecution('wf-ghost')).toBeUndefined()
  })
})

// ─── completeWorkflow / abortWorkflow: non-matching id ───

describe('WorkflowEngine: complete/abort with non-matching id', () => {
  it('completeWorkflow on non-existent id — no-op, other workflows unchanged', () => {
    const { engine: e1 } = WorkflowEngine.empty().startWorkflow({
      workflow_id: 'wf-real',
      workflow_type: 'research',
      agent_id: 'a1',
      sequence: 1,
    })
    const e2 = e1.completeWorkflow('wf-other', 5)
    // 'wf-real' still active
    expect(e2.getExecution('wf-real')?.status).toBe('active')
  })

  it('abortWorkflow on non-existent id — no-op, other workflows unchanged', () => {
    const { engine: e1 } = WorkflowEngine.empty().startWorkflow({
      workflow_id: 'wf-real',
      workflow_type: 'refactor',
      agent_id: 'a1',
      sequence: 1,
    })
    const e2 = e1.abortWorkflow('wf-other', 5)
    expect(e2.getExecution('wf-real')?.status).toBe('active')
  })
})
