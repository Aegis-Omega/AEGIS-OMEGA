# Cloudflare Account Collector V1

- Domain: `AEGIS_CLOUDFLARE_COLLECTOR_V1`
- Read-only API host: `https://api.cloudflare.com/client/v4`
- API operations: exactly four fixed `GET` requests for AI Gateway prepaid balance, AI Gateway topup config, Workers account settings and the Worker script list.
- **No AI inference, chargeable call, route to a user-supplied URL, provider mutation, spend authority, or production deployment.**
- Auth: supply a trusted account-scoped read-only Cloudflare API token. Keep it in a secret manager, never in GitHub or an artifact. This collector is not configured with any account identity, token, or customer-specific value in source.
- Source binding: HTTPS origin and fixed endpoints, account fingerprint and normalized receipt integrity root. Not a Cloudflare signature and not proof that Workers AI free-neuron quota or any hard stop is available.
- GitHub test: `cd sovereign-omega-v2 && npx vitest run test/unit/cloudflare-account-collector.test.ts && npm run typecheck`. The tests use injected fake HTTP readers, never a real provider token.
- Failure semantics: 401, 403, redirects, malformed JSON and network errors leave quota UNKNOWN and `zero_spend_admission=HOLD`.
- The `collectCloudflareAccountResourcesV1` function delegates to the existing `observeConnectedResourcesV1` sanitizer and exposes only safe, whitelisted data. Its output may be used for resource discovery, **not** as a standalone `approved_roots` source for funded or free-quota execution.
