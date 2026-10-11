# AEGIS Dendrite Mesh — opt-in local cross-process handoff (v1)

## What actually runs

`agents/dendrite_mailbox.py` is a minimal local transport adapter for
`agents/dendrite_system.py`, not another agent runtime or coordinator.
It materializes validated, inert informational messages on disk and independently
reconstructs their bounded topology and source-record hashes when read.

Each recipient's own folder contains one `<event_hash>.json` file. Messages
survive the Python publisher process ending and are readable by another
Python process with filesystem access. Files are immutable by protocol:
repeating the same event is deduplicated, and a conflicting file fails closed.
If a batch is interrupted, retrying the same informational receipt can finish
missing recipients. **The entire multi-recipient batch is not atomic.**

Default: disabled; no network, model call, autonomous execution, spending,
skill promotion, formal-proof promotion, payment settlement or governance authority.

## Exact commands

From an AEGIS-OMEGA checkout of PR #773:

```sh
# 1. Formal, security, engineering or operations source record.
# See examples/dendrite_formal_observation.json (explicitly synthetic).
python3 -m agents.dendrite_mailbox publish \
  examples/dendrite_formal_observation.json \
  --root "$HOME/.aegis-dendrite-inbox"

# 2. Independent process, informational read only.
python3 -m agents.dendrite_mailbox read engineering \
  --root "$HOME/.aegis-dendrite-inbox"

# 3. Existing research path, optional persistence.
python3 -m agents.cognitive_pipeline demo \
  --dendrite --source-head "$(git rev-parse HEAD)" \
  --spool-dir "$HOME/.aegis-dendrite-inbox"

# 4. Existing revenue path: ONLY IN A DISPOSABLE WORKTREE.
python3 -m agents.revenue_engine demo \
  --dendrite --source-head "$(git rev-parse HEAD)" \
  --spool-dir "$HOME/.aegis-dendrite-inbox"
```

The Revenue Engine's pre-existing `run_revenue_cycle` may write
`agents/adaptive_lineage.json` and alter its skill-tree registry.
Those producer side effects are *not* introduced or authorized by this transport.
Never run that producer demo casually in a protected repository checkout.

Formal source producer on [formal-conjectures PR #82](https://github.com/tarikskalic33/formal-conjectures/pull/82):

```sh
python3 scripts/export_aegis_dendrite.py --repo . > /tmp/aegis_lean_source.json
# Move the exported JSON to the authorized local AEGIS checkout, then:
python3 -m agents.dendrite_mailbox publish /tmp/aegis_lean_source.json \
  --root "$HOME/.aegis-dendrite-inbox"
```

Use only authorized, nonsecret data. Informational payloads are **plaintext**.
The local directory and recipient folders must be owned by the current Unix user
and have no group/other permissions (0700); individual packet files are 0600.
Root paths must be absolute. Parent folders are under the operator's control.
Symlinks at the root/recipient/file level are rejected. No public cloud transport
or cross-tenant access is implemented.

## Security and epistemic contract

- Sender is **not authenticated**; hashes show consistency, not publisher truth.
- `UNVERIFIED_SOURCE_CLAIM` and `NOT_VERIFIED` are intentional, even for
  successful Lean builds, KAN scores, or revenue forecasts.
- Every inbox packet binds the event hash, original source commit/reference,
  exact recipient and source claim, and recomputed TTL-limited route.
- Reconstructed topology denies recipients that were not subscribed.
- `QUARANTINE` is restricted to security/oversight roles.
- Reading a file never invokes an agent or evaluates its text as instructions.
- Plaintext data handling, ACLs, quota management, lifecycle expiry, remote
  persistence, event-signing, authenticated publisher identities, and
  operational `EventEnvelope` mediation require separate review.
- No production guarantee: a crash between two per-recipient writes can produce
  an incomplete batch; a retry repairs the missing recipients. This is an
  **informational local spool**, not exactly-once distributed delivery.

## Tests / admission

```sh
python3 -m unittest \
  agents.tests.test_dendrite_mesh \
  agents.tests.test_dendrite_system \
  agents.tests.test_dendrite_mailbox -v
```

Existing `.github/workflows/ci.yml` Python Bridge job includes these tests.
A GitHub workflow showing `SKIPPED` or no executed steps is **not** a
native success. Do not merge or activate external delivery while exact-head
hosted tests, signature policy and independent review remain unresolved.
