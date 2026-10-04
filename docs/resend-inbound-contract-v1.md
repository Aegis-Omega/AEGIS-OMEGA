# Resend inbound adapter v1 — local, metadata-only contract

Contract review: **2026-10-04**. Status: **offline implementation and regression evidence**, not a deployment or operational admission. New files only; no changes to outbound Supabase functions, `platformConsole.ts`, the capability registry, policy, or existing AEGIS authority implementation.

## Upstream contract, not newsletter inference

Two distinct provider contracts are supported, with separate strict decoders:

| Provider event | Routing binding | Payload source |
| --- | --- | --- |
| `email.received` | All normalized `data.received_for` recipients must belong to the trusted route allowlist. `to`, `cc`, `from` and `reply_to` never select authority. | `data`; requires `email_id`, provider creation time, sender/recipient metadata, subject, Message-ID and attachment metadata. |
| `inbox.email.received` | Exact allowlisted `data.inbox_id`; nested thread/email IDs must match the outer IDs; direction must be inbound and folder must be inbox. | `data.email`, with `data.thread` consistency checks. `data.source == system` is a provider-pipeline marker, not an agent identity. |

The Inboxes event contract is explicitly private beta and may change. An added/removed field in the objects decoded here stops processing with a schema error; upgrade fixtures and review the contract before widening acceptance. Ordinary Receiving and Inboxes are not interchangeable APIs. The stable identity of an email across the two products is **not established**; subscribe a given route to one appropriate product, rather than assuming cross-product deduplication.

The ordinary webhook carries metadata, not email bodies, MIME headers or attachment bytes. The documented Inboxes event likewise contains metadata. This adapter does **not** call any body/detail/attachment endpoint, render HTML, resolve URLs or create inboxes. Every candidate says `content_state: NOT_FETCHED`. Supplying `text`, `html`, `verified`, an authority field or another unexpected field in the signed provider object does not bypass the boundary.

Account inspection used a read-only `list-inboxes(limit=1)` call. It returned “No inboxes found.” That establishes no configured inbox was found, **not** that beta entitlement was denied or enabled. No real inbound webhook was received or replayed. All request fixtures in this change are synthetic.

Official sources reviewed:

- https://resend.com/docs/webhooks/inboxes/email-received
- https://resend.com/docs/webhooks/emails/received
- https://resend.com/docs/webhooks/verify-webhooks-requests
- https://resend.com/docs/dashboard/receiving/get-email-content
- https://resend.com/docs/dashboard/receiving/attachments
- https://resend.com/docs/webhooks/retries-and-replays
- https://docs.svix.com/receiving/verifying-payloads/how-manual

## Existing AEGIS model and zero authority expansion

The implementation imports, rather than duplicates, `ExecutionIdentityEnvelope`, `AuthorityRequest`, `AuthorityEvaluator`, `PolicyDecision`, `EventEnvelope` and canonical hashing from `harness/sdk/sovereign_execution.py`.

The operator-controlled host supplies the runtime identity, route, endpoint scope, signing keys, journal and actual policy/registry. Load the registry and its root together using the existing `load_capability_registry`; load the policy with the existing `load_policy`. Do not populate any of these inputs from email, webhook JSON or claimed authentication results. This adapter is not a new registry loader, workspace verifier, identity issuer or permission authority.

Required neutral runtime fields are `actor_class=TRANSPORT_ADAPTER`, `actor_identity=resend-inbound`, `model_identity=NONE`, `observed_authority=NONE`, `approval_reference=NONE`, `tool_identity=resend_inbound` and `requested_capability=resend.inbound.observe`. The authority domain must equal the configured routing domain. All existing repository/source/workspace bindings must validate. Registry and policy roots must match the trusted runtime binding. The full workspace and registry evidence still belong to the existing host/admission process; validating an envelope alone does not establish an operating environment.

`resend.inbound.observe` names a **request**, not a registered capability. The inspected capability map does not contain it. Do not alias it to `mcp.execution.read` or `mcp.platform.status` to manufacture permission. This change neither adds that mapping nor changes existing grants. The default fixture uses the real evaluator with an empty registry, deliberately reproducing the unmapped-capability denial. It does not claim to have loaded the entire live skill tree. A separate explicitly synthetic positive D0 fixture tests the existing evaluator's allowed-observation path; its registry entry is test-only.

The adapter evaluates **D0 only**, without an approval grant or dispatch call. The envelope binds the trusted transport adapter as its sender identity. The normalized external address lives under `payload.data.sender`, with `sender_authentication=UNVERIFIED_EMAIL_CLAIM`. The webhook proves possession of the provider signing key, not SPF/DKIM/DMARC validity, S/MIME/PGP identity, ownership of the From mailbox, operator approval, or authority conveyed by `source=system`.

A valid but denied request produces a blocked evidence envelope with the actual evaluator's denial root and zero score. The journal is transport-owned local evidence storage, **not** the agent's executable queue. The result never changes `observed_authority`, creates a mutation receipt, registers a capability, calls an agent or performs an external action. `receipt_reference` remains the existing zero-hash sentinel because no execution receipt exists. A D0 admitted fixture remains observation-only; all outputs state `NOT_EXECUTED` and grant no capabilities.

## Python interface

```python
from harness.sdk.resend_inbound import InboundAdapter, LocalJournal, Route

# These variables are supplied by the trusted host, never by the request.
# identity must carry the neutral fields and existing bindings described above.
adapter = InboundAdapter(
    secrets=(webhook_signing_secret,),
    route=Route(endpoint_scope, authority_domain, receiving_addresses, inbox_ids),
    identity=identity,
    evaluator=existing_authority_evaluator,
    registry_root=loaded_registry_root,
    journal=LocalJournal(private_journal_path),
)
result = adapter.handle(raw_request_bytes, original_header_pairs, method="POST")
```

The argument is **original header pairs**, not a dictionary that has lost duplicate-header evidence. Preserve original request bytes. The HTTP host must bound streaming reads before collecting the body and must not decompress, parse/re-encode, or blindly acknowledge a request before this boundary returns. There is no HTTP server, Supabase entrypoint, API key, environment-secret reader, deployment manifest or network dependency in this change.

## Verification and resource limits

| Boundary | v1 policy |
| --- | --- |
| Webhook signature | Svix v1 HMAC-SHA256 over `id.timestamp.original_body`; strict base64; constant-time comparison; one or two trusted `whsec_` keys, not a Resend API bearer token. |
| Delivery freshness | At most 300 seconds before or after the host clock; signed provider event timestamps are separately syntax-checked, but old emails can be replayed with fresh delivery signatures. |
| Headers | At most 32 pairs and 8,192 bytes of accounted names/values/separators; duplicate names, controls, malformed names and unsupported signing headers fail closed. Only documented `svix-*` names are supported, not white-labelled aliases. |
| Signatures per request | At most 8 space-separated candidates. Unknown versions do not authenticate the request; at least one valid v1 signature is required. |
| Body | Nonempty raw bytes, at most 65,536 bytes. POST and explicit JSON content type only; compressed content rejected. |
| JSON | UTF-8, unique keys, no nonfinite numbers, depth at most 16; strict decoded object keys. |
| Sender | One ASCII dot-atom mailbox, optional constrained display name; domain lowercased only. Local-part case, dots and plus tags remain distinct. Quoted local parts, groups, comments and SMTPUTF8 addresses are unsupported. Display-name controls/bidi and ambiguous multi-address forms are rejected. |
| Address fields | At most 10 per field, 20 across recipient fields including `received_for`; a mailbox is at most 254 characters and local part at most 64. |
| Subject / Message-ID | At most 2,048 / 512 UTF-8 bytes, respectively; no control characters or non-NFC text. RFC Message-ID is data, never the replay key. |
| Attachments | **Zero permitted**, including inline items and metadata with missing/negative/large size. Maximum admitted attachment bytes is therefore zero; no fetching, MIME scanning or safe-file claim. |
| AEGIS payload | Existing `EventEnvelope.validate` enforces 16,384 bytes. Only existing top-level `data` and `content_type` fields are used. |
| Local storage | Defaults to 1,000 observations and 10,000 delivery IDs. Full or inconsistent storage fails closed; no eviction or in-memory fallback. Limits can be changed only through trusted host configuration. |

These are deliberate local policy bounds, not claims about Resend platform limits or complete RFC mailbox support.

## Replay and crash boundary

SQLite `BEGIN IMMEDIATE` commits the message observation, event chain position and delivery ID atomically. Replay keys include the **server-configured endpoint scope**, provider event family, actual provider email ID and (for Inboxes) inbox ID. The secret itself is not a scope identifier, so key rotation does not silently clear deduplication. Endpoint scope must remain stable across retries, restarts and key rotation, and must not be shared across unrelated accounts.

Exact delivery replays return `DUPLICATE`, without returning a candidate for repeated processing. A fresh delivery ID for the same provider email also deduplicates when normalized metadata matches. Reusing a delivery ID for different bytes or a logical message ID for conflicting metadata is rejected. Dedupe has no automatic TTL: a manual replay after ten days is still a duplicate, as covered by regression. A blocked record does not become admitted merely because policy later changes; any operator-approved re-evaluation must be a separate governed workflow.

The database stores normalized metadata (which can contain personal data), binding/decision/event records, and digests, but not webhook keys, signatures or original bodies. Newly created database files use mode 0600. The host must provide a private trusted directory and appropriate backups/retention. Stored hashes are not a cryptographic proof that a live provider request happened, nor a tamper-proof database. No distributed exactly-once or agent-completion guarantee is made. Database loss or deletion destroys the replay history; restoring state and retention changes require operator control before resuming.

## Results and host acknowledgement contract

| Result | Meaning | Host behaviour |
| --- | --- | --- |
| `VERIFIED_NOT_ADMITTED` | Signature/schema/routing verified; blocked envelope durably recorded with real evaluator denial. | Acknowledge durable receipt with 2xx; **do not execute**. |
| `VERIFIED_OBSERVATION_ONLY` | Existing evaluator allowed only the D0 observation; no execution occurred. | Acknowledge durable receipt with 2xx; **do not interpret as an execution grant**. |
| `DUPLICATE` | Previously recorded delivery/logical message. No event returned. | Acknowledge with 2xx; do not dispatch again. |
| `REJECTED` | No newly accepted envelope or executable effect. Stable error codes only. | Bad auth/schema/route/size: appropriate 4xx. Missing service/configuration, inconsistent/full journal or storage failure: retryable 5xx and operator attention. Never convert failure into success. |

An HTTP acknowledgement confirms transport receipt, not AEGIS admission. Review the provider retry policy when writing a future HTTP wrapper. Subscribe only to supported event types. Changes to beta event shape require explicit review, not silent field acceptance.

## Offline regression commands

Run from the repository root:

```bash
python -m unittest discover -s tests -p 'test_resend_inbound.py' -v
python -m pytest -q
python -m compileall -q harness/sdk/resend_inbound.py tests/test_resend_inbound.py
```

The unittest command requires only the Python standard library. Pytest is an optional runner, not a production dependency. The suite uses actual AEGIS classes and an independent published Svix known-answer signature; other signatures and events are synthetic. It covers concurrent deliveries, restart, key rotation, old-message/fresh-signature replay, failed transactions, full/inconsistent storage, schema/identity attacks and limits.

The delivered replay bundle is a **bounded source snapshot**, not a full repository checkout. Its bare pytest run covers all tests in that snapshot, not the original monorepo's complete CI. No hosted CI, Supabase/Deno integration, HTTP server, live beta body retrieval, production credentials, send, deploy, remote commit or merge has been tested or performed.

## Exact source binding

Primary repository: `Aegis-Omega/AEGIS-OMEGA`.

- Inspected main: `495bfd85d79abcb2b4f6898fe9c156488492426a`.
- Unmodified authority-core git blob: `d0fb7848dc0296b2c95f92dd11265cd7efbb7e88` (41,851 bytes).
- Inspected capability-map git blob: `4f61adb4f2c9b293282ab52c7de0f3d224967a5e`.
- Secondary repository `Aegis-Omega/AegisOmega` inspected main: `ed426124475cc9ee8b4d138b2928ae547352e97b`; not patched or replayed as a separate repository.

Tests stop when the authority-core bytes differ from the reviewed blob; do not remove that guard to hide an upstream change. Rebind and review against a newer source deliberately. A source commit identifies the baseline, not an unsigned new commit containing this local work. The patch contains only the five new adapter/test/fixture/documentation files.


## Local ingest execution seam

`scripts/resend_inbound_ingest.py` is the local process boundary for agents/tools that need to submit an already-received Resend webhook to this adapter without introducing an HTTP bridge. It reads one JSON request from stdin with `raw_body_base64`, ordered header pairs, and optional `method`, then emits exactly one JSON result.

Trusted host configuration is environment-bound and never accepted from webhook data or tool arguments:

- `AEGIS_EXECUTION_IDENTITY_JSON` — pre-bound `ExecutionIdentityEnvelope` for actor `resend-inbound`, capability `resend.inbound.observe`, observed authority `NONE`;
- `AEGIS_RESEND_WEBHOOK_SECRETS_JSON` — JSON array of one or two Resend/Svix `whsec_` signing secrets;
- `AEGIS_RESEND_RECEIVING_ADDRESSES_JSON` — JSON array of configured receiving mailboxes;
- `AEGIS_RESEND_ENDPOINT_SCOPE` — durable replay/dedup namespace;
- `AEGIS_RESEND_ROUTING_DOMAIN` — must equal the identity authority domain;
- `AEGIS_RESEND_JOURNAL_PATH` — absolute path to the private durable SQLite evidence journal.

The CLI loads consequence policy, skill tree and capability map only from their repository-controlled paths. It performs no network I/O, body/attachment fetch, email send/reply, subprocess dispatch beyond its own process invocation, agent dispatch, capability grant, or live provider mutation. Every result includes `external_effect: NOT_EXECUTED`; an unmapped capability remains `VERIFIED_NOT_ADMITTED`. Missing or malformed trusted configuration fails closed before provider data is retained.
