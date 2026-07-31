# RFC 0003 — AEGIS Metacognitive Ecosystem Backbone

Status: Draft implementation contract  
Authority: Non-deployment; requires exact-head verification and operator admission  
Scope: Models, tools, connectors, runtimes, verifiers, corpus sources, and the human operator

## Problem

AEGIS currently contains many capable components and connected systems, but each surface can carry a different account of identity, capability, evidence, runtime state, and authority. A connected plugin is not necessarily operational. A discovered file is not read evidence. Tested code is not deployed code. A model recommendation is not an authority grant.

The ecosystem therefore needs one minimal contract before additional orchestration:

1. stable adapter identity;
2. declared capabilities;
3. maximum authority per capability;
4. evidence state;
5. explicit operator-approval and independent-verification requirements;
6. a deterministic admission decision;
7. weakest-link reconciliation across multiple witnesses.

## Canonical loop

```text
Observed signal or operator objective
→ adapter identity resolution
→ declared capability lookup
→ requested authority comparison
→ evidence sufficiency check
→ operator approval check
→ independent verification check
→ admitted intent or fail-closed denial
→ existing Scale OS signed event / receipt path
```

This RFC does not create a second control plane. `metacognitive-ecosystem.ts` is an admission contract intended to feed the existing Scale OS signed event spine.

## Model-to-model study

Models may:

- examine another model's outputs, test results, calibration records, schemas, and receipts;
- identify contradictions, regressions, strengths, and missing evidence;
- propose prompts, adapters, tests, model configurations, or replacement models;
- produce bounded evaluation records and migration recommendations.

Models may not:

- grant themselves or another model new authority;
- rewrite the adapter registry without an admitted repository change;
- treat linguistic agreement as verification;
- turn a proposed model, prompt, or policy into production execution without admission;
- issue operator approval records;
- erase superseded evidence or temporal voice.

"AI can create AI" is implemented as **proposal plus verified construction**, not unrestricted recursive self-modification. A generated model adapter, evaluator, prompt compiler, fine-tuning recipe, or agent definition enters the ecosystem as `PROPOSED/DISCOVERED` and must independently progress through content review, wiring, execution, and verification.

## Authority lattice

From weakest to strongest:

```text
OBSERVE
< PROPOSE
< VERIFY
< EXECUTE_REVERSIBLE
< EXECUTE_CONSEQUENTIAL
```

An intent is denied when its requested authority exceeds the declared capability ceiling. Every consequential capability must require explicit operator approval. Capabilities may additionally require independent verification.

## Evidence lattice

```text
UNKNOWN
< DISCOVERED
< CONTENT_READ
< WIRED
< EXECUTED
< VERIFIED
```

`REJECTED` is terminal for the evaluated claim or artifact until a new, separately identified witness is admitted.

When multiple adapters support a shared conclusion, the ecosystem authority cannot exceed the weakest evidence state among the required witnesses. This is the same epistemological rule used by repository reconciliation: no claim has greater authority than its weakest verified transition.

## Adapter registry

`config/metacognitive-ecosystem.adapters.v1.json` is a seed registry of observed integration surfaces. It is descriptive and grants no runtime authority. Each record must distinguish:

- connector presence;
- content discovery;
- content read;
- actual runtime wiring;
- executed behavior;
- independent verification.

Secrets, tokens, personal message content, and sensitive account identifiers must not be stored in the registry.

## Initial integration order

1. GitHub repository and CI receipts.
2. Supabase database, functions, migrations, and runtime evidence.
3. Google Drive / OneDrive / Slack / email corpus discovery and deduplication.
4. Deployment evidence from Vercel and other active runtime providers.
5. Model-provider adapters and lifecycle migration receipts.
6. Design and media systems as non-authoritative representation adapters.

## Acceptance criteria

- deterministic unit tests cover authority ceilings, approval requirements, independent verification, and weakest-link evidence;
- the seed registry contains no secrets and makes no deployment claims;
- exact-head repository tests, typecheck, build, lint, and security gates pass;
- no production mutation, deployment, database migration, or merge is performed by this RFC;
- future connector work emits evidence-bound adapter updates rather than new parallel handoff documents.
