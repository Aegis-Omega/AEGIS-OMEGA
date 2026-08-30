# aegis-interface — RFC 0001 Stage 1

Deterministic, contract-first interface compilation. A single WIT-subset source
of truth is lowered through a normalised IR and projected into **Rust**,
**TypeScript**, and **Python**. A CI equivalence gate rejects cross-runtime
schema drift.

```
WIT source ──► AST ──► IR (normalised contract graph) ──► { Rust, TypeScript, Python }
                                                              │
                                                              ▼
                                                    CI equivalence gate
```

This is the **Stage 1** implementation of RFC 0001: structural equivalence, no
formal proof engine. SMT-backed verification is deferred to RFC 0002 (Stage 2).

## Install / run

No build step. From this directory:

```bash
# emit projections + canonical schema to ./generated
python -m aegis_interface.cli compile wit/skill_snapshot.wit --out generated

# run the equivalence gate in memory (exit != 0 on drift)
python -m aegis_interface.cli validate wit/skill_snapshot.wit

# CI gate: assert committed artefacts are equivalent AND up to date
python -m aegis_interface.cli check wit/skill_snapshot.wit --out generated

# tests
PYTHONPATH=. python -m pytest -q
```

Installed as a console script (`pip install -e .`), the same commands are
available as `aegis-interface <subcommand>`.

## WIT subset (§4)

```wit
variant Tier { bronze, silver, gold }

record SkillSnapshot {
  skill_id: string,
  tier: Tier,
  @range(0.0, 1.0)
  confidence: f64,
  attempts: u64,
  tags: list<string>,
  parent_skill: option<string>,
}
```

- `record` (or `interface`) and `variant` declarations.
- Primitives: `string`, `bool`, `s32/s64/u32/u64`, `f32/f64`. RFC-style aliases
  (`float64`, `int`, `boolean`, `str`, …) are normalised by the IR.
- Wrappers: `list<T>`, `option<T>`.
- `@range(min, max)` constraint annotation on numeric fields.
- `//` line comments.

## How the equivalence gate actually works (§7, §8)

The gate is not tautological. Each projection can **read its own generated
source back** into a *coarse comparison schema* — structural nesting, reference
targets, and a leaf category in `{string, bool, number, <RefName>}`. The gate
asserts all three readbacks equal the IR's expected schema. A projection bug
(dropped field, wrong type mapping, altered enum case, missing range) changes
that projection's readback and fails the build with a deterministic diff. See
`tests/test_equivalence.py` for the falsification cases.

`number` is the strongest *honest* cross-language leaf invariant: TypeScript and
Python both collapse every numeric width to a single type, so the gate checks
what is genuinely checkable across all three. Full numeric width is preserved in
the IR, the canonical `schema.json`, and the Rust projection.

## Versioning (§10)

- **Major** — breaking WIT change (field removed/renamed/retyped, variant case
  removed, range tightened).
- **Minor** — additive, backward-compatible WIT change (new optional field, new
  variant case, range widened).
- **Patch** — projection/codegen change with no contract-surface change.

## RFC 0005 — schema evolution & multi-agent consensus

Built on the same IR: schema evolution is treated as a category **Sch_ver**
whose objects are interface graphs and whose morphisms are certified
evolutions.

```bash
# diff two versions -> verdict, version bump, proof obligations, certificate
python -m aegis_interface.cli evolve --from wit/skill_snapshot.wit \
    --to wit/skill_snapshot_v2.wit --out cert.json

# multi-agent consensus (φ = verified obligations / total; quorum = 1/φ)
python -m aegis_interface.cli consensus --proposed wit/skill_snapshot_v2.wit \
    --agents a.wit b.wit c.wit

# verify the composition / confluence law over three versions (Δ13 = Δ23∘Δ12)
python -m aegis_interface.cli compose v1.wit v2.wit v3.wit

# versioned migration codegen (§5): Rust Upgrade/Downgrade + TS V1/V2 + assertions
python -m aegis_interface.cli evolve-codegen --from v1.wit --to v2.wit \
    --type SkillSnapshot --out generated/versioned
```

- **Compatibility algebra (§2).** Each evolution vector is classified
  `backward` / `forward`; the overall verdict is `FULL`, `BACKWARD_COMPATIBLE`,
  `FORWARD_COMPATIBLE`, or `BREAKING`. Classes form a semiring whose product
  `⊗` is boolean-AND on the two directions — a single breaking step
  contaminates a composed path.
- **Proof obligations (§4).** Certificates are obligation-centric:
  `NoFieldLoss`, `ConstraintPreserved`, `TypeSafetyPreserved`,
  `SerializationInvariant`. The structure admits richer obligations later
  without changing the certificate model.
- **Composition / confluence.** The net evolution depends only on the
  endpoints, so any two paths to the same version induce the same
  transformation; `compose` witnesses that the direct evolution is at least as
  compatible as a composed path (a path can be stricter when steps cancel).
- **Consensus over obligations, not votes (§3).** Agents independently
  re-derive and discharge obligations against their *own* local schema; the
  φ ratio is verified-obligations / total, gated at the constitutional 1/φ
  quorum. A thousand agreeing agents do not help if a critical obligation
  stays unverified.

### Evolution honesty boundary

RFC 0005's certificate specifies a Lean4 kernel proof object and §5 specifies
Canonical-ABI byte-offset dispatch. Those depend on Stage 2–4 (RFC 0002–0004),
which are not implemented. Here the proof is a *structural* derivation
(engine `aegis-structural-v1`, independently re-checkable by the consensus
kernel) and the versioned codegen emits structural dispatch + type-level
assertions, with no fabricated byte offsets. The certificate structure is
shaped so SMT/Lean witnesses can slot in later without changing it.

## Stage 1 scope limitations (deliberate)

These are out of scope here and tracked for later RFC stages:

- **Identifier casing.** This subset uses `snake_case`/`PascalCase` identifiers
  for a clean 1:1 mapping to each target language. Canonical WIT uses
  `kebab-case`; adopting it requires per-language name mangling — deferred.
- **Variant payloads.** Variants are payload-free (enum domains). WIT variants
  with payloads — and the TypeScript *discriminated-union* projection they
  imply — are not yet generated.
- **Structural subtyping & the type lattice (§5.3).** The IR records types and
  references; it does not yet compute `⊑` / least-upper-bound relations. That
  formalisation is RFC 0002.
- **Runtime constraint enforcement.** `@range` is emitted as documentation only
  (RFC §9: projections execute no code). SMT-backed enforcement is RFC 0002.

## Layout

```
aegis_interface/
  parser.py            WIT-subset tokeniser + recursive-descent parser (§4)
  ir.py                AST -> normalised IR, canonical schema (§5)
  projections/
    __init__.py        shared helpers + coarse comparison schema
    rust.py            serde structs / enums (§6.2)
    typescript.py      interfaces / string-literal unions (§6.3)
    python.py          dataclasses / Literal aliases (§6.4)
  equivalence.py       readback comparison gate (§8)
  evolution.py         RFC 0005 — Δ diff, compatibility semiring, obligations,
                       composition/confluence, evolution certificates
  consensus.py         RFC 0005 — obligation-based multi-agent φ consensus
  versioned.py         RFC 0005 §5 — versioned Rust/TS + migration codegen
  compiler.py          pipeline orchestrator (§2.1)
  cli.py               compile / validate / check / evolve / consensus /
                       compose / evolve-codegen
wit/skill_snapshot*.wit  example source of truth + v2/v3 evolutions
generated/             committed artefacts verified by `check` in CI
tests/                 parser / IR / projection / equivalence / determinism /
                       evolution / consensus / versioned
```
