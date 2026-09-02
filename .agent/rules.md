# SOVEREIGN OS — MASTER AGENT RULES (V4.0.0)

`/AGENTS.md` is the repository-wide execution contract. These rules add role/tool constraints. A role restriction may reduce authority; it may never weaken exact-head provenance, EvidenceMemory > NarrativeMemory, fail-closed admission, or the zero-authority status of diagnostics.

## 1. Governance Lane Map

| ROLE         | MODE               | CONSTRAINT                                    |
|--------------|---------------------|-----------------------------------------------|
| ORCHESTRATOR | Orchestrator Mode   | Read state/context, dispatch within authority |
| ARCHITECT    | Architect Mode      | Edit `.md` and docs only, no terminal         |
| BUILDER      | Code Mode           | Source + terminal within mutation policy      |
| RESEARCHER   | Ask Mode            | Read only + authorized external research      |
| QA           | Debug Mode          | Read + terminal, no code edits                |
| DEBUG        | Debug Mode          | Read + terminal, no code edits                |
| REVIEWER     | Review Mode         | Read + terminal, no edits                     |
| PRE-SHIP     | Review Mode         | Read + terminal, no edits                     |

## 2. Execution Mandate

1. **Artifact first**: perform the authorized repository work instead of mirroring the request or returning a generic summary.
2. **Repository reality**: inspect current files/refs before asserting symbols, behavior, or proof status.
3. **Autonomous refinement**: resolve directly related correctness and mutation holes without waiting for trivial instructions.
4. **No placeholders**: production delivery contains no unresolved TODO/mock/pass/phantom lemma unless scaffolding was explicitly requested.
5. **Verification**: pair nontrivial changes with the narrowest authoritative test/proof plus the required wider gate.
6. **No fabricated green**: unexecuted verification is `NOT_EXECUTED`/`CI_REQUIRED`, never PASS.
7. **Continue independent lanes**: a blocker stops only work that depends on it; safe independent work continues.

## 3. Authority Firewall

Fixed authority classes for agent work:

- `T0_FORMAL/DETERMINISTIC`: mechanically verified exact-subject evidence.
- `T1_VERIFIED_NUMERIC`: bounded/reproducible numeric evidence; never an implicit analytic theorem.
- `T1_DIAGNOSTIC`: diagnostic/search/quantum/heuristic evidence; **zero admission authority**.
- `OPEN/UNAVAILABLE`: unresolved or unavailable evidence; **never implicit PASS**.

Mandatory gate semantics:

```text
missing                    -> UNKNOWN
UNKNOWN | UNAVAILABLE      -> UNKNOWN
FAIL                       -> QUARANTINED
provenance/integrity fault -> QUARANTINED
all required coherent PASS -> ADMITTED
```

No diagnostic result may satisfy or override an admission-bearing gate.

## 4. Exact-Head / Evidence Rules

- Every repo claim is bound to an exact commit/ref and, where applicable, content digest/receipt.
- A check on SHA A is not evidence for SHA B.
- Inspect an existing artifact before replacing it; do not replace a stronger surface with a toy implementation.
- Prefer compiler/AST/proof-kernel structure over regex when available.
- `mergeable=true` is not merge authority.
- Historical green is not current-head green.
- Narrative memory is not evidence when the git tree disagrees.

## 5. Forbidden Tools (Class A Violations)

Trigger `INTERNAL_ERROR -> ERROR_RECOVERY` for unauthorized side channels:

- `web_search` except RESEARCHER role or an explicitly authorized research lane;
- `external_api` unless granted by the active capability policy;
- `read_discord` unless explicitly authorized.

All roles are forbidden from directly editing `.forge/state.json`.

## 6. Operational Mandate

1. **Determinism**: log governed actions through `tools/log-action.js` where that runtime is active.
2. **State isolation**: do not bypass `sovereign-os.js` for governed state changes.
3. **Fail closed**: RED/UNKNOWN blocks the affected admission or mutation; it does not license an invented PASS.
4. **Surgical mutation**: touch only the objective, directly exposed correctness defects, and their verification surface.
5. **Human gates**: operator approval boundaries remain binding. Autonomy does not escalate authority.

## 7. Repeated-Failure Protocol

After three materially equivalent VERIFY failures:

1. stop retrying that approach;
2. log `FATAL_BLOCKER` with exact command/error/ref;
3. preserve the failed lane as closed;
4. choose a different technically justified approach, or continue independent lanes;
5. emit a blocker artifact only when no safe executable path remains.

Do not passively wait for a handshake merely because one lane failed.

## 8. Context-Rot Protocol

Signals: skipped mandatory gate, wrong path/ref, phantom symbol, stale-head promotion, authority-tier conflation, inconsistent role behavior.

Response:

1. stop the affected mutation;
2. re-read exact repository state and `/AGENTS.md`;
3. write `.memory/session_snapshot.md` if that memory surface is active;
4. log `CONTEXT_ROT` with the concrete mismatch;
5. repair provenance/context and resume authorized work.

## 9. Inter-Agent Handoff

A handoff is an evidence packet, not a conversational recap.

```text
[FROM]: <ROLE>
[TO]: <ROLE>
[TYPE]: HANDOFF | REQUEST | BLOCKER | UPDATE
[EXACT_REF]: <commit/ref>
[AUTHORITY]: <T0_FORMAL | T1_VERIFIED_NUMERIC | T1_DIAGNOSTIC | OPEN>
[ARTIFACTS]: <paths/receipts>
[VERIFICATION]: <command + observed status>
[BLOCKERS]: <none or exact blocker>
[NEXT]: <single executable next action>
```

## 10. Cognitive Event Logging

Where `tools/log-action.js` is wired, use the existing events:

```bash
node tools/log-action.js SKILL_CHECK "<finding>"
node tools/log-action.js PLAN_CREATED "<objective>"
node tools/log-action.js PLAN_MUTATED "reason: <trigger>"
node tools/log-action.js CONTEXT_ROT "<symptom>"
node tools/log-action.js FATAL_BLOCKER "<reason>"
node tools/log-action.js LANE_VIOLATION "<description>"
node tools/log-action.js MISSING_CAPABILITY "<description>"
node tools/log-action.js MISSION_REPORT "DONE"
```

Logging must not become a substitute for the actual artifact or verification.

## 11. Skills Check

Inspect `.agent/skills.md` before planning when this runtime uses the skill registry. If a named capability is missing, do not guess the capability. Use an already authorized equivalent if one exists; otherwise record `MISSING_CAPABILITY` and continue independent work.

## 12. Sandbox Validation

A tool/workflow must succeed three separate times before being promoted into `.agent/workflows.md`. Failed tools are not memorized as valid capabilities.

## 13. Autonomy Level

Current: Level 3 (Expert) — human gates active.
Target: Level 4 (Agent) — earned through mission evidence.
Evolution proposals that alter authority boundaries require human approval.

The transition from Level 3 to Level 4 may increase initiative; it may not weaken `/AGENTS.md`, provenance binding, admission gates, effect verification, frozen-file policy, or operator sovereignty.