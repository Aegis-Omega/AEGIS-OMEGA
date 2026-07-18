# Claims Ledger — Metrological Calibration of Cognitive Integrity

**Status: Draft.** Manuscript claims ledger for the ECD / ERD / execution-provenance line of work.
Anchor commit: `db9d8a0` (branch `claude/slack-session-yyw7h6`).

This ledger is the manuscript-facing projection of the repository's own epistemic tier
system. The repo grades every construct T0–T5 (CLAUDE.md, "Epistemic Tier System" table:
T0 mechanically proven → T5 blocked worldbuilding), and enforces that grading in code:
`sovereign-omega-v2/src/constitutional/reduction.ts` `admitAbstraction()` (line 114) refuses
to admit any abstraction whose record lacks a `primitive_mapping` (line 53) and
`epistemic_tier` (line 56), and hard-blocks T4/T5 (lines 119–124). The ledger below applies
the same discipline to prose: each manuscript assertion is bound to a falsifiable evidence
contract, not to reviewer opinion.

---

## Evidence contracts

Each claim carries two orthogonal grades. **Status** is the epistemic *kind* of the claim.
**Evidence Quality (EQ)** is the *strength* of its supporting evidence. They are independent
axes: a claim's status says what sort of thing it is; its EQ says how convincingly a reviewer
can reproduce the backing.

**Status legend:**

| Status | Meaning |
|--------|---------|
| **Verified** | Established directly by evidence. |
| **Derived** | Logical consequence of verified evidence. |
| **Proposed** | Design or research hypothesis. |
| **Removed** | Explicitly rejected. |

**Evidence Quality legend (strength / reproducibility axis):**

| EQ | Meaning |
|----|---------|
| **EQ-A** | Independently reproducible — a reviewer can reproduce the result directly from the cited artifact (a passing test, a cryptographic construction, a formal proof, or a runnable script such as `verify.sh`). |
| **EQ-B** | Strong but incomplete evidence — the mechanism is confirmable by inspection, but no dedicated mechanical check pins it. |
| **EQ-C** | Limited supporting evidence — a partial or indirect indication only. |
| **EQ-D** | Speculative — no evidence yet. |

**Orthogonality rule — EQ never compensates for tier.** A high EQ cannot upgrade a weak
status. In particular, **`Proposed + EQ-A` and `Proposed + EQ-B` are prohibited**: a Proposed
claim is EQ-C at best and normally EQ-D, because "reproducible evidence for a hypothesis that
is not yet built" is a contradiction. Verified claims should reach EQ-A/EQ-B; a Verified claim
that can only muster EQ-C is a signal it should be re-examined.

**Evidence type tags:** `Code: path:lines @commit` · `Test: path` · `Proof: Appendix/Theorem` ·
`Experiment: EXP-NNN` · `Dataset: DATA-NNN` · `Spec: SPEC-NNN`.

---

## What AEGIS Ω is (identity resolution)

> **AEGIS Ω is a reference measurement substrate for capturing, preserving, replaying, and
> verifying execution provenance required to compute Evidence–Claim Distance (ECDist) under
> reproducible conditions.**

The IDS / BiLSTM / W-Functional / NASA-telemetry / STM32 identities that appear in the draft
are **not this project** and must be struck (see CLM-309). They are a splice from unrelated
manuscripts and ground nothing in this tree.

---

## Verified (Tier A)

All rows below were confirmed by reading the cited artifact at commit `db9d8a0`; existence in code
is necessary but not sufficient, so EQ reflects reproducibility strength, not mere presence. No row
was status-downgraded. On the EQ axis: **CLM-004 is EQ-A** — a mechanical test
(`python/tests/test_envelope_request_digest.py`) source-pins bridge.py's hashed field set and asserts
each execution-affecting field changes `request_digest`. **CLM-007 stays EQ-B**: its client-side
provenance half is now pinned by `test/shared/inference-router.test.ts`, but the server-side provider
gate lives in the Deno chat function and cannot be unit-tested without a Deno runtime (inspection-only).
CLM-006 is **EQ-A** (a runnable `verify.sh` reproduces it).

| Claim ID | Claim | Status | EQ | Depends on | Evidence | Fails if… |
|----------|-------|--------|----|------------|----------|-----------|
| CLM-001 | Deterministic, float-free canonical serialization envelope (`canon`, `payload_digest`, `EnvelopeChain`); Unicode NFC normalization was **removed** so the Python path is byte-identical to the TS T0 path (Codex fix 1). | Verified | A | — | `Code: sovereign-omega-v2/python/canonical_envelope.py:32-79 @db9d8a0` (NFC-removal rationale documented at lines 38-42) · `Test: sovereign-omega-v2/python/tests/test_canon_equivalence.py` | `canon()` reintroduces NFC/`unicodedata`, accepts a raw `float` without raising, or `payload_digest` is non-deterministic across two runs of the same payload. |
| CLM-002 | The TS and Python paths produce **identical digests**; a decomposed-Unicode vector proves neither path normalizes (digest `a2b964dcb6a519031c512c9714172760861f305c9b7050917e4378d8449854fd`). | Verified | A | — | `Test: sovereign-omega-v2/test/vectors/canon-vectors.json:115-122` (vector "decomposed unicode (NFC-divergent…)") · `Test: test/unit/canon-equivalence.test.ts:52` · `Test: python/tests/test_canon_equivalence.py:82-92` | Equivalent payloads serialized on two supported runtimes (TS `canonicalizeJCS`, Python `canon`) produce different SHA-256 digests for any shared vector, including the decomposed-Unicode one. |
| CLM-003 | Hash-chained, tamper-evident envelope: `prev_hash` links envelope N→N-1, `seq` is a monotonic per-process counter (never a timestamp), genesis `prev_hash` = GENESIS (64 zeros). | Verified | A | — | `Code: sovereign-omega-v2/python/canonical_envelope.py:82-115 @db9d8a0` · `Test: python/tests/test_canon_equivalence.py:130-134` (field-set + `canon_version` asserted) | Genesis `prev_hash` ≠ 64 zeros, `seq` does not increment by exactly 1 per emit, or altering one envelope's body leaves a later envelope's `prev_hash` unchanged. |
| CLM-004 | Dual-emit on the **live path**: legacy hashes stay byte-identical and the canonical envelope is additive; the collaboration `request_digest` covers the full field set (objective, mode, live, generation, autonomous, max_agents, memory_context) (Codex fix 2). | Verified | A | — | `Code: sovereign-omega-v2/python/bridge.py:362-376 @db9d8a0` (`_platform_run_collaboration`) · `Code: sovereign-omega-v2/python/bridge.py:576-600` (governed `/claude` path; legacy `request_hash`/`response_hash`/`chain_hash` preserved at 597-599, `envelope` additive at 600) · `Test: sovereign-omega-v2/python/tests/test_envelope_request_digest.py` (source-pins bridge.py's hashed key set to the 7-field set + asserts each field changes `request_digest`) | The collaboration `request_digest` omits any of the seven input fields (source-pinned test extracts bridge.py's hashed key set and asserts equality), or flipping any one execution-affecting field leaves `request_digest` unchanged. The additive-dual-emit half (adding the envelope changes no pre-existing legacy hash byte) remains confirmable by inspection at bridge.py:576-600. |
| CLM-005 | Frozen-file hash integrity gate: three constitutional files are pinned by SHA-256 and the gate exits non-zero on mismatch. Ran it at `db9d8a0` → exit 0. | Verified | A | — | `Code: sovereign-omega-v2/scripts/verify-hashes.mjs:17-19,46 @db9d8a0` · pins match CLAUDE.md "Constitutional Files" table (gate.py/dna.py/router.py) | Mutating one byte of `gate.py`/`dna.py`/`router.py` does not make `verify-hashes.mjs` exit non-zero, or its pins diverge from the CLAUDE.md "Constitutional Files" table. |
| CLM-006 | Cross-language **independent replay** (executor ≠ verifier): a Python emitter, a Node re-chainer, and a Rust re-chainer independently re-derive the chain. | Verified | A | — | `Code: verifiable/cross_language/verify.sh:10-20 @db9d8a0` (runs `emit_fixture.py` → `rechain.mjs` → `rust_rechain/…/rechain stages.json`); `rechain.mjs` and `rust_rechain/` present | Running `verifiable/cross_language/verify.sh` yields a non-zero exit, or the Node and Rust re-chainers derive a chain hash differing from the Python emitter's for the shared `stages.json`. |
| CLM-007 | Server-side provider gate + model provenance in the audit record: a client cannot force a paid backend via the request body, and the model actually used is reported back to callers (Codex fixes 5/7). | Verified | B | — | `Code: supabase/functions/chat/index.ts:11-13,45-59,114-118 @db9d8a0` · `Code: packages/shared/lib/inference-router.ts:176-178,216-217` (prefers server-reported model) · `Test: sovereign-omega-v2/test/shared/inference-router.test.ts` (pins the provenance half: the router records the edge function's `data.model`, not the caller's `req.model`) | A request with `provider:"openai"` while `CHAT_ENABLE_OPENAI≠"true"` reaches the paid backend instead of falling back to dashscope, or the returned `model` is not the one actually invoked. **Held at EQ-B:** the client-side provenance half is now mechanically pinned by `inference-router.test.ts`, but the server-side provider gate lives in the Deno chat function and cannot be unit-tested without a Deno runtime — it stays inspection-only at chat/index.ts:45-57. Full EQ-A needs an edge-function (Deno) test asserting a gated `provider` falls back to dashscope. |
| CLM-008 | Determinism test discipline: determinism tests run the subject ≥3 times and assert byte-identical output. | Verified | A | — | `Spec: sovereign-omega-v2/.claude/rules/testing.md` (3-run byte-identical rule) · `Test: test/unit/canon-equivalence.test.ts:61-63` · `Test: python/tests/test_canon_equivalence.py:66-67` | The determinism tests run the subject fewer than 3 times, or accept a run whose output differs byte-for-byte from the first. |
| CLM-009 | The AEGIS swarm runtime default model was `claude-fable-5` from 2026-06-10 (commit `4747755`, PR #148) to 2026-06-23 (commit `8305ec6`, PR #172); it was never the frontend code default. | Verified | A | — | `Spec: docs/transitions/2026-06-model-default.md` (full transition record) · `Code: sovereign-omega-v2/python/platform_helpers.py:20 @aae8f5c` (current canonical `claude-opus-4-8`) · `Code: packages/shared/lib/inference-router.ts:96` (frontend default was and is `claude-haiku-4-5-20251001`) · Repro: `git log --all -S"claude-fable-5"` · `git show 4747755` · `git show 8305ec6` | Pickaxe over reachable history (`git log --all -S"claude-fable-5"`) stops listing `4747755`/`8305ec6`, or those commits' diffs stop containing the quoted default flips (`claude-sonnet-4-6` → `claude-fable-5` at `4747755`; `claude-fable-5` → `claude-opus-4-8` at `8305ec6`). |

**Downgraded / not verified:** none — every Verified candidate was located and matched its claim.

---

## Derived (Tier B)

Logical consequences of Verified rows. No benchmark numbers.

| Claim ID | Claim | Status | EQ | Depends on | Evidence | Fails if… |
|----------|-------|--------|----|------------|----------|-----------|
| CLM-101 | **Reproducibility** — a governed call's provenance can be regenerated byte-identically by an independent party. | Derived | A | CLM-002, CLM-006, CLM-008 | Follows: identical cross-language digests (CLM-002) under enforced 3-run determinism (CLM-008), independently re-chained (CLM-006). | Any of CLM-002/006/008 is downgraded, or a second party re-deriving from the same inputs obtains a different chain hash. |
| CLM-102 | **Traceability** — every audited step carries request/response digests and a chain link back to genesis. | Derived | A | CLM-003, CLM-004 | Follows: the hash-chained envelope (CLM-003) is emitted on the live path alongside legacy hashes (CLM-004). | CLM-003 or CLM-004 is downgraded, or a live-path response is emitted with no `envelope` (no `prev_hash` link to genesis). |
| CLM-103 | **Measurement repeatability** — the substrate's own integrity is re-checkable on demand and fails loudly on drift. | Derived | A | CLM-005, CLM-008 | Follows: the frozen-file gate (CLM-005) plus mandated repeat-run determinism (CLM-008). | CLM-005 or CLM-008 is downgraded, or an integrity re-check passes despite a mutated frozen file. |
| CLM-104 | **Architecture-independence of the digest** — the digest depends only on canonical bytes, not on language runtime or Unicode form. | Derived | A | CLM-001, CLM-002 | Follows: NFC-free canonicalization (CLM-001) yields identical TS/Python digests including decomposed input (CLM-002). | CLM-001 or CLM-002 is downgraded, or the same canonical bytes hash differently on a third supported runtime. |

---

## Proposed (Tier C)

Design specs / protocols only. No implementation yet — must not be presented as completed work.

Per the orthogonality rule these are EQ-D (no evidence yet); none may claim EQ-A/EQ-B.
The full ECDist implementation ladder is broken out separately below.

| Claim ID | Claim | Status | EQ | Depends on | Evidence | Fails if… |
|----------|-------|--------|----|------------|----------|-----------|
| CLM-201 | Online prefix auditing (AgentForesight-style) over the live chain. | Proposed | D | — | `Spec: (design only — no implementation in repo)` | Presented as implemented, or cited as an empirical result, before code + a passing test land. |
| CLM-202 | MRM / SABER governance layer. | Proposed | D | — | `Spec: (design only)` | Presented as implemented before code lands. |
| CLM-203 | Phase 2 — KMS Ed25519 signing over `envelope_hash` + client-principal binding. | Proposed | D | CLM-003 | `Code: canonical_envelope.py:114` marks `signature = None  # Phase 2`; not yet implemented. | Any envelope emits a non-null `signature` claimed as production-verified before signing is implemented. |
| CLM-204 | Phase 3 — public transparency log of envelope hashes. | Proposed | D | CLM-203 | `Spec: (design only)` | Presented as operational before a log exists. |
| CLM-205 | Phase 4 — offline verifier CLI. | Proposed | D | CLM-006 | `Spec: (design only)` | Presented as shipped before a CLI + test exist. |

---

## ECDist implementation status (split ladder)

The draft's single "ECDist stress-test" claim conflated one thing that exists (a digest of a
structured payload) with three that do not (a graph estimator, its metric-axiom guarantees, and
production-readiness). Splitting them prevents implementation evidence from laundering theoretical
claims. Repo grepped at `db9d8a0` for `laplacian|adjacency|spectral|ecdist|graph.?distance|eigen`:
the only hits are unrelated (omega_dynamics T3 spectral-gap research, `sovereign_hd.py` attention
spectral radius, `aegis-runtime/src/semantic_graph.rs` adjacency, `dodecagonal_router` adjacency,
`constitutional_chord` fingerprint). **No ECDist graph-distance / normalized-Laplacian / spectral
$\hat{HD}$ estimator module exists.**

| Claim ID | Claim | Status | EQ | Depends on | Evidence | Fails if… |
|----------|-------|--------|----|------------|----------|-----------|
| CLM-210 | Canonical digest of a structured payload is implemented (the digest-based substrate any ECDist would build on). | Verified | A | CLM-001 | `Code: sovereign-omega-v2/python/canonical_envelope.py:76-79 @db9d8a0` (`payload_digest`) | `payload_digest` cannot digest a nested structured payload deterministically. |

The three former rows for a **graph-construction / normalized-Laplacian / spectral $\hat{HD}$ estimator**
(CLM-211), its **metric-space axioms** (CLM-212), and its **production-readiness** (CLM-213) have been
**struck** (see Removed, Tier D). No such module ever existed in the tree, and — decisively — the real
submitted metacognition metric is not a graph/spectral construct at all: the hash-pinned Kaggle lineage
(`docs/evidence/kaggle-2026/`) defines **Hallucination Delta** as `HD = |claimed − actual|`. The
Levenshtein / graph-Laplacian / spectral reformulation was fabricated in later manuscript drafts. The
real HD is recorded as CLM-220 below.

---

## Hallucination Delta — real Kaggle lineage

The genuine, externally-submitted metacognition metric — separate from the ECDist provenance line
above. Its definition is `HD = |claimed − actual|` (absolute gap between an agent's claimed correctness
and its actual correctness), taken directly from the April 2026 Kaggle submission whose archive is
hash-pinned in `docs/evidence/kaggle-2026/` (manifest.json; zip SHA-256 `517f9287…`). It is an
author-supplied external artifact under review, **not** repo-reproducible (the live multi-model runs
require the original runtime and NVIDIA NIM credentials), so it is graded **Proposed / EQ-C**: real
evidence exists and is byte-pinned, but a reviewer cannot rerun it from this tree alone.

| Claim ID | Claim | Status | EQ | Depends on | Evidence | Fails if… |
|----------|-------|--------|----|------------|----------|-----------|
| CLM-220 | Real Kaggle **Hallucination Delta**, `HD = \|claimed − actual\|`: the metacognition-track submission scores calibration as the absolute gap between claimed and actual correctness. Author-supplied external artifact under review; not repo-reproducible. | Proposed | C | — | `Experiment: docs/evidence/kaggle-2026/manifest.json` (Kaggle "Measuring Progress Toward AGI" Metacognition track, 2026-04, HD=\|claimed−actual\|, zip SHA-256 `517f9287…`) | The pinned zip's metric is not `HD=\|claimed−actual\|`, or its recorded model/ARC HD values don't match `manifest.json`. |

---

## Removed (Tier D)

Struck as unsupported, fabricated, or contradictory. Do not reintroduce without new evidence.

| Claim ID | Struck item | Reason |
|----------|-------------|--------|
| CLM-211 | Graph-construction / normalized-Laplacian / spectral $\hat{HD}$ estimator | Not the submitted metric; real Kaggle Hallucination Delta is `HD=\|claimed−actual\|` (see `docs/evidence/kaggle-2026/`), Levenshtein/Laplacian reformulation fabricated in later drafts. |
| CLM-212 | ECDist metric-space axioms (identity/symmetry/triangle inequality) of the spectral estimator | Not the submitted metric; describes the struck CLM-211 spectral estimator and grounds nothing without it (`docs/evidence/kaggle-2026/`); Levenshtein/Laplacian reformulation fabricated in later drafts. |
| CLM-213 | Spectral estimator suitable for production evaluation | Not the submitted metric; real Kaggle Hallucination Delta is `HD=\|claimed−actual\|` (see `docs/evidence/kaggle-2026/`), Levenshtein/Laplacian reformulation fabricated in later drafts. |
| CLM-301 | AgentTrace Hit@1 = 94.9% | No dataset, run, or code in repo produces this number; confirmed absent from the real Kaggle submission (`docs/evidence/kaggle-2026/`). |
| CLM-302 | Aegis-Bench F1 table | No benchmark harness or results artifact exists; confirmed absent from the real Kaggle submission (`docs/evidence/kaggle-2026/`). |
| CLM-303 | AgentForesight +19.9% improvement | No experiment or baseline in repo. |
| CLM-304 | 550-scenario dataset | Fabricated; no `DATA-*` artifact. |
| CLM-305 | ~10k trajectories corpus | Fabricated; not present. |
| CLM-306 | AFTraj-2K dataset | Fabricated; not present. |
| CLM-307 | Yatav Inc. corporate study | Unverifiable third-party claim; no source; confirmed absent from the real Kaggle submission (`docs/evidence/kaggle-2026/`). |
| CLM-308 | SABER empirical eval across GPT-5 / Claude Opus 4.6 / etc. | Unverifiable; no eval code or logs; models not run; confirmed absent from the real Kaggle submission (`docs/evidence/kaggle-2026/`). |
| CLM-309 | IDS / BiLSTM / W-Functional / NASA-telemetry / STM32 identity splice | Not this project; grounds nothing in this tree (see identity resolution). |
| CLM-310 | Sleep-paralysis "HD" etymology | Non-technical, unsupported narrative origin story. |

---

## Terminology resolution

- **ERD** — the theoretical phenomenon (Evidence–Reality Divergence): the object of study.
- **ECDist** — the primary *operational* metric of **this** provenance line: distance between
  claimed and evidenced state over provenance + evidence graphs.
- **HD (Hallucination Delta)** — the real, externally-submitted metacognition metric, defined as
  `HD = |claimed − actual|` (the absolute gap between an agent's claimed correctness and its actual
  correctness). It belongs to the `swarm_os` / Sovereign AGI OS Kaggle "Measuring Progress Toward
  AGI" Metacognition-track submission (April 2026), a parallel research lineage **zero-code-coupled**
  to this provenance line. Its evidence is hash-pinned at `docs/evidence/kaggle-2026/`
  (manifest.json; zip SHA-256 `517f9287…`) and recorded as CLM-220.

HD is **not** a normalized Levenshtein edit distance and **not** a graph-Laplacian / spectral
$\hat{HD}$ estimator — those reformulations were fabricated in later manuscript drafts and are struck
(CLM-211–213). ECDist (this project's provenance metric) and HD (the swarm_os calibration metric)
remain distinct and must not be conflated (`docs/AUDIT_FINDINGS.md:165-169`, finding H-04).

---

## The publishable narrative (5 points)

1. Measure **integrity, not outcomes** — a system can be catastrophically wrong yet perfectly
   replayable; correctness and auditability are distinct.
2. The phenomenon of interest is **ERD** — divergence between what an agent claims and what
   reality/evidence supports.
3. Operationalize it as **ECDist** — a distance computed over provenance and evidence graphs.
4. Computing ECDist **requires deterministic, auditable instrumentation** — you cannot measure
   divergence you cannot reproduce.
5. **AEGIS Ω provides that instrumentation** — the reference measurement substrate for capturing,
   preserving, replaying, and verifying execution provenance.

---

## The ledger as claim-provenance

The Claims Ledger applies the same provenance discipline to the manuscript that AEGIS Ω applies
to autonomous systems. Every scientific assertion is treated as an evidence-bearing artifact with
explicit provenance, dependency relationships, falsification criteria, and epistemic status.
Reviewers can audit the paper using the same provenance framework the paper advocates.
