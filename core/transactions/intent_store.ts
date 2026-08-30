import { Intent } from "./intent";

export class IntentStore {
  private intents = new Map<string, Intent[]>();

  add(intent: Intent) {
    if (!this.intents.has(intent.key)) {
      this.intents.set(intent.key, []);
    }
    this.intents.get(intent.key)!.push(intent);
  }

  resolve(key: string, txnId: string) {
    const list = this.intents.get(key) || [];
    for (const i of list) {
      if (i.txnId === txnId) {
        i.status = "COMMITTED";
      }
    }
  }
}
