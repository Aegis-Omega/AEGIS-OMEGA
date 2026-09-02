# AEGIS-Ω product operations

## Plans and limits

| Plan | Requests / period | Tokens / period | Included spend | Models | Retention |
| --- | ---: | ---: | ---: | --- | --- |
| Explorer | 100 | 100,000 | $0 | `aegis-demo` | 7 days |
| Operator | 10,000 | 10,000,000 | $49 | `aegis-demo`, `gemini` | 30 days |
| Sovereign | 100,000 | 100,000,000 | $499 | `aegis-demo`, `gemini`, `claude` | 90 days |

Limits reset at the start of the next UTC calendar month. A request may be rejected when any of requests, tokens, or included spend is exhausted. The inference gateway returns `X-Quota-*` headers, including the plan, each limit and remaining value, and reset time. Limit rejections use HTTP 429 with `error.code = "quota_exceeded"`, a dimension, and a machine-readable retry time.

## Billing and entitlement activation

Checkout creates a pending payment session only. It does not change access. A paid plan is activated solely after the billing provider sends a verified `entitlement.granted` webhook and that event has been durably recorded. Webhook event IDs are idempotent. Invoices become visible in the authenticated dashboard after this grant.

## API keys, usage, and notifications

Keys are shown once at creation, are stored only as hashes, and can be revoked from the API or dashboard. The dashboard exposes current plan, remaining quota, usage history, period-end projections, invoice history, and upgrade choices. Teams can configure integer utilization warnings from 1 through 100 percent. Transient metering failures use a marked, limited grace path rather than silently bypassing quota enforcement.

## Data retention and analytics

Usage and operational metadata are retained according to the plan table. Prompt content, messages, and similarly named properties are removed from funnel analytics by default. Funnel events are limited to signup, API-key creation, first successful request, quota warning, checkout start, conversion, churn, and reactivation.

## Availability, SLA, and support

Model availability depends on the selected plan and upstream provider availability; models may be temporarily unavailable for maintenance, capacity, policy, or regional reasons. The service does not provide a financial-services, safety-critical, or uptime SLA unless a separately signed enterprise agreement says otherwise. Public plans receive best-effort support through the project support channel; enterprise customers should use their contracted support channel and escalation terms.
