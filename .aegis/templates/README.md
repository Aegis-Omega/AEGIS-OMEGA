# AEGIS Authority State Card V2

`authority-state-card-v2.template.json` is a fail-closed template, not evidence. Its zero digests and `REPLACE_*` values are sentinels. The template defaults to `DENY`, every mandatory verifier defaults to `NOT_RUN`, and no sentinel-bearing instance is admissible.

The binding model is inherited from `.aegis/experiments/pr-253-rfc8785-fail-closed-v1.json`: candidate commit/tree, expected parent SHA/root, policy blob, claims-ledger root, admission workflow blob, and admission executable blob are part of the subject.

Load-bearing claims must be `COMPUTED` or `THIRD_PARTY_ATTESTED`; a `DECLARED` load-bearing claim is denied. `source_entailment` is an independent gate. Replay authority is evaluated at an explicit time and requires an available custody manifest. Ledger synchronization requires a named verifier, execution reference, and matching roots.

The card hash is SHA-256 over RFC 8785/JCS canonical bytes after replacing these fields with `null`:

- `/attestation/canonical_hash`
- `/attestation/signature`
- `/external_anchor/anchored_hash`

The last exclusion prevents recursive hashing when the external anchor records the card hash.

`validateAuthorityStateCardV2()` is the executable admission predicate. `APPROVE` is invalid unless every mandatory check and every entailment edge passes, replay remains unexpired and in custody, ledger roots synchronize, the attestation recomputes, and an external anchor binds the same hash.

Current status on PR #258: implementation and tests are present, but exact-head execution is not established. The PR remains draft and must follow PR #253.
