export class IndexStore {
  private index = new Map<string, Set<string>>();

  add(key: string, valueRef: string) {
    if (!this.index.has(key)) {
      this.index.set(key, new Set());
    }
    this.index.get(key)!.add(valueRef);
  }

  lookup(key: string): string[] {
    return Array.from(this.index.get(key) || []);
  }
}
