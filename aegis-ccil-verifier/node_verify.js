/**
 * node_verify.js
 * Cross-language verification harness. Reads a signed record on stdin (or a
 * path arg) and verifies it using the EXACT canonicalBytes() the server uses
 * (shared canonical.js), so the test exercises the production code path.
 *
 * Exit 0 = VALID, exit 1 = INVALID.
 *
 * Usage:
 *   python sign.py | node node_verify.js
 *   node node_verify.js signed_record.json
 */

const crypto = require('crypto');
const fs = require('fs');
const { canonicalBytes } = require('./canonical');

function readInput() {
  const arg = process.argv[2];
  if (arg) return fs.readFileSync(arg, 'utf-8');
  return fs.readFileSync(0, 'utf-8'); // stdin
}

const rec = JSON.parse(readInput());
const digest = crypto.createHash('sha256').update(canonicalBytes(rec.payload)).digest();
const spkiDer = Buffer.concat([
  Buffer.from('302a300506032b6570032100', 'hex'),
  Buffer.from(rec.public_key, 'base64'),
]);
const pub = crypto.createPublicKey({ key: spkiDer, format: 'der', type: 'spki' });
const ok = crypto.verify(null, digest, pub, Buffer.from(rec.signature, 'base64'));

console.log('NODE VERIFY:', ok ? 'VALID' : 'INVALID');
process.exit(ok ? 0 : 1);
