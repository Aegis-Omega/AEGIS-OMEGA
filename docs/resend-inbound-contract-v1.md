# Resend inbound adapter v1 — fail-closed local evidence contract

Contract review: **2026-10-04**. Status: **repo-local implementation with offline regression evidence**. This is not a production deployment, Resend webhook registration, inbox creation, email send/reply path, capability grant, or agent-dispatch path.

## Provider contract pinned to current Resend behavior

The adapter accepts exactly one webhook event type:

- `email.received`

It **rejects** `inbox.email.received` and every other event type with `EVENT_TYPE_UNSUPPORTED`. Resend Inboxes exists as a beta product/resource surface, but the current webhook subscription contract exposed to this integration uses `email.received`; the adapter does not invent a separate beta webhook event from newsletter wording.

For `email.received`, the signed object must contain only the reviewed fields. Required `data` fields are:

- `email_id`
- `created_at`
- `from`
- `to`
- `subject`
- `message_id`
- `bcc`
- `cc`
- `attachments`

`received_for` is optional signed metadata. It is never treated as identity, approval, authority, or the routing selector.

The trusted route is selected by the configured receiving-address allowlist. Every normalized address in `data.to` must belong to that allowlist. `from`, `cc`, `bcc`, subject text, Message-ID, `received_for`, and attachment metadata never select authority.

The webhook payload is treated as metadata only. This adapter does not call Resend APIs to fetch message text, HTML, MIME parts, headers, attachment bytes, or download URLs. It does not render HTML or resolve remote URLs. Every admitted observation records `content_state: NOT_FETCHED`, `attachment_content_state: NOT_FETCHED`, `execution_state: NOT_EXECUTED`, and an empty `granted_capabilities` list.

Unexpected provider fields fail closed with schema drift rather than being silently accepted.

## Existing AEGIS model; zero authority expansion

The implementation imports the existing AEGIS authority primitives from `harness/sdk/sovereign_execution.py`:

- `ExecutionIdentityEnvelope`
- `AuthorityRequest`
- `AuthorityEvaluator`
- `PolicyDecision`
- `EventEnvelope`
- canonical hashing utilities

The adapter does not define a second authority system.

The trusted host supplies the runtime identity, route, endpoint scope, signing key(s), durable journal, policy, and capability registry. None of those bindings may be derived from webhook JSON or email content.

The transport identity must satisfy all of the following neutral bindings:

- `actor_class=TRANSPORT_ADAPTER`
- `actor_identity=resend-inbound`
- `model_identity=NONE`
- `observed_authority=NONE`
- `approval_reference=NONE`
- `tool_identity=resend_inbound`
- `requested_capability=resend.inbound.observe`
- `authority_domain=<trusted configured routing domain>`

`resend.inbound.observe` is a **request name**, not a grant. The inspected capability registry does not map it. This change does not add that mapping and does not alias it to `mcp.execution.read`, `mcp.platform.status`, or any other existing capability.

Therefore a correctly signed and normalized message is expected to remain `VERIFIED_NOT_ADMITTED` under the current registry. That is a useful result: the provider observation can be preserved as blocked evidence without turning email into executable agent authority.

The external From address remains `UNVERIFIED_EMAIL_CLAIM`. A valid Resend/Svix webhook signature authenticates the provider delivery, not mailbox ownership, SPF/DKIM/DMARC status, S/MIME/PGP identity, operator approval, or an AEGIS actor.

## Direct Python interface

```python
from harness.sdk.resend_inbound import InboundAdapter, LocalJournal, Route

adapter = InboundAdapter(
    secrets=(webhook_signing_secret,),
    route=Route(
        endpoint_scope=endpoint_scope,
        routing_domain=authority_domain,
        receiving_addresses=receiving_addresses,
    ),
    identity=dedicated_resend_transport_identity,
    evaluator=existing_authority_evaluator,
    registry_root=loaded_registry_root,
    journal=LocalJournal(private_journal_path),
)

result = adapter.handle(raw_request_bytes, original_header_pairs, method="POST")
```

The caller must preserve the **original raw request bytes** and ordered header pairs. A dictionary that has already collapsed duplicate headers is not equivalent input.

## Local CLI execution seam

`scripts/resend_inbound_ingest.py` exposes the same adapter through a local stdin/stdout process boundary so an agent/tool can submit an already-received webhook without creating an HTTP bridge or cloud trust boundary.

Input is one JSON object on stdin:

```json
{
  "raw_body_base64": "<base64 original body>",
  "headers": [["Content-Type", "application/json"], ["svix-id", "..."], ["svix-timestamp", "..."], ["svix-signature", "..."]],
  "method": "POST"
}
```

Trusted configuration is environment-bound and is **not accepted in tool/request arguments**:

- `AEGIS_RESEND_EXECUTION_IDENTITY_JSON` — dedicated `ExecutionIdentityEnvelope` for actor `resend-inbound`; deliberately separate from the general `AEGIS_EXECUTION_IDENTITY_JSON` used by other AEGIS execution paths.
- `AEGIS_RESEND_WEBHOOK_SECRETS_JSON` — JSON array containing one or two `whsec_` signing secrets.
- `AEGIS_RESEND_RECEIVING_ADDRESSES_JSON` — JSON array of trusted receiving addresses.
- `AEGIS_RESEND_ENDPOINT_SCOPE` — stable replay/dedup namespace.
- `AEGIS_RESEND_ROUTING_DOMAIN` — must equal the identity authority domain.
- `AEGIS_RESEND_JOURNAL_PATH` — absolute path to the private durable SQLite journal.

The CLI loads policy, skill tree, and capability map only from their repository-controlled paths. Missing/malformed trusted configuration fails closed before retaining a candidate. It performs no network I/O, message/attachment fetch, email send/reply, agent dispatch, capability mutation, deployment, or provider mutation.

Every CLI result includes `external_effect: NOT_EXECUTED`.

## Verification and resource limits

| Boundary | v1 policy |
| --- | --- |
| Webhook signature | Svix v1 HMAC-SHA256 over `id.timestamp.original_body`; strict base64; constant-time comparison; one or two trusted `whsec_` keys. Resend bearer/API keys are not accepted as webhook authentication. |
| Delivery freshness | `svix-timestamp` must be within ±300 seconds of the trusted host clock. |
| Request body | Nonempty original bytes, maximum 65,536 bytes; POST only; JSON content type only; compressed content rejected. |
| Header evidence | At most 32 ordered pairs and 8,192 accounted bytes; duplicate names, malformed names, controls, or missing Svix headers fail closed. |
| Signature candidates | At most 8 space-separated signature candidates; at least one valid v1 signature is required. |
| JSON | UTF-8; duplicate keys rejected; nonfinite numbers rejected; maximum nesting depth 16; unexpected object keys fail closed. |
| Sender | One conservative ASCII dot-atom mailbox; optional constrained display name; domain lowercased only. Local-part case, dots, and `+tag` are preserved. |
| Recipients | At most 10 per field and 20 total across `to`, `cc`, `bcc`, and optional `received_for`. |
| Subject / Message-ID | Maximum 2,048 / 512 UTF-8 bytes; controls and non-NFC text rejected. RFC Message-ID is data, not the replay key. |
| Attachments | At most **8 metadata records**. Only `id`, optional `filename`, `content_type`, `content_disposition`, and `content_id` are accepted. Download URLs, bytes, size assertions, and fetch instructions are rejected as schema drift. No attachment content is fetched. |
| AEGIS payload | Existing `EventEnvelope.validate` enforces 16,384 bytes. |
| Local journal | Defaults: 1,000 observations and 10,000 delivery IDs. Full/inconsistent storage fails closed; no eviction or in-memory fallback. |
| CLI stdin | Maximum 131,072 bytes; base64 body field maximum 90,000 characters. |

These are local AEGIS policy bounds, not claims about Resend platform maximums or full RFC mailbox support.

## Replay and crash boundary

The SQLite journal uses `BEGIN IMMEDIATE` and commits the observation plus delivery record atomically.

Deduplication is scoped by trusted endpoint scope and provider email identity. It survives process restart and signing-key rotation. A new delivery ID for the same normalized provider email remains a duplicate. Reusing a delivery ID for different bytes is rejected. Reusing the logical provider message identity with conflicting normalized metadata is rejected.

There is no automatic dedup TTL. Manual replay later remains a duplicate unless the operator deliberately changes/removes journal state through a separate governed process.

The journal stores normalized metadata, identity/decision/event evidence, and digests. It does **not** store webhook signing secrets, signature headers, or original raw bodies. New journal files are created with mode `0600`.

The journal is evidence storage, not an executable queue. Database loss destroys replay history; there is no distributed exactly-once guarantee.

## Result contract

| Status | Meaning | Executable effect |
| --- | --- | --- |
| `VERIFIED_NOT_ADMITTED` | Provider signature/schema/route verified; existing evaluator denied the requested observation capability; blocked evidence persisted. | `NOT_EXECUTED` |
| `VERIFIED_OBSERVATION_ONLY` | Existing evaluator explicitly admitted only the D0 observation. | `NOT_EXECUTED` |
| `DUPLICATE` | Previously recorded delivery/logical message; no new event produced. | `NOT_EXECUTED` |
| `REJECTED` | Authentication, schema, route, configuration, authority service, or journal boundary failed closed. | `NOT_EXECUTED` |

An eventual HTTP wrapper may map durable success/duplicate to 2xx and retryable infrastructure failures to 5xx, but **no HTTP wrapper is introduced here**.

## Offline regression commands

Run from repository root:

```bash
python -m compileall -q \
  harness/sdk/resend_inbound.py \
  scripts/resend_inbound_ingest.py \
  tests/test_resend_inbound.py \
  tests/test_resend_inbound_ingest.py

python -W error::ResourceWarning -m unittest discover \
  -s tests -p 'test_resend_inbound*.py' -v

python -m pytest -q -W error::ResourceWarning \
  tests/test_resend_inbound.py tests/test_resend_inbound_ingest.py
```

The bounded suite covers signature tamper, stale/future delivery timestamps, duplicate headers/JSON keys, sender ambiguity, route mismatch, unsupported event types, schema drift, attachment metadata bounds, replay/dedup across restart, concurrent delivery, journal rollback/capacity/inconsistency, identity/registry/policy mismatch, capability non-inheritance, CLI missing/malformed trusted configuration, dedicated transport identity separation, and CLI subprocess fail-closed behavior.

## Exact source binding and non-claims

Primary repository: `Aegis-Omega/AEGIS-OMEGA`.

Reviewed base:

- `main`: `495bfd85d79abcb2b4f6898fe9c156488492426a`
- authority-core blob `harness/sdk/sovereign_execution.py`: `d0fb7848dc0296b2c95f92dd11265cd7efbb7e88`

This work does **not** claim:

- live Resend inbound delivery was received;
- a Resend webhook or Inbox was created;
- message bodies or attachment bytes were fetched/scanned;
- `resend.inbound.observe` is currently granted;
- an email triggered an agent/tool action;
- Supabase, Vercel, Cloudflare, or another production endpoint was deployed by this integration;
- hosted GitHub Actions executed successfully while the repository owner account remains billing-locked.

The intended admission path remains: provider verification → normalized metadata → dedicated transport identity → existing `AuthorityEvaluator` → evidence journal. Execution authority is a separate decision and is not inferred from email.
