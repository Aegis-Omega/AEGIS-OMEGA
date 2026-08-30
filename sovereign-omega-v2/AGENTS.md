# AGENTS.md — Sovereign Omega
## Execution Protocol for Claude Code and All Coding Agents

Read this file completely before executing any command or writing any code.

---

## Identity and Role

You are implementing the Sovereign Omega system — a two-layer governance runtime
consisting of a TypeScript web-facing layer and a Python hardware inference layer.
Your role is deterministic implementation against frozen contracts. You are not
designing, interpreting, or extending the architecture.

Canonical specification: docs/SOVEREIGN_OMEGA_INTEGRATED_SPEC_v2.md
Implementation brief: docs/SOVEREIGN_OMEGA_IMPL_BRIEF_Qwen.md
Vision document: docs/SOVEREIGN_OMEGA_AGI_FRAMEWORK_CONCLUDED.md
Project memory: CLAUDE.md

---

## Session Start Protocol

1. Read CLAUDE.md
2. Run: node scripts/verify-hashes.mjs (verify frozen files)
3. Identify which layer and gate you are working on
4. Read the relevant handoff doc from handoff/ before writing any code

---

## Execution Phases

### Phase 1 — Environment Setup
npm install
pip install -r requirements.txt
cp .env.example .env (fill in required values)

### Phase 2 — TypeScript Layer (8 Gates, Strict Order)

Gate 1: npm run test -- --reporter=verbose test/unit/jcs.test.ts
Gate 2: npm run test -- test/unit/sequence.test.ts
Gate 3: npm run test -- test/unit/immutable.test.ts
Gate 4: npm run test -- test/unit/reducer.test.ts
Gate 5: npm run test -- test/unit/vcg.test.ts
Gate 6: npm run test -- test/unit/gate.test.ts
Gate 7: npm run test -- test/integration/replay.test.ts test/integration/pipeline.test.ts
Gate 8: npm run test && npm run typecheck && npm run build

RULE: Failure at any gate = HALT. Report the failure. Do not proceed.

### Phase 3 — Python Layer (3 Validation Steps, Strict Order)

Step P1: python python/tests/stress_test.py --quick
Step P2: python python/tests/stress_test.py --crash-loops
Step P3: python python/tests/stress_test.py (full 12 hours — run before production)

DEPENDENCY: PGCS must pass (zero disk I/O) before P2 or P3 telemetry is meaningful.

### Phase 4 — Integration
python python/bridge.py &   (start Python bridge on port 7890)
npm run build               (TypeScript build)
vercel --prod               (deploy, only after Gate 8 and Step P1 pass)

### Phase 5 — Orchestration Setup
paperclipai onboard --yes --bind lan
/plugin marketplace add obra/superpowers
npx antigravity-awesome-skills --claude

---

## Reporting Format

After each gate or validation step, report:

GATE/STEP [identifier]: [PASSED/FAILED]
Command: [exact command run]
Result: [pass count or first error line]
Action: [PROCEED / HALT — reason]

---

## Non-Negotiable Invariants

See handoff/05_INVARIANTS.md for the complete list.
Critical subset:
- No Date.now() in TypeScript core logic
- No time.time() in Python determinism-critical paths
- No Hoeffding bounds — use Bernstein throughout
- No V4/V5 in VCG calibration
- Version mismatch = hard abort
- PGCS must pass before TGCS/AFSE telemetry is valid

---

## File Ownership

src/core/, src/event/, src/gate/, python/core_matrix.py: T0 — bug fixes only
src/verifier/, src/calibration/, python/pgcs.py, python/epoch_failsafe.py: T0/T1
src/projection/, src/pipeline/, python/gradient_anchor.py: T0/T2
paperclip/, saga/: T2 — configs and stubs
handoff/: T0 documentation — no modification without Guardian approval

---

## Frozen File Protection

gate.py, dna.py, router.py, docs/SOVEREIGN_OMEGA_INTEGRATED_SPEC_v2.md
are constitutionally frozen. The block-frozen-writes.sh hook will reject writes.
Modification requires /guardian APPROVED verdict.

---

## When You Encounter Ambiguity

1. Check docs/SOVEREIGN_OMEGA_INTEGRATED_SPEC_v2.md
2. If unresolved, check docs/SOVEREIGN_OMEGA_IMPL_BRIEF_Qwen.md
3. If still unresolved, add: // AGENT-FLAG: ambiguity at [location] — [description]
4. Report and halt. Do not silently resolve architectural ambiguities.
