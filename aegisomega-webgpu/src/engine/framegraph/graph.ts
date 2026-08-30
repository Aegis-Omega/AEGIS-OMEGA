import type { PassNode } from './pass.js'

export class FrameGraph {
  private readonly passes: PassNode[] = []

  addPass(pass: PassNode): void {
    this.passes.push(pass)
  }

  build(): readonly PassNode[] {
    const n = this.passes.length
    if (n === 0) return []

    const idx = new Map<string, number>()
    for (let i = 0; i < n; i++) idx.set(this.passes[i].name, i)

    const writtenBy = new Map<string, number>()
    for (let i = 0; i < n; i++) {
      for (const resource of this.passes[i].writes) {
        writtenBy.set(resource, i)
      }
    }

    const adj: Set<number>[] = Array.from({ length: n }, () => new Set<number>())
    const inDegree = new Array<number>(n).fill(0)

    for (let i = 0; i < n; i++) {
      for (const resource of this.passes[i].reads) {
        const producer = writtenBy.get(resource)
        if (producer !== undefined && producer !== i && !adj[producer].has(i)) {
          adj[producer].add(i)
          inDegree[i]++
        }
      }
    }

    const queue: number[] = []
    for (let i = 0; i < n; i++) {
      if (inDegree[i] === 0) queue.push(i)
    }

    const sorted: PassNode[] = []
    while (queue.length > 0) {
      const current = queue.shift()!
      sorted.push(this.passes[current])
      for (const dep of adj[current]) {
        inDegree[dep]--
        if (inDegree[dep] === 0) queue.push(dep)
      }
    }

    if (sorted.length < n) {
      throw new Error('FrameGraph: cycle detected — frame graph is not a DAG')
    }

    return Object.freeze(sorted)
  }
}
