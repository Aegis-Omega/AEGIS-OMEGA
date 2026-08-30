# Resident runtime operations and epistemic contract

The resident runtime is a selectively wired Python capability behind the
production `sovereign-omega-v2/python/bridge.py` handler. It observes a
configured repository, runs bounded work in disposable Git worktrees, persists
receipts, and exposes replay verification. It does not gain merge, deployment,
secret-management, or authority-escalation capability.

## Live HTTP surface

All routes require an `x-api-key` whose tier permits live execution. Stored
artifacts are bound to a pseudonymous HMAC of the verified principal; a caller
cannot select the owner in the request body, and cross-owner reads return 404.

| Method and route | Function |
|---|---|
| `POST /platform/resident/events` | Process a typed repository event through observation, hypothesis, isolated experiment, falsifier, deterministic verification, knowledge decision, and SelfModel update |
| `GET /platform/resident/runs/{run_id}` | Read the owner-bound run receipt |
| `GET /platform/resident/runs/{run_id}/verify` | Replay-check receipt integrity and lineage |
| `GET /platform/resident/status` | Read an authenticated operational projection; it grants no authority |
| `POST /platform/resident/memory/synthesize` | Deterministically synthesize provider records as evidence candidates |
| `GET /platform/resident/memory/syntheses/{synthesis_id}` | Read an owner-bound synthesis receipt |
| `GET /platform/resident/memory/syntheses/{synthesis_id}/verify` | Replay-check synthesis integrity and lineage |

## Knowledge semantics

The terminal verdict vocabulary is `VERIFIED`, `REJECTED`, `QUARANTINED`, or
`UNKNOWN`. A command exit code, hash, citation, model vote, or replay check is
never sufficient on its own to establish semantic truth.

Cross-provider synthesis specifically preserves these distinctions:

- each provider/model record remains a T2 evidence candidate;
- records with a shared provenance root count as one root, not independent
  confirmations;
- contradictions and missing provenance quarantine the candidate;
- generated summaries cannot form cycles that independently support their own
  source claim;
- consensus never promotes a candidate to T1 knowledge;
- replay proves stored bytes and lineage only, and reports semantic truth as
  unproven.

The attached relationship export used during design contains LLM-inferred
relationships and is treated under this same T2 candidate contract. It is not
an independent source of truth.

## Persistence and deployment

`AEGIS_RESIDENT_STATE_ROOT` defaults to `/app/data/resident`. Docker Compose
mounts persistent `/app/data`; free Render storage is ephemeral and therefore
does not satisfy restart-survival requirements. The bootstrap owns a disposable
sensor clone rather than mutating a bind-mounted canonical checkout. If the
sensor cannot initialize, the existing governance bridge stays available while
resident routes fail closed as unavailable/`UNKNOWN`.

When Supabase-backed identity verification is configured,
`AEGIS_RESIDENT_IDENTITY_HMAC_KEY` is required and must contain at least 32
bytes of secret material. Rotating it changes owner pseudonyms and makes prior
tenant-bound receipts inaccessible through the live API unless a separately
admitted migration is performed.

## Focused verification

```bash
cd sovereign-omega-v2
python3 -m pip install -r requirements.txt
python3 -m unittest python/tests/test_resident_live_path.py
python3 -m unittest python/tests/test_resident_bootstrap.py
```

The broader resident/receipt/admission suites live under
`sovereign-omega-v2/python/tests/` and `harness/sdk/tests/`. Test presence alone
does not make other `harness/sdk` modules live; only imports reachable from
`bridge.py` are part of this production surface.
