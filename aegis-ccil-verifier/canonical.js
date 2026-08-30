/**
 * canonical.js
 * Dependency-free canonical serialization shared by the Express server and the
 * cross-language test. Must produce byte-identical output to the Python
 * verifier's canonical_bytes (sorted keys, no whitespace, literal UTF-8, NFC).
 */

function canonicalize(obj) {
  if (obj === null) return 'null';
  if (typeof obj !== 'object') return JSON.stringify(obj);
  if (Array.isArray(obj)) {
    return '[' + obj.map(canonicalize).join(',') + ']';
  }
  const sortedKeys = Object.keys(obj).sort();
  const keyValues = sortedKeys.map(key => {
    return `"${key}":${canonicalize(obj[key])}`;
  });
  return '{' + keyValues.join(',') + '}';
}

/** Canonical bytes: NFC-normalized UTF-8, matching the Python verifier. */
function canonicalBytes(payload) {
  return Buffer.from(canonicalize(payload).normalize('NFC'), 'utf-8');
}

module.exports = { canonicalize, canonicalBytes };
