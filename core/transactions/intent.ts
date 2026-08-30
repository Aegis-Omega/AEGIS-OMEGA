export type IntentStatus =
  | "PENDING"
  | "COMMITTED"
  | "ABORTED";

export type Intent = {
  key: string;
  value: Buffer;
  txnId: string;
  ts: number;
  status: IntentStatus;
};
