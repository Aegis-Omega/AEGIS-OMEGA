# AEGIS Ω — ChatGPT Plugin / Apps SDK Distribution Concept

## Product thesis

Use ChatGPT as a distribution surface for AEGIS verification rather than as another generic chatbot.

Working product name:

**AEGIS Evidence Governor**

The first public version should be deliberately narrow and safe: a read/verify experience that turns a proposed agent action or supplied execution artifact into a structured evidence and authority assessment.

## User jobs

A user should be able to ask:

- "Can this agent action be admitted under this policy?"
- "Verify this execution receipt."
- "Compare this observed outcome to the declared action."
- "Show me what is proved versus not proved."
- "Replay this deterministic evidence chain."
- "Explain why this action was denied."

## V1 tool surface

### `verify_receipt`

Input:
- receipt or receipt reference;
- expected schema/version;
- optional expected task/actor/resource identifiers.

Output:
- structural validity;
- integrity result;
- replay result where supported;
- contradictions;
- `not_proved[]`.

### `evaluate_admission`

Input:
- typed action proposal;
- capability scope;
- authority evidence;
- current state/precondition evidence;
- policy contract.

Output:
- `ADMIT | DENY | REVIEW | BLOCKED`;
- exact gates used;
- evidence references;
- no side effect in V1.

### `explain_evidence`

Input:
- one AEGIS certificate, ledger entry, or test artifact.

Output:
- what it establishes;
- what it does not establish;
- reproduction instructions where available.

### `run_public_demo`

Runs a bounded, deterministic demonstration included in the public repository and returns the resulting certificate.

## Safety posture

V1 should expose **no consequential external write tool**.

This has three advantages:

1. the app can demonstrate the AEGIS thesis without asking users to trust AEGIS with production authority;
2. review and threat modelling are substantially simpler;
3. the public artifact becomes a funnel into deeper enterprise evaluations.

A later enterprise version may expose mediated write actions only after task-level authority, resource scope, state preconditions, confirmation rules, and outcome verification are defined.

## Chat-native experience

The UI should make evidence status immediately visible:

```text
ACTION              proposed database migration
ACTOR               agent://finance-ops/07
CAPABILITY          db.schema.migrate
AUTHORITY            VALID / scoped
STATE PRECONDITION  STALE
VERDICT              DENY
WHY                  target schema changed after authorization
PROVED               identity, policy, observed state
NOT PROVED           business outcome
```

The product should avoid anthropomorphic "agent thinks" language. It should present claims, evidence, authority, observations, and outcomes as separate fields.

## Directory positioning

Category fit:
- Developer Tools
- Security
- Productivity / Enterprise workflows

Short description:

> Verify what an AI agent was allowed to do, what evidence it used, and whether the execution can be replayed.

Long description:

> AEGIS Evidence Governor is an evidence-first control and verification layer for agentic workflows. It checks action proposals and execution receipts against explicit capability, authority, state, and policy constraints, then returns a reproducible verdict with clear `proved` and `not_proved` boundaries.

## Conversion path

```text
ChatGPT user
→ public verifier/demo
→ reproducible evidence result
→ GitHub repository
→ integration/evaluation request
→ design partner / research collaboration / paid pilot
```

## Submission readiness gates

Before public submission:

- stable remote MCP endpoint;
- deterministic public demo;
- privacy policy;
- support contact;
- accurate tool annotations;
- threat model;
- abuse cases;
- app-directory metadata;
- test instructions;
- no unsupported production/security claims;
- public documentation for data retention and logging.

## Build principle

Do not build an "AEGIS assistant" that merely talks about AEGIS.

Build an **AEGIS verifier that does something independently checkable**.
