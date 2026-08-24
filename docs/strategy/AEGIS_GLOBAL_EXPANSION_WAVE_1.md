# AEGIS Ω — Global Expansion Wave 1

Date context: 2026-08

Purpose: convert existing AEGIS technical capital into external evaluation, distribution, funding, partnerships, and revenue.

This is a conversion plan, not a provenance project.

## 1. Immediate funding / resource targets

### Digital Europe — DIGITAL-2026-AI-DATA-10-COMPLIANCE

Status: OPEN
Deadline: 2026-10-01 17:00 CEST
Primary source: https://digital-strategy.ec.europa.eu/en/events/info-session-call-proposals-digital-solutions-regulatory-compliance-through-data

Fit:
- digital compliance infrastructure;
- machine-readable evidence;
- traceable reporting;
- accountable automation;
- public/private sector applicability.

AEGIS pitch:

> Evidence-governed automation for compliance workflows: every consequential action is bound to actor, authority, state, evidence, receipt, and outcome verification.

Critical next step: identify consortium partners and decide whether AEGIS participates as technical partner or coordinator.

### EIC Accelerator 2026

Status: OPEN
Remaining full-proposal batching dates: 2026-09-02 and 2026-11-04
Primary source: https://eic.ec.europa.eu/eic-funding-opportunities_en

Fit:
- deep-tech commercialization;
- developer/security infrastructure;
- enterprise agent governance.

Critical next step: qualify entity/SME eligibility, TRL, IP/commercial structure, and whether a short proposal must precede the desired full-proposal batch.

### Long-Term Future Fund

Status: ALWAYS OPEN
Typical EA Funds application range shown by current application surface: USD 1,000–500,000
Primary source: https://funds.effectivealtruism.org/apply-for-funding

Fit:
- technical AI safety;
- AI security;
- demonstration projects;
- infrastructure supporting safe advanced AI.

Candidate proposal:

**Evidence-Bound Runtime Authority for Autonomous Agent Systems**

Deliverables:
- open-source runtime reference implementation;
- adversarial benchmark;
- reproducibility package;
- independent external evaluation target.

### OpenAI Researcher Access Program

Status: OPEN on current grants surface
Resource: up to USD 1,000 in API credits
Review cadence: quarterly
Primary source: https://grants.openai.com/prog/openai_researcher_access_program/

Fit:
- metacognitive calibration;
- agentic oversight;
- adversarial reliability;
- safety properties under adversarial input.

Candidate proposal:

**Operator-Model Hallucination and Evidence-Bounded Agent Routing**

### OpenAI Cybersecurity Grant Program / Trusted Access for Cyber

Status: current application surface available
OpenAI announced USD 10M in API credits for teams through the Cybersecurity Grant Program.
Primary sources:
- https://openai.com/index/trusted-access-for-cyber/
- https://openai.com/form/cybersecurity-grant-program/

Fit:
- defensive agent security;
- open-source security infrastructure;
- vulnerability prevention through task-scoped runtime authority;
- agent privilege / tool-use containment.

Candidate proposal:

**Capability-Bound Agent Execution: Preventing Tool Misuse and Privilege Drift in Autonomous Security Workflows**

## 2. Distribution target — ChatGPT Plugin Directory

OpenAI accepts app submissions for review and publication. The Plugin directory is now the primary discovery surface for workflow capabilities across ChatGPT and Codex.

AEGIS product candidate:

**AEGIS Evidence Governor**

V1 must be read/verify only:
- verify receipt;
- evaluate admission without executing a side effect;
- explain proved / not_proved boundaries;
- run deterministic public demo.

Conversion funnel:

```text
ChatGPT discovery
→ verifier/demo
→ reproducible result
→ GitHub
→ partner evaluation request
→ paid pilot / research collaboration
```

See `docs/public/AEGIS_CHATGPT_PLUGIN_SPEC.md`.

## 3. Strategic enterprise partner targets

These are not generic logo targets. Each currently works on the same emerging problem from a different control layer.

### Microsoft — Entra Agent ID / Agent Governance Toolkit

Observed market problem:
- dedicated agent identities;
- authorization and governance;
- runtime agent security;
- agent lifecycle and accountability.

AEGIS complement:

**identity says who the agent is; AEGIS binds whether a particular consequential action is admissible under current task/state/evidence and produces a replayable receipt.**

Smallest credible ask:

> Evaluate one Entra-identified agent action through an AEGIS execution-admission and receipt layer.

### CyberArk — Secure AI Agents

Observed market problem:
- agent identities;
- privilege controls;
- MCP access;
- just-in-time privilege and runtime monitoring.

AEGIS complement:
- purpose/task binding;
- state-bound admission;
- deterministic execution receipts;
- post-action outcome verification.

Smallest credible ask:

> Combine privileged identity controls with an evidence-bound action receipt for one MCP workflow.

### Okta — AI Agent Governance

Observed market problem:
- lifecycle governance;
- regulated environments;
- authorization/accountability for autonomous identities.

AEGIS complement:
- execution-level evidence beyond identity lifecycle;
- explicit `OUTCOME_UNKNOWN` handling;
- replay and compensation semantics.

Smallest credible ask:

> Joint technical evaluation of identity governance + task-level execution governance in a regulated workflow.

### Palo Alto Networks — Agentic Identity Security / MCP access controls

Observed market problem:
- AI agents as privileged identities;
- MCP data access;
- least-privilege brokerage;
- visibility and runtime governance.

AEGIS complement:
- deterministic proof of the admission decision;
- state/freshness constraints;
- independent outcome verification.

Smallest credible ask:

> Red-team an AEGIS-wrapped MCP action where identity is valid but task authority or state is stale.

## 4. Commercial wedge

Do not sell "AGI OS" first.

Sell one measurable control surface:

**Evidence-bound consequential agent execution.**

Buyer problem:

> "Our agent has valid credentials and can call the tool. How do we prove this specific action was authorized, appropriate to current state, and actually produced the declared outcome?"

Initial paid offer:

### AEGIS Agent Action Assurance — Evaluation Sprint

Scope:
- one agent workflow;
- one consequential external action;
- threat model;
- typed execution contract;
- positive + adversarial test cases;
- deterministic receipt;
- outcome verifier;
- replay package;
- integration recommendations.

Commercial objective:
- paid technical evaluation first;
- platform integration second.

Do not wait for a universal production runtime before selling a bounded evaluation.

## 5. Fame / reputation loop

One technical result should generate multiple surfaces:

```text
reproducible demo
→ GitHub proof
→ technical write-up
→ short visual explanation
→ researcher outreach
→ security-community outreach
→ grant application evidence
→ partner evaluation artifact
```

Public content rule:

**show a failure that AEGIS blocks.**

Better than "AEGIS is revolutionary":

> This agent had valid credentials. The action was still denied because its authority was stale. Here is the receipt and replay.

## 6. Wave-1 execution order

1. Ship public launch brief and partner brief as reviewable GitHub PR.
2. Turn existing replay proof into a 60–90 second deterministic demo.
3. Build `AEGIS Evidence Governor` minimal ChatGPT Plugin / Apps SDK surface.
4. Prepare LTFF and OpenAI Cybersecurity Grant proposals from the same technical wedge.
5. Prepare Digital Europe partner one-pager and consortium outreach package.
6. Prepare four enterprise evaluation pitches: Microsoft, CyberArk, Okta, Palo Alto Networks.
7. Do not send or publish until each outward-facing artifact has a final operator review.

## Success metric

Not number of documents.

```text
external technical reviews
+ qualified partner conversations
+ submitted funding applications
+ plugin users
+ paid evaluations
+ independently reproduced proofs
```
