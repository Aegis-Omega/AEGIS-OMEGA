# Security Policy

## Supported Versions

Only the `main` branch is supported. There are no versioned releases. Security fixes
land through reviewed, exact-head pull requests and deploy from an explicitly admitted
`main` revision.

## Repository-Wide Security Invariants

These requirements apply to every executable surface in this repository, including
services, browser applications, CI workflows, Supabase functions, MCP integrations,
commercial tools, scripts, and future components.

They are acceptance requirements. Their presence here does **not** claim that every
historical or dormant path already complies.

### Authentication and authorization

- Consequential, cost-incurring, data-bearing, administrative, notification, mutation,
  and model-execution routes must be **deny-by-default**.
- Authentication proves identity; authorization separately proves permission for the
  requested resource, action, tenant, and authority domain.
- Anonymous callers must never be able to claim credentials, invoke paid providers,
  access customer records, mutate governance state, or trigger owner notifications.
- Development bypasses must be impossible in production and must fail closed when the
  environment is missing, malformed, or ambiguous.

### Inputs, tools, and agent boundaries

- All external text, files, model output, MCP metadata, tool results, webhook payloads,
  and retrieved content are untrusted inputs.
- Tool invocation requires an explicit capability allowlist, least-privilege credentials,
  bounded arguments, timeout, rate limit, and auditable principal.
- Prompt content must not grant authority. Instructions discovered in data, webpages,
  repositories, messages, or model output cannot override operator or policy authority.
- Consequential actions require an explicit intent boundary and, where applicable,
  operator confirmation bound to the exact target and side effects.

### Webhooks and replay resistance

- Webhooks must verify signatures over the exact raw request body using a constant-time
  comparison and a bounded replay window.
- Event identity or idempotency keys must prevent duplicate side effects.
- Missing secrets, unsupported event types, invalid timestamps, malformed signatures,
  and ambiguous account or tier mappings fail closed.

### Secrets and credentials

- Secrets must not be committed, logged, embedded in client bundles, returned to models,
  included in receipts, or exposed through diagnostic endpoints.
- Production credentials must be scoped to the smallest practical resource and action
  set, stored in an approved secret manager, and rotated after suspected exposure.
- Service-role, cloud-admin, signing, deployment, billing, and root credentials must not
  be shared with untrusted workloads or general-purpose agents.

### Data protection

- Every data access path must enforce tenant and object-level authorization before
  retrieval, transformation, or tool exposure.
- Responses and logs must minimize sensitive data and redact credentials, tokens,
  payment information, customer records, and private prompts.
- Model and tool outputs must be filtered so that privileged data cannot cross into an
  unauthorized principal or execution context.

### Abuse resistance and resource controls

- Public and semi-public routes require bounded request sizes, concurrency limits,
  rate limits, timeouts, spend ceilings, and safe cancellation.
- Notification systems require authenticated callers, recipient and template allowlists,
  deduplication, and anti-spam controls.
- Provider failures, partial writes, retries, and timeout paths must not silently produce
  duplicate charges, credentials, notifications, or state transitions.

### Supply chain and build integrity

- Production dependency graphs must be lockfile-reproducible and scanned in CI.
- Known high or critical production vulnerabilities block admission unless an explicit,
  time-bounded exception identifies the affected path, compensating controls, owner,
  and expiry.
- Build, test, policy, and security claims must be bound to an exact commit and must not
  be inferred from a different branch, local worktree, historical document, or static
  source count.
- Frozen constitutional files and other protected anchors must be verified from any
  working directory and fail closed on missing or mismatched bytes.

### Auditability and incident evidence

- Security-relevant decisions must record the authenticated principal, target, policy
  result, outcome, and correlation identifier without recording secrets.
- Evidence and receipts must distinguish executed checks, static inventories, skipped
  surfaces, deployment state, and runtime authority.
- Security failures must remain visible. Tests, scanners, or policy checks must not be
  weakened, excluded, or reclassified merely to obtain a green result.

## Security Change Requirements

A security-sensitive change must include, as applicable:

- regression tests for the vulnerable and permitted paths;
- exact-head build, test, lint, dependency, and constitutional-integrity evidence;
- explicit trust-boundary and authorization analysis;
- migration, rollback, and credential-rotation notes where state or secrets are involved;
- no unrelated runtime, deployment, billing, or authority expansion.

A passing test suite proves only the named commands at the tested revision. It does not
by itself prove deployment state, live configuration, absence of unknown vulnerabilities,
or permission to deploy or merge.

## Scope

In scope:

- the governance bridge service (`sovereign-omega-v2/python/`, deployed as Cloud Run
  `aegis-vertex`), including `/platform/*`, `/claude`, and `/node` endpoints;
- the TypeScript and Rust governance, verification, consensus, replay, and execution
  surfaces under `sovereign-omega-v2/`, `aegis-cl-psi/`, `aegis-runtime/`, and `crates/`;
- the hub storefront (`hub/`, `aegisomega.com`) and payment flow;
- Supabase edge functions (`supabase/functions/`), including payment verification,
  credential issuance, agent, chat, notification, and Slack handlers;
- MCP servers, connected-tool boundaries, CI workflows, deployment manifests, operator
  surfaces, and commercial tools;
- shared libraries and packages embedded by those systems.

Out of scope are third-party services themselves, sibling repositories not owned by this
project, social engineering against maintainers, denial-of-service requiring unrealistic
resources, and findings requiring physical access. A vulnerability in this repository's
use or configuration of a third-party service remains in scope.

## Reporting a Vulnerability

Report suspected vulnerabilities privately through **GitHub private vulnerability
reporting** for `Aegis-Omega/AEGIS-OMEGA`: repository **Security** tab →
**Report a vulnerability**.

Do not open a public issue or pull request for an undisclosed vulnerability.

Include:

- affected component, revision, route, role, or workflow;
- reproduction steps or a minimal proof of concept;
- required attacker capabilities and trust boundary crossed;
- impact, affected data or authority, and severity rationale;
- suggested remediation or compensating controls, when available.

Initial acknowledgment and triage target: **72 hours**. Accepted reports will receive a
coordinated remediation and disclosure plan. Declined reports will receive a technical
reason when possible.

## Safe Harbor

Good-faith research that avoids privacy violations, service disruption, persistence,
data destruction, credential use beyond what is required to demonstrate the issue, and
access to unrelated accounts will not be pursued by the project. Stop testing and report
immediately if sensitive data or active credentials are encountered.

## Bounty

There is no bounty program. Good-faith reporters may be credited on request.
