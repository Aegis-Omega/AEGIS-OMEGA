# AEGIS Epistemic Lineage Preflight

This layer extends PR #290's artifact locator. It does **not** replace artifact-existence discovery.

Before implementing a new AEGIS primitive:

1. Run the PR #290 artifact/absence scan across current tree, refs, worktrees and PR metadata.
2. Read `ARTIFACT_REGISTRY`, `TRACEABILITY`, `CORPUS_MINDMAP`, `ONTOLOGY`, and the exact-head Integration Ledger artifact.
3. Resolve the proposal in `LINEAGE_MANIFEST.v1.json` and `LINEAGE_CONFLICTS.json`.
4. Check the Drive triage/timeline for historical source snapshots, replicas, revisions and unresolved bindings.
5. State explicitly whether the proposal is a new root, refinement, successor, fork, rename, or unrelated name collision.
6. If evidence is incomplete, classify `UNKNOWN` and do not create another implementation.

Filename equality, gate-number equality, and lexical similarity are never sufficient lineage evidence.

`python scripts/lineage_preflight.py --proposed-name NAME --semantic-role ROLE [--acknowledge-conflict]`

The preflight does not establish scientific truth or admission. It blocks context-free implementation.
