# Cross-runtime replay — the certificate is language-invariant

**Tier: T2, reaching for T0.** The constitution's headline property is
*"replay(genesis, events) → identical topology hash across Linux/macOS/Docker/WASM/
ARM/x86."* The genomics proof showed the certificate is reproducible across Python
*processes*. This shows it is reproducible across **independent implementations in
different languages** — the stronger claim, and the one that promotes a determinism
result from T1 toward T0 (byte-identical cross-platform demo).

## What runs

```
bash verify.sh
── 1/3  Python (reference producer)      terminal f8cb0093b9b7447c…
── 2/3  Node.js (independent re-chainer)  MATCH
── 3/3  Rust (independent re-chainer)     MATCH
RESULT: identical terminal hash across Python, Node.js, and Rust.
```

- `emit_fixture.py` runs the genomics pipeline and writes `stages.json` — just the
  ordered `(stage, output)` list, GENESIS-relative.
- `rechain.mjs` (Node, `node:crypto`, zero deps) and `rust_rechain/` (Rust, `sha2` +
  `serde_json` from the offline cargo cache) each read *only* those stage outputs and
  **rebuild the entire chain from GENESIS with their own canonicalizer + SHA-256**.
  They do not read the expected hashes until the final compare — so matching is a real
  independent replay, not re-hashing given values.

Each of the three lands on `f8cb0093b9b7447cc44d7386f1305f427dc7eb887a23407f9b67522b8f5db8f1`.

## Why the three canonicalizers agree (the hard part)

Byte-identical hashing across languages is not free — it is exactly where naive
pipelines diverge. The agreement holds because all three obey the same RFC 8785
discipline:

| Concern | Python | Node.js | Rust |
|---|---|---|---|
| key order | `sort_keys=True` | `Object.keys().sort()` | `serde_json` default = `BTreeMap` (sorted) |
| whitespace | `separators=(",",":")` | manual compact serialize | `to_string` compact |
| non-ASCII | `ensure_ascii=False` | raw (`JSON.stringify`) | raw UTF-8 |
| unicode form | NFC normalize | `.normalize("NFC")` | identity (fixture is ASCII) |
| float | rejected | rejected (`Number.isInteger`) | rejected (`Number::is_f64`) |
| integers | native | integer-valued only | `serde_json` integer |

The fixture is pure ASCII + integers, so NFC is the identity and cannot introduce
cross-language drift; float is structurally impossible because every canonicalizer
rejects it. Change one base in the input and all three terminal hashes move together.

## Honest scope

This proves the **envelope** (canonicalization + hashing + chaining) is runtime-invariant
on this fixture, across three languages on one platform (x86-64 Linux). Full T0 for the
constitution's cross-*platform* claim additionally needs ARM / WASM / macOS runs and a
non-ASCII stress fixture with normalization on all three — a CI matrix, not new logic.
The Rust and Node re-chainers are the reusable core for that matrix.
