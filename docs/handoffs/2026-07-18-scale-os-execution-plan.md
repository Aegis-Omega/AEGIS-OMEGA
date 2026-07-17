# Scale OS Execution Plan — 2026-07-18

This plan is ordered by dependency and risk. Every step must be verified against current `main` and the live service before execution.

## P0 — Ground truth

1. Review the Scale OS handoff draft.
2. Run `bash scripts/ground-truth.sh` in a real worktree.
3. Verify open PRs, current CI, deployment workflows, and live endpoints.
4. Treat older branch, PR, production, and revenue status statements as historical until rechecked.

## P1 — Signed control plane

Create one narrow implementation PR:

```text
feat(scale-os): add signed event-envelope contract and approval state machine
```

Required scope:

- Canonical Scale OS event schema.
- Deterministic serialization.
- Reuse of the existing Ed25519 signing/verification path.
- Verification, replay, tamper, duplicate, and invalid-approval tests.
- Explicit approval lifecycle and terminal states.
- Repository migrations matching the deployed `scale_os` schema.
- No external messages, cloud IAM, deployment, visionOS, or outreach in the same PR.

## P2 — Always-running orchestrator

1. Add a server-side orchestrator service.
2. Start with read-only GitHub, Drive, Outlook, and Supabase adapters.
3. Use isolated Git worktrees for changes.
4. Make MYTHOS BUILD produce actual patches rather than change descriptions.
5. Run narrow tests, then required test/typecheck/build/hash gates.
6. Create draft PRs only after verification.
7. Keep send, publish, deploy, and merge behind authenticated approval records.

## P3 — Cloud identity

1. Inspect the current Google Cloud workload identity pool, provider, condition, and service-account binding.
2. Repair only the verified repository-identity mismatch.
3. Re-run the failed deployment workflow only after identity verification.
4. Configure Azure managed or federated identity with minimum roles.
5. Bind Microsoft Foundry only after the Azure project/resource identity is confirmed.
6. Use short-lived workload identity; do not create downloadable long-lived cloud keys.

## P4 — Corpus census

1. Connect direct OneDrive/SharePoint access.
2. Identify every authoritative Google Drive, OneDrive, repository, and archive root.
3. Recursively record metadata, hashes, duplicates, version families, sensitivity, evidence status, code links, experiments, and publication readiness.
4. Keep source files in their source systems; store normalized metadata and evidence references in Scale OS.
5. Never treat one folder or ZIP as the complete corpus.

## P5 — Product surfaces

1. Stabilize the evidence/governance API.
2. Build visionOS as an operator cockpit, not the background automation host.
3. Expose system health, evidence links, MYTHOS stages, approvals, competition deadlines, and commercial pipeline state.
4. Keep production deployment and public publishing approval-gated.

## P6 — Distribution

1. Maintain OpenAI and Gemini/XPRIZE competition records with receipts, rules, deadlines, IP terms, repositories, demos, and claims evidence.
2. Prepare outreach and proposals internally.
3. Require operator approval before first contact, proposals, publication, submission, invoicing, or spending.

## Definition of done for each task

```text
live path verified
scope stated
smallest change made
narrow tests pass
required full gates pass
no secret exposure
result recorded in Scale OS
external side effects approved separately
```
