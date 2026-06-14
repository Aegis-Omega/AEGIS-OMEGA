# Claude Code on the Web — AEGIS-Ω environment config (NO Google Cloud)

Paste these two fields into the cloud environment editor (claude.ai → the cloud icon →
**Edit environment**). Source: <https://code.claude.com/docs/en/claude-code-on-the-web>.
This is the full, Google-free setup — the bridge runs on Render, frontends on Vercel,
payments on Supabase, models via the direct Anthropic API. Nothing here touches GCP.

---

## 1. Network access — set to **Custom**

Select **Custom**, tick **"Also include default list of common package managers"**
(keeps npm / PyPI / GitHub / Docker registries), then paste this into **Allowed domains**
(one per line). These are the hosts AEGIS code calls *directly* (MCP connectors —
Supabase, Vercel, GitHub, Cloudflare — route through Anthropic and do NOT need listing):

```text
api.anthropic.com
dashscope.aliyuncs.com
*.supabase.co
*.aegisomega.com
*.onrender.com
onrender.com
*.vercel.app
api-m.paypal.com
api-m.sandbox.paypal.com
*.paypal.com
```

Why each:
- `api.anthropic.com` — direct Anthropic API for the bridge swarm + the tools' Claude backend.
- `dashscope.aliyuncs.com` — Qwen generation for the 3 commercial tools.
- `*.supabase.co` — `api_key_store`, edge functions, swarm memory (REST, not via MCP).
- `*.aegisomega.com` — hub, bridge, product subdomains.
- `*.onrender.com` / `onrender.com` — the new bridge host (Render).
- `*.vercel.app` — preview/prod URLs when verifying renders.
- `*.paypal.com` (+ api-m hosts) — payment capture testing.

> The default **Trusted** level blocks `dashscope.aliyuncs.com` and `api.anthropic.com`,
> which is exactly why tool generation and live swarm runs failed in earlier sessions.
> Switching to **Custom** with the list above fixes that.

---

## 2. Setup script (runs once at container start, snapshot-cached)

No `gcloud`, no Google SDK. Just installs JS + Python deps so sessions start ready
(parallelised to stay under the ~5-minute cache-build limit):

```bash
#!/bin/bash
# AEGIS-Ω web env setup — Google-free. Installs JS + Python deps (cached in the snapshot).
set -uo pipefail
REPO="${CLAUDE_PROJECT_DIR:-/home/user/AEGIS--}"

# JS deps (shared lib + governance runtime + frontends) — parallel, non-fatal
for d in packages/shared sovereign-omega-v2 hub platform-picker hook-generator content-calendar cockpit; do
  [ -f "$REPO/$d/package.json" ] && \
    npm --prefix "$REPO/$d" install --prefer-offline --no-audit --no-fund --silent &
done
wait

# Python deps for the bridge + swarm (anthropic[vertex] pulls the SDK; Vertex is unused)
[ -f "$REPO/sovereign-omega-v2/python/requirements.txt" ] && \
  pip install -q -r "$REPO/sovereign-omega-v2/python/requirements.txt" || true
```

(The repo's `.claude/hooks/session-start.sh` already does the same on every session; the
setup script just makes it snapshot-cached so cold starts are fast.)

---

## 3. Environment variables / secrets (set in the env editor, marked secret)

| Var | Purpose | Secret? |
|-----|---------|---------|
| `ANTHROPIC_API_KEY` | direct Anthropic API (bridge swarm + tools) | yes |
| `AEGIS_USE_VERTEX` | set `false` — force direct API, never Google | no |
| `AEGIS_SWARM_MODEL` | `claude-opus-4-8` (avoids the Fable 5 entitlement block) | no |
| `VITE_DASHSCOPE_API_KEY` | Qwen key for the tools | yes |
| `SUPABASE_URL` | key store + swarm memory | yes |
| `SUPABASE_SERVICE_ROLE_KEY` | server-side key verification | yes |

---

## 4. Container registries (only if you build/pull Docker images here)

Per the official docs, the Trusted list already allows: `registry-1.docker.io`,
`ghcr.io`, `public.ecr.aws`, `mcr.microsoft.com`, etc. You do **not** need `gcr.io`
or `*.googleapis.com` — those are GCP and we're not using them.

---

*Replaces the GCP-centric `GCLOUD_WEB_ENV_SETUP.md` for the off-Google deployment.*
