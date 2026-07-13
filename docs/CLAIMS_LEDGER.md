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

A claim's **Status** is a contract it must satisfy. Verification is not "someone read it" —
it is "the artifact exists and matches." A claim is Verified because it **satisfies its
contract**, not because it was reviewed.

| Status | Required evidence | Fails if… |
|--------|-------------------|-----------|
| **Verified** | A direct artifact with an immutable reference: `file:line @commit`, a theorem, or an experiment ID. | The artifact cannot be located, no longer matches the claim, or the reference is ambiguous. |
| **Derived** | A logical consequence of ≥1 Verified claims, with those dependencies listed by ID. | Any dependency is downgraded, or the inference is not formally justified. |
| **Proposed** | A design spec or experimental protocol only. | It is presented as completed work or as empirical fact. |
| **Removed** | Unsupported, contradictory, or obsolete. | It is reintroduced without new evidence. |

**Evidence Quality (EQ)** is graded independently of Status — it rates *how* the evidence
was established, not *whether* the claim holds:

- **EQ-A** — mechanically verifiable (passing test, cryptographic construction, or formal proof).
- **EQ-B** — reproducible empirical measurement.
- **EQ-C** — manual inspection (a human read the artifact and confirmed the logic).
- **EQ-D** — proposal only; no evidence yet.

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

All rows below were confirmed by reading the cited artifact at commit `db9d8a0`. None required
downgrading — every candidate held.

| Claim ID | Claim | Status | EQ | Dependencies | Evidence |
|----------|-------|--------|----|--------------|----------|
| CLM-001 | Deterministic, float-free canonical serialization envelope (`canon`, `payload_digest`, `EnvelopeChain`); Unicode NFC normalization was **removed** so the Python path is byte-identical to the TS T0 path (Codex fix 1). | Verified | A | — | `Code: sovereign-omega-v2/python/canonical_envelope.py:32-79 @db9d8a0` (NFC-removal rationale documented at lines 38-42) · `Test: sovereign-omega-v2/python/tests/test_canon_equivalence.py` |
| CLM-002 | The TS and Python paths produce **identical digests**; a decomposed-Unicode vector proves neither path normalizes (digest `a2b964dcb6a519031c512c9714172760861f305c9b7050917e4378d8449854fd`). | Verified | A | — | `Test: sovereign-omega-v2/test/vectors/canon-vectors.json:115-122` (vector "decomposed unicode (NFC-divergent…)") · `Test: test/unit/canon-equivalence.test.ts:52` · `Test: python/tests/test_canon_equivalence.py:82-92` |
| CLM-003 | Hash-chained, tamper-evident envelope: `prev_hash` links envelope N→N-1, `seq` is a monotonic per-process counter (never a timestamp), genesis `prev_hash` = GENESIS (64 zeros). | Verified | A | — | `Code: sovereign-omega-v2/python/canonical_envelope.py:82-115 @db9d8a0` · `Test: python/tests/test_canon_equivalence.py:130-134` (field-set + `canon_version` asserted) |
| CLM-004 | Dual-emit on the **live path**: legacy hashes stay byte-identical and the canonical envelope is additive; the collaboration `request_digest` covers the full field set (objective, mode, live, generation, autonomous, max_agents, memory_context) (Codex fix 2). | Verified | C | — | `Code: sovereign-omega-v2/python/bridge.py:362-376 @db9d8a0` (`_platform_run_collaboration`) · `Code: sovereign-omega-v2/python/bridge.py:576-600` (governed `/claude` path; legacy `request_hash`/`response_hash`/`chain_hash` preserved at 597-599, `envelope` additive at 600) |
| CLM-005 | Frozen-file hash integrity gate: three constitutional files are pinned by SHA-256 and the gate exits non-zero on mismatch. Ran it at `db9d8a0` → exit 0. | Verified | A | — | `Code: sovereign-omega-v2/scripts/verify-hashes.mjs:17-19,46 @db9d8a0` · pins match CLAUDE.md "Constitutional Files" table (gate.py/dna.py/router.py) |
| CLM-006 | Cross-language **independent replay** (executor ≠ verifier): a Python emitter, a Node re-chainer, and a Rust re-chainer independently re-derive the chain. | Verified | C | — | `Code: verifiable/cross_language/verify.sh:10-20 @db9d8a0` (runs `emit_fixture.py` → `rechain.mjs` → `rust_rechain/…/rechain stages.json`); `rechain.mjs` and `rust_rechain/` present |
| CLM-007 | Server-side provider gate + model provenance in the audit record: a client cannot force a paid backend via the request body, and the model actually used is reported back to callers (Codex fixes 5/7). | Verified | C | — | `Code: supabase/functions/chat/index.ts:11-13,45-59,114-118 @db9d8a0` · `Code: packages/shared/lib/inference-router.ts:176-178,216-217` (prefers server-reported model) |
| CLM-008 | Determinism test discipline: determinism tests run the subject ≥3 times and assert byte-identical output. | Verified | A | — | `Spec: sovereign-omega-v2/.claude/rules/testing.md` (3-run byte-identical rule) · `Test: test/unit/canon-equivalence.test.ts:61-63` · `Test: python/tests/test_canon_equivalence.py:66-67` |

**Downgraded / not verified:** none — every Verified candidate was located and matched its claim.

---

## Derived (Tier B)

Logical consequences of Verified rows. No benchmark numbers.

| Claim ID | Claim | Status | EQ | Dependencies | Evidence |
|----------|-------|--------|----|--------------|----------|
| CLM-101 | **Reproducibility** — a governed call's provenance can be regenerated byte-identically by an independent party. | Derived | A | CLM-002, CLM-006, CLM-008 | Follows: identical cross-language digests (CLM-002) under enforced 3-run determinism (CLM-008), independently re-chained (CLM-006). |
| CLM-102 | **Traceability** — every audited step carries request/response digests and a chain link back to genesis. | Derived | A | CLM-003, CLM-004 | Follows: the hash-chained envelope (CLM-003) is emitted on the live path alongside legacy hashes (CLM-004). |
| CLM-103 | **Measurement repeatability** — the substrate's own integrity is re-checkable on demand and fails loudly on drift. | Derived | A | CLM-005, CLM-008 | Follows: the frozen-file gate (CLM-005) plus mandated repeat-run determinism (CLM-008). |
| CLM-104 | **Architecture-independence of the digest** — the digest depends only on canonical bytes, not on language runtime or Unicode form. | Derived | A | CLM-001, CLM-002 | Follows: NFC-free canonicalization (CLM-001) yields identical TS/Python digests including decomposed input (CLM-002). |

---

## Proposed (Tier C)

Design specs / protocols only. No implementation yet — must not be presented as completed work.

| Claim ID | Claim | Status | EQ | Dependencies | Evidence |
|----------|-------|--------|----|--------------|----------|
| CLM-201 | Online prefix auditing (AgentForesight-style) over the live chain. | Proposed | D | — | `Spec: (design only — no implementation in repo)` |
| CLM-202 | MRM / SABER governance layer. | Proposed | D | — | `Spec: (design only)` |
| CLM-203 | Phase 2 — KMS Ed25519 signing over `envelope_hash` + client-principal binding. | Proposed | D | CLM-003 | `Code: canonical_envelope.py:114` marks `signature = None  # Phase 2`; not yet implemented. |
| CLM-204 | Phase 3 — public transparency log of envelope hashes. | Proposed | D | CLM-203 | `Spec: (design only)` |
| CLM-205 | Phase 4 — offline verifier CLI. | Proposed | D | CLM-006 | `Spec: (design only)` |
| CLM-206 | ECDist as a graph-distance over provenance + evidence graphs (implementation). | Proposed | D | — | `Spec: (design only — no ECDist code in repo)` |
| CLM-207 | ECDist satisfies metric axioms (non-negativity, identity, symmetry, triangle inequality). | Proposed | D | CLM-206 | `Proof: (pending — no formal proof in repo yet)` |

---

## Removed (Tier D)

Struck as unsupported, fabricated, or contradictory. Do not reintroduce without new evidence.

| Claim ID | Struck item | Reason |
|----------|-------------|--------|
| CLM-301 | AgentTrace Hit@1 = 94.9% | No dataset, run, or code in repo produces this number. |
| CLM-302 | Aegis-Bench F1 table | No benchmark harness or results artifact exists. |
| CLM-303 | AgentForesight +19.9% improvement | No experiment or baseline in repo. |
| CLM-304 | 550-scenario dataset | Fabricated; no `DATA-*` artifact. |
| CLM-305 | ~10k trajectories corpus | Fabricated; not present. |
| CLM-306 | AFTraj-2K dataset | Fabricated; not present. |
| CLM-307 | Yatav Inc. corporate study | Unverifiable third-party claim; no source. |
| CLM-308 | SABER empirical eval across GPT-5 / Claude Opus 4.6 / etc. | Unverifiable; no eval code or logs; models not run. |
| CLM-309 | IDS / BiLSTM / W-Functional / NASA-telemetry / STM32 identity splice | Not this project; grounds nothing in this tree (see identity resolution). |
| CLM-310 | Sleep-paralysis "HD" etymology | Non-technical, unsupported narrative origin story. |

---

## Terminology resolution

- **ERD** — the theoretical phenomenon (Evidence–Reality Divergence): the object of study.
- **ECDist** — the primary *operational* metric: distance between claimed and evidenced state
  over provenance + evidence graphs.
- **HD** — a historical, sequence-based predecessor metric, retained **only** for prior-literature
  comparison; not the operational metric.

This disambiguates from the repo's separate **"Hallucination Delta" (HD)**, which belongs to the
`swarm_os` Kaggle metacognition track — a parallel, zero-code-coupled project, not this
provenance line (`docs/AUDIT_FINDINGS.md:165-169`, finding H-04). The two HDs are unrelated.

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

This ledger applies the manuscript's own thesis to itself. Every assertion above carries its
**origin** (Claim ID), **dependencies** (dependency IDs), **evidence** (immutable artifact
reference), **epistemic status** (the contract it satisfies), and a **reproducibility reference**
(commit `db9d8a0`) — self-similar to how the `ExecutionEnvelope` records `request_digest`,
`response_digest`, `prev_hash`, and `seq` for every agent step. The manuscript does not merely
*describe* a metrology of cognitive integrity; by structuring its own claims this way, it
*embodies* one. A reviewer can falsify any Verified row by dereferencing its `file:line @commit`
and checking that the artifact still says what the claim says. If it does not, the row fails its
contract and must be downgraded — the same failure discipline the substrate applies to itself.
