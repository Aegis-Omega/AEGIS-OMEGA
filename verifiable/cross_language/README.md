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
── 1/3  Python (reference producer)      terminal ab4c952b476a9d74…
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

Each of the three lands on `ab4c952b476a9d743f8b307ed9f360ba5006254d9e1d0e10e0b06ef5d3d6b987`.

## Why the three canonicalizers agree (the hard part)

Byte-identical hashing across languages is not free — it is exactly where naive
pipelines diverge. The agreement holds because all three obey the explicit `aegis-integer-json-v2` fixture subset (not full RFC 8785):

| Concern | Python | Node.js | Rust |
|---|---|---|---|
| key order | `sort_keys=True` | code-point key sort | `serde_json` default = `BTreeMap` (sorted) |
| whitespace | `separators=(",",":")` | manual compact serialize | `to_string` compact |
| non-ASCII | `ensure_ascii=False` | raw (`JSON.stringify`) | raw UTF-8 |
| unicode form | exact text | exact text | exact text |
| float | rejected | rejected before numeric parsing | rejected (`Number::is_f64`) |
| fixture integers | JavaScript safe range | same range, checked before parsing | same range, checked after parsing |

The genomics stages use ASCII and small integers. Four additional canonical vectors
cover composed/decomposed Unicode, BMP/non-BMP key ordering, controls, booleans, null
and safe-integer boundaries. Python's general-purpose profile permits larger integers;
these replayers reject values outside their explicitly narrower shared range. Node
validates numeric literals before JSON.parse can round them. Both replayers require
the exact v2 profile identifier and bind it into each stage preimage.

`test_replay_profiles.py` runs after successful positive replay. All sixteen negative
checks must reject: missing/wrong profile, changed stage data, normalized Unicode,
an unsafe integer, a fractional literal that JavaScript would round to the original integer, and
unpaired surrogate keys/values (each tested in Node and Rust). Surrogate cases use
the digest an unchecked Node serializer would compute, so rejection cannot be
explained by an incidental hash mismatch. The build uses Cargo.lock; the fixture is regenerated
from the running Python implementation, not manually edited hashes.

## Honest scope

This proves the **envelope** (canonicalization + hashing + chaining) is runtime-invariant
on these fixtures, across three languages. The v2 update was locally verified on
Windows x86-64, including both negative replay checks and two complete session runs.
Ubuntu/macOS checks are defined in CI and must pass on the migrated revision; this
local result is not evidence of ARM or WASM behavior. Arbitrary Unicode/number
conformance and biological correctness are outside this bounded fixture proof.
