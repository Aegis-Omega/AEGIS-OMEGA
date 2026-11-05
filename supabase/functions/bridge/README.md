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
