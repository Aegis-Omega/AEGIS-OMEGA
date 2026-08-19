# SOL Cross-Platform Control Plane — Specification

Status: DRAFT / non-production
Owner: AEGIS-Ω operator
Authority root: Automaton-3

## Purpose

SOL is the governed integration layer that connects model runtimes, knowledge stores, verifiers, design surfaces, deployment infrastructure, and operator clients without granting any provider independent mutation authority.

The system follows one invariant:

```text
provider proposes or computes
AEGIS authorizes
provider executes within the granted capability
AEGIS records the result and state transition
```

No platform listed here is a constitutional authority. Automaton-3 remains the sole authority evaluator for consequential actions.

## First implementation slice

1. OpenAI Agents SDK orchestrates bounded workflows and specialist handoffs.
2. The existing AEGIS MCP server is the canonical tool surface.
3. Cloudflare hosts the remote MCP edge and durable execution coordination.
4. GitHub stores reviewed source, policy, schemas, and admission evidence.
5. SharePoint stores published operator knowledge and approved runbooks.
6. Hugging Face stores model cards, evaluation datasets, and immutable evaluation bundles.
7. NVIDIA supplies GPU inference and accelerated evaluation workers.
8. Wolfram supplies deterministic mathematical verification.
9. Dataverse stores governed business entities and workflow state.
10. Figma is the editable product-design source; generated UI must not become authority state.
11. Web and iOS clients are operator control surfaces only.
12. oGemma/MYTHOS is a T2 advisory holon whose verdict is evidence, never unilateral authority.

## Application archetype

Primary archetype: interactive-decoupled ChatGPT/MCP app.

Data tools return concise structured content. Render tools attach operator-console resources. Mutating tools require an Automaton-3 admission decision before any provider call.

## Trust boundaries

### T0 — constitutional authority

- Automaton-3 evaluator
- consequence policy
- capability evidence
- writer lease and fencing token
- mutation receipt

### T1 — deterministic verification

- schema validation
- digest verification
- Wolfram verification results
- provider response normalization
- GitHub OIDC attestations

### T2 — engineering evidence

- model and agent evaluations
- oGemma/MYTHOS holon verdicts
- NVIDIA runtime telemetry
- operator-console diagnostics

### T3 — advisory content

- model reasoning
- generated plans
- design proposals
- narrative summaries

T2 and T3 inputs cannot upgrade themselves into authority.

## Consequence classes

- D0: read-only observation
- D1: reversible local state
- D2: shared-state mutation
- D3: external or costly mutation
- D4: irreversible, destructive, privileged, or high-impact mutation

D2+ requires explicit capability evidence, expected parent state, idempotency semantics, and a mutation receipt. D3+ requires operator approval. D4 remains denied until a dedicated policy and recovery procedure are admitted.

## Canonical execution envelope

Every provider operation must be represented by the schema in `contracts/execution-request.v1.schema.json` and include:

- stable request ID
- actor and agent identity
- provider and capability
- consequence class
- target and normalized arguments digest
- expected parent state root
- writer lease generation
- idempotency key
- compensation reference when applicable
- operator approval reference when required

## Canonical result envelope

Every provider result must include:

- request ID
- provider operation ID
- normalized status
- output digest
- external state reference
- observed completion time
- receipt root
- error class when unsuccessful

Provider-native IDs and timestamps are evidence, not the canonical state root.

## Platform responsibilities

### OpenAI

- Use the Responses API / Agents SDK for orchestration.
- Begin with one primary agent and narrow function tools.
- Use structured outputs for contracts.
- Keep approval boundaries explicit.
- Add evals against the real governed tool path.
- Use SOL for difficult synthesis; use lower-cost model classes only after evaluation proves parity for the task.

### Cloudflare

- Remote MCP endpoint at `/mcp`.
- OAuth for user-specific tools.
- Durable Objects or Workflows for durable coordination.
- bindings over Cloudflare REST calls.
- secrets only through the secret store.
- structured logs, traces, and sampled observability.
- no request-scoped mutable global state.

### GitHub

- Source of reviewed implementation and policy.
- All changes through branches and pull requests.
- Exact-head CI, dependency scanning, schema validation, adversarial tests, replay artifacts, and OIDC attestations.
- No merge or deployment from this specification alone.

### SharePoint

- Published, human-readable operating knowledge.
- Content is versioned and linked to Git commit and receipt roots.
- SharePoint documents never override repository policy or executable schemas.

### Hugging Face

- Publish honest model cards, evaluation datasets, and evaluation bundles.
- Pin base-model and dataset revisions.
- Separate model weights, adapters, prompts, and governance artifacts.
- oGemma has no custom weights unless independently produced and documented.

### NVIDIA

- Accelerated inference and evaluation workers.
- Runtime identity, image digest, driver/runtime versions, model digest, and benchmark output must be captured.
- GPU execution cannot bypass AEGIS admission.

### Wolfram

- Deterministic verification service for equations, invariants, units, and symbolic claims.
- Verification output must include exact input expression and normalized result.
- Failed or indeterminate verification cannot be represented as proof.

### Dataverse

- Governed business entities, relationships, and workflow projections.
- Mutations are idempotent and keyed by AEGIS request ID.
- Dataverse is a projection store, not the constitutional source of truth.

### Figma and product design

- Figma is the editable design source.
- Design tokens and component mappings are exported through reviewed artifacts.
- Operator-console UX must show authority decision, consequence class, provider, state root, and receipt before confirmation.

### iOS

- SwiftUI client uses narrow state ownership and explicit dependency injection.
- App Intents expose only high-value verbs: inspect execution, review decision, continue approved workflow.
- Intents do not perform D2+ mutations without opening the app for governed approval.

## oGemma/MYTHOS integration

The current implementation contains an important incomplete path: `POST_VALIDATE` and full `POST_REVIEW` integration are described but not fully wired into the pipeline. The adapter must:

1. validate biological-state input bounds;
2. bind the task, plan digest, gate name, model identity, prompt version, and state digest into the verdict envelope;
3. reject unknown gates rather than returning APPROVED;
4. submit each gate result through the canonical AEGIS evidence path;
5. treat the holon as advisory evidence with an explicit evidence tier;
6. never convert its quorum weight into unilateral mutation authority;
7. add replay tests for every gate and malformed input.

## Minimum working contract

The first PR is complete only when it provides:

- this specification;
- versioned execution and result schemas;
- a machine-readable platform registry;
- an oGemma adapter contract and regression cases;
- a remote MCP deployment plan for Cloudflare;
- an OpenAI agent contract and evaluation matrix;
- web and iOS operator-surface contracts;
- SharePoint publishing structure;
- CI checks that validate all new JSON and JSONL artifacts.

Production deployment, DNS mutation, OAuth application creation, secret provisioning, model publication, Dataverse schema migration, and merge to `main` are explicitly outside this draft PR.