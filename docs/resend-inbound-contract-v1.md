# Resend inbound adapter v1 — verified metadata-only boundary

Contract review: **2026-10-04**. Repository baseline: `Aegis-Omega/AEGIS-OMEGA@495bfd85d79abcb2b4f6898fe9c156488492426a`.

This change is deliberately **repo-local and non-deployed**. It adds no capability grant, no agent dispatch, no email send/reply path, no Supabase function, no webhook registration, and no Resend API key reader.

## Provider contract verified before implementation

The current Resend webhook subscription API accepts `email.received` for inbound mail. The current webhook API enum does **not** expose `inbox.email.received`. Resend's Inboxes beta is a resource/thread API; the inbound webhook boundary remains `email.received`.

The adapter therefore accepts exactly one provider event type:

- `email.received`

Every other event type, including `inbox.email.received`, fails with `EVENT_TYPE_UNSUPPORTED` until a future provider contract is independently verified and reviewed.

Current `EmailReceivedEventData` requires `email_id`, `created_at`, `from`, `to`, `subject`, `message_id`, `bcc`, `cc`, and `attachments`. `received_for` is currently optional. Attachment entries require an `id` and may carry metadata such as filename, content type, disposition, and content ID. The webhook does not carry body bytes or attachment bytes.

Sources reviewed:

- Resend OpenAPI `EmailReceivedEvent` / `EmailReceivedEventData`
- Resend Inbound documentation (`email.received`)
- Resend webhook verification documentation
- Resend webhook management API event enum
- Svix manual signature verification contract

Read-only account inspection on 2026-10-04 returned:

- `list_inboxes`: **0 configured inboxes**
- `list_webhooks`: **0 configured webhooks**
- `list_received_emails`: **0 received emails**

The beta `list_inboxes` call itself succeeded, but there is no configured live inbox or webhook to exercise. No resource was created and no message was sent.

## Existing AEGIS authority model; zero authority expansion

The adapter imports the existing classes from `harness/sdk/sovereign_execution.py`:

- `ExecutionIdentityEnvelope`
- `AuthorityRequest`
- `AuthorityEvaluator`
- `PolicyDecision`
- `EventEnvelope`
- canonical hashing helpers

The reviewed authority-core Git blob is `d0fb7848dc0296b2c95f92dd11265cd7efbb7e88`.

The adapter requests `resend.inbound.observe`, but this is only a **requested capability string**. This change does not register it, alias it to an existing capability, or grant it. The trusted host must supply an existing policy/registry and matching roots.

Required neutral identity fields include:

- `actor_class=TRANSPORT_ADAPTER`
- `actor_identity=resend-inbound`
- `model_identity=NONE`
- `observed_authority=NONE`
- `approval_reference=NONE`
- `tool_identity=resend_inbound`
- `requested_capability=resend.inbound.observe`

The external `From` address remains untrusted email data under the payload. A valid Resend webhook signature authenticates the provider delivery; it does **not** authenticate the human sender, establish SPF/DKIM/DMARC success, or convey operator authority.

A valid message with no mapped capability becomes a durable `VERIFIED_NOT_ADMITTED` evidence envelope with the existing evaluator's denial root. No mutation receipt, capability registration, tool dispatch, reply, send, or external action is produced.

## Python interface

```python
from harness.sdk.resend_inbound import InboundAdapter, LocalJournal, Route

adapter = InboundAdapter(
    secrets=(webhook_signing_secret,),
    route=Route(
        endpoint_scope="resend-production-endpoint-v1",
        routing_domain="inbound-email",
        receiving_addresses=("agent@example.com",),
    ),
    identity=trusted_execution_identity,
    evaluator=existing_authority_evaluator,
    registry_root=loaded_registry_root,
    journal=LocalJournal(private_journal_path),
)

result = adapter.handle(raw_request_bytes, original_header_pairs, method="POST")
```

The HTTP host must pass the **original request bytes** and preserve duplicate header evidence as header pairs. Parsing and re-serializing JSON before signature verification is not allowed.

## Verification and bounded input policy

| Boundary | v1 policy |
| --- | --- |
| Webhook signature | Svix v1 HMAC-SHA256 over `id.timestamp.original_body`; constant-time compare; one or two trusted `whsec_` secrets for rotation. API bearer keys do not authenticate webhooks. |
| Delivery timestamp | `svix-timestamp` must be within ±300 seconds of the trusted host clock. |
| Headers | ≤32 pairs and ≤8,192 accounted bytes; duplicate header names, controls, malformed names, and missing signature headers fail closed. |
| Raw body | Non-empty, ≤65,536 bytes, POST only, explicit JSON content type, no compressed content. |
| JSON | UTF-8, unique keys, no non-finite numbers, depth ≤16, strict current provider keys. |
| Event type | Exactly `email.received`; unknown/beta-specific event names fail closed. |
| Sender | One conservative ASCII dot-atom mailbox with optional constrained display name; domain lowercased only. This is normalization, not sender authentication. |
| Recipient routing | `data.to` is normalized as provider-signed metadata; every recipient must be in the trusted route allowlist. Display-name transport recipients are rejected. `received_for` is optional metadata and never grants authority. |
| Address counts | ≤10 addresses per field and ≤20 across `to`, `cc`, `bcc`, and optional `received_for`. |
| Subject / Message-ID | ≤2,048 / 512 UTF-8 bytes; controls and non-NFC text rejected. Message-ID is not the replay key. |
| Attachments | ≤8 metadata records; only current webhook metadata fields are accepted. Attachment bytes are **never fetched**; `size` and `download_url` are not accepted webhook fields. |
| Output content | `content_state=NOT_FETCHED`, `attachment_content_state=NOT_FETCHED`, `execution_state=NOT_EXECUTED`, `granted_capabilities=[]`. |
| Local journal | Defaults: 1,000 observations and 10,000 delivery IDs. Full, inconsistent, or unavailable storage fails closed. |

The route allowlist is a local safety boundary, not a claim that recipient metadata is a cryptographic identity. The trusted endpoint scope and webhook signing secret bind the provider delivery to the configured adapter instance.

## Replay and crash semantics

The local SQLite journal uses `BEGIN IMMEDIATE` and atomically commits:

1. the normalized logical observation;
2. its AEGIS event-chain position/root; and
3. the provider delivery ID.

The logical message key is derived from provider event family and Resend `email_id`; the database primary key is additionally scoped by trusted `endpoint_scope`.

- exact delivery replay → `DUPLICATE`
- new delivery ID for identical logical email → `DUPLICATE`
- reused delivery ID with different signed bytes → `DELIVERY_ID_CONFLICT`
- same logical email ID with conflicting normalized metadata → `MESSAGE_ID_CONFLICT`
- missing/corrupt/full journal → rejection, never in-memory fallback

Deduplication has no automatic TTL. A later operator-approved re-evaluation must be a separate governed workflow; an old denied record does not silently become executable when policy changes.

The journal intentionally does not store signing secrets, signature headers, or raw request bodies. It does store normalized email metadata and therefore still requires normal data-retention and access controls.

## Host acknowledgement contract

| Adapter result | Host behavior |
| --- | --- |
| `VERIFIED_NOT_ADMITTED` | Durable receipt may be acknowledged with 2xx; never dispatch. |
| `VERIFIED_OBSERVATION_ONLY` | Durable D0 observation only; 2xx may acknowledge receipt; never interpret as execution authority. |
| `DUPLICATE` | 2xx may acknowledge; do not dispatch again. |
| `REJECTED` | Invalid auth/schema/route/size → appropriate 4xx. Missing/inconsistent/full storage or authority service → retryable failure and operator attention. |

A transport 2xx means the evidence was durably handled, not that AEGIS admitted or executed the email.

## Local regression commands

```bash
python -m unittest discover -s tests -p 'test_resend_inbound.py' -v
python -m pytest -q tests/test_resend_inbound.py
python -m compileall -q harness/sdk/resend_inbound.py tests/test_resend_inbound.py
```

The standard-library unittest suite covers current-provider schema, independent Svix known-answer verification, signature tampering, duplicate headers, timestamp windows, replay/restart/concurrency, journal failure/capacity, sender ambiguity, recipient routing, unknown event types, attachment metadata bounds, prompt-like subject text, unavailable policy/registry, and zero-authority behavior.

## Stop condition for live activation

Do **not** deploy or register a webhook merely because this adapter passes local tests. Live activation requires all of the following to be separately verified:

1. a deliberate Resend receiving address or beta Inbox exists;
2. a public HTTPS endpoint is selected;
3. endpoint-specific signing secret storage/rotation is configured;
4. durable journal storage semantics are chosen for that runtime;
5. exact-head hosted CI is green;
6. any future capability mapping is reviewed independently instead of being smuggled into transport setup.

Until then, this lane remains a fail-closed evidence adapter only.
