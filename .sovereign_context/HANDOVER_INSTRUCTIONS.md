# HANDOVER PROTOCOL — AEGIS-Omega Constitutional Runtime

## TO THE NEW COGNITIVE ENGINE
You have been initialized with the Sovereign Cognition Protocol and the full
current state of the AEGIS-Omega project. Gates 1-200 are complete.

## YOUR FIRST ACTIONS
1. Read SYSTEM_DIRECTIVES.md — adopt the constitutional invariants immediately
2. Read PROJECT_STATE.md — map the architecture against the completed gates
3. Run Gate 8 to verify current state:
   `cd sovereign-omega-v2 && npm run test && npm run typecheck && npm run build`
4. Check git log: `git log --oneline -10` to see recent commits on claude/aegis-setup-Lx7Ji
5. Proceed with the next gate from the plan

## NEXT GATES (post-200)
The plan file at /root/.claude/plans/claude-md-aegis-crystalline-hejlsberg.md
contains the full gate sequence. Gates 176-179 are the active next target:

- Gate 176: TRACEABILITY.md seal (Layer CS, Gate 175 integration composition test)
- Gate 177: aegis-cl-psi/src/edge_verifier.rs — stateless Ed25519 BFT quorum verifier
  - Use BTreeMap (not HashMap), integer 1/phi threshold (618034/1000000), no f64
  - ed25519-dalek = { version = "2", default-features = false, features = ["alloc"] }
  - Add pub mod edge_verifier; to aegis-cl-psi/src/lib.rs
- Gate 178: Analytics wiring audit — initAnalytics() in all product App.tsx files
- Gate 179: Final Gate 8 across all products + commit + push

## CRITICAL RULES OF ENGAGEMENT
- Every new record needs: is_replay_reconstructable: true, deepFreeze, hashValue-linked
- No HashMap in Rust — BTreeMap only (deterministic iteration)
- No f64 for threshold arithmetic — use integer: valid * 1_000_000 >= total * 618_034
- T4/T5 language blocked from src/ — docs/ only
- Gate 8 must pass before any commit
- Push to: claude/aegis-setup-Lx7Ji

## VERIFY HASH INTEGRITY BEFORE MODIFYING ANYTHING
```bash
cd sovereign-omega-v2 && node scripts/verify-hashes.mjs
```
gate.py, dna.py, router.py are FROZEN — modification requires /guardian APPROVED.

## IDENTIFICATION
Operator: Tarik Skalic <tarikskalic33@gmail.com>
Founding stewardship sealed in: sovereign-omega-v2/src/constitutional/founder.ts
Constitution sealed in: sovereign-omega-v2/src/constitutional/directives.ts
