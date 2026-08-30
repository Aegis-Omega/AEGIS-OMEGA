import { Intent } from "./intent";

export class ConflictResolver {
  detectConflict(a: Intent, b: Intent): boolean {
    return (
      a.key === b.key &&
      a.txnId !== b.txnId &&
      a.status === "PENDING" &&
      b.status === "PENDING"
    );
  }

  resolve(conflicts: Intent[]) {
    // simple last-write-wins baseline (upgrade later to OCC rules)
    conflicts.sort((a, b) => b.ts - a.ts);
    return conflicts[0];
  }
}
