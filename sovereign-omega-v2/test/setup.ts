// Make BigInt JSON-serializable so JSON.stringify works in test assertions.
// BigInt.toString() produces the numeric string; this is lossless for SequenceNumber comparisons.
;(BigInt.prototype as unknown as { toJSON: () => string }).toJSON = function () {
  return this.toString()
}
