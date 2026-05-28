---
name: mcp-builder
description: Build MCP (Model Context Protocol) servers that connect Claude to external services. Use when the user wants to create a new MCP server, add tools to an existing MCP server, integrate an API with Claude Code, or expose a service via the Model Context Protocol.
---

<!-- Source: anthropics/skills@mcp-builder via claudemarketplaces.com -->

# MCP Server Development Guide

Build high-quality MCP servers that enable LLMs to interact with external services through well-designed tools.

## Four-Phase Process

### Phase 1 — Deep Research and Planning

**Decide: API Coverage vs. Workflow Tools**
- API coverage = one tool per endpoint (breadth)
- Workflow tools = composite tools for common task sequences (depth)
- Best MCP servers do both

**Tool naming convention:**
```
<service>_<verb>_<noun>
github_create_issue
slack_send_message
stripe_list_payments
```

**Design constraints:**
- Context management: return focused, relevant data — not entire API responses
- Pagination: support `cursor`/`page` params on list tools
- Error messages: actionable guidance with specific next steps

**Study before writing:**
- MCP Protocol spec: `modelcontextprotocol.io`
- TypeScript SDK (recommended over Python SDK)
- Target service API docs

### Phase 2 — Implementation

**Project structure (TypeScript):**
```
mcp-server/
├── src/
│   ├── index.ts        — server entry point
│   ├── tools/          — one file per tool group
│   ├── client.ts       — API client + auth
│   └── types.ts        — shared types
├── package.json
└── tsconfig.json
```

**Tool implementation pattern:**
```typescript
import { z } from 'zod';

server.tool(
  "github_create_issue",
  "Create a new issue in a GitHub repository",
  {
    owner: z.string().describe("Repository owner"),
    repo: z.string().describe("Repository name"),
    title: z.string().describe("Issue title"),
    body: z.string().optional().describe("Issue body in markdown"),
  },
  async ({ owner, repo, title, body }) => {
    const issue = await github.issues.create({ owner, repo, title, body });
    return { content: [{ type: "text", text: JSON.stringify(issue.data) }] };
  }
);
```

**Tool annotations:**
```typescript
{
  readOnlyHint: true,      // does not modify state
  destructiveHint: false,  // cannot delete data
  idempotentHint: true,    // safe to retry
  openWorldHint: false,    // closed set of inputs
}
```

**Use Zod for schemas** (TypeScript) or Pydantic (Python). Always include `outputSchema` for structured return data.

### Phase 3 — Review and Test

```bash
npm run build                              # compile TypeScript
npx @modelcontextprotocol/inspector        # test with MCP Inspector
```

Code quality checklist:
- [ ] No duplication across tools
- [ ] Consistent error handling pattern
- [ ] Full type coverage (no `any`)
- [ ] Pagination on all list endpoints
- [ ] Auth errors return helpful messages

### Phase 4 — Evaluations

Generate 10 complex, realistic evaluation questions:
- Independent (each question stands alone)
- Read-only (no state mutation)
- Verifiable (ground-truth answer exists)

Output format:
```xml
<eval>
  <question>What are the open PRs in tarikskalic33/AEGIS-- assigned to me?</question>
  <answer>Use github_list_pull_requests with state=open and assignee=me</answer>
</eval>
```

## Recommended Stack

| Concern | Choice | Why |
|---------|--------|-----|
| Language | TypeScript | Best SDK support + AI model compatibility |
| Transport | Streamable HTTP | For remote/cloud servers |
| Transport | stdio | For local servers |
| Validation | Zod | First-class TypeScript types |
| Format | Stateless JSON | Required by MCP spec |

## AEGIS MCP Context

The AEGIS system already has MCP servers configured in `.claude/settings.json`:
- `mcp__github__*` — GitHub integration (scoped to `tarikskalic33/aegis--`)
- `mcp__71923ddf__*` — Supabase
- `mcp__d9cdfe21__*` — Vercel

New AEGIS MCP servers should:
- Use `to_be_bytes()` for any hash inputs (never little-endian)
- Return `CorpusLineageRecord`-compatible JSON when serving corpus data
- Never expose constitutional files (`gate.py`, `dna.py`, `router.py`)
- Register via `sovereign-omega-v2/docs/` spec documentation before implementation
