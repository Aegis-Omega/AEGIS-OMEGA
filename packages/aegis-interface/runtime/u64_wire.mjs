// Canonical 64-bit integer wire transport for the AEGIS interface runtime.
// Wire representation: canonical base-10 UTF-8 decimal string.
import fs from 'node:fs';

const U64_MAX = (1n << 64n) - 1n;
const S64_MIN = -(1n << 63n);
const S64_MAX = (1n << 63n) - 1n;
const SIGNED_CANONICAL = /^(?:0|-?[1-9][0-9]*)$/;
const CANONICAL = /^(?:0|[1-9][0-9]*)$/;

export function decodeU64(wire) {
  if (typeof wire !== 'string' || wire.length > 20 || !CANONICAL.test(wire)) {
    throw new TypeError('U64_WIRE_FORMAT');
  }
  const value = BigInt(wire);
  if (value > U64_MAX) throw new RangeError('U64_OUT_OF_RANGE');
  return value;
}

export function encodeU64(value) {
  if (typeof value !== 'bigint') throw new TypeError('U64_NATIVE_TYPE');
  if (value < 0n || value > U64_MAX) throw new RangeError('U64_OUT_OF_RANGE');
  return value.toString(10);
}

export function decodeS64(wire) {
  if (typeof wire !== 'string' || wire.length > 20 || !SIGNED_CANONICAL.test(wire)) {
    throw new TypeError('S64_WIRE_FORMAT');
  }
  const value = BigInt(wire);
  if (value < S64_MIN || value > S64_MAX) throw new RangeError('S64_OUT_OF_RANGE');
  return value;
}

export function encodeS64(value) {
  if (typeof value !== 'bigint') throw new TypeError('S64_NATIVE_TYPE');
  if (value < S64_MIN || value > S64_MAX) throw new RangeError('S64_OUT_OF_RANGE');
  return value.toString(10);
}

// Batch stdin protocol for deterministic cross-language testing.
if (process.argv[1] === new URL(import.meta.url).pathname) {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  const output = {
    valid: input.valid.map(s => encodeU64(decodeU64(s))),
    invalid: input.invalid.map(s => {
      try { decodeU64(s); return 'ACCEPTED'; }
      catch (err) { return err.message; }
    }),
    s64Valid: (input.s64Valid ?? []).map(s => encodeS64(decodeS64(s))),
    s64Invalid: (input.s64Invalid ?? []).map(s => {
      try { decodeS64(s); return 'ACCEPTED'; } catch (err) { return err.message; }
    }),
    lossWitness: Number(9007199254740992n) === Number(9007199254740993n),
  };
  process.stdout.write(JSON.stringify(output));
}
