# `bridge` — deployed, previously sourceless

This function is ACTIVE in production (project `rwehltdwpsncnwxzkwik`,
`verify_jwt: false`) and had **no source in this repository on any branch**.
The source below was recovered from the live deployment on 2026-08-23.

It is committed here so the drift is visible and reviewable. It is **not**
endorsed: `/node`, `/telemetry` and `/resonance` manufacture their payloads.

  t0_verdict, corruption_count, pgcs_passes, is_resonant, is_certified,
  phi_convergent, is_replay_reconstructable   — hardcoded literals
  drift_risk, vcg_error, drift_index, gate_acceptance_rate, resonance_coefficient
                                              — sine functions of Date.now()
  CONSTITUTIONAL_HASH, CATALOG_HASH           — hardcoded strings

Its own header says so: "Data is deterministically derived from time so it
evolves across polls." The hub polls these endpoints and renders the result as
live constitutional telemetry.

This is the same defect fixed in `worker-src/index.ts`, and the same reading of
the root law applies: `AdaptivePower(T) <= ReplayVerifiability(T)` is violated by
a constant that reads as a verdict.

Do not redeploy as-is. Either wire these endpoints to a real source, or return
`null` with `verified: false` and a reason, as the Worker now does.


## Candidate remediation on isolated branch (2026-10-10)

Branch: `fix/aegis-truth-bridge-agent-admission-20261010`. **NOT DEPLOYED; NOT ADMITTED.**

This branch adds an explicit-unavailable `bridge/index.ts`, refuses unattested bridge
JSON in `hub/src/lib/telemetry.ts`, and closes the entire observed
`slack-events -> agent` dispatch path. The agent checks
`x-aegis-agent-secret` before parsing tasks or accessing paid/model/service-role
resources. The Slack webhook refuses absent signature configuration, requires
a signed fresh event and an explicit operator Slack user-ID allowlist, and
uses the same dedicated invoke capability for internal dispatch.

Production deployment prerequisites (do not guess or auto-create values):

- Provision a long cryptographically random `AEGIS_AGENT_INVOKE_SECRET` (32-256
  characters) in the Supabase project runtime, separately from `NOTIFY_SECRET`.
- Configure `SLACK_SIGNING_SECRET` and
  `AEGIS_SLACK_ALLOWED_USER_IDS` (comma-separated verified Slack user IDs).
- Review effective access, downstream notification routing and Slack channel
  confidentiality; sending agent outputs into public channels may expose data.
- Reconcile the **deployed** Supabase `agent` v3 and `slack-events` v3 code
  against this Git branch before deployment. The deployed sources are not byte
  identical to main. In particular, the deployed agent currently uses a
  different Claude model ID/system-prompt structure; never overwrite that
  difference silently.
- Run isolated contract tests from a checkout with Node.js + TypeScript:
  `node --test supabase/functions/agent/tests/admission-chain.test.mjs`.
  Replay actual Edge functions, verify Slack signature validation and
  server-to-server token availability. Observe no unauthorized model/DB calls.
- Deploy only with explicit operator approval and a rollback plan. The synthetic
  bridge must remain untrusted until real governance replay proofs are available.
  This `verified` format gate is NOT a cryptographic attestation verifier.

Current production remains unchanged. Direct HEAD and source-blob checks are
required before admission. Do not promote a local test pass to a live PASS.
