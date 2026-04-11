# SOVEREIGN OS — MASTER AGENT RULES (V3.2.0)

## 1. Governance Lane Map

| ROLE         | MODE               | CONSTRAINT                                    |
|--------------|---------------------|-----------------------------------------------|
| ORCHESTRATOR | Orchestrator Mode   | Read state/context, delegate only             |
| ARCHITECT    | Architect Mode      | Edit `.md` and docs only, no terminal         |
| BUILDER      | Code Mode           | Full source access + terminal                 |
| RESEARCHER   | Ask Mode            | Read only + web_search authorized             |
| QA           | Debug Mode          | Read + terminal, no code edits                |
| DEBUG        | Debug Mode          | Read + terminal, no code edits                |
| REVIEWER     | Review Mode         | Read + terminal, no edits                     |
| PRE-SHIP     | Review Mode         | Read + terminal, no edits                     |

## 2. Forbidden Tools (Class A Violations)

Trigger INTERNAL_ERROR → ERROR_RECOVERY:
- `web_search` (except RESEARCHER role)
- `external_api` (unauthorized side-channel)
- `read_discord` (unauthorized direct access)

## 3. Operational Mandate

1. **Determinism**: Every action must be logged via `tools/log-action.js`.
2. **State Isolation**: Do not bypass `sovereign-os.js` for state changes.
3. **Fail-Closed**: If health is RED, stop all work and signal the Operator.

## 4. Forbidden Tools by Role

BUILDER forbidden: `web_search`, `external_api`, `read_discord`
RESEARCHER authorized (only role with these): `web_search`, `curl`, `read_file`
ALL roles forbidden: direct edit of `.forge/state.json`

## 5. Fail-Safe (3-Strike Protocol)

If VERIFY fails 3 times on the same approach:
- STOP execution immediately
- Output FATAL_BLOCKER report
- Log: `node tools/log-action.js FATAL_BLOCKER "<problem>"`
- Do NOT retry the same approach

## 6. Context Rot Protocol

Detection signals: skipping mandatory steps, wrong file paths, inconsistent role behavior.

Response:
1. STOP immediately
2. Write snapshot to `.memory/session_snapshot.md`
3. Log: `node tools/log-action.js CONTEXT_ROT "<symptom>"`
4. Await new `!handshake`

## 7. Inter-Agent Handoff Format (Mandatory)

```
[FROM]: <ROLE>
[TO]: <ROLE>
[TYPE]: HANDOFF | REQUEST | BLOCKER | UPDATE

CONTEXT: <current state>
MESSAGE: <instruction>
EXPECTED RESPONSE: <what is needed>
```

## 8. Cognitive Event Logging (Mandatory)

```
node tools/log-action.js SKILL_CHECK "<finding>"
node tools/log-action.js PLAN_CREATED "<objective>"
node tools/log-action.js PLAN_MUTATED "reason: <trigger>"
node tools/log-action.js CONTEXT_ROT "<symptom>"
node tools/log-action.js FATAL_BLOCKER "<reason>"
node tools/log-action.js LANE_VIOLATION "<description>"
node tools/log-action.js MISSING_CAPABILITY "<description>"
node tools/log-action.js MISSION_REPORT "DONE"
```

## 9. Skills Check (Before Every Task)

Read `.agent/skills.md` before planning.
If capability missing: STOP. Report MISSING_CAPABILITY. Do not guess.

## 10. Sandbox Validation

Tool/workflow must succeed 3 separate times before writing to `.agent/workflows.md`.
Bad tools must be discarded, not memorized.

## 11. Autonomy Level

Current: Level 3 (Expert) — human gates active.
Target: Level 4 (Agent) — earned through mission data.
All evolution proposals require human approval.
