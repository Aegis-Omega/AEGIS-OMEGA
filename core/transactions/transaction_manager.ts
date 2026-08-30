import { MVCCStore } from "../storage/mvcc_store";
import { IntentStore } from "./intent_store";

export class TransactionManager {
  constructor(
    private mvcc: MVCCStore,
    private intents: IntentStore
  ) {}

  write(txnId: string, key: string, value: Buffer, ts: number) {
    this.intents.add({
      key,
      value,
      txnId,
      ts,
      status: "PENDING"
    });
  }

  commit(txnId: string, key: string) {
    this.intents.resolve(key, txnId);
  }
}
