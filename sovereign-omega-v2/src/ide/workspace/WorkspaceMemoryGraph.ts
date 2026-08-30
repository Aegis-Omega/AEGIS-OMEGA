// ============================================================
// Workspace Memory Graph — append-only provenance graph
// EPISTEMIC TIER: T1
// Replay archives function as evolutionary workspace memory.
// Immutable: addNode / addEdge return new graph instances.
// ============================================================

import { deepFreeze } from '../../core/immutable'
import type { SHA256Hex } from '../../core/types'

export type GraphNodeType =
  | 'file'
  | 'mutation'
  | 'agent_interaction'
  | 'extension_impact'
  | 'telemetry_transition'
  | 'ontology_reference'

export interface GraphNode {
  readonly node_id: string
  readonly node_type: GraphNodeType
  readonly sequence: number
  readonly agent_id?: string
  readonly payload_hash: SHA256Hex
}

export interface GraphEdge {
  readonly edge_id: string
  readonly from_node_id: string
  readonly to_node_id: string
  readonly relation: string
  readonly sequence: number
}

export class WorkspaceMemoryGraph {
  private readonly _nodes: readonly GraphNode[]
  private readonly _edges: readonly GraphEdge[]

  private constructor(nodes: readonly GraphNode[], edges: readonly GraphEdge[]) {
    this._nodes = nodes
    this._edges = edges
  }

  static empty(): WorkspaceMemoryGraph {
    return new WorkspaceMemoryGraph(deepFreeze([]), deepFreeze([]))
  }

  get nodeCount(): number { return this._nodes.length }
  get edgeCount(): number { return this._edges.length }
  get nodes(): readonly GraphNode[] { return this._nodes }
  get edges(): readonly GraphEdge[] { return this._edges }

  addNode(node: GraphNode): WorkspaceMemoryGraph {
    return new WorkspaceMemoryGraph(
      deepFreeze([...this._nodes, deepFreeze(node)]),
      this._edges
    )
  }

  addEdge(edge: GraphEdge): WorkspaceMemoryGraph {
    return new WorkspaceMemoryGraph(
      this._nodes,
      deepFreeze([...this._edges, deepFreeze(edge)])
    )
  }

  nodesForAgent(agent_id: string): readonly GraphNode[] {
    return this._nodes.filter(n => n.agent_id === agent_id)
  }

  // Edges whose to_node_id matches target — the provenance lineage leading to it.
  replayLineage(target_node_id: string): readonly GraphEdge[] {
    return this._edges.filter(e => e.to_node_id === target_node_id)
  }
}
