# Cloudflare Remote MCP Contract

Target: authenticated remote MCP server on Cloudflare Workers.

## Runtime

- `/mcp` is the only public protocol endpoint.
- OAuth is mandatory for user-specific tools.
- Durable Objects or Workflows own durable coordination; request state never lives in module globals.
- D1/KV/R2/Queues/Workflows are accessed through bindings, not Cloudflare REST calls from inside Workers.
- External databases use Hyperdrive.
- All promises are awaited, returned, explicitly voided, or attached to `ctx.waitUntil()`.
- Large or unknown responses are streamed.

## Security

- Secrets are provisioned through Wrangler/Secrets Store and never committed.
- Secret comparisons use timing-safe cryptographic comparison.
- Production CORS and CSP use exact allowlists.
- No `passThroughOnException`.
- No public unauthenticated mutation tools.
- OAuth subject is bound into the AEGIS execution identity envelope.
- Provider tokens are scoped per capability and environment.

## AEGIS flow

```text
MCP request
  -> authenticate operator/service
  -> normalize tool input
  -> construct execution-request.v1
  -> call Automaton-3 authority evaluator
  -> deny with receipt OR execute provider call
  -> normalize execution-result.v1
  -> persist durable event and emit receipt
```

## Configuration requirements

- current `compatibility_date` at implementation time;
- `nodejs_compat` only when required by dependencies;
- generated `Env` types from `wrangler types`;
- structured observability with sampling;
- service bindings for internal Worker-to-Worker calls;
- separate preview and production environments;
- explicit CPU, memory, duration, retry, and queue limits.

## Deployment gate

Deployment is blocked until:

- exact Worker code exists and compiles;
- Wrangler schema validates;
- local MCP Inspector tests pass;
- OAuth callback and token rotation are documented;
- replay and idempotency tests pass;
- ChatGPT Developer Mode test succeeds over HTTPS;
- production domain, CSP, and privacy policy are approved;
- Automaton-3 admits the exact deployment candidate.
