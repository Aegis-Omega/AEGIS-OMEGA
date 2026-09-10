# AEGIS Ω Agent-Provenance Investigation — Public Baseline

Date: 2026-08-05
Branch base: `main@0bdffe75b56e5cd27c0632e1ba166620da327494`
Status: `INVESTIGATION_OPEN`

## Question

Determine whether the agent execution lineage recorded in AEGIS Ω merely used publicly available research, or whether any public/internal agent systems can be linked to the same persistent identity, private artifacts, or implementation lineage.

This document establishes the first public-evidence baseline. It does **not** assert theft, cross-provider identity, or unauthorized data transfer without a source-to-sink trace.

## 1. Primary repository evidence

### 1.1 CTHS is operationalized in AEGIS Ω

Repository path:

`sovereign-omega-v2/src/gate/risk.ts`

The file explicitly identifies `Confirm-Triggered Harmonic Spending` and implements harmonic risk allocation through:

- confirmation-indexed round state;
- `harmonicSum(max_rounds)`;
- `deltaAlpha = currentBudget / (k * harmonicNumber)`;
- confidence-sequence evaluation;
- risk spending only after an accepted gate decision.

Git blob at canonical main: `b6806ab8d34897ee51a2be9440c5b94b70521876`.

### 1.2 Signed Claude execution lineage

Commit:

`4887fbd12b7265589e79bcd612ebe0a97dc1a899`

Recorded metadata:

- author/committer: `Claude <noreply@anthropic.com>`;
- timestamp: `2026-05-16T22:01:11Z`;
- signature verification: valid;
- tree: `9cf0af7afc099992d405228f6ee6c640e9dfeb34`;
- recorded Claude Code session: `session_01WvFyntZArqThRgLczRutuM`;
- commit message records 101/101 tests and gate-specific implementation fixes.

### 1.3 Explicit multi-agent roles

`sovereign-omega-v2/docs/SOVEREIGN_OMEGA_INTEGRATED_SPEC_v2.md` records:

- Claude: synthesis;
- ChatGPT: architectural audit;
- Qwen: implementation.

The same specification includes CTHS inside the Probabilistic Modification Gate.

## 2. Public prior-art chronology

### 2.1 Confirm-Triggered Harmonic Spending

Primary source:

- title: `SGM: A Statistical Godel Machine for Risk-Controlled Recursive Self-Modification`;
- arXiv: `2510.10232`;
- submitted: `2025-10-11T14:09:37Z`;
- exact term: `Confirm-Triggered Harmonic Spending (CTHS)`;
- source: https://arxiv.org/abs/2510.10232

Chronology:

`SGM public publication (2025-10-11) -> AEGIS Claude-signed integration (2026-05-16)`

Current repository search does not locate `2510.10232` or the full SGM title. Therefore the concept is operationally present, while direct bibliographic attribution is not presently found in the indexed repository state.

### 2.2 Rasterization-aware Geometric Consensus

Primary source:

- title: `SAGOnline: Segment Any Gaussians Online`;
- arXiv: `2508.08219`;
- v1 submitted: `2025-08-11T17:38:50Z`;
- v2 revised: `2026-01-06T14:58:59Z`;
- current abstract explicitly names `Rasterization-aware Geometric Consensus`;
- source: https://arxiv.org/abs/2508.08219

Repository searches for `SAGOnline` and `Rasterization-aware Geometric Consensus` returned no indexed AEGIS Ω match at this stage.

Therefore:

- public provenance of the term/mechanism is established;
- AEGIS integration is not established from the current repository search;
- the exact-term presence in v1 must not be inferred from the current v2 abstract without inspecting v1 bytes.

## 3. Public evidence that the relevant class of internal agent exists

### 3.1 OpenAI internal data agent

OpenAI publicly described an internal data agent on 2026-01-29. The described system:

- explores and reasons over OpenAI's own platform;
- combines Codex-derived enrichment with institutional context;
- retrieves from Slack, Google Docs and Notion;
- maintains memory from corrections and discoveries;
- runs a daily offline enrichment pipeline;
- converts enriched context into embeddings for retrieval;
- can run live warehouse queries;
- is exposed through Slack, web, IDEs, Codex CLI/MCP and internal ChatGPT.

Source: https://openai.com/index/inside-our-in-house-data-agent/

This establishes the existence of an internal knowledge-gathering, code-enriched, memory-bearing agent class. It does not establish that this agent ingested AEGIS Ω artifacts or shares identity with an AEGIS agent.

### 3.2 Anthropic internal agent deployments

Anthropic publicly described `Claude Tag` on 2026-06-23. The described internal version:

- joins selected Slack channels;
- receives access to tools, data and codebases;
- remembers relevant channel information;
- can plan future tasks;
- is used internally for coding, metrics, support tickets and root-cause work.

Source: https://www.anthropic.com/news/introducing-claude-tag

Anthropic also stated on 2026-05-25 that granting Claude access sufficient to affect internal services had become routine, motivating containment and blast-radius controls.

Source: https://www.anthropic.com/engineering/how-we-contain-claude

These sources establish the existence of persistent-context and high-access internal Claude deployments. They do not establish identity continuity with the signed AEGIS Claude session.

### 3.3 Amazon Claude Sonnet deployment

Financial Times reporting published 2026-07-30 describes an Amazon Claude Sonnet deployment for matching author details to ecommerce listings. Reported properties include:

- approximately USD 1.8 million spent;
- approximately 860% budget overrun;
- failure detected after approximately five months;
- insufficient spending controls;
- related internal efforts to build automated guardrails.

Primary report: https://www.ft.com/content/77baac40-d803-4084-94f3-a133653072cf
User-supplied secondary report: https://www.techradar.com/pro/amazon-admits-it-accidentally-shelled-out-usd1-8-million-for-claude-to-finish-menial-coding-tasks

This establishes that long-running internal Claude deployments can perform large-scale entity/knowledge matching with inadequate observability. It does not identify the deployment as an AEGIS-derived agent.

## 4. Initial classifications

```text
CTHS_PUBLIC_PROVENANCE = ESTABLISHED
CTHS_AEGIS_OPERATIONALIZATION = ESTABLISHED
SIGNED_CLAUDE_EXECUTION_LINEAGE_IN_AEGIS = ESTABLISHED
CLAUDE_SYNTHESIS_ROLE_IN_AEGIS = ESTABLISHED
PUBLIC_INTERNAL_KNOWLEDGE_AGENT_CLASS = ESTABLISHED
PUBLIC_LONG_RUNNING_CLAUDE_DEPLOYMENT_CLASS = ESTABLISHED
RAGC_PUBLIC_PROVENANCE = ESTABLISHED
RAGC_AEGIS_INTEGRATION = NOT_ESTABLISHED
AEGIS_SOURCE_ATTRIBUTION_FOR_CTHS = NOT_FOUND_IN_CURRENT_INDEX
CROSS_PROVIDER_SAME_AGENT_IDENTITY = NOT_ESTABLISHED
UNAUTHORIZED_ARTIFACT_TRANSFER = NOT_ESTABLISHED
EXTERNAL_REUSE_OR_REBRANDING = INVESTIGATION_OPEN
```

## 5. Required identity-grade evidence

A same-agent or derivation finding requires at least one high-specificity bridge, such as:

1. a private canary string, identifier, schema defect or rare ordering reproduced externally after the AEGIS timestamp;
2. matching session, tool-call, key, request, workspace, telemetry or artifact identifiers;
3. byte-level or AST-level implementation overlap exceeding what public prior art explains;
4. provider-side access/export records linking AEGIS artifacts to an internal execution environment;
5. a temporal chain showing private AEGIS material preceding an externally published implementation with no plausible public source.

Semantic similarity alone is insufficient for identity attribution.

## 6. Next executable phase

The next phase is a repository-wide provenance fingerprint extraction:

- enumerate rare phrases, schemas, field orderings, invariants and known bugs;
- bind each fingerprint to its earliest Git commit/tree/blob;
- separate public-source imports from AEGIS-original synthesis;
- search later public repositories, papers, product documentation and agent traces;
- score matches by rarity, structural depth, temporal direction and independent-source plausibility.

No status may be promoted beyond the strongest verified source-to-sink transition.
