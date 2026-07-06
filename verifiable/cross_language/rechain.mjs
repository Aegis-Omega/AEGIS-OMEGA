// AEGIS-Ω cross-runtime replay — Node.js re-chainer (dependency-free, node:crypto).
//
// Reads stages.json, rebuilds the lineage from GENESIS with an independent RFC 8785
// canonicalizer + SHA-256, and asserts it reproduces the Python-declared hashes
// byte-for-byte. Exit 0 = the genomics certificate replays identically on Node.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const GENESIS = "0".repeat(64);
const HERE = dirname(fileURLToPath(import.meta.url));

// RFC 8785-style canonical JSON, matching Python json.dumps(sort_keys=True,
// separators=(",",":"), ensure_ascii=False) + NFC. Rejects float (non-integer number).
function canon(value) {
  const s = serialize(value);
  return Buffer.from(s.normalize("NFC"), "utf-8");
}

function serialize(v) {
  if (v === null) return "null";
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "number") {
    if (!Number.isInteger(v)) throw new Error("float in hashed state is forbidden");
    return String(v);
  }
  if (typeof v === "string") return JSON.stringify(v); // JS escapes match Python for our data
  if (Array.isArray(v)) return "[" + v.map(serialize).join(",") + "]";
  if (typeof v === "object") {
    const keys = Object.keys(v).sort(); // code-unit order == code-point order for ASCII keys
    return "{" + keys.map((k) => JSON.stringify(k) + ":" + serialize(v[k])).join(",") + "}";
  }
  throw new Error("uncanonicalizable value: " + typeof v);
}

function sha256hex(buf) {
  return createHash("sha256").update(buf).digest("hex");
}

function rechain(stages) {
  const stageHashes = [];
  let prev = GENESIS;
  stages.forEach((rec, i) => {
    const payload = { stage: rec.stage, sequence: i, previous_hash: prev, output: rec.output };
    const h = sha256hex(canon(payload));
    stageHashes.push(h);
    prev = h;
  });
  return { terminal: prev, stageHashes };
}

const fixture = JSON.parse(readFileSync(join(HERE, "stages.json"), "utf-8"));
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
