# Shared AEGIS operations

Bounded operations slice of GitHub #246, related to #734 and #756. The SOL
capability registry in PR #225 remains an unadmitted candidate; this deployment
view references that source and does not replace the Automaton-3 authority root.

`infrastructure/production.json` binds the existing production domains, cloud
projects, source directories, agent registry and deployment workflows. Inspect
the fleet with `npm run ops:status`; this performs only GET requests and never
calls a model or dispatches an agent. An HTTP success reports reachability,
not agent execution, payment verification or deployment admission.

## One local stack

Copy `.env.example` to `.env` and set server credentials there or in the caller's
environment. Docker Compose reads that file. `npm run ops:check` validates source
bindings and Compose configuration. `npm run ops:up` builds and starts:

| Surface | Address | Runtime connection |
| --- | --- | --- |
| Bridge | http://localhost:7890 | Governance and platform API |
| Cockpit | http://localhost:3000 | Same-origin governance API proxy to bridge |
| Studio | http://localhost:3001 | `/api/bridge` proxy to bridge |

`npm run ops:up:agents` additionally starts the existing Vertex platform on
http://localhost:8081 and a private Redis with a persisted audit-chain volume.
It uses `agents/coordinator.py`, `agents/agents.yaml`, the existing managed-agent
IDs, and the Automaton-3 evaluator. Agent dispatch still requires valid identity,
workspace provenance and approval inputs. A running container alone does not
establish these prerequisites. No recurring agent schedule is installed.

`npm run ops:down` stops this stack. It retains the checkpoint and audit-chain
volumes. Secrets are passed only to server containers; no frontend build receives
provider or Supabase service-role keys.

## MCP and SDK connections

Both `.mcp.json` files expose the same AEGIS, Drive, Gmail and Calendar connections.
The AEGIS entry uses `scripts/start-aegis-mcp.sh`, which resolves the repository
from its own path, builds the existing MCP server when needed, and loads the root
`.env` using Node's env-file loader. Caller environment values take precedence.
Google connections keep their existing remote OAuth configuration.

`AEGIS_BASE_URL` selects the same runtime for the MCP server and existing `aegis`
CLI. Production is `https://aegis-vertex.aegisomega.com`; set
`AEGIS_BASE_URL=http://localhost:7890` for the local bridge. The existing
`AEGIS_BRIDGE_URL` MCP override remains supported. Export the variables when
calling the Python SDK/CLI, which does not load the root `.env` automatically.
Use `AEGIS_API_KEY` for authenticated platform calls. Authority inputs remain
separate from API authentication and are never synthesized by the launcher.

## Hosted production

Existing Vercel projects and GCP/Supabase project IDs are registered in
`infrastructure/production.json`. The hub production release follows
`preview/hub/mcp-production-v1`; its branch must be preserved when deploying.
The product frontends follow `main`. Cloud Run workflows remain manual to retain
the existing billing policy; this integration does not create duplicate services
or change production aliases. The GitHub Actions billing lock and absence of a
configured GCP identity in the managed execution environment still prevent a
hosted Cloud Run release from this session.
