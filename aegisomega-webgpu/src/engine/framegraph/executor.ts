import type { PassNode } from './pass.js'
import type { ResourceRegistry } from './resources.js'
import type { FrameGraph } from './graph.js'

export class Executor {
  private readonly sortedPasses: readonly PassNode[]

  constructor(graph: FrameGraph) {
    this.sortedPasses = graph.build()
  }

  get passNames(): readonly string[] {
    return this.sortedPasses.map(p => p.name)
  }

  execute(encoder: GPUCommandEncoder, registry: ResourceRegistry): void {
    for (const pass of this.sortedPasses) {
      pass.execute(encoder, registry)
    }
  }
}
