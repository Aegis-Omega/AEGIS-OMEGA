import type { ResourceRegistry } from './resources.js'

export type PassKind = 'COMPUTE' | 'RENDER'

export interface PassNode {
  readonly name: string
  readonly kind: PassKind
  readonly reads: readonly string[]
  readonly writes: readonly string[]
  execute(encoder: GPUCommandEncoder, registry: ResourceRegistry): void
}
