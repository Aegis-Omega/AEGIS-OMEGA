# Devpost submission draft — CockroachDB × AWS Hackathon

Status: **PRE-EXECUTION DRAFT — DO NOT SUBMIT YET**

Challenge deadline: 2026-08-18 21:00 UTC / 5:00 PM Eastern Time.

This sheet maps the live Devpost submission field IDs to candidate answers. Runtime-dependent language must not be submitted until the corresponding receipts exist.

## Required project-level deliverables

- Project name: `AEGIS Memory Sentinel`
- Tagline: `A governed agent memory layer that detects stale, replayed, and authority-mismatched state before consequential action.`
- Public repository: `https://github.com/Aegis-Omega/AEGIS-OMEGA`
- Submission subtree: `hackathons/cockroach-memory-sentinel/`
- License URL: `https://github.com/Aegis-Omega/AEGIS-OMEGA/blob/main/LICENSE`
- Functional demo URL: **PENDING AWS DEPLOYMENT**
- Public video URL (<3 min, YouTube/Vimeo): **PENDING LIVE DEMO RECORDING**

## Custom fields

### 27812 — Functional demo URL — REQUIRED

`PENDING_AWS_LAMBDA_FUNCTION_URL`

Do not fill until `npm run verify:aws` produces a PASS receipt.

### 28078 — Testing credentials / instructions — OPTIONAL

Candidate post-deploy answer:

> Open the public `/health` endpoint without credentials to verify the no-authority health contract. The consequential POST demo is application-token protected to prevent uncontrolled model/database spend. Judges will receive a bounded demo bearer token in this field together with one test prompt. The token is not stored in the public repository and can be revoked after judging.

Never commit the actual bearer token to Git.

### 27813 — Public open-source repository URL — REQUIRED

`https://github.com/Aegis-Omega/AEGIS-OMEGA`

### 27814 — Open-source license URL — REQUIRED

`https://github.com/Aegis-Omega/AEGIS-OMEGA/blob/main/LICENSE`

### 27815 — CockroachDB tools — REQUIRED MULTISELECT

Submit only after runtime evidence exists:

- `Distributed Vector Indexing`
- `Agent Skills Repo`

Potential third tool only if actually executed before submission:

- `Cloud Managed MCP Server`

Do not select ccloud CLI or MCP merely because they are documented.

### 27816 — AWS services — REQUIRED MULTISELECT

- `AWS Lambda`

Do not add other AWS services unless actually used by the final deployed project.

### 27817 — Meaningful integration explanation — REQUIRED

Post-receipt candidate answer:

> AEGIS Memory Sentinel uses CockroachDB as the agent's persistent operational memory, not as a passive log. Transactional node state stores the admitted state digest, policy digest, authority epoch, calibration/freshness/load/reliability signals, contradiction count, and receipt-chain anchor. Evidence memories are stored alongside that state as 1536-dimensional vectors. Distributed Vector Indexing is used for semantic evidence retrieval while the deterministic memory-authority gate remains bound to exact transactional state; vector similarity can nominate evidence but cannot grant authority. The project pins and applies CockroachDB's open-source `cockroachdb-sql` Agent Skill to the connected schema/query validation flow, including `SHOW CREATE TABLE` inspection and `EXPLAIN` validation before the vector query is accepted. AWS Lambda hosts the bounded OpenAI Agents SDK runtime. The Lambda endpoint refuses unauthenticated POST requests before allocating model/database work. A live run is accepted by our verifier only when the Agents SDK reports an actual `evaluate_action_memory` tool call against Cockroach-backed state; HTTP success alone is insufficient. The resulting Cockroach and AWS runtime receipts are SHA-256-bound and exclude secrets/raw tool arguments.

Before receipts exist, this answer is **NOT YET SAFE TO SUBMIT**.

### 27818 — Project start date — REQUIRED

`08-16-26`

Basis: the dedicated Memory Sentinel hackathon subtree/branch was created on 2026-08-16. Pre-existing AEGIS work is disclosed separately below.

### 27819 — Pre-existing code/work disclosure — REQUIRED

> AEGIS Omega is a pre-existing open-source research/engineering project that predates this challenge and already contains experiments around agent governance, metacognitive observations, replay, receipts, and deterministic authority boundaries. We did not present that corpus as new hackathon work. The challenge-period project is AEGIS Memory Sentinel: the new `hackathons/cockroach-memory-sentinel/` subtree containing the MCM collective metacognition layer, stale/replay-aware persistent-memory authority contract, CockroachDB transactional/vector schema and store adapter, Cockroach sponsor-tool bindings and runtime verifier, bounded OpenAI Agents SDK tool surface, AWS Lambda deployment/verification path, test suites, execution runbook, demo and submission artifacts. Any reused AEGIS concepts are explicitly treated as pre-existing inputs rather than newly invented work.

### 27820 — Architecture diagram — OPTIONAL FILE

`PENDING_FINAL_RUNTIME_TOPOLOGY`

Create only after the deployed service URLs/components are known so the diagram reflects executed architecture rather than planned architecture.

### 27821 — CockroachDB tool feedback — OPTIONAL

Candidate after execution:

> The strongest design property for this project is being able to keep transactional agent state and semantic vector memory in one CockroachDB consistency domain. That lets semantic retrieval remain advisory while exact state/policy/authority bindings remain transactional. For agent tooling, a machine-readable conformance output from Agent Skills (for example a compact JSON record of inspected schema, EXPLAINed query, detected anti-patterns, and exact skill version) would make evidence-oriented agent workflows substantially easier to audit and replay.

Do not submit this feedback until it is validated against the actual connected-tool experience.

### 27822 — Submitter type — REQUIRED

`Individual`

### 27823 — Country of residence — REQUIRED

`Bosnia and Herzegovina`

### 27824 — Organization name — OPTIONAL

Leave blank for an individual submission unless a legal entity is actually used for the final entry.

### 27825 — AI tools leveraged — REQUIRED

> OpenAI ChatGPT was used as an engineering/orchestration assistant for repository-bound implementation and evidence management. The application itself uses the OpenAI Agents SDK (`@openai/agents`) with a bounded agent/tool surface, `gpt-5.6-luna` as the cost-sensitive default demo model, and `text-embedding-3-small` for the 1536-dimensional Cockroach vector-memory path. The project also uses the open-source CockroachDB Agent Skills Repo as a pinned schema/query-validation input. AI-generated proposals were not treated as execution evidence; TDD contracts, exact Git state, runtime receipts, and fail-closed status labels are used to separate implementation from claims.

### 27826 — Learning level — REQUIRED

Candidate: `Significant`

### 27827 — Career AI value — REQUIRED

Candidate: `Yes`

### 27828 — Not employee of sponsors — REQUIRED LEGAL CHECKBOX

**OPERATOR MUST PERSONALLY CONFIRM.** Do not infer or auto-check.

### 27829 — Eligible jurisdiction — REQUIRED LEGAL CHECKBOX

Bosnia and Herzegovina appears as a selectable country in the live form and was not identified as excluded in the rules review, but this checkbox is still the submitter's legal representation.

**OPERATOR MUST PERSONALLY CONFIRM.**

### 27830 — Age of majority — REQUIRED LEGAL CHECKBOX

**OPERATOR MUST PERSONALLY CONFIRM.** Do not infer age.

## Final pre-submit gate

Submission is allowed only when all are true:

```text
COCKROACHDB_REAL_ENGINE_RUNTIME_RECEIPT == ESTABLISHED
COCKROACHDB_DISTRIBUTED_VECTOR_INDEX_EXECUTION == ESTABLISHED
COCKROACHDB_AGENT_SKILL_EXECUTION == ESTABLISHED
AWS_LAMBDA_LIVE_DEPLOYMENT == ESTABLISHED
OPENAI_LIVE_AGENT_INFERENCE == ESTABLISHED
LIVE_evaluate_action_memory_TOOL_CALL == ESTABLISHED
FUNCTIONAL_DEMO_URL == PRESENT
PUBLIC_VIDEO_UNDER_3_MIN == PRESENT
PUBLIC_REPO_AND_LICENSE == PRESENT
PRE_EXISTING_WORK_DISCLOSED == TRUE
LEGAL_CHECKBOXES_PERSONALLY_CONFIRMED == TRUE
```

If any mandatory term is false, keep the Devpost submission in draft state.
