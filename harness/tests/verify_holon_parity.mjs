#!/usr/bin/env node
// Cross-runtime parity at the exact AEGIS TypeScript canonicalizeJCS source.
// Byte agreement for this restricted holon interchange profile does NOT imply
// general RFC 8785/Python-JSON equivalence or semantic truth.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { canonicalizeJCS } from '../../sovereign-omega-v2/src/core/canonicalize.ts';

const MAX_SAFE = Number.MAX_SAFE_INTEGER;

function assertInterchangeProfile(v, path = '$') {
  if (v === null || typeof v === 'boolean') return;
  if (typeof v === 'number') {
    if (!Number.isSafeInteger(v) || Object.is(v, -0)) {
      throw new TypeError(path + ':UNSAFE_INTEGER_OR_FLOAT');
    }
    return;
  }
  if (typeof v === 'string') {
    for (let i = 0; i < v.length; i++) {
      const cu = v.charCodeAt(i);
      if (cu >= 0xd800 && cu <= 0xdbff) {
        const next = v.charCodeAt(i + 1);
        if (!(next >= 0xdc00 && next <= 0xdfff)) throw new TypeError(path + ':SURROGATE');
        i++;
      } else if (cu >= 0xdc00 && cu <= 0xdfff) {
        throw new TypeError(path + ':SURROGATE');
      }
    }
    return;
  }
  if (Array.isArray(v)) {
    for (let i = 0; i < v.length; i++) {
      assertInterchangeProfile(v[i], path + '[' + i + ']');
    }
    return;
  }
  if (typeof v === 'object' && Object.getPrototypeOf(v) === Object.prototype) {
    for (const [key, value] of Object.entries(v)) {
      if (!/^[\x00-\x7f]*$/.test(key)) throw new TypeError(path + ':KEY_NOT_ASCII');
      assertInterchangeProfile(key, path + '.key');
      assertInterchangeProfile(value, path + '.' + key);
    }
    return;
  }
  throw new TypeError(path + ':UNSUPPORTED_TYPE');
}

function sha256(buf) {
  return createHash('sha256').update(buf).digest('hex');
}

function assertReject(value, expected) {
  assert.throws(() => assertInterchangeProfile(value), (err) => String(err.message).includes(expected));
}

// These prove the harness refuses to report parity outside its tested domain.
assertReject({ n: 1.5 }, 'UNSAFE_INTEGER_OR_FLOAT');
assertReject({ n: 1e20 }, 'UNSAFE_INTEGER_OR_FLOAT');
assertReject({ n: -0 }, 'UNSAFE_INTEGER_OR_FLOAT');
assertReject({ n: MAX_SAFE + 1 }, 'UNSAFE_INTEGER_OR_FLOAT');
assertReject({ 'é': 'value' }, 'KEY_NOT_ASCII');
assertReject({ x: '\ud800' }, 'SURROGATE');
assertReject({ x: '\udc00' }, 'SURROGATE');
assertReject({ x: undefined }, 'UNSUPPORTED_TYPE');
assertReject({ x: 1n }, 'UNSUPPORTED_TYPE');

const input = process.argv[2];
if (!input) throw new Error('Usage: node --experimental-strip-types harness/tests/verify_holon_parity.mjs <vectors.jsonl>');
const rows = readFileSync(input, 'utf8').trimEnd().split('\n').map(line => JSON.parse(line));
assert.ok(rows.length >= 45, 'Too few independently generated Python vectors');
const seen = new Set();
for (const row of rows) {
  assert.deepEqual(Object.keys(row).sort(), ['domain', 'expected_canonical_hex', 'expected_root', 'label', 'value']);
  assert.ok(!seen.has(row.label), 'duplicate vector ' + row.label);
  seen.add(row.label);
  assertInterchangeProfile({ domain: row.domain, value: row.value });
  const actualBytes = canonicalizeJCS({ domain: row.domain, value: row.value });
  const actualHex = Buffer.from(actualBytes).toString('hex');
  assert.equal(actualHex, row.expected_canonical_hex, 'canonical-byte mismatch: ' + row.label);
  const actualRoot = sha256(actualBytes);
  assert.equal(actualRoot, row.expected_root, 'SHA-256 root mismatch: ' + row.label);
}
console.log('HOLON_INTERCHANGE_PROFILE=SAFE_INTEGERS_NO_FLOAT_ASCII_KEYS_UTF8_VALUES');
console.log('HOLON_PARITY_PASS=' + rows.length);
