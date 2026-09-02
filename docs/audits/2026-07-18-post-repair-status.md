# AEGIS Operator-Sovereignty Post-Repair Status — 2026-07-18

**Canonical baseline:** `707b2b6486d9ebfb6e38e332bc8d233af65356aa`  
**Supersedes:** the unresolved OSV status in `2026-07-18-operator-sovereignty-evidence-matrix.md`  
**Operator authorization:** repository merge and configured deployment fan-out are authorized.

## Executed repair

PR #208 repaired `.github/workflows/osv-scanner.yml` by:

- updating the Google OSV reusable workflows from `v2.0.0` to `v2.3.8`;
- granting `actions: read` at both workflow and reusable-job scope;
- preserving pull-request, merge-queue, push and scheduled scan triggers;
- preserving recursive scanning and SARIF upload.

The pull-request validation created a real `scan-pr / osv-scan` job. Both target-branch and candidate-branch scans completed successfully, the reporter completed, scan artifacts were uploaded and SARIF upload to code scanning succeeded. The previous `startup_failure` condition is therefore resolved at the pull-request execution boundary.

## Deployment finding

Repository branches and merges automatically trigger configured Vercel and Cloudflare deployment integrations. These are not passive checks: they create externally hosted preview or deployment state.

For AEGIS governance, each deployment integration is therefore an authority domain and durable executor. A complete future mutation receipt must bind:

- repository and commit SHA;
- provider, project and deployment identifiers;
- environment and target URL;
- initiating GitHub event and workflow or integration identity;
- before-state and after-state where available;
- operator authorization reference;
- cancellation, rollback or supersession mechanism;
- terminal deployment status.

Automatic deployment is permitted by the operator. Permission does not remove the observability and receipt requirements.

## Updated P0 sequence

1. **Resolved:** OSV Scanner startup and evidence generation.
2. **Open:** repair `award_graces_for_cycle()` and isolate read-only fitness logic (#204).
3. **Open:** make the Integration Ledger commit-bound and admission-safe (#206).
4. **Open:** sign Scale OS control-plane events and enforce explicit approval state.

## Current decision

Continue implementation and deployment. Consequential changes should move through tested pull requests, expected-head merge fencing and post-merge verification. The repository is not yet fully operator-sovereign, but work is no longer limited to documentation-only staging.
