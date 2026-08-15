# AEGIS Provider Receipts

Every pull request targeting `main` must add exactly one new JSON receipt in this directory.

The receipt is branch-editable while the PR is open because the file is still new relative to the PR base. After merge it becomes immutable historical provenance: later PRs may add a new receipt but may not modify, rename, or delete an existing receipt.

Required fields:

- `schema_version`
- `receipt_id` — must equal the JSON filename stem
- `provider`
- `model`
- `session_id`
- `session_id_status` — use `EXPOSED_BY_PROVIDER` or `NOT_EXPOSED_BY_PROVIDER`; never invent a hidden provider session ID
- `base_sha`
- `declared_scope`
- `destructive_intent`

For high-risk AI changes, also bind `reviewer_provider` and a 64-hex `review_receipt_hash`. The reviewer provider must differ from the producing provider.

For physical deletion, `destructive_intent` must be true, the operator must issue `operator_approval_id`, and every deleted path must have a path-level reconciliation disposition. Physical deletion is admitted only under `DELETE_BYTE_DUPLICATE_ONLY`.

A single-ref absence claim such as “not on main, therefore absent from AEGIS” is non-admissible. Repository topology and relevant branch lineage must be observed first.
