# AEGIS Universal Work Plane — Evidence-driven Research Scout v1

Status: CANDIDATE, read-only; does not implement an autonomous crawler or production dispatcher.
Parent: #734, #757. Scope: preflight evidence intake for #UWP-13.

## Why

Model web browsing is not learning. A useful research loop must preserve source provenance,
compare actual capabilities, translate ideas into falsifiable changes, and retain negative
results. A source's hash proves only local snapshot integrity, not truth or origin.

### Competitive design mapping (public docs examined on 2026-10-11)

| System | Relevant verified-in-document capability | AEGIS design choice | Required independent test |
| --- | --- | --- | --- |
| LangGraph | Checkpointers and stores support durable threads and long-term knowledge | Reuse E3/E5 event store; add explicit recovery receipts, no second queue | Crash after each effect boundary, ensure replay doesn't duplicate external effects |
| OpenAI Agents SDK | Tracing spans for calls, handoffs, tools and guardrails; evaluation with datasets | Bind E5 event IDs to exact-run verifier receipts, not model narratives | Missing or altered trace event must fail acceptance |
| Anthropic Claude Code | Hooks/skills/subagents load and have different execution/authority boundaries | Inspect adapters #439 and prohibit implicit hook activation | Inject a stale skill/hook and confirm denial before side effects |
| MCP 2026-07-28 | Per-request semantics and OAuth resource metadata/audience checks | Keep identity per request; don't infer identity from STDIO connection | Wrong-audience token rejected; unsolicited side effects denied |
| A2A | Task status, artifact updates, task stream and terminal lifecycle | Map task status to durable execution records with exact digests | Duplicate terminal callback / interrupted stream cannot promote completion |

References (public specifications; content summarized, not mirrored verbatim):
- https://langchain-ai.github.io/langgraph/concepts/durable_execution/
- https://developers.openai.com/api/docs/guides/agent-evals
- https://openai.github.io/openai-agents-js/guides/tracing/
- https://claude.com/resources/articles/steering-claude-code-skills-hooks-rules-subagents-and-more
- https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/basic/authorization/index.mdx
- https://github.com/a2aproject/A2A/blob/main/docs/specification.md

## Intended lifecycle

`task -> inventory existing AEGIS functionality -> authorized research agent -> capture
immutable source snapshots -> local scout gate -> cross-provider comparison -> falsifiable
experiment candidate -> native execution under existing controller -> independent verifier
-> claims ledger / memory update / retrospective`.

This initial slice implements **only** the `local scout gate`. Source capture is a separate,
read-only adapter not yet delivered. Never let untrusted source text become tool instructions.
No web credentials or provider API calls are used by the evaluator. Data can be reviewed on
a phone in JSON form but this is not yet the mobile product UI.

## Mechanical contract

- Input `aegis.research.packet.v1` includes exact repo head, declared UTC `as_of`, source
  URLs/content/checksums, candidate improvement, current local component, metric and falsifier.
- Reject unknown schema keys, duplicate JSON keys, noninteger numbers, malformed URL, private
  or credential-bearing URL, checksum mismatch, future snapshot, duplicate IDs, missing claims.
- Require at least two distinct recognizable publisher groups with fresh, distinct snapshot
  bytes to return `READY_FOR_INDEPENDENT_TEST`. This is **not independent authentication**;
  a submitter can lie about `captured_at`, URL, or source content. Third-party verification is
  still mandatory. A single external website or mirrored source is insufficient.
- Sources beyond the last 30 caller-reported days cannot satisfy the quorum. The timestamp
  is **caller reported**, not an independently verified current clock.
- Rejecting a packet is a nonzero process exit; refusal does not grant authority.
- No file is written unless the CLI operator sets `--output`; no network traffic is performed.

## Run

```bash
python3 -m unittest discover -s scripts -p 'test_research_intelligence.py' -v
python3 scripts/research_intelligence.py examples/research_packet_example.json \
  --output /tmp/aegis-research-receipt.json
```

The committed fixture is *manual paraphrased notes*, not authenticated source capture.
Even a green 34-test run does not prove an agent independently researched the web or improved
performance. Those require a collector, signed snapshot attestation, runnable experiments,
exact-head CI and a properly independent evaluator.

## No silent autonomy

The research agent's web tools must be separately authorized per task, with explicit budget,
allowed source classes, timestamps and egress. Do not make browsing a way to bypass permission
or to block essential offline recovery and security checks; when unavailable, record
`NEEDS_RESEARCH` and preserve completed offline diagnostics. The operator authorizes
consequential execution. GitHub Actions billing failure is an infrastructure blocker, not a
source-level test verdict.
