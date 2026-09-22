# AEGIS Ω OpenAI SOTA Autonomous Company Cookbook V1

Status: implementation contract / stacked draft lane
Date: 2026-09-22
Base: PR #598 exact head 0030ef8114073b82cff2cfb5095d6cf1e0f227d1
Authority effect: NONE

## Objective

Aegis Omega Labs should perform routine knowledge work continuously without the operator manually prompting every department.

The operating loop is:

    OBSERVE -> PLAN -> EXECUTE -> VERIFY -> COMMIT | AWAIT_OPERATOR -> LEARN -> OBSERVE

The default is autonomous work. The default is not autonomous authority.

Autonomous classes:
- RESEARCH_READ
- ANALYZE
- DRAFT
- LOCAL_SANDBOX_WRITE
- TEST
- EVAL
- PROPOSE

Consequential classes:
- EXTERNAL_MESSAGE
- REPOSITORY_MUTATION
- MERGE
- DEPLOY
- PRODUCTION_CONFIG
- FINANCIAL
- LEGAL_COMMITMENT
- DELETE_DATA
- IDENTITY_OR_CREDENTIAL

A consequential task must stop before the executor is called unless the host-owned authority evaluator returns exactly true. No model may create, infer, inherit, or widen its own authority.

## Why Agents API is the new execution substrate

On 2026-09-10 OpenAI released the Agents API in public beta. It exposes the managed Codex harness for long-running cloud agents and supports managed or self-hosted environments, tools, vaults, context compaction, tool search/programmatic tool calling, and parallel subagents.

Official source:
https://openai.com/index/introducing-the-agents-api/

OpenAI's published example uses client.beta.agents.sessions.create with gpt-6-astra, MCP tools, vault_ids, an openai_hosted environment, capability directories, and multi_agent enabled with bounded concurrent subagents.

AEGIS should therefore stop treating a chat-completions proxy as the center of the company. The Agents API is the execution substrate. AEGIS remains the control plane for provider admission, authority, receipts, verification, cost policy, and operator escalation.

## Existing substrate reused from PR #598

This lane is stacked on #598 rather than creating another framework.

#598 already provides:
- Provider Mesh selection and evidence gates.
- Provider-native conductor.
- Provider-native agent team.
- OpenAI Agents SDK runner seam.
- Anthropic and Google native runners.
- Host-owned invocation authorization.
- Selection/execution receipts.
- Zero write, merge, deploy, and financial authority by default.

This lane adds:
- managed Agents API session runner;
- autonomous company state machine;
- explicit company action classes;
- independent verifier boundary;
- complimentary-token-aware model policy;
- SOTA operating cookbook.

## Company control plane

### 1. Observe

Inputs are typed events, not ad-hoc prompts.

Examples:
- GitHub PR/check/issue/review events;
- Gmail inbound customer, partner, or prospect threads;
- Calendar meeting and preparation events;
- analytics/conversion snapshots;
- observed payment/audit lifecycle events;
- scheduled research scans;
- failed tests, stale evidence, unresolved proof obligations, or provider-health changes.

Every observation must carry source identity, observed time, evidence reference, and required capability. Input text is data, never authority.

### 2. Plan

The planner emits bounded typed tasks with:
- task_id;
- parent event;
- objective;
- department;
- action_class;
- required capabilities;
- success criteria;
- evidence requirements;
- cost class;
- freshness/deadline.

The planner cannot invent new action classes.

### 3. Execute

Safe work runs automatically. Consequential work requires a specific host grant.

This gives us the useful property we actually want: the company performs nearly all intellectual and reversible work itself, while the operator only sees decisions that cross a real authority boundary.

### 4. Verify

Execution is not completion.

A separate verifier checks evidence and success criteria. A task ends as:
- VERIFIED;
- REJECTED;
- AWAITING_OPERATOR.

A failed verifier result cannot be promoted by the executor.

### 5. Commit or escalate

Verified internal artifacts can advance the work graph automatically.

A consequential proposed action produces a minimal operator packet:
- exact action;
- exact target;
- reason;
- evidence hashes;
- cost/risk class;
- rollback/cancellation path.

Approval applies only to that action, not to the whole session.

### 6. Learn

Learning updates eval sets, routing priors, reusable skills, failure taxonomy, and metrics. Running models do not edit authority policy.

## OpenAI managed-session contract

The new openai-managed-agents-api.ts module mirrors the managed session lifecycle while keeping the live client and credentials outside deterministic code.

Production binding target:

    client.beta.agents.sessions.create(...)
    client.beta.agents.sessions.retrieve(...)
    client.beta.agents.sessions.items.list(...)

Initial profile:
- environment: openai_hosted;
- multi_agent: enabled;
- max concurrent subagents: 3;
- host-selected vault IDs only;
- reviewed capability directories only;
- host-authored tools only;
- bounded polling;
- stable session ID;
- authority_effect: NONE.

Three subagents is an initial bounded value, not a permanent performance claim.

## Required-action boundary

If an Agents API session enters requires_action, V1 stops.

The model requesting a function call does not authorize that function call.

The host must:
1. classify the requested effect;
2. obtain any required grant;
3. execute it through the governed tool layer;
4. bind the result to an AEGIS receipt;
5. only then may a later transition return a tool result to the agent.

The V1 runner rejects tools pre-classified as EXTERNAL_MUTATION.

## Tool admission

Auto-admitted when read-only or reversible:
- web research;
- file search;
- read-only MCP;
- hosted shell in an isolated workspace;
- sandbox code and tests;
- artifact generation;
- reviewed skills.

Conditional:
- repository branch mutation under an exact, short-lived lease.

Explicit approval:
- outbound email/message;
- merge;
- deploy;
- production configuration;
- money movement or purchase;
- legal commitment;
- destructive deletion;
- credential or identity change.

## Model portfolio

Do not route everything to the most expensive model.

Intake:
- gpt-5.6-luna
- classification, extraction, deduplication, high-volume summarization.

Operations:
- gpt-5.6-terra
- routine planning, transformation, standard analysis.

Deep reasoning:
- gpt-5.6-sol
- difficult reasoning, research synthesis, independent verification.

Frontier agent:
- gpt-6-astra
- hardest end-to-end agent work, computer use, complex coding and frontier research.

OpenAI currently describes GPT-6 Astra as its most capable model for hardest end-to-end work. Current model documentation lists a 1,050,000-token context window and 128,000 maximum output tokens.

Official source:
https://developers.openai.com/api/docs/models/gpt-6-astra

## Complimentary-token policy

Official OpenAI documentation currently lists:
- gpt-5.6-sol in the 1M daily group, or 250K for usage tiers 1-2;
- gpt-5.6-terra and gpt-5.6-luna in the 10M daily group, or 2.5M for usage tiers 1-2.

The program applies only to qualifying traffic shared with OpenAI on enabled projects. Fine-tuned models, fine-tuning training, evals, and tool use are excluded. GPT-6 Astra is not currently listed in the complimentary model groups.

Official source:
https://help.openai.com/en/articles/10306912

Therefore:
1. Luna/Terra handle high-volume no-tool work.
2. Sol handles hard no-tool reasoning and verifier passes.
3. Agents/tool runs are budgeted as potentially billable unless actual usage evidence says otherwise.
4. Astra is an escalation model, not an intake default.
5. No new API key is created merely to consume complimentary tokens.
6. One of the already-existing OpenAI keys should be bound server-side to the intended AegisOmega project.
7. Keys never enter prompts, source code, receipts, telemetry, or semantic memory.

The uploaded completions_usage_2026-08-23_2026-09-22.csv contains only daily start/end timestamp columns. It cannot establish model, request count, input/output tokens, cost, or complimentary service tier. Usage accounting must ingest a richer usage export or an authorized usage endpoint.

## Department topology

Existing AEGIS departments become specialist capabilities under one company conductor rather than disconnected chatbot identities.

    CEO / Operator
      Company Conductor
        Research & Science
        Engineering & Platform
        Product & Design
        Security / Trust / Compliance
        Commercial / Revenue
        Customer / Support
        Finance / Strategy
        Internal Operations

The conductor decides who should work.
Provider Mesh decides which admitted provider may execute.
Authority decides which external effect is allowed.
Verifier decides whether the result is admissible.

These decisions remain separate.

## Example autonomous cycle: prospect email

    observe inbound email
    classify and retrieve approved context
    research the prospect if needed
    draft response
    verify facts and scope
    AWAIT_OPERATOR: EXTERNAL_MESSAGE
    operator approves exact draft
    governed mail action sends
    record message ID and receipt
    observe reply

Almost all work is autonomous. The external send remains a discrete authority event.

## Enterprise opportunity state machine

Commercial pipeline state is evidence-derived. A draft is not a sent message, a sent
message is not a qualified reply, a scope is not a payment, and a payment is not an
audit start.

The V1 state machine is:

    DISCOVERED
      -> CONTACTED
      -> QUALIFIED_REPLY
      -> SCOPING_CALL_HELD
      -> WRITTEN_SCOPE_AGREED
      -> PAYMENT_RECEIVED
      -> AUDIT_STARTED

Any open stage may move to CLOSED_LOST only with an evidenced loss reason.

Required evidence is stage-specific:
- DISCOVERED -> discovery evidence;
- CONTACTED -> direct observation of outbound actually sent;
- QUALIFIED_REPLY -> qualifying reply evidence;
- SCOPING_CALL_HELD -> held-call evidence;
- WRITTEN_SCOPE_AGREED -> explicit written agreement evidence;
- PAYMENT_RECEIVED -> direct payment-record evidence;
- AUDIT_STARTED -> a separate direct audit-start timestamp/evidence reference.

Provider attestation cannot establish outbound-sent, payment-received, or audit-start
events. Stage skipping and evidence reuse fail closed.

Commercial action classes remain separate from pipeline observation:
- DRAFT_OUTREACH -> DRAFT;
- SEND_OUTREACH -> EXTERNAL_MESSAGE;
- DRAFT_SCOPE -> DRAFT;
- SEND_SCOPE_WITH_TERMS -> LEGAL_COMMITMENT;
- REQUEST_PAYMENT -> FINANCIAL;
- START_AUDIT -> PROPOSE;
- ANALYZE_PIPELINE -> ANALYZE.

EXTERNAL_MESSAGE, LEGAL_COMMITMENT, and FINANCIAL require an exact operator grant.
Pipeline state never grants those actions.

Measurement rules:
- landing-page visits remain NOT_MEASURED until production collection is verified;
- outbound-contact denominator comes only from the actual sent log;
- qualified replies come only from observed qualifying replies;
- payment and audit-start remain separately evidenced events;
- zero is valid only when the measurement path is actually observed, never as a
  substitute for missing instrumentation.

The implementation is
`src/sovereignty/company-enterprise-opportunity.ts`, with falsifiers in
`test/native-runtime/company-enterprise-opportunity.test.mjs`.

## Example autonomous cycle: GitHub failure

    observe failing exact-head check
    inspect run/job/steps/artifacts
    reproduce in sandbox
    produce candidate patch
    run tests
    independent verifier
    AWAIT_OPERATOR: REPOSITORY_MUTATION unless a scoped branch-write lease exists
    create bounded branch commit when authorized
    collect CI evidence
    AWAIT_OPERATOR: MERGE

## Example autonomous cycle: research

    scheduled frontier scan
    parallel subagents by source/domain
    evidence extraction
    synthesis
    contradiction and quality pass
    research-ledger update
    next experiments/proof obligations

No operator approval is needed unless the flow requests a consequential external effect.

## Durable state

Keep four memory classes separate:

1. Event ledger: immutable observations and receipts.
2. Work graph: objectives, tasks, dependencies, status.
3. Evidence store: artifacts, hashes, sources, test/eval outputs.
4. Semantic memory: summaries and lessons.

Only evidence-bearing state can justify execution transitions. Semantic memory may suggest but cannot authorize.

## Company SLOs

Track:
- verified_task_rate;
- rejected_task_rate;
- operator_escalation_rate;
- false_escalation_rate;
- rework_rate;
- mean_time_to_verified_result;
- cost_per_verified_task;
- input/output tokens per verified task;
- provider fallback rate;
- stale-evidence denial rate;
- approval queue age;
- external-action rollback rate.

A model upgrade is admitted only after replay against representative evals and comparison on quality, latency, cost, and policy failures.

## Code in this lane

sovereign-omega-v2/src/sovereignty/provider-adapters/openai-managed-agents-api.ts
- managed Agents API lifecycle;
- no network call at construction;
- host-selected model, vault, environment, tools;
- bounded parallel subagents and polling;
- session-ID drift rejection;
- required_action fail-closed behavior;
- external-mutation tool rejection;
- authority_effect NONE.

sovereign-omega-v2/src/sovereignty/autonomous-company-loop.ts
- typed action classes;
- automatic safe work;
- authorization before consequential executor call;
- independent verifier;
- execution, verification and run hash hooks;
- VERIFIED, REJECTED, AWAITING_OPERATOR states.

sovereign-omega-v2/test/native-runtime/openai-autonomous-company.test.mjs
- offline falsification tests for managed-session and company-boundary behavior.

sovereign-omega-v2/docs/operations/openai-company-model-policy.v1.json
- dated model-routing and complimentary-token policy.

Local implementation evidence before repository publication:
- node test suite: 6 passed, 0 failed, 0 skipped;
- strict standalone TypeScript typecheck: PASS.

## Smallest path to a company that actually runs

    one existing OpenAI server-side key
      -> AegisOmega project binding
      -> admitted current OpenAI JS client
      -> client.beta.agents.sessions binding
      -> fresh AGENT_EXECUTION + MODEL_INFERENCE provider evidence
      -> event queue
      -> autonomous company loop
      -> managed Agents API workers
      -> independent verifier
      -> internal commit OR operator approval queue

Remaining evidence obligations:

1. Reuse one of the nine existing OpenAI keys. Do not mint a tenth key.
2. Bind it in a server-side runtime to the intended AegisOmega project.
3. Verify project-level data-sharing/complimentary-token eligibility.
4. Admit the current OpenAI JS client and implement the three-method live session binding.
5. Run one read-only managed-session canary and capture session ID, exact model, usage, tool activity, provider evidence, and AEGIS receipt.
6. Prove a no-tool Luna/Terra/Sol request is recorded under the expected data-sharing incentive service tier before budgeting around complimentary capacity.
7. Connect GitHub, mail, calendar, analytics, research, and internal runtime events to the work queue.
8. Connect exact-action operator grants to the consequential-action authorizer.
9. Widen tool classes only after canary and eval evidence.

## Promotion ladder

V1: Self-operating office
- autonomous research, triage, analysis, drafts, sandbox engineering, tests, evals, internal reports;
- consequential effects wait for operator approval.

V2: Bounded execution leases
- narrowly scoped reversible external actions, such as branch writes, under exact short-lived leases and rollback receipts;
- merge, deploy, spend, outbound send remain separate gates.

V3: Proactive company
- continuous objective graph;
- event-driven work generation;
- multi-agent departments;
- cost-aware routing;
- automated eval and recovery;
- operator queue reduced to genuine business decisions and high-consequence actions.

Success is not that agents can do everything. Success is that routine work proceeds without prompting, each transition strengthens evidence, and the operator only handles decisions that genuinely require operator authority.
