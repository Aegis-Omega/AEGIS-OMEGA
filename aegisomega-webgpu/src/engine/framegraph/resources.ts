export interface ResourceHandle {
  readonly id: string
}

export class ResourceRegistry {
  private readonly textures = new Map<string, GPUTexture>()
  private readonly aliases  = new Map<string, string>()

  register(id: string, texture: GPUTexture): ResourceHandle {
    this.textures.set(id, texture)
    return Object.freeze({ id })
  }

  alias(aliasId: string, sourceId: string): void {
    if (!this.textures.has(sourceId) && !this.aliases.has(sourceId)) {
      throw new Error(`ResourceRegistry: source "${sourceId}" not registered`)
    }
    this.aliases.set(aliasId, sourceId)
  }

  get(handle: ResourceHandle): GPUTexture {
    const id = this.resolve(handle.id)
    const tex = this.textures.get(id)
    if (!tex) throw new Error(`ResourceRegistry: texture "${id}" not found`)
    return tex
  }

  private resolve(id: string): string {
    let current = id
    const seen = new Set<string>()
    while (this.aliases.has(current)) {
      if (seen.has(current)) throw new Error(`ResourceRegistry: alias cycle at "${current}"`)
      seen.add(current)
      current = this.aliases.get(current)!
    }
    return current
  }
}
