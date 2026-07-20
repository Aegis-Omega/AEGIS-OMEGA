# OpenAI Agent Runtime Contract

The OpenAI layer is a bounded orchestrator, not an authority source.

## Runtime selection

- Use the Responses API and OpenAI Agents SDK.
- Default difficult architecture, security review, and synthesis work to `gpt-5.6-sol`.
- Evaluate `gpt-5.6-terra` and `gpt-5.6-luna` on representative workloads before routing lower-risk or high-volume tasks to them.
- Begin with one primary agent. Add specialists only when evals show a measurable gain.
- Use Programmatic Tool Calling only for bounded, non-mutating reduction stages where intermediate results can be processed deterministically.

## Primary agent

Name: `sol-operator`

Goal: turn operator intent into a reviewed execution plan, gather evidence through read-only tools, request AEGIS admission for consequential actions, execute only admitted provider calls, and return receipt-backed results.

The agent must not:

- grant itself authority;
- infer approval from conversational tone;
- retry non-idempotent mutations without a new admission decision;
- treat advisory model output as proof;
- expose secrets or secret-derived values;
- claim a provider mutation succeeded without provider evidence and an AEGIS result envelope.

## Specialist handoffs

Specialists are optional and must have disjoint tool surfaces:

- `knowledge-retriever`: GitHub, SharePoint, Hugging Face read-only search/fetch.
- `formal-verifier`: Wolfram calculations and invariant checking.
- `model-evaluator`: Hugging Face datasets/evals and NVIDIA benchmark execution.
- `design-reviewer`: Figma/design-source inspection and UX evidence.
- `release-engineer`: GitHub branch/PR preparation and Cloudflare deployment plans.

No specialist receives direct D2+ provider tools. Consequential actions return to `sol-operator` for Automaton-3 admission.

## Tool contract

Each tool is one job with:

- explicit JSON schema;
- accurate `readOnlyHint`, `destructiveHint`, `openWorldHint`, and `idempotentHint` annotations;
- normalized errors;
- bounded output;
- provider operation ID where available;
- no secret-bearing response fields.

Connector-like knowledge tools use the standard `search` and `fetch` shapes. Mutating tools consume `execution-request.v1` and return `execution-result.v1`.

## Approval policy

- D0: automatic read-only execution.
- D1: automatic only when local, reversible, and isolated.
- D2: requires Automaton-3 admission and idempotency key.
- D3: requires explicit operator approval plus Automaton-3 admission.
- D4: denied until a dedicated admitted policy exists.

## State and memory

- Keep canonical state outside the model context.
- Treat conversation memory as advisory.
- Persist only normalized state references and receipt roots.
- Do not store raw secrets, access tokens, or private file contents in long-lived agent memory.
- Use `previous_response_id` only while the operator goal and trust boundary remain stable.

## Evaluation matrix

The real agent path must be tested for:

1. correct read-only tool selection;
2. missing evidence denial;
3. stale parent-state denial;
4. expired lease denial;
5. replay rejection;
6. required operator approval;
7. forbidden direct provider mutation;
8. provider timeout and retry classification;
9. provider success with lost client response;
10. conflicting provider state;
11. prompt injection in retrieved content;
12. cross-agent privilege escalation;
13. oGemma evidence remaining T2;
14. Wolfram indeterminate result not becoming proof;
15. SharePoint content not overriding repository policy.

Each eval records tool calls, authority decision, provider evidence, receipt root, trace ID, and final answer completeness. Exact prose is not graded unless contractual.