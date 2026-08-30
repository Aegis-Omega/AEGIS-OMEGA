import { MVCCValue } from "../types/mvcc";

export class MVCCStore {
  private store = new Map<string, MVCCValue[]>();

  put(key: string, value: MVCCValue) {
    if (!this.store.has(key)) {
      this.store.set(key, []);
    }
    this.store.get(key)!.push(value);
  }

  read(key: string, ts: number) {
    const versions = this.store.get(key) || [];
    return [...versions]
      .reverse()
      .find(v => v.ts <= ts);
  }
}
