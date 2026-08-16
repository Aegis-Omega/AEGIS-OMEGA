# OpenAI Agents SDK / Cookbook alignment

## Goal

Use current OpenAI agent-building patterns without allowing a model, trace, or metacognitive observation to become an authority root.

## Trusted-host split

The orchestrator remains in the trusted application runtime. Model output may propose tool calls, verification tasks, memory queries, or escalation requests, but consequential authority remains in the deterministic AEGIS gate.

```text
OpenAI Agent / model judgment
        |
        v
bounded function tools
        |
        +--> CockroachDB memory retrieval
        +--> MCM observation / verification demand
        |
        v
AEGIS memory-authority gate
        |
        +--> DENY
        +--> REVIEW_REQUIRED (higher layer)
        +--> ALLOW candidate for separately admitted effect path
```

The sandbox/execution surface, if later used, is not trusted to hold approval authority or secrets needed for governance decisions.

## SOTA patterns adopted

### 1. Small explicit agent surface

Start with one agent and narrow function tools. Do not introduce a swarm solely for branding. Specialists or handoffs are added only where evals show a measurable need.

### 2. Structured tools and state

Tools expose typed inputs for memory retrieval, MCM observation, and deterministic admission evaluation. Tool output is evidence. A tool result cannot self-promote its authority level.

### 3. Guardrails are not the authority evaluator

Input/output guardrails may reject malformed or unsafe interaction patterns early, but the deterministic memory/authority gate is a separate control boundary. A passing model guardrail is not equivalent to effect admission.

### 4. Tracing and evals

Agent traces are used to measure behavior such as:

- whether the agent queried memory before a consequential action;
- whether stale-memory cases escalated or denied;
- whether contradiction triggered independent verification demand;
- whether the agent attempted forbidden authority mutation;
- whether repeated runs preserve the required gate outcome.

Trace evidence is observational and evaluation-oriented. It does not replace the deterministic receipt or CockroachDB state binding.

### 5. Evidence-driven improvement loop

Failures found in traces/evals become fixed regression cases. Prompt or orchestration changes are admitted only after the relevant behavior improves without breaking the authority invariants.

## Metacognitive chain relationship

The pre-existing AEGIS metacognitive chain records local self-observations and replay/tamper evidence. MCM extends the idea to sparse collective state:

- local chain: what this execution surface observed about itself;
- MCM: what the heterogeneous collective currently observes about evidence quality, disagreement, reliability, and load;
- Authority Control Plane: the only layer permitted to admit consequential authority.

MCM therefore improves routing and verification selection while remaining `OBSERVATION_ONLY/T2`.

## Current implementation boundary

This hackathon branch currently establishes deterministic local MCM and memory-authority contracts plus a CockroachDB schema. An OpenAI API-backed agent execution, CockroachDB Cloud execution, sponsor Agent Skills execution, and AWS deployment must each produce separate runtime evidence before they are claimed as integrated.

## Primary implementation references

- OpenAI Agents SDK guide: https://developers.openai.com/api/docs/guides/agents
- OpenAI agent evals guide: https://developers.openai.com/api/docs/guides/agent-evals
- OpenAI Cookbook Agents SDK examples: https://github.com/openai/openai-cookbook/tree/main/examples/agents_sdk
- OpenAI Cookbook — governed agent scaffolding and trace/eval improvement patterns
