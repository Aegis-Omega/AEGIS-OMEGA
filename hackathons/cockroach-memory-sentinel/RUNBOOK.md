# AEGIS Memory Sentinel — cash-conversion runbook

Goal: convert the current branch from implemented code into a valid CockroachDB × AWS Stage-One submission with runtime receipts and a <3 minute demo.

## 0. Fail-closed preflight

```bash
git fetch origin
git checkout feat/cockroach-memory-sentinel-v1-final
git pull --ff-only
HEAD=$(git rev-parse HEAD)
printf 'HEAD=%s\n' "$HEAD"
cd hackathons/cockroach-memory-sentinel
node --version
```

Require Node 24+ for parity with the Lambda runtime.

Do not continue if the branch is dirty unless the changed files are understood and intentionally part of the submission.

## 1. Install and run local contracts

```bash
npm install
npm test
npm run demo
```

The first successful dependency-bearing install should generate `package-lock.json`; preserve it in the submission branch before final freeze.

Local tests are component evidence only. They do not establish Cockroach Cloud or AWS execution.

## 2. OpenAI API key

Use the secure OpenAI Platform key setup flow. Never paste or commit the raw key.

Set it only in the local deployment environment:

```bash
export OPENAI_API_KEY='...'
export OPENAI_MODEL='gpt-5.6-luna'
export OPENAI_EMBEDDING_MODEL='text-embedding-3-small'
```

Live inference remains `NOT_ESTABLISHED` until the deployed receipt shows a real Agents SDK tool call.

## 3. CockroachDB Cloud — required runtime witness

Create or sign in to a CockroachDB Cloud account, then create a free CockroachDB 25.4+ cluster. No claim is promoted merely because the account or cluster exists.

Obtain the connection URL and keep it outside Git:

```bash
export COCKROACH_URL='postgresql://...'
npm run verify:cockroach
```

The verifier MUST:

1. prove `SELECT version()` identifies CockroachDB;
2. apply `db/schema.sql`;
3. execute `SHOW CREATE TABLE mcm_evidence_memory`;
4. seed sparse MCM state and two 1536-dimensional evidence vectors;
5. execute `EXPLAIN` on the vector query;
6. execute the real `<->` nearest-neighbor query;
7. preserve `sha256:evidence-a` as the expected top match;
8. emit `evidence/cockroach-runtime-receipt.json` with a SHA-256 digest.

If any step fails, the sponsor-tool runtime claim stays `NOT_ESTABLISHED`.

### Cockroach Agent Skill evidence

The branch pins the official `cockroachdb-sql` skill from:

- repository: `cockroachlabs/cockroachdb-skills`
- commit: `e14e86d23ce8ee2e7e40a34ce2944c2502b6eadd`
- skill blob: `2690e972a99fe632818f0fc1a434080bc7acd917`

Use that exact skill against the connected cluster/schema during the final validation session. Preserve the generated/validated SQL and its `EXPLAIN` output. The skill is one sponsor tool; Distributed Vector Indexing is the second.

## 4. AWS Lambda deployment — required AWS witness

Prerequisites:

```bash
aws sts get-caller-identity
sam --version
```

Generate a high-entropy demo token locally. Do not commit it.

```bash
export DEMO_TOKEN="$(openssl rand -hex 24)"
```

Build:

```bash
sam build
```

Deploy the SAM template. Supply `CockroachUrl`, `OpenAIApiKey`, and `DemoToken` through the deployment environment / protected parameters; never save them into the repository.

```bash
sam deploy --guided
```

Keep:

- stack name;
- region;
- Lambda function ARN;
- Function URL;
- deployment timestamp;
- exact Git HEAD.

The Function URL health path is public, but POST model/database execution requires `Authorization: Bearer $DEMO_TOKEN` before resources are allocated.

## 5. Generate AWS + OpenAI live receipt

Copy the deployed Function URL from the stack output:

```bash
export MEMORY_SENTINEL_URL='https://...lambda-url...'
npm run verify:aws
```

The verifier MUST fail unless:

- `/health` returns `status=ok` and `authority=NO_AUTHORITY_GRANTED`;
- authenticated POST succeeds;
- the live Agents SDK run reports a real `evaluate_action_memory` tool call;
- the bearer token and raw tool arguments are absent from the receipt.

Success writes:

```text
evidence/aws-runtime-receipt.json
```

A `200` response without `evaluate_action_memory` is a failure, not a successful demo.

## 6. Evidence freeze

After both runtime receipts exist:

```bash
npm test
sha256sum evidence/cockroach-runtime-receipt.json evidence/aws-runtime-receipt.json

git status --short
```

Commit only secret-free artifacts. Bind the Devpost submission to the exact final commit SHA.

Promotions allowed only after receipts exist:

```text
COCKROACHDB_REAL_ENGINE_RUNTIME_RECEIPT: ESTABLISHED
COCKROACHDB_DISTRIBUTED_VECTOR_INDEX_EXECUTION: ESTABLISHED
COCKROACHDB_AGENT_SKILL_EXECUTION: ESTABLISHED  # only with actual skill session evidence
OPENAI_LIVE_AGENT_INFERENCE: ESTABLISHED
AWS_LAMBDA_LIVE_DEPLOYMENT: ESTABLISHED
```

Do not promote `HACKATHON_STAGE_ONE_ELIGIBILITY` until the functional demo and submission requirements are also satisfied.

## 7. <3 minute demo script

Target: 2:15–2:40.

1. **0:00–0:20 — problem**: long-running agents can remember stale state and then act under an obsolete authority context.
2. **0:20–0:45 — architecture**: CockroachDB holds transactional MCM state + VECTOR evidence memory; MCM is `OBSERVATION_ONLY/T2`; authority stays separate.
3. **0:45–1:20 — Cockroach evidence**: show tables, vector index/query, and the Cockroach runtime receipt.
4. **1:20–2:05 — live AWS agent**: call the Lambda demo with the stale-state prompt. Show `evaluate_action_memory` in tool-call evidence and the final DENY.
5. **2:05–2:25 — MCM differentiation**: contradiction/resource pressure increases verification demand/routing priority but cannot mutate authority.
6. **2:25–2:40 — evidence boundary**: show the two runtime receipt hashes and exact Git SHA; state what is and is not established.

The video must visibly demonstrate persistent memory and the sponsor integrations, not merely slides.

## 8. Devpost submission boundary

Before submit, verify all required challenge fields against the live form/rules and use the exact final project URL, repository URL, demo URL and public video URL.

Pre-existing work disclosure must say that AEGIS Omega predates the challenge, while Memory Sentinel's MCM layer, CockroachDB/AWS integration, demo, tests and submission artifacts are challenge-period work.

No unsupported production, certification, scale, AGI, originality, revenue or security-compliance claims.
