# AEGIS Audit Findings
## Premortem Analysis — 2026-05-17
## Method: Assume failure. Find the kill vector. Reassemble better.

Findings ranked by epistemic tier. T0 = must resolve before any deployment.
T1 = must resolve before production. T2 = resolve before Gumroad listing.

---

## T0 FINDINGS — Critical (resolve before deployment)

### F-01 · ~~TGCS Invariant Violation: `time.monotonic()` in determinism-critical path~~
**File:** `sovereign-omega-v2/python/tgcs_afse.py`
**Fix applied:** Replaced `_cycle_times: List[float]` (wall-clock timestamps) with
`_cycle_seqs: List[int]` (sequence numbers). Variance now measures sequence-number
regularity — deterministic and reproducible across runs regardless of OS scheduling.
**Status:** ✅ RESOLVED — commit 79647e8

### F-02 · ~~AFSE R² hardcoded to 0.98 — stress test proves nothing~~
**File:** `sovereign-omega-v2/python/tests/stress_test.py`
**Fix applied:** Replaced hardcoded `afse_r2 = 0.98` with live `AFSEController` instance.
Also fixed the broken linear distributed-model R² computation (produced R²≈0 for constant
throughput) with a throughput-stability coefficient: R² = 1 − σ²/μ². Smoke test R²=0.9977.
**Status:** ✅ RESOLVED — commit 79647e8

### F-03 · ~~CoreMatrix M2 offset collision for same-length verifier results~~
**File:** `sovereign-omega-v2/python/core_matrix.py`
**Fix applied:** M2 offset now incorporates sequence: `(sequence * 8 + len(verifier_result)) % (len(state) // 8)`.
**Status:** ✅ RESOLVED — commit 79647e8

### F-04 · ~~GradientAnchor zero-tolerance "hard abort" doesn't abort~~
**File:** `sovereign-omega-v2/python/gradient_anchor.py`
**Fix applied:** When `anchor.tolerance_fixed == 0` and `drift_fixed > 0`, raises
`RuntimeError` instead of silently snapping. Enforces CLAUDE.md invariant.
**Status:** ✅ RESOLVED — commit 79647e8

### F-05 · ~~Bridge race condition: CoreMatrix not ready before HTTP server accepts requests~~
**File:** `sovereign-omega-v2/python/bridge.py`, `core_matrix.py`
**Fix applied:** Added `_ready: threading.Event` to CoreMatrix, set in `start()`. Bridge
calls `matrix.wait_ready(timeout=5.0)` before `serve_forever()`.
**Status:** ✅ RESOLVED — commit 79647e8

### ~~F-06 · Constitutional files declared frozen but do not exist~~
**File:** `sovereign-omega-v2/CLAUDE.md` + `scripts/verify-hashes.mjs`
**Fix applied:** All three constitutional files authored and committed:
  - `python/dna.py` — genome/schema: canonical type definitions (EventClass, GateSignal,
    EventSchema, SCHEMAS, VERIFIER_MAP, INVARIANTS, TELEMETRY_FIELDS)
  - `python/gate.py` — mutation authority: sliding-window gate signal tracker (WINDOW_SIZE=32,
    MIN_ACCEPTANCE_RATE=0.5), mirrors TypeScript Bernstein gate
  - `python/router.py` — execution router: deterministic verifier-byte dispatch, fail-closed
    for unknown bytes, schema size bounds, rolling audit trail
  Hashes updated in CLAUDE.md, sovereign-omega-v2/CLAUDE.md, and verify-hashes.mjs.
  `node scripts/verify-hashes.mjs` → exit 0 (all files present and hash-verified).
  Python smoke test of all three: ALL CONSTITUTIONAL FILES: PASS
  bridge.py now imports and integrates gate + router: _register_handlers() seals
  the router before serve_forever(); /gate_signal feeds gate.record_signal();
  /event routes through router.route(); /telemetry includes gate + router telemetry.
**Status:** ✅ RESOLVED — commit 315fb2c

---

## T1 FINDINGS — Important (resolve before production)

### F-07 · ~~CoreMatrix M1 wraps silently, overwriting state without signalling~~
**File:** `sovereign-omega-v2/python/core_matrix.py`
**Kill vector:** At ~80k eps (this machine), M1 wraps every ~670 seconds during the 12h
stress test. State is overwritten silently in a circular log with no era marker.
**Fix applied:** Added `_era: int` counter and `_m1_era_capacity` threshold. Each time
`sequence % _m1_era_capacity == 0`, `_era` increments and fires `M1_ERA_WRAP` event so
the operator knows circular overwrite is occurring. Circular behavior is now explicit.
**Status:** ✅ RESOLVED — commit (this session)

### F-08 · PGCS disk I/O detection uses cumulative swap counters (not deltas)
**File:** `sovereign-omega-v2/python/pgcs.py:302`
**Kill vector:** `psutil.swap_memory().sin/sout` returns cumulative page swap counts since
boot, not incremental. The code captures a baseline at init (correct) and computes a delta
(correct approach), but `sin/sout` values are in **pages** on Linux, not bytes. The page
size (typically 4096 bytes) is never applied. On a system with pre-existing swap activity,
any swap since boot inflates the delta.
**Fix applied:** `import resource` added to pgcs.py. `_read_disk_io` now returns
`(swap.sin * resource.getpagesize(), swap.sout * resource.getpagesize())`. Fields renamed
`disk_page_ins/outs` → `disk_swap_bytes_in/out` to reflect byte semantics. `passes_criterion`
unchanged (zero-equality works for both units). Python smoke test PASS confirmed post-fix.
**Status:** ✅ RESOLVED

### F-09 · ~~Epoch snapshot captures 1KB of 2GB M1 region — not representative~~
**File:** `sovereign-omega-v2/python/core_matrix.py`
**Fix applied:** `get_epoch_snapshot()` now samples 256 bytes from four evenly-spaced
positions across the M1 region (offsets 0, 25%, 50%, 75%) plus sequence + era bytes.
Total: 1036 bytes representative of the full 2GB state.
**Status:** ✅ RESOLVED — commit (this session)

### F-10 · ~~EpochFailsafe RECOVERING state does not gate new event processing~~
**File:** `sovereign-omega-v2/python/core_matrix.py`
**Fix applied:** `process_event()` now gates on `{FROZEN, RECOVERING}` (both non-nominal
states). Returns `{'status': 'RECOVERING', ...}` during recovery so callers know to
discard the event and retry after state normalises.
**Status:** ✅ RESOLVED — commit (this session)

---

## T2 FINDINGS — Should fix before Gumroad listing

### F-11 · ~~callDashScope() has no timeout~~
**File:** `packages/shared/lib/dashscope.ts`
**Fix applied:** `signal: AbortSignal.timeout(60_000)` added to fetch call.
**Status:** ✅ RESOLVED — commit 90e8d26

### F-12 · ~~Bridge URL hardcoded to localhost~~
**Files:** `cockpit/src/lib/telemetry.ts`, `cockpit/src/App.tsx`
**Fix applied:** `VITE_BRIDGE_URL` env var with `localhost:7890` default.
**Status:** ✅ RESOLVED — commit 90e8d26

### F-13 · ToolkitFooter hardcodes Vercel URLs that don't exist yet
**File:** `packages/shared/components/ToolkitFooter.tsx:2-4`
**Kill vector:** All three cross-product links 404 until Vercel deployments are live.
**Fix:** Update with real Vercel URLs after deployment. No code change needed now.
**Status:** DEFERRED — update post-deployment

### F-14 · hub ProductCard has no deployUrl — "Launch app" buttons are dead
**File:** `hub/src/App.tsx` — ProductCard instances have no `deployUrl` prop
**Kill vector:** Hub landing page "Launch app" buttons don't link anywhere.
**Fix:** Pass real Vercel URLs to each ProductCard after deployment.
**Status:** DEFERRED — update post-deployment

### F-15 · ai_prompts/ is leftover from game project — not part of AEGIS
**Directory:** `ai_prompts/` (ARCHITECT.md, BUILDER.md, ART_DIRECTOR.md, NARRATOR.md, AGENT_BOOT.md)
**Finding:** These are Godot game development orchestration prompts for SYSTEM_REBUILD.
They reference a "Game Bible" and GameState autoload not present in the AEGIS monorepo.
**Fix:** Move to `godot_client/ai_prompts/` or leave — no impact on builds or products.
**Status:** INFORMATIONAL

---

## HOLONIC FINDINGS

### ~~H-01 · PGCS _trigger_compression() is a no-op stub~~
**File:** `sovereign-omega-v2/python/pgcs.py:296`
**Fix applied:** `_trigger_compression()` now performs real memory reduction in three steps:
  1. `gc.collect(2)` — full Python GC sweep across all three generations (frees cyclic garbage)
  2. `ctypes.CDLL('libc.so.6').malloc_trim(0)` — returns freed malloc pages to OS on Linux,
     reducing RSS immediately before kernel swap pressure; silently skips on non-Linux
  3. Writes typed compression-marker to ring buffer (`0xC0 | compressions_count | objects_freed`)
     so audit trail remains continuous even when no external data is available to compress
  Also added constitutional file test suite: `python/tests/test_constitutional.py`
  104/104 assertions PASS across dna.py, gate.py, router.py + SHA256 hash verification.
  P2 crash-loop validation: 629k events, 1000 crash simulations, all 5 criteria PASS.
**Status:** ✅ RESOLVED — this commit

### ~~H-02 · No transaction atomicity between M1, M2, M3 in CoreMatrix~~
M1/M2/M3 are called sequentially under `_lock`, but the memoryview regions had no
transactional isolation. A concurrent read of M1 during M2 execution saw torn state.
**Fix applied:** `emit_vcg_telemetry()` and `get_epoch_snapshot()` now acquire `self._lock`
before reading `_m1_region`, `_sequence`, `_epoch`, and related counters. Lock is released
before the `pgcs.snapshot()` call (which reads psutil/disk and must not hold the write lock).
RLock is used throughout so the fix is deadlock-safe. P1 smoke test: 5.15M events, PASS.
**Status:** ✅ RESOLVED — this commit

### ~~H-03 · `gate/hoeffding.ts` implements Bernstein, not Hoeffding~~
File name is a historical artifact from v1. The implementation is correct (Bernstein
anytime-valid confidence sequences per Waudby-Smith & Ramdas 2024).
**Fix applied:** Header comment at lines 4–9 of `hoeffding.ts` documents the naming
discrepancy, the Bernstein/Waudby-Smith rationale, and the legacy constraint.
**Status:** ✅ RESOLVED — annotation confirmed present

### H-04 · swarm_os and sovereign-omega-v2 are parallel, not integrated
Both are Kaggle competitors (Tarik Skalić, operator) but on different tracks:
- sovereign-omega-v2: VCG/PGCS governance proof track
- swarm_os: Hallucination Delta (HD) metacognition track

Zero code coupling. Epistemic tiers correctly separated (T0 vs T4/T5).
The CLAUDE.md non-equivalence table applies to their relationship:
*Calibration is not Truthfulness. Governance is not Alignment.*

### H-05 · No canonical ontology — semantic overload risk
**Source:** ChatGPT adversarial audit (CONFIDENCE 0.95) — 2026-05-19
**Kill vector:** Every layer introducing novel ontology → superlinear complexity growth.
Ontology governance undisciplined → impossible for collaborators to reason about.
Recursive architectures fail at interoperability and onboarding unless abstractions
are aggressively normalized.
**Fix applied:**
  - `docs/ONTOLOGY.md` — canonical glossary: every term defined once, in one place.
    Includes governance rules: one definition per term, provenance required at T0–T2,
    new terms must reduce not increase conceptual entropy, interoperability by default.
  - `docs/TRACEABILITY.md` — explicit implementation → research source chains for
    every T0–T2 component. Open provenance gaps documented as migration rule violations.
  - `HolonMetadata.provenance: readonly string[]` — Drive document IDs wired into the type.
  - `HolonMetadata.ontology_term: string` — canonical term from ONTOLOGY.md required per holon.
  - All canonical phrases updated in CLAUDE.md (root), sovereign-omega-v2/CLAUDE.md,
    types.ts, ralph-loop.ts per audit recommendation (CONFIDENCE 0.93 + 0.95).
**Theoretical synthesis confirmed:** Koestler holons + cybernetics + category-layered design +
information theory + constitutional governance + recursive knowledge graphs.
**Status:** ✅ RESOLVED — this commit

### H-06 · HolonMetadata had no provenance or ontology_term fields
**Source:** H-05 resolution audit
**Kill vector:** HolonMetadata instances could be created with no traceability to the
research corpus — silent provenance gap with no type-level enforcement.
**Fix applied:** `HolonMetadata.provenance` (Drive IDs) and `HolonMetadata.ontology_term`
(canonical ONTOLOGY.md term) added as required fields. Missing provenance is now a
TypeScript compile error, not a documentation gap.
**Status:** ✅ RESOLVED — this commit

---

## Summary

| Tier | Count | Resolved | Open |
|------|-------|----------|------|
| T0 — Critical | 6 | 6 | 0 |
| T1 — Important | 4 | 4 | 0 |
| T2 — Pre-listing | 5 | 2 | 3 (F-13, F-14 post-deployment; F-15 informational) |
| Holonic | 6 | 5 | 1 (H-04 informational) |

**Layer B Python is production-ready** — all 11 fixable findings resolved.
F-06 resolved: dna.py / gate.py / router.py authored, hashed, and verified.
F-08 (swap counter page size) should be verified on target AMD RX 570 hardware before P3.
Dead content purged: swarm_os (1199 files), godot_client (129), sovereign-omega v1 (114),
game (7), ai_prompts (5), deploy-swarm.ps1, run-swarm.ps1 — 1456 files total removed.
P1 smoke test post-sweep: 3.7M events, PGCS/TGCS/AFSE/Epoch/Anchor all PASS.

**TypeScript Layer A is sound** — Gate 8 passes 184/184 (19 test files), all invariants enforced mechanically.
Tier classification system (T0–T5) and SchemaRegistry added with full test coverage (33 new tests).
PR #16 adversarial audit (ChatGPT): all 3 review comments addressed and confirmed fixed.

**Commercial products are Gumroad-ready** — F-11 and F-12 fixed, all builds pass.
Gumroad zips regenerated: platform-picker.zip (128 KB), hook-generator.zip (127 KB), content-calendar.zip (125 KB).

---

## 2026-11-16 M1/M2/M3 V2 mathematical contract review (draft / HOLD)

This independent audit supersedes any blanket "Layer B Python is production-ready"
conclusion in the historical summary **for the M1/M2/M3 interfaces**. The
historical F-03 and F-07 fixes addressed narrower symptoms; they did not
establish the stated stronger cryptographic/statistical invariants.

- **M1 (confirmed on main):** prior payload hash was substituted for prior
  chain digest; variable payload writes overlapped fixed-stride records; near
  the end of a region a write could be skipped while acknowledging a sequence;
  append-only claims were false for the mutable ring.
- **M2 (confirmed on main):** `(2*error)>>1` equals nonnegative error; the
  claimed Bernstein LCB had no variance, n or alpha. Byte-level modulo over
  eight-byte slots allowed collisions and overlap. Router EventClass and
  verifier correctness were incorrectly conflated.
- **M3 (confirmed on main):** `expected=w_scale>>8` makes identity projection
  have nonzero "divergence" and zero-scale information destruction score 0.
- **Reconciled stacked candidate semantics:** M1 retains #806's transitive SHA-256(prev_digest || SHA-256(payload)) digest ring
  (NOT event storage). M2 records pointwise error and reserves the legacy LCB
  field at zero until a separately validated E4 confidence sequence exists.
  M3 reports normalized mean absolute projection distortion. All functions
  mutate caller memory under a caller-managed lock; they are not pure.
- **Checkpoint 2.1.0:** contains the actual #806-format chain digest tail and persisted calibration counters, but no
  event payloads. It states `is_replay_reconstructable=false`, and rejects
  V1 and earlier V2.0 checkpoints. This deliberately requires an explicit migration plan before
  any deployment with existing checkpoint files.
- **Not established:** replay reconstruction, authenticated external ledger,
  cryptographic checkpoint authenticity against writers, M1/M2/M3 cross-layer
  CI at actual PR HEAD, full TypeScript/Python parity, statistical anytime-valid
  coverage, safety of accepting actions in E4, or deployment readiness.
- **Remaining integration risks:** CoreMatrix mutations are not fully
  transactional across M1/M2/M3 and calibration callbacks; the projection
  leaves stale bytes after a shorter window (only active length is valid);
  the ring cannot detect substitution of all records by an attacker with
  full memory-write access. An independent reviewer must inspect these before
  any release or promotion.

**Governance:** DRAFT / HOLD_NO_ADMISSION. No merge or deployment authorized.
A passing regression test is not a formal security proof or a production receipt.

### PR #806 → #810 stacked reconciliation (2026-11-16)

- **Source of M1:** PR #806's standalone stdlib-only `m1_chain.py`, with unchanged SHA256(prev_digest || SHA256(payload)) digest format. This format binds earlier events transitively, but does not individually bind sequence or payload length to the digest. Event sequence remains in the 40-byte record header.
- **Source of M2/M3:** PR #810 fail-closed statistical gate and byte projection corrections; actual CI MUST be checked on the stacked candidate HEAD.
- **Checkpoint 2.1.0:** distinguishes newly persisted calibration counters from older 2.0.0 format, rejects all earlier versions for resume. Preservation of calibrator model state across epochs remains unproven.
- **Authorization:** review admission is not equivalent to a merge; keep DRAFT/HOLD_NO_ADMISSION until the exact-head gates and independent review approve.

### Calibration Continuation Checkpoint 2.2.0 (draft candidate, 2026-11-16)

The 2.1.0 checkpoint preserved M1 SHA-256 chain continuity and calibration **counters**, but lost actual `GradientAnchorCalibrator` dynamic state. That state includes token-specific `w_scales`, momentum `_velocities`, `cumulative_drift`, per-epoch `DriftMeasurement` records, and historical convergence conditions. **`_epoch` alone is not evidence of uninterrupted measurement history.**

The 2.2.0 draft introduces `calibration_checkpoint.py`, with lossless consecutive-identical-epoch RLE, exact token identity/tolerance validation, Q16.16 momentum replay and continuity checks from trusted genesis, exact reconstruction of all historical measurements, monotonic epoch bounds, and a configurable maximum decoded measurement count (default 1,000,000) to limit untrusted checkpoint expansion. Checkpoint save/load now rejects an incomplete calibration snapshot on a real `CoreMatrix`, validates before applying any M1 slot, and rejects 2.1.0 and earlier checkpoint formats. Chain-only test fixtures without a calibrator are explicitly marked as **not** preserving calibration.

**These properties remain CLAIMED IN DRAFT pending the exact-head CI result.** Even after passing tests, this is an unkeyed local checkpoint, *not* proof of authenticated provenance, remote durability or immutable event replay. Full `CoreMatrix.process_event` transactionality, fail-safe state recovery, and M2/M3 arena restoration remain open. Keep **DRAFT / HOLD_NO_ADMISSION** and do not merge or deploy.


### Calibration epoch preflight and committed-callback state (draft, 2026-11-16)

**Observed issue:** the old `GradientAnchorCalibrator.calibrate_epoch` mutates individual anchor scales, velocities and measurements as it traverses the registry. A zero-tolerance anchor violation late in the registry raises after earlier anchors have already been mutated. `CoreMatrix.process_event` also previously incremented sequence and entered the M1 digest ring before calling calibration, which could expose a committed sequence with an incomplete epoch.

**Draft corrective mechanism:** `prepare_epoch` computes an entire epoch in temporary maps and rejects hard-abort failures with zero mutation; `commit_epoch` checks the originating epoch/scales/velocities and installs the batch. `process_event` validates inputs and prepares the next epoch before M1 commits. It reports `COMMITTED_CALLBACK_ERROR` if an era-boundary event callback fails after a successful M1/M2/M3 commit, instead of incorrectly implying rollback. These are mechanical local guarantees subject to the direct exact-head CI tests; **not** a proof of fully atomic event processing, external delivery or authenticated execution.

**OPEN:** M1/M2/M3, callback and external lifecycle cannot yet guarantee crash-atomic remote delivery; separately durable idempotent outbox plus explicit event-commit receipts would be needed for end-to-end exactly-once semantics. Calibrator access outside the matrix lock must be audited before concurrency claims.

### Epoch Failsafe Continuity, checkpoint 2.3.0 (draft, 2026-11-16)

**Source evidence:** `EpochFailsafeController` initializes to ACTIVE, while checkpoint 2.2.0 does not persist the controller's quarantine/frozen state, failure counter, snapshots or incident log. A restarted `CoreMatrix` can therefore silently leave a prior FROZEN/QUARANTINE state, and `process_event` formerly omitted QUARANTINE from its refusal states. This breaks the T0 fail-closed contract regardless of M1 digest continuity.

**Draft candidate:** checkpoint 2.3.0 stores `failsafe_snapshot` and its explicit presence declaration, validates a versioned full-state import with strict counters, snapshot hashes, logs, resource ceilings and target freshness before installing. A real CoreMatrix may not load a chain-only mock checkpoint; versions 1.0 through 2.2 reject without fallback. `process_event` blocks QUARANTINE, RECOVERING and FROZEN. CI extends the actual-module regression suite with frozen recovery, quarantine, partial failure counts, snapshot tampering, both buffer snapshots and negative-freshness tests.

**Critical limits:** existing exported snapshot hashes are unkeyed, so this does not authenticate a malicious writer. No full replay, immutable event archive, or production restore receipt is established. Concurrent `report_agent_failure` outside CoreMatrix's event lock and direct controller manipulation still need an independent lock-order/concurrency audit. **DRAFT / HOLD_NO_ADMISSION until exact-HEAD CI PASS.**

### HOLON composite lineage reconciliation, PR #806 → #810 → #813 (2026-11-16)

**Research merge candidate (NOT an admission receipt):** exact PR #810 head `d54284fa502b310961a475c807a7d2e51ed9990e` is the canonical source of the M1/M2/M3 contracts and checkpoint 2.3.0. Previous #813 head `c0e466bf740f5b243effeaa6caa9183ac15ac613` contains the independent five-lane Q16, causal, lattice-coherence, and NTT research updates. New reconciliation must preserve both commit histories and match exact source blob IDs recorded in `docs/holon_five_lane_integration_v3.json`. Historical V2 receipt is preserved unchanged as evidence of an earlier 2.2.0 candidate; it does **not** describe current 2.3 state.

Use an ancestry-verified merge commit with #813 and #810 as parents and retarget #813 to the named #810 draft branch, with `stacked-pr` only if the real base/HEAD comparison verifies. Preserve CI enforcement and the five-lane source files. No production checkpoint migration.

**Gates still required:** independently run M123, Python Bridge, exact NTT, Q16, Rust CL-Ψ, trusted cognitive admission, Automaton checks, PR Overlap Guard and external Appwrite status on the new composite SHA. Some overlaps with third-party draft source lanes may persist even after direct #810/#813 ancestry becomes correct; record them, do not exempt unrelated PRs or weaken policies.

**Status:** OPEN / DRAFT / HOLD_NO_ADMISSION. No assertion of deployed or merged code.
