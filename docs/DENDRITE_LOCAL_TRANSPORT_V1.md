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


## Optional attested local relay (HMAC-SHA256)

The default mailbox remains **unverified local information**. A second, explicitly
opted-in verification mode in agents/dendrite_attestation.py provides relay-key
authentication. It does not verify the originating publication or Git commit,
does not make a scientific claim true, and does not grant tool-use authority.

The signing scope binds: recipient role, event hash, source HEAD, packet hash,
route receipt hash, relay key ID, and information_only=true. The MAC is
HMAC-SHA256 with domain separation. A strict consumer rejects missing,
malformed, altered, unauthorized-key or mismatching attestations. Legacy
read_local continues to return **untrusted**, unauthenticated data;
consumers requiring relay verification MUST use read_attested or its CLI.

Use a private pre-existing, operator-managed raw key file of at least 32
cryptographically random bytes. Permissions must be 0600 and ownership must
match the current Unix user. Do not commit, paste, transmit or log this key.
Pass the file path, never key material, on the CLI:

~~~sh
# From an exact-head PR #773 checkout; no change to protected main
python3 -m agents.dendrite_attestation publish \
  examples/dendrite_formal_observation.json \
  --root "$HOME/.aegis-dendrite-inbox" \
  --key-file "$HOME/.config/aegis/dendrite-relay.key" \
  --key-id operator_relay

# Separate process: strict local authenticated relay read
python3 -m agents.dendrite_attestation read engineering \
  --root "$HOME/.aegis-dendrite-inbox" \
  --key-file "$HOME/.config/aegis/dendrite-relay.key" \
  --key-id operator_relay

# Existing offline research producer (auth off unless explicitly requested)
python3 -m agents.cognitive_pipeline demo \
  --dendrite --source-head "$(git rev-parse HEAD)" \
  --spool-dir "$HOME/.aegis-dendrite-inbox" \
  --relay-key-file "$HOME/.config/aegis/dendrite-relay.key" \
  --relay-key-id operator_relay
~~~

The existing Revenue Engine exposes the same --relay-key-file and
--relay-key-id alongside --spool-dir. Its pre-existing evolution
side-effects still require a disposable checkout. An incomplete relay-key
option pair is rejected before a pipeline run.

**Security limits:**
- A shared HMAC secret authenticates the **local relaying party** only, not
  the original author, original repository, actual theorem proof, or model.
- Shared-key members can forge another member's relay attestation. Therefore
  this is NOT public-key identity, tenant isolation, or end-to-end provenance.
- A replayed, previously authenticated packet remains authenticated; there
  is no expiration, revocation or globally monotonic stream validation.
- Files are plaintext and private to the same OS user; compromise of that
  user account or secret key defeats the relay trust boundary.
- Per-recipient files/attestations are written atomically, but the batch is
  not atomic; rerunning the same publication fills missing signatures.
- No canonical operational EventEnvelope dispatch, capability escalation,
  automatic agent execution, external network transport or settlement.
- Never reuse Kernel One operational signing keys as local relay keys.

Reproduction: python3 -m unittest agents.tests.test_dendrite_attestation -v
(19 dedicated tests in the candidate, including independent-process publishing,
key mismatches, missing-signature denial and strict mode).
