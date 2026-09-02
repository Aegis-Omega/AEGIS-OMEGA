# Law of Silence V2 — mediated agents, visible operator

Agents may not exchange uncontrolled raw peer messages. This restriction never suppresses operator authorization requests, deterministic receipts, security alerts, consequential mutation notices, cancellation state, or failure reporting.

Every peer-directed message uses `EventEnvelope V1` and binds sender identity, recipient or routing domain, source state, requested capability, typed payload schema, payload digest, provenance, policy decision, parent event, sequence, and receipt reference.

Natural-language text is permitted only in the bounded `payload.text` field. It is data, not authority. Authority-bearing fields reject ambiguous Unicode normalization, control characters, hidden formatting, malformed sequence, stale parent state, sender/lease mismatch, schema drift, oversized content, and digest mismatch.

Operator-visible notifications and receipts are constitutionally privileged observability channels. A coordinator, router, hook, workflow, or agent may not invoke the Law of Silence to hide or delay them.
