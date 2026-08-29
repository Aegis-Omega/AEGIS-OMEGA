# Agent Dispatch operations

`AEGIS Agent Dispatch` turns explicitly admitted GitHub events into bounded requests for
the existing `POST /agents/dispatch` route in `vertex/serve.py`. Agent output is
an execution result, not verified knowledge and not repository authority.

## Why the workflow used to show `skipped`

The former workflow placed the whole job behind `if: vars.PROXY_URL != ''`.
When the repository Actions variable was absent, GitHub correctly marked the
job skipped. It also subscribed to a workflow named `CI`, while the repository's
actual CI workflow is named `⊕ AEGIS-Ω Constitutional Automaton`; therefore CI
completion events did not match the declared trigger.

The current contract always runs classification and preflight. It reports one
of these states in the GitHub step summary:

| State | Meaning | External side effect |
|---|---|---|
| `IGNORED_NO_ADMITTED_ROUTE` | The event/action has no admitted route | None |
| `DEFERRED_NOT_CONFIGURED` | URL or dispatch credential is absent | None |
| `READY` | The event is admitted and both settings are present | The authenticated dispatch step may run |
| `DENIED` | Proxy reached; routing receipts deny every candidate | Request occurred; zero agents executed |
| `EXECUTED` | Every returned agent has a matching admitted routing receipt | Governed execution occurred; semantic truth remains unproven |

The network step may still appear skipped in the first two states. That is the
intended fail-closed behavior; the job itself remains visible and successful.

## Required GitHub configuration

Configure both values under repository **Settings → Secrets and variables →
Actions**:

| Kind | Name | Required value |
|---|---|---|
| Variable | `PROXY_URL` | HTTPS origin of the deployed `vertex/serve.py` service, without `/agents/dispatch` |
| Secret | `AGENT_DISPATCH_API_KEY` | The same value supplied to the service as `PLATFORM_API_KEY` |

Do not enable the variable alone. The workflow defers until both values exist.
Direct `pull_request` execution is intentionally not a trigger for this
secret-bearing workflow. Pull-request outcomes arrive through the completed CI
`workflow_run`, which executes the workflow and classifier from the trusted
default branch. Issue dispatch is opt-in through the exact `aegis-agent` label;
comments require an explicit `@aegis-agent` mention.

## Safety and evidence boundary

- `scripts/agent_dispatch_payload.py` selects and truncates untrusted GitHub
  fields; the serialized request is capped at 8 KiB.
- Only `success`/`failure` CI completions, issues carrying the exact
  `aegis-agent` label, and comments explicitly mentioning `@aegis-agent` are
  routed. Direct PR workflows never receive the dispatch credential.
- The call requires HTTPS and `x-api-key`, times out after 30 seconds, rejects
  non-2xx responses, caps the response at 64 KiB, and validates both `results`
  and non-empty central `routing_receipts`. Every result must match an
  `ADMITTED` receipt; a zero-result response must contain only `DENIED` receipts.
- A successful call uploads a 14-day receipt containing result/denial counts,
  lineage metadata, and a response SHA-256 commitment—not model output or the
  untrusted source text.
- The receipt explicitly records `semantic_truth_proven: false`. Dispatch does
  not admit claims, merge code, deploy services, or change authority.

## Local verification

```bash
python3 scripts/test_agent_dispatch_payload.py
```

This test covers action-preserving classification, ignored events, input
bounds, the real CI workflow name, authentication, timeout, response limit, and
fail-closed response checking.

## Remaining production admission blockers

Authenticated transport is necessary but not sufficient. The coordinator requires
an exact action-bound `AEGIS_EXECUTION_IDENTITY_JSON`; the current
`vertex/cloudbuild.yaml` does not provision a trustworthy request-bound identity.
The mapped `orchestration_routing` capability is also `UNOBSERVED` with
`validated_runs=0`. Until both obligations are satisfied by independent evidence,
the correct live outcome is `DENIED`.

The route is owned by the separately deployed `vertex/serve.py` / `aegis-platform`
image. The similarly named `aegis-vertex` bridge image does not package
`/agents/dispatch`. Never install a static execution identity or mutate the
capability registry merely to turn the workflow green.
