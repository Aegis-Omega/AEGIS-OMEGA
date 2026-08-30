export type Timestamp = number;
export type MVCCValue = {
  value: Buffer;
  ts: Timestamp;
  txnId?: string;
};
