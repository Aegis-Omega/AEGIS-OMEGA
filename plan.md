# AEGIS Ω Constitutional Bundle — Execution Plan

1. Snapshot PR #264 exact head immediately before mutation.
2. Write falsification tests first; require an observed RED caused by missing constitutional implementation.
3. Implement only Ω1, Ω2, Ω3 and the explicit Sensorium metadata boundary required by the tests.
4. Run `node --test tests/unit/constitutional_invariants.test.mjs`; require 35/35 and zero skips.
5. Generate a local witness binding the source parent and SHA-256 of spec, implementation and test bytes.
6. Commit the bundle only as a fast-forward child of the freshly observed #264 head. If the head changes, discard the stale parent assumption and recreate the commit on the new parent.
7. Re-fetch #264 after ref update and verify the new exact head contains the bundle.
8. Keep AGNT-004 quarantined until a separate exact-head admission evaluation. Do not infer GitHub CI PASS from this local witness.
