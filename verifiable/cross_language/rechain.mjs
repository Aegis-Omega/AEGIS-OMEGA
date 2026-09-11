// AEGIS-Ω cross-runtime replay — Node.js re-chainer (dependency-free, node:crypto).
//
// Reads stages.json, rebuilds the lineage from GENESIS with the explicit v2
// canonicalizer + SHA-256, and asserts it reproduces the Python-declared hashes
// byte-for-byte. Exit 0 = the genomics certificate replays identically on Node.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const GENESIS = "0".repeat(64);
const CANONICAL_PROFILE = "aegis-integer-json-v2";
const HERE = dirname(fileURLToPath(import.meta.url));

// The safe-integer subset of Python's v2 profile, with exact Unicode text.
function canon(value) {
  const s = serialize(value);
  return Buffer.from(s, "utf-8");
}

function compareCodePoints(left, right) {
  const a = Array.from(left, c => c.codePointAt(0));
  const b = Array.from(right, c => c.codePointAt(0));
  for (let i = 0; i < Math.min(a.length, b.length); i++) {
    if (a[i] !== b[i]) return a[i] - b[i];
  }
  return a.length - b.length;
}

function scalarString(value) {
  for (const character of value) {
    const point = character.codePointAt(0);
    if (point >= 0xd800 && point <= 0xdfff) throw new Error("unpaired Unicode surrogate");
  }
  return JSON.stringify(value);
}

function serialize(v) {
  if (v === null) return "null";
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "number") {
    if (!Number.isSafeInteger(v)) throw new Error("hashed number must be a safe integer");
    return String(v);
  }
  if (typeof v === "string") return scalarString(v);
  if (Array.isArray(v)) return "[" + v.map(serialize).join(",") + "]";
  if (typeof v === "object") {
    const keys = Object.keys(v).sort(compareCodePoints);
    return "{" + keys.map((k) => scalarString(k) + ":" + serialize(v[k])).join(",") + "}";
  }
  throw new Error("uncanonicalizable value: " + typeof v);
}

function sha256hex(buf) {
  return createHash("sha256").update(buf).digest("hex");
}

function parseFixture(raw) {
  // Inspect number tokens before JSON.parse can round them. Strings (including
  // escaped quotes) are consumed separately so digits inside text are untouched.
  const tokens = /("(?:\\.|[^"\\])*")|(-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?)/g;
  for (const token of raw.matchAll(tokens)) {
    if (!token[2]) continue;
    if (!/^-?(?:0|[1-9]\d*)$/.test(token[2])) throw new Error("fixture numbers must be integer literals");
    const value = BigInt(token[2]);
    if (value < -9007199254740991n || value > 9007199254740991n) throw new Error("fixture integer outside safe range");
  }
  return JSON.parse(raw);
}

function rechain(stages) {
  const stageHashes = [];
  let prev = GENESIS;
  stages.forEach((rec, i) => {
    const payload = { canonicalization: CANONICAL_PROFILE, stage: rec.stage, sequence: i, previous_hash: prev, output: rec.output };
    const h = sha256hex(canon(payload));
    stageHashes.push(h);
    prev = h;
  });
  return { terminal: prev, stageHashes };
}

const fixture = parseFixture(readFileSync(process.argv[2] ?? join(HERE, "stages.json"), "utf-8"));
if (fixture.canonicalization !== CANONICAL_PROFILE) throw new Error("unsupported canonicalization profile");
if (!Array.isArray(fixture.canonical_vectors) || fixture.canonical_vectors.length === 0) throw new Error("missing canonical vectors");
for (const vector of fixture.canonical_vectors) {
  if (sha256hex(canon(vector.value)) !== vector.sha256) throw new Error("canonical vector mismatch");
}
const got = rechain(fixture.stages);
const exp = fixture.expected;

let ok = got.terminal === exp.terminal &&
  got.stageHashes.length === exp.stage_hashes.length &&
  got.stageHashes.every((h, i) => h === exp.stage_hashes[i]);

console.log(`node terminal   : ${got.terminal}`);
console.log(`python terminal : ${exp.terminal}`);
console.log(ok ? "MATCH — genomics certificate replays byte-identically on Node.js"
              : "MISMATCH — cross-runtime divergence");
process.exit(ok ? 0 : 1);
