# AEGIS Ω Source Plane V1

## Scope and origin

An **additive, read-only federated source adapter** for the existing `Aegis-Omega/AEGIS-OMEGA` repository. It adapts selected agent-scale design ideas from OpenAI **Pando** and Anthropic **Scion** without claiming to implement either storage engine.

References:
- https://openai.com/bs-BA/index/scaling-git-at-openai/
- https://www.anthropic.com/research/redesigning-source-control

Existing integration anchor at inspected main SHA `c6f4f2131ab06c5b20cfd3d0eafd99e3ca246bc8`:
- `harness/sdk/repository_knowledge.py` supplies local exact-HEAD snapshots, path/object deltas and content-addressed receipts.
- `.github/workflows/repository-knowledge.yml` has a read-only exact-candidate CI contract.
- Historical PR #400 was closed without merge, but the current `main` coordinator **does** contain a repository-knowledge deny-only dispatch gate (confirmed from `agents/coordinator.py` at the source commit above). Do not attribute that gate to #400 or equate provenance with dispatch authorization. This patch does not change the coordinator.
- GitHub repository cognition (PR #310) provides complete local repository census; this adapter does **not** repeat that census.

## What this working slice adds

- Read sparse file paths from **multiple existing GitHub repositories** using immutable full commit SHAs and GitHub REST Git objects.
- No clone, checkout, local working copy, new branch, new repository, or GitHub mutation.
- Verify blob payloads against the actual **Git SHA-1 blob ID**, computed as `SHA1('blob <size>\\0' + payload)`, and additionally record content SHA-256.
- Resolve only requested tree paths (do not recursively enumerate a monorepo).
- Generate deterministic cross-repo manifests carrying repository, commit SHA, tree SHA, file mode, blob SHA-1, content SHA-256 and manifest digest.
- In-memory, repository-scoped deduplication of repeated immutable API calls and blobs.
- `LocalGitTransport`: reads existing SHA-1 Git object stores without network, clone or checkout; verifies raw commit/tree/blob bytes against Git object IDs.
- `verify_local_repository_binding`: bridges into the canonical AEGIS `repository_knowledge.py`, checks exact local HEAD/tree, and independently re-reads blob content before admitting the read-only evidence document. The canonical file is **not duplicated in this bundle**.
- Fail closed for missing objects, mismatched declared SHA, mutated payload, unsupported submodules, missing permissions, truncation, oversized blobs, malformed paths, unsafe metadata, or non-read authority claims.

## Use

Place `harness/sdk/source_plane.py`, the three `scripts/test_source_plane*.py` test files, and this document in their matching paths **in the existing repo**, on an approved existing development branch. It requires Python 3.11+ and only standard-library modules. No package install.

Run local offline contracts:

```sh
python3 -m unittest discover -s scripts -p "test_source_plane*.py" -v
```

Read only the named files from the specified immutable revisions (the example source SHAs were observed 2026-11-03; replace only after re-verification):

```sh
python3 harness/sdk/source_plane.py \
  --artifact Aegis-Omega/AEGIS-OMEGA@c6f4f2131ab06c5b20cfd3d0eafd99e3ca246bc8:harness/sdk/repository_knowledge.py \
  --artifact Aegis-Omega/formal-conjectures@791f16d6cd8bab1cdc9b3fd4be1272e799eacd3e:lean-toolchain
```

An offline, **already-existing worktree** can be used without any network request:

```sh
python3 harness/sdk/source_plane.py \
  --local-repo Aegis-Omega/AEGIS-OMEGA=/absolute/path/to/existing/AEGIS-OMEGA \
  --artifact Aegis-Omega/AEGIS-OMEGA@<40-char-exact-commit>:harness/sdk/repository_knowledge.py \
  --verify-local-head
```

`--verify-local-head` requires that the canonical `harness/sdk/repository_knowledge.py` is present in the existing AEGIS tree and that the requested commit matches the checked-out HEAD. An older commit can still be read in offline mode without that gate, but must not be represented as current source.

The preceding remote command uses the public GitHub API. Optional `GITHUB_TOKEN` may be supplied for access to authorized private repositories, with **read-only Contents permission**; do not commit or print credentials. The token is never written to the manifest. The manifest is printed to stdout and carries **no source file contents**. Missing access produces `SOURCE_PLANE_DENIED`.

After review, apply the minimal diff from `integration/repository-knowledge-ci.patch` to the *existing* `Run repository cartographer contract` step of `.github/workflows/repository-knowledge.yml`. Keep `permissions: contents: read`; do not add dispatch, deploy, write, secrets, or billing permissions.

## Deliberate boundaries

**VERIFIED locally:** deterministic manifest, **38/38 offline contract tests** including 12 real-Git object-store tests and 4 schema-compatible bridge-boundary tests. The synthetic bridge suite still uses a fake. An additional 8-test suite imports byte-exact canonical `repository_knowledge.py` from `main@c6f4f213` (Git blob `8a4468fa94ae71c3410f89b87d6c0055bf5ba3af`) and proves read-only binding and negative cases with two real local Git repositories. These tests run in a reconstructed local test context, not the full AEGIS repository or native CI. Checks reject forged content even if a manifest hash is recalculated, stale commits, invalid routes and tampered blobs. No production service has been deployed.

**Not yet verified:** end-to-end live GitHub HTTP execution by this Python program; exact-head native CI; organization-wide permission policy; latency gains and cost savings; permissions for private repository read; full decentralized distributed storage; branch writer leases; cross-repo source compatibility; production throughput.

**Trust boundary:** for the remote transport, GitHub API is trusted to supply commit identity, tree identity and tree membership. For the local backend, Git commit/tree/blob object bytes are independently hashed against their Git OIDs. Blob bytes are independently checked against Git's SHA-1 object ID. The manifest digest detects modifications to the manifest, but cannot prove that GitHub's tree assertions were honest, that remote HEAD is still at a specific SHA, that the code is correct, or that an agent may execute/mutate/merge anything.

`verify_manifest_document()` verifies document structure and digest; it does **not** fetch or re-check Git content. This separation is intentional. Any execution/admission must still pass the existing Automaton-3 and repository enforcement gates, independent review and authority lease checks.

**Scale limitations:** at most 100 requested files per manifest; max 2 MiB per blob, 32 path components and 12 MiB API response. This is suitable for scoped agent tasks, **not** a replacement for large-object delivery or a complete repo census.

## Next architecture stages (not claimed implemented)

1. **Read plane:** integrate this pinned sparse adapter into `repository_knowledge` and coordinator routing, guard it with provider-side independent fetches and exact-head CI.
2. **Agent plane:** expose an authenticated `/source/v1` read API and per-agent ephemeral workspaces backed by the existing repository. Instrument cache hit rates and fetch/checkout time before optimizing storage.
3. **Write plane:** propose changesets without mutable branches; verify expected HEAD, lease, fencing token and cross-repo provenance; only existing authorized GitHub PR workflows may actually publish. Never bypass protected main or existing governance.
4. **Scale plane:** only if data demonstrates checkout/CI bottlenecks, consider object-cache daemon, server-side diffs, content-based transfer and per-ref concurrency. No need to invent a Pando/Scion replacement prematurely.

## STATUS

- Repository baseline: `AEGIS-OMEGA@c6f4f2131ab06c5b20cfd3d0eafd99e3ca246bc8` (read-only inspected).
- Formal baseline: `formal-conjectures@791f16d6cd8bab1cdc9b3fd4be1272e799eacd3e` (read-only inspected).
- Candidate: local bundle only; **not pushed, merged, deployed, or admitted**.
- Local: `38/38 tests PASS`; `python3 -m py_compile` PASS. 14 mock REST + 12 real local Git + 4 synthetic bridge interface + 8 real canonical-module tests.
- Hosted CI/prod: `UNKNOWN` for this new adapter.
- Next gate: put the candidate files into a reviewed non-protected integration lane, execute the suite *inside the real AEGIS repo* against the canonical `repository_knowledge.py`, then run read-only exact-head CI. No new repo, branch, deployment, billing or permission expansion.

## V1.2 integration-test receipt (2026-11-03)

The **exact canonical source bytes** of `harness/sdk/repository_knowledge.py` were retrieved from GitHub via the connected read-only repository interface. Their recomputed Git blob OID is `8a4468fa94ae71c3410f89b87d6c0055bf5ba3af` (matching the GitHub tree). The unchanged canonical file was temporarily placed next to `source_plane.py` for 8 true integration tests, then omitted from the distributable patch, which only adds the new source plane module and tests. Existing `.github/workflows/repository-knowledge.yml` is patched without increasing permissions or creating a new workflow. Its original blob OID is `840e3c78f8ccddfae820646ec5248dfa0219ac60`.

The test suite totals **38/38 PASS** in the local staging environment. This supports code-path compatibility, not a source-tree-native hosted PASS, production authorization, or independent end-to-end network performance. `git apply --check` against the independently reconstructed exact old blob files is used to validate the patch.
