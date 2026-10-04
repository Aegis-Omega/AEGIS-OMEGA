# AEGIS Dual Report Contract v1

Status: implementation candidate  
Authority effect: **none**  
Canonical authority source: `harness/sdk/sovereign_execution.py`

## Purpose

Every Automaton-3 authority evaluation now has one evidence state with two views:

1. a canonical, machine-readable JSON result for agents, CI, analytics, and downstream verification; and
2. a deterministic Markdown report for operators and reviewers.

The two views are cryptographically bound. The human report is not a second decision engine and cannot grant authority.

## Contract

`harness/sdk/dual_report.py` applies deterministic redaction, binds the result to the exact source commit when available, and emits a `reports` envelope.

The machine payload is the complete redacted authority result plus:

- `source_commit_state`;
- `source_commit`.

The machine payload hash explicitly excludes the `reports` field to avoid self-reference.

The binding chain is:

```text
machine_payload_sha256
        |
        v
AEGIS_DUAL_REPORT_ATTESTATION_V1
        |
        +---- deterministic human Markdown
        |              |
        |              v
        |        human_sha256
        |              |
        +--------------+
               |
               v
AEGIS_DUAL_REPORT_BUNDLE_V1
```

The human view includes the exact-head state, decision summary, evidence roots, denial codes, machine payload digest, and attestation root.

## Fail-closed invariants

- `ADMITTED` cannot be reported without a valid 40–64 hex source commit.
- `ADMITTED` requires valid execution identity, workspace, workspace decision, policy decision, and mutation receipt roots.
- `ADMITTED` cannot carry denial codes.
- A pre-injected `reports` field is rejected.
- Any machine-payload mutation invalidates `machine.payload_sha256`.
- Any human-rendering mutation invalidates its deterministic rendering/hash.
- Any binding mutation invalidates the attestation or bundle root.
- Sensitive values are deterministically redacted before either report is emitted.
- Report generation failure is converted to a fail-closed denial at the CLI boundary.

## CLI

`scripts/automaton3-authority.py evaluate` continues to emit one canonical JSON document on stdout. That JSON now always contains both report views.

Use `--human-output PATH` to materialize the Markdown view separately. Use `--human-output -` to send the Markdown view to stderr while keeping stdout machine-clean.

## Schema

The presentation envelope is described by:

`harness/schemas/dual-report.v1.schema.json`

The schema is descriptive; runtime security is enforced by `build_dual_report` and `verify_dual_report`, which use the repository's existing canonical hashing and fail-closed error model.

## Non-claims

This change does not deploy a new runtime, change D0–D4 policy, broaden tool access, create approvals, merge code, or claim that an external side effect occurred.
