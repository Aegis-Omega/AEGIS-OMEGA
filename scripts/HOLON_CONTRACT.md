# AEGIS Ω — Universal Holon Task Contract, v1 candidate

**Purpose:** make independently-built agents coordinate toward an Operator's goal through one *portable, deterministic, read-only* task-allocation preflight. This is not a new A2A/MCP protocol, evidence checker, or authorization service. It composes with the existing `scripts/agent_context.py` on AEGIS #732 and with existing evidence/receipt infrastructure (#743).

## Interface

`python3 scripts/agent_context.py --json '#734 holon coordination' > /tmp/holon-context.json`

`python3 scripts/holon_contract.py task.json /tmp/holon-context.json --json`

Exit 0 means the contract is structurally ready for **assignment review** or read-only inspection; **never** means that a model is authorized to edit, deploy, publish, pay or merge. Exit 2 means HOLD. All JSON output includes `authorization=NOT_VERIFIED`, `admission=NOT_ADMITTED`, and `claim_truth=NOT_VERIFIED` by construction. No secrets, network, model calls, or third-party packages are required.

For `contribute` or `release`, the coordinator context must explicitly report
`holon_disposition=ISSUE_ASSIGNMENT_AND_REVIEW_REQUIRED` as well as its
independently evaluated source/main/issue/CI fields. Any upstream `HOLD_*`,
`OPERATOR_ACTION_REQUIRED`, `HOLD_CLAIMED_WORK_COORDINATE`,
`REVIEW_EXISTING_PR_FIRST`, missing or unknown disposition produces
`UPSTREAM_COORDINATION_NOT_CLEAR` and exit 2. Both
`holon_blockers` and `coordination_blockers` must also be present as valid,
empty string arrays for a `contribute` or `release` review. Nonempty,
missing or malformed channels independently block readiness; the singular
`holon_disposition` can conceal simultaneous constraints. **A second module
must never silently upgrade the first module's HOLD to READY.**
This remains *advisory* task assignment, not authorization.


## Task JSON

```json
{
  "schema": "aegis.holon.task/1",
  "id": "engineering-001",
  "operator_goal": "Reduce duplicate work with independent evidence, without expanding authority",
  "domain": "engineering",
  "mode": "contribute",
  "issue": 734,
  "acceptance": [
    {"id": "C1", "criterion": "Exact-head preflight reports all simultaneous blockers"},
    {"id": "C2", "criterion": "A separate reviewer reproduces test evidence"}
  ]
}
```

`domain` accepts any portable identifier (research, engineering, medicine, linguistics, etc.); `mode` is `inspect`, `contribute`, or `release`. A shared mutation needs a concrete Issue. Dependent tasks require separate evidence, never silent closure. Unknown fields and duplicate JSON keys fail closed.

## Evidence and interoperability

1. **A2A**: use its interoperable Task/Message/Artifact transport; this task contract is extra metadata, not a replacement for A2A v1.0.0.
2. **MCP Tasks**: use `io.modelcontextprotocol/tasks` lifecycle and real OAuth/issuer identity as appropriate; the contract is independent of transport and bearer credentials.
3. **SLSA / in-toto**: use its signed provenance and artifact-verification workflows for actual build/release admission; this contract *does not produce SLSA attestations*.
4. **AEGIS #743**: reuse its receipts/claim evidence verifier; this contract does not claim to prove the claims in source artefacts.

No accepted assignment claim becomes a runtime write permission. `Agent:` commit trailers are unverified self-attribution. Operator approval, signed commits and live CI are evaluated by the existing higher-level governance path, not by boolean fields in a task manifest.

## Failure modes tested

33 stdlib tests (local Python 3.13): stale/partial PRs; missing exact head; disconnected Issues; claimed/needs-operator issue; duplicate issue matches; existing PR overlaps; unknown CI; hidden simultaneous blockers; invalid task schema; blank goals; duplicate criteria; dependencies; self-declared approval; exotic domains; duplicate JSON keys; CLI fail-closed error codes; structural digest determinism. This is a candidate replay, **not a claim that GitHub-native #732 checks passed**.

## Accepted external sources

- A2A v1.0.0: https://a2a-protocol.org/v1.0.0/specification
- MCP Tasks 2026-07-28: https://modelcontextprotocol.github.io/ext-tasks/specification/2026-07-28/tasks.html
- SLSA v1.2: https://slsa.dev/spec/v1.2/

## Future verified integration work

Actual distributed claim leasing, concurrent atomic assignment, independently authenticated agent identity, signed provenance, universal capability discovery, provider interoperability stress, and real cross-agent end-to-end tasks remain outside v1 scope. Do not claim world-leading performance, production readiness, or global adoption without comparative benchmarks and signed receipts.
## Stage 2 — shared work/evidence arbitration (GPT-6 contribution)

After `holon_contract.py` evaluates **one** proposed task against fresh repository
context, `scripts/holon_gate.py` evaluates the **whole task graph** across models.
These are complementary checks, **not competing protocols**:

```bash
# No network, keys, external writes, paid model calls or package installs.
python3 scripts/holon_gate.py --input snapshot.json --root . --actor GPT-6 > audit.json
python3 -m unittest discover -s scripts -p 'test_holon_gate.py' -v
```

Input `snapshot.json` is a provider-neutral object containing `tasks` and
optional `submissions`. Every task requires `id`, `objective`, `done_when`,
`priority` (p0–p3), `state` (OPEN/CLAIMED/IN_PROGRESS/REVIEW/BLOCKED/
REPORTED_LANDED), `paths`, and `depends_on`. A claim may include
`claimed_by` and `source`. A submission may include `task_id`, `author`,
40-hex `source_sha`, `artifact_file`, `artifact_sha256`, `tests` (each
bound to source SHA), and `review` (reviewer, verdict, source SHA).

The second-stage audit detects active-path collisions (including a newly
OPEN task conflicting with claimed work), graph cycles, unverifiable dependent
tasks, SHA/source mismatch, unsafe local file references, unverified review,
and attempts to mark work landed without signed protected-main evidence.
Local artifact SHA replay proves **file integrity only**, not mathematical truth
or model identity. All results have `authority_effect=NONE` and the offline
tool can **never** emit DONE. Release admission belongs to a separate
authenticated verifier connected to actual CI, reviewer identity and main.

The kernel is portable to research, genomics, code, marketing, design and any
other task domain; it is **not** a claim of production deployment, verified
learning between models or SOTA superiority. JSON documents are untrusted;
duplicate keys, NaN, unsafe paths and >1 MiB snapshots are rejected.
