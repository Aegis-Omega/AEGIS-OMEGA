# Integration Ledger evidence boundary

The Integration Ledger is a static inventory of top-level repository areas.
Generator 2.1.0 binds classification to one full commit object ID and reads
regular blobs from that commit's entire tree. The working directory, index,
untracked files and local Git replacement refs do not supply classification
evidence. Missing objects and non-commit identifiers abort generation.

## Status contract

| Status | Evidence in the selected commit |
| --- | --- |
| WIRED | Reserved for separately verified execution; this generator never emits it. |
| LINKED | A scanned `vercel.json` deployment configuration, or at least three external text files containing the area's path prefix. |
| DORMANT | One or two scanned external text files containing that prefix. |
| ORPHAN | No reference found in the scanned text and no scanned deployment configuration. |

References are lexical observations, including references in source comments
and workflow configuration. They do not prove imports, reachability, successful
CI execution, deployment or production readiness. `ORPHAN` is a bounded search
result, not a claim that an area cannot be used.

The scan excludes Markdown (case-insensitive `.md`), the generator's declared
dependency/build exclusions, symlinks, submodule contents and blobs containing
NUL bytes. Workflow text under `.github` remains eligible reference evidence.
Area enumeration comes from tracked paths, so empty or untracked directories
are absent. Names are decoded as UTF-8; invalid path bytes abort the scan.

## Reproduction

```sh
python3 scripts/test_integration_ledger.py
python3 -m unittest discover -s scripts/tests -p 'test_integration_ledger*.py' -v
python3 scripts/integration_ledger.py --write \
  --output-dir /tmp/aegis-integration-ledger \
  --expected-sha "$(git rev-parse HEAD)"
```

The workflow runs both regression suites before generating the paired JSON and
Markdown artifacts. Commit, tree and timestamp are derived from the same pinned
commit. `SOURCE_DATE_EPOCH` does not override source identity or timestamp.
The generator SHA-256 identifies the executed script bytes, including local
development edits; it is not an assertion that those bytes are committed.
Repository name is contextual metadata from `GITHUB_REPOSITORY` or origin.
Byte-for-byte document reproduction therefore requires the same generator bytes
and repository identity as well as the same source commit.

This change continues the local tree-binding correction and covers five
additional reproduced failures: subdirectory truncation, replacement-object
substitution, symbolic refs, abbreviated SHAs and tree IDs. It does not refresh
cognitive anchors or grant admission authority. Execution evidence must remain
bound to a separate verifier and the exact subject it actually checked.
