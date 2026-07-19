# AEGIS Discovery Portfolio

**Status:** evidence-bound working register  
**Repository baseline:** `main` at `601dc35276792af136c53f118244b4f582bbacb6`  
**Portfolio branch:** `claude/slack-session-yyw7h6`  
**Rule:** attribution and reproduction are independent axes. Neither substitutes for the other.

## Axes

### Reproduction grade

| Grade | Meaning |
|---|---|
| `R0` | Narrative or design claim only; no executable evidence. |
| `R1` | Code or external artifact exists; not independently rerun in the current evidence package. |
| `R2` | Tests or runtime behavior reproduced on one implementation/runtime. |
| `R3` | Independently reproduced across implementations, runtimes, or verifiers. |
| `R4` | Exercised across the real production boundary with a durable receipt. |

### Attribution grade

| Grade | Meaning |
|---|---|
| `A0` | Origin or causal actor unknown. |
| `A1` | Repository commit/PR provenance only. |
| `A2` | Session and model identity recovered. |
| `A3` | Session, source corpus, prompt/tool calls, and resulting mutation are causally bound. |
| `A4` | Signed or independently attested actor/session/source-to-mutation chain. |

These axes must remain separate. A result can be highly reproducible while its originating model session is unknown; a strongly attributed story can remain unreproduced.

## Register

| ID | Discovery | Reproduction | Attribution | Current verdict | Canonical evidence |
|---|---|---:|---:|---|---|
| `DSC-001` | TypeScript and Python canonicalize the shared JSON vectors to identical bytes/digests, including decomposed Unicode. | `R3` | `A1` | **Verified.** Full-structure parity is proven for TS ↔ Python only. | `docs/proofs/cross-platform-determinism.md`; `docs/claims.json` (`CLM-001`, `CLM-002`); `sovereign-omega-v2/test/vectors/canon-vectors.json` |
| `DSC-002` | Big-endian `f64` bytes followed by SHA-256 produce identical primitive digests in Node, Python, and Rust. | `R3` | `A1` | **Verified primitive parity.** This is not full tri-language envelope replay. | `docs/proofs/cross-platform-determinism.md` |
| `DSC-003` | Python `EnvelopeChain` reconstructs the same linked chain and final digest from the same inputs. | `R2` | `A1` | **Verified in Python.** Node/full-envelope and Rust/full-structure independent replay are not both established by a shared vector. | `docs/proofs/cross-platform-determinism.md`; `sovereign-omega-v2/python/canonical_envelope.py` |
| `DSC-004` | Two repository representations of φ differ by one IEEE-754 ULP: computed `(√5−1)/2` versus literal `0.6180339887498948`. | `R3` | `A1` | **Verified inconsistency.** Each representation is cross-language stable, but the two representations are not equal. | `docs/proofs/cross-platform-determinism.md` |
| `DSC-005` | Canonical provenance was added to the bridge without changing the pre-existing legacy integrity hashes. | `R2` | `A1` | **Verified migration property.** | `docs/claims.json` (`CLM-004`); `sovereign-omega-v2/python/bridge.py` |
| `DSC-006` | The AEGIS swarm runtime default was `claude-fable-5` from commit `4747755` until `8305ec6`; the frontend code default was not Fable. | `R3` | `A1` | **Verified chronology and surface divergence.** | `docs/claims.json` (`CLM-009`); `docs/transitions/2026-06-model-default.md` |
| `DSC-007` | A Fable session that ingested the Mythos model card initiated or shaped commit `4747755` / PR #148. | `R0` | `A0` | **Proposed, not established.** Requires one artifact binding model/session + Mythos ingestion + mutation authorship. | `docs/claims.json` (`CLM-206`) |
| `DSC-008` | Mixed technical, mythic, and governance language can propagate through briefs, persistent instructions, skills, hooks, and memory until conceptual language influences operational behavior. | `R1` | `A1` | **Research hypothesis with a documented mechanism.** Controlled replay is still required. | `HANDOFF.md` CP-001 record; recovered session/hook corpus outside the public repository |
| `DSC-009` | Hallucination Delta measures metacognitive calibration as `HD = |claimed correctness − actual correctness|`. | `R1` | `A2` | **External artifact under review; not repo-reproduced.** | `docs/claims.json` (`CLM-220`); `docs/evidence/kaggle-2026/manifest.json` |
| `DSC-010` | Product flows previously allowed pre-payment client-side grant-token minting; the product path now accepts server-verified P-256 tokens and `verify-paypal` can mint `tool_token`. | `R2` | `A1` | **Security defect repaired in code. Not live-activated.** `GRANT_PRIVATE_KEY_JWK` and a verified production redeploy remain absent. | PR #192; `packages/shared/lib/access.ts`; `supabase/functions/verify-paypal/index.ts`; `HANDOFF.md` |
| `DSC-011` | The Python SDK package metadata referenced a missing README, preventing editable installation and CLI registration. | `R2` | `A2` | **Runtime defect reproduced and repaired on PR #215.** Local bridge `/platform/status` was exercised through the installed CLI. | PR #215; `packages/aegis-py/README.md` |
| `DSC-012` | Gate 188 implements bounded generation and immutable slot-registry metadata transitions in TypeScript. | `R2` | `A1` | **Verified as tested application invariants, not as Iris ownership proofs.** | `sovereign-omega-v2/src/memory/bounded-generation.ts`; `src/memory/slot-registry.ts`; `test/unit/bounded-generation.test.ts` |
| `DSC-013` | Gate 188 provides a mechanically checked Coq/Iris proof of WebAssembly allocator relocation correctness and adequacy. | `R0` | `A1` | **Refuted as a current claim.** The repository contains a Markdown scaffold, no compiled `.v` proof or `coqc` receipt, and the scaffold has material type/specification contradictions. | `sovereign-omega-v2/docs/FORMAL_VERIFICATION_WASM.md` |

## Reproduce commands

Run from `sovereign-omega-v2` unless noted.

### DSC-001 — TS ↔ Python full-structure canonicalization

```bash
npm run test -- test/unit/canon-equivalence.test.ts
python3 python/tests/test_canon_equivalence.py
```

Expected: TypeScript suite passes 15 tests; Python suite passes 45 tests; shared digests include:

```text
44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a
eb622bb50cb4872c5b5490ffbda81e1b88c48ffddec151833403ef0b0942eced
a2b964dcb6a519031c512c9714172760861f305c9b7050917e4378d8449854fd
```

### DSC-002 / DSC-004 — cross-language primitive parity and φ discrepancy

Use the Node, Python, and Rust commands in `docs/proofs/cross-platform-determinism.md`.

Expected byte encodings:

```text
computed φ: 3fe3c6ef372fe950
literal φ:  3fe3c6ef372fe94f
```

### DSC-003 — Python chain reconstruction

Use the `EnvelopeChain` replay script in `docs/proofs/cross-platform-determinism.md`.

Expected final digest:

```text
b47f17579501b0b9f9125be4b7732b50fcb4016629b9cabe10fa56cbc1fbae68
```

### DSC-006 / DSC-007 — Fable chronology versus causal attribution

```bash
git log --all -S"claude-fable-5" --oneline
git show 4747755
git show 8305ec6
```

These commands reproduce `DSC-006`. They do **not** establish `DSC-007`; that requires the missing session-level causal artifact specified by `CLM-206`.

### DSC-010 — payment-access implementation boundary

```bash
rg -n "createGrantToken|verifyGrantToken|verifyServerToken|issueGrantToken|GRANT_PRIVATE_KEY_JWK|tool_token" \
  packages/shared hub platform-picker hook-generator content-calendar supabase/functions
```

Interpretation must distinguish code presence from live activation. A production claim requires a configured signing key, redeployed function, successful paid transaction, accepted tool token, and durable receipt.

### DSC-011 — SDK install and live local endpoint

```bash
cd packages/aegis-py
python3 -m venv /tmp/aegis-sdk-verify
. /tmp/aegis-sdk-verify/bin/activate
pip install -e .
aegis --help
AEGIS_BASE_URL=http://localhost:7890 aegis status
```

The final command requires the local bridge to be running.

### DSC-012 — Gate 188 TypeScript invariants

```bash
npm run test -- test/unit/bounded-generation.test.ts
```

This verifies the implemented TypeScript behavior only: bounded construction, saturation return, per-registry duplicate rejection, immutable successor registries, metadata relocation, and deterministic certification.

### DSC-013 — current formal-proof absence

```bash
find . -type f -name '*.v' -o -name '*.vo'
rg -n "Admitted\.|Proof\. admit|block_relocation_invariance_proof|free_pool_composition_law" .
```

At the portfolio baseline, the two theorem names occur in Markdown documentation, not in a compiled Coq source artifact.

## Gate 188 formal-claim audit

The TypeScript implementation is useful and testable, but it must not be described as a proof of physical WebAssembly relocation. The current scaffold has these blocking mismatches:

1. **Layout arithmetic:** the document labels three 32-bit fields as 128-bit. Three words are 96 bits unless a fourth reserved/padding word is modeled.
2. **Bound absent from Coq:** `slot_gen : nat` contains no `< 2^32` invariant and no saturated `⊥` state.
3. **Generation contradiction:** the prose requires `σ_new.gen = σ_old.gen + 1`, while the theorem constructs `σ_new` with the unchanged old generation.
4. **No executable Wasm semantics:** the theorem is a fancy update between propositions, not a WP theorem over a `memory.copy` expression or concrete allocator bytecode.
5. **No authoritative update resource:** the theorem premise does not own the authoritative map required to update the authoritative state and fragment together.
6. **Payload not tracked:** the theorem postcondition does not preserve a concrete vector `v`; it cannot establish copied-data equality.
7. **Fractional-source reclamation gap:** a fractional read permission cannot generally be converted into exclusive anonymous/free ownership without an additional quiescence or ownership-transfer protocol.
8. **TypeScript scope mismatch:** `ExclusiveSlotMap.relocate()` updates metadata and hashes only. It performs no memory copy, source erasure, region ownership transfer, or Wasm execution.
9. **FreeRegion mapping unsupported:** `src/capsule/kernel.ts` implements ordinary capability objects and entropy budgets; it does not implement an allocator-specific opaque or linear `FreeRegion` token.
10. **API exclusivity is local:** duplicate registration is rejected within one registry instance, but immutable registries can be forked from a common parent. This is not global linear ownership or a CMRA validity proof.
11. **Input-domain gaps:** slot indices, addresses, and sizes are not fully constrained to non-negative 32-bit integers; `slot_size` rejects zero but not negative or fractional values.
12. **No compilation receipt:** the Markdown snippet references placeholders and an undefined `Σ` at top level; no `.v` file or `coqc` output establishes that the scaffold typechecks.

### Required promotion path

`DSC-013` can move from `R0` only after:

1. a pinned Coq/Iris toolchain and actual `.v` sources exist;
2. the scaffold compiles with no `Admitted`, `admit`, placeholder axioms, or undefined model components;
3. generation bounds and saturation are represented in the logic;
4. a concrete free-space RA is constructed;
5. the allocator language/Wasm state interpretation and `memory.copy` WP are defined;
6. the relocation theorem tracks payload, authoritative ownership, generation increment, and source reclamation soundly;
7. `coqc` logs and artifact hashes are committed or attached;
8. the proven model is connected to the real allocator implementation through refinement tests or verified extraction.

## Commercial and research routes

| Route | Best-supported discoveries |
|---|---|
| Provenance/governance product | `DSC-001`, `DSC-003`, `DSC-005` |
| Enterprise AI bill of materials | `DSC-006`, `DSC-007` |
| Security audits and authorization hardening | `DSC-008`, `DSC-010`, `DSC-011` |
| Evaluation and benchmarking | `DSC-009` |
| Deterministic systems research | `DSC-001`, `DSC-002`, `DSC-004` |
| Formal-methods research program | `DSC-012`, promotion work for `DSC-013` |

## Non-negotiable wording

- Say **“TS ↔ Python full-structure parity; Rust primitive parity”**, not “full tri-language replay.”
- Say **“P-256 access path is code-complete but not live-activated”**, not “production verified.”
- Say **“Gate 188 TypeScript metadata invariants are tested”**, not “the WebAssembly allocator is formally verified.”
- Keep `CLM-009`, `CLM-206`, and `CLM-220` at their existing evidence levels until their explicit promotion conditions are satisfied.
