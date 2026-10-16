# AEGIS Ω Source-Reuse Preflight V1

Scope: existing UWP #753 (knowledge discovery), #758 (evidence-gated learning)
and PR #773 (dendrite/evolution information workplane). **Read-only**.
No second memory engine, dispatcher, provider router or execution authority.

## Why this exists

Historical failure: A new session searches one repository or one Google Drive
page, incorrectly concludes an existing artifact is absent, creates a duplicate
and loses previous exact-head findings. A name in an index is not content proof;
a cached "Verified" label is not independent validation.

The preflight demands an explicit coverage receipt and a reuse decision for each
identified candidate. It **does not perform provider searches itself**. The
authorized GitHub/Google Drive/Library/OneDrive/Supabase connectors perform
discovery; the caller records metadata, not raw source content. If access or
pagination is incomplete, the result stays HOLD.

## Invocation

```sh
PYTHONPATH=. python3 -m agents.source_reuse_preflight task-reuse.json
PYTHONPATH=. python3 -m unittest agents.tests.test_source_reuse_preflight -v
```

Example (timestamps and refs are illustrative; refresh them before an actual
run; no secrets should appear in this manifest):

```json
{
  "task_id": "Aegis-Omega/AEGIS-OMEGA#753",
  "source_head": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "tenant": "aegis-omega",
  "intent": "USE_EXISTING",
  "as_of": "2026-10-16T12:00:00Z",
  "max_age_hours": 24,
  "required_surfaces": ["github", "drive", "library"],
  "surfaces": [
    {"name": "github", "state": "SEARCHED_COMPLETE", "observed_at": "2026-10-16T11:00:00Z"},
    {"name": "drive", "state": "SEARCHED_COMPLETE", "observed_at": "2026-10-16T11:00:00Z"},
    {"name": "library", "state": "SEARCHED_PARTIAL", "observed_at": "2026-10-16T11:00:00Z"}
  ],
  "assets": [
    {
      "asset_id": "github:agents/dendrite_workplane.py",
      "surface": "github",
      "revision": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "evidence": "CONTENT_READ",
      "disposition": "REUSE",
      "reason": "Uses existing governed workplane",
      "access": "TENANT",
      "tenant": "aegis-omega"
    }
  ]
}
```

This exact example returns HOLD because Library coverage is partial. The agent
must disclose the unknown, never invent "nothing exists". A real successful
run requires a pinned source head, complete and fresh required surface checks,
reviewed candidates, and no unresolved conflicts.

## Source trust ladder

- SOURCE_SEEN: title, search result, metadata; insufficient for reuse proof.
- CONTENT_READ: fetched bytes/content (still caller-reported, NOT attested).
- UNDERSTOOD_BY_TASK_TEST: caller reports task-specific examination; no
  independent proof unless separately bound to execution evidence.
- ACTUALLY_REUSED: caller reports reuse, not a benchmark or correctness proof.
- VERIFIED_BENEFIT: caller reports improvement; this preflight **never promotes**
  a skill or validates the claimed benefit.

The exact name and revision of every asset are preserved in the hash receipt.
Private or tenant-only assets cannot be reused across tenants. Rejection of an
existing asset requires an explicit explanatory reason. Proposal of a duplicate
while a reusable artifact is present is HOLD. Unindexed or disconnected stores
must be explicitly identified; pagination is not automatically exhaustive.

## Effects and limitations

- No network access, API key access, database writes, paid inference, automatic
  retries, tool execution, cloud deployment or secret materialization.
- SHA-256 binds the caller manifest and resulting deterministic receipt; this is
  **NOT** source publisher authentication or an operator signature.
- No automatic external provider scan or durable replay database is introduced.
  For independent provenance and durable memory use the existing repository
  knowledge / issue-evolution / HMAC checkpoint components already in #773.
- `READY_FOR_AUTHORITY_REVIEW` means only that this specific metadata manifest
  passed structural and deny-only screening. No D1-D4 privilege is granted.
- #758 still requires independently admitted paired held-out trials, security/
  privacy/cost checks, regressions and protected approval before any learning.
- No Lean proof or product revenue claim is established by this filter.

## Regression contract

`agents/tests/test_source_reuse_preflight.py` covers deterministic replay,
unsearched/partial/stale/future sources, content-unread reuse, duplicate builds,
unexplained rejection, cross-tenant isolation, unknown candidates, duplicate IDs,
unregistered surfaces, self-reported benefit non-promotion, secret/payload schema
rejection, client-authored authority rejection, empty search results, source
prompt-injection inertness and invalid exact source head.

Run it inside the existing Python Bridge workflow job. A skipped/runnerless job
is not test PASS. Signature and main admission remain separately required.
