// ============================================================
// Workflow Engine — replay-safe workflow execution tracking
// EPISTEMIC TIER: T1
// All workflows emit replay frames. Append-only mutation.
// ============================================================

import { deepFreeze } from '../../core/immutable'
import type { WorkflowExecution } from '../types'
import { AgentCoordinationError } from '../types'
import type { WorkflowReplayFrame } from './types'
import { BUILT_IN_WORKFLOWS } from './types'

export class WorkflowEngine {
  private readonly _executions: readonly WorkflowExecution[]
  private readonly _frames: readonly WorkflowReplayFrame[]

  private constructor(
    executions: readonly WorkflowExecution[],
    frames: readonly WorkflowReplayFrame[]
  ) {
    this._executions = executions
    this._frames = frames
  }

  static empty(): WorkflowEngine {
    return new WorkflowEngine(deepFreeze([]), deepFreeze([]))
  }

  get executions(): readonly WorkflowExecution[] { return this._executions }
  get frames(): readonly WorkflowReplayFrame[] { return this._frames }

  startWorkflow(params: {
    workflow_id: string
    workflow_type: WorkflowExecution['workflow_type']
    agent_id: string
    sequence: number
  }): { engine: WorkflowEngine; execution: WorkflowExecution } {
    const definition = BUILT_IN_WORKFLOWS.find(w => w.workflow_type === params.workflow_type)
    if (!definition) {
      throw new AgentCoordinationError(
        `Unknown workflow type: ${params.workflow_type}`
      )
    }
    const execution: WorkflowExecution = deepFreeze({
      workflow_id: params.workflow_id,
      workflow_type: params.workflow_type,
      agent_id: params.agent_id,
      started_at_sequence: params.sequence,
      replay_frame_count: 0,
      status: 'active' as const,
    })
    return {
      engine: new WorkflowEngine(
        deepFreeze([...this._executions, execution]),
        this._frames
      ),
      execution,
    }
  }

  recordFrame(workflow_id: string, frame: WorkflowReplayFrame): WorkflowEngine {
    const nextFrames = deepFreeze([...this._frames, deepFreeze(frame)])
    const nextExecutions = this._executions.map(e =>
      e.workflow_id === workflow_id
        ? deepFreeze({ ...e, replay_frame_count: e.replay_frame_count + 1 })
        : e
    )
    return new WorkflowEngine(deepFreeze(nextExecutions), nextFrames)
  }

  completeWorkflow(workflow_id: string, sequence: number): WorkflowEngine {
    return new WorkflowEngine(
      deepFreeze(this._executions.map(e =>
        e.workflow_id === workflow_id
          ? deepFreeze({ ...e, status: 'completed' as const, completed_at_sequence: sequence })
          : e
      )),
      this._frames
    )
  }

  abortWorkflow(workflow_id: string, sequence: number): WorkflowEngine {
    return new WorkflowEngine(
      deepFreeze(this._executions.map(e =>
        e.workflow_id === workflow_id
          ? deepFreeze({ ...e, status: 'aborted' as const, completed_at_sequence: sequence })
          : e
      )),
      this._frames
    )
  }

  getExecution(workflow_id: string): WorkflowExecution | undefined {
    return this._executions.find(e => e.workflow_id === workflow_id)
  }

  replayIntegrity(): number {
    if (this._frames.length === 0) return 1
    const satisfied = this._frames.filter(f => f.invariant_satisfied).length
    return satisfied / this._frames.length
  }
}
