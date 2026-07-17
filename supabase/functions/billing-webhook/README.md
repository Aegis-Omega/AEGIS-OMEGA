# Billing webhook deployment

Deploy `billing-webhook` with JWT verification disabled. Stripe is the billing
system of record. Configure Stripe to POST to this function with no provider
query parameter. GitHub Sponsors may POST with `?provider=github_sponsors`.
Set `STRIPE_WEBHOOK_SECRET`, `GITHUB_WEBHOOK_SECRET`, and (where applicable)
`STRIPE_SELF_SERVE_PRICE_ID`. PayPal is deliberately not accepted here: its
current order-capture endpoint is not a signed webhook and therefore cannot
deterministically change entitlements.

The inference gateway must call `authorize_api_key_usage(key_sha256,
idempotency_key, quantity)` before dispatching inference. A zero-row response
is a hard deny; successful calls atomically resolve the active entitlement and
record metered usage.
