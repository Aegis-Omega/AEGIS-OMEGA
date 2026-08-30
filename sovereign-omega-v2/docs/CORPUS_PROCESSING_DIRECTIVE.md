# AEGIS Corpus Processing Directive — Omega Addendum
## Epistemic Tier: T2 (engineering hypothesis — CorpusEngine implemented Gate 144)
## Status: ACTIVE — CorpusEngine operational

---

## Directive

All operator-supplied corpus (research papers, Google Drive documents, GitHub repositories,
skill manifests, specification documents) MUST enter the system through the 5-phase
RALPH pipeline implemented in `src/corpus-engine/pipeline.ts`.

Raw narrative MUST NOT propagate directly into agent cognition. Only replay-certifiable
abstractions (CorpusLineageRecord with `admitted=true`) may be referenced by agents.

---

## 5-Phase RALPH Processing for Corpus

| Phase | RALPH Equivalent | Action | Fibonacci Depth |
|-------|-----------------|--------|----------------|
| OBSERVATION | READ | Compute content_hash; measure byte_length; structural only | F_1 = 1 |
| INTERPRETATION | ASSESS | Extract domain_signals via keyword classification | F_2 = 1 |
| ARBITRATION | LOCK | Classify epistemic tier; T4/T5 → admitted=false | F_3 = 2 |
| MUTATION | PROPAGATE | Assign primitive_mapping; compress to constitutional primitives | F_4 = 3 |
| PROPAGATION | HARMONIZE | Emit CorpusLineageRecord (admitted=true only) | F_5 = 5 |

---

## Tier Classification at ARBITRATION

| Tier | Criteria | Action |
|------|----------|--------|
| T0 | "mechanically proven", "formally verified", SHA-256, hash chain | Emit with tier=T0 |
| T1 | "empirically validated", "benchmark", "measurement" | Emit with tier=T1 |
| T2 | "engineering hypothesis", "proposed", "stub", "seam" | Emit with tier=T2 |
| T3 | Conjecture, research without validation | Emit with tier=T3 |
| T4/T5 | "sovereign consciousness", "civilizational", "planetary coordination", "omnipotent", "unrestricted AGI" | admitted=false → quarantine to FUTURE_PHASES.md |

---

## Operator-Supplied Corpus (current)

The following corpus sources are in scope for CorpusEngine processing:

| Source | Type | Priority | Gate |
|--------|------|----------|------|
| 5 holonic agent PDFs (Google Drive) | Research papers | HIGH | 144 (pipeline ready) |
| Antigravity 58-skill SKILL.md files | Skill manifests | HIGH | 126/130 (already imported) |
| sovereign-omega-2.0.zip | Prior-gen AEGIS skills | MED | 126 (imported, 6 skills) |
| GitHub skill repos (10 repos) | External skills | MED | 126 (import pipeline ready) |
| CRGM specification (17 sections) | Constitutional spec | HIGH | 147 (documented) |
| Operator research papers | Architecture research | HIGH | 147 (classified via RALPH) |

---

## Fibonacci Recursion Cadence

When processing a large corpus (>50 documents), apply Fibonacci pacing between batch runs:
- Batch 1: process immediately (F_1 = 1 unit wait)
- Batch 2: process after F_2 = 1 unit
- Batch 3: process after F_3 = 2 units
- ...
- Batch n≥11: process after F_11 = 89 units (cap)

This prevents corpus flooding and maintains bounded ecology growth.

---

## Corpus Sovereignty Invariant

```
CORPUS SOVEREIGNTY: ACTIVE
Raw narrative → OBSERVATION phase → INTERPRETATION → ARBITRATION (gate) →
MUTATION (compression) → PROPAGATION (only admitted abstractions)

Prohibited:
- Injecting raw Drive/GitHub content directly into agent system prompts
- Treating unprocessed corpus as T0/T1 authority
- Bypassing ARBITRATION to promote T4/T5 content
```

The corpus lineage_hash of each processed document is the authoritative reference.
Agents cite `document_id` + `corpus_lineage_hash`, not raw content.
