# SOL Web Operator Console

Primary product surface: an inspectable control plane for governed cross-platform workflows.

## Information architecture

- Executions: active and historical workflows.
- Decisions: Automaton-3 admissions and denials.
- Providers: health, capability scopes, and evidence freshness.
- Evidence: model evals, Wolfram checks, oGemma verdicts, and provider receipts.
- Knowledge: GitHub and SharePoint sources with provenance.
- Settings: environments and non-secret configuration references.

## Execution detail

The primary screen must show, without hidden drawers:

- objective and current phase;
- agent and model identity;
- provider and capability;
- consequence class;
- expected and observed state roots;
- lease generation and expiry;
- authority decision and denial codes;
- provider operation status;
- receipt root and verification state;
- compensation status;
- event timeline.

## Interaction rules

- Read-only inspection is available without mutation controls.
- D2+ controls display an explicit confirmation step.
- D3+ confirmation requires the operator to review the exact target and digest.
- D4 controls are absent until policy admits them.
- Retried operations reuse the original idempotency key only when the provider contract permits it.
- UI optimism never represents an external mutation as committed before receipt verification.

## React implementation rules

- Prefer server-side or route-level parallel data loading; eliminate avoidable waterfalls.
- Keep provider payloads on the server and serialize only the fields the client renders.
- Dynamically load heavy trace, graph, and diff viewers.
- Use stable primitive dependencies and derived state rather than effect-driven mirrors.
- Use transitions for non-urgent filtering and large evidence views.
- Version and minimize persisted browser state.
- Respect reduced motion and WCAG 2.2 AA interaction targets.

## ChatGPT/MCP widget

The widget uses a decoupled data/render architecture:

- `search` and `fetch` expose knowledge and execution records.
- data tools return concise `structuredContent`.
- render tools attach the versioned operator-console resource URI.
- large trace payloads remain widget-only metadata.
- mutating component actions call governed MCP tools and display returned authority evidence.

CSP is exact and versioned. The widget does not embed arbitrary providers or fetch from undeclared domains.

## Design direction

The visual system should communicate evidence and authority, not science-fiction decoration:

- dense but legible operational typography;
- calm neutral surfaces;
- one semantic color system for admitted, denied, pending, failed, and compensated states;
- no decorative metrics;
- receipts and state roots are copyable and verifiable;
- provider logos never outweigh the authority decision.

A visual prototype must be generated and selected before frontend implementation.