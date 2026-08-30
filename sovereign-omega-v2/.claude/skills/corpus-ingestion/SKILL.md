---
name: corpus-ingestion
description: Invoked when the user wants to process Drive corpus files, ingest research documents, run ARBITRATION on document summaries, extract T2 engineering claims as skill files, or quarantine T4/T5 material to FUTURE_PHASES.md. Also invoked when batching corpus documents through the RALPH pipeline.
---

# Corpus Ingestion Skill

**Metacognitive Layer: L4 (Long-term Memory) + L6 (Metacognition) + L2 (Perception)**

Corpus ingestion is the L4 long-term memory formation protocol. Raw narrative from the Drive corpus is L1 signal — unverified, unclassified, potentially containing T4/T5 framing that would contaminate T0–T2 code if admitted directly. The RALPH pipeline is the L2→L6 filter: it transforms raw signal into classified, tier-stamped, hash-referenced long-term memory entries.

L4 invariant: **Only admitted=true CorpusLineageRecords enter the adaptive lineage. Raw narrative that bypasses ARBITRATION is not long-term memory — it is contamination.**
L2 invariant: **The corpus fingerprint (sha256 of content) is the L2 perception of the document. All citations use the lineage_hash, not the document title — because the hash is tamper-evident and the title is not.**
L6 invariant: **ARBITRATION is the L6 step — reasoning about the tier of the knowledge before admitting it. Skipping ARBITRATION is LOCK-before-ASSESS at the knowledge-formation scale.**

## Core Invariant

```
CORPUS SOVEREIGNTY: ACTIVE
Raw narrative → OBSERVATION → INTERPRETATION → ARBITRATION (gate) →
MUTATION (compression) → PROPAGATION (admitted abstractions only)
```

Raw Drive content MUST NOT enter agent cognition directly. Only `admitted=true`
CorpusLineageRecords may be referenced. The corpus lineage_hash is the authoritative
citation — not the document title, not the raw content.

**Excluded from corpus pipeline forever:**
- `AccessKey*.csv`, `AccessKey*.json` — credentials, never process
- `.env*` files — environment secrets
- `*.gdoc` files named "Token" — Vercel/API tokens

---

## 5-Phase RALPH Pipeline

| Phase | Action | Tool |
|---|---|---|
| OBSERVATION | Compute content fingerprint; measure byte_length; structural only | Drive MCP read → sha256 of content |
| INTERPRETATION | Extract domain_signals via keyword scan | Gemini/Claude summary already counts as this phase |
| ARBITRATION | Classify epistemic tier; T4/T5 → admitted=false | See criteria below |
| MUTATION | Compress to constitutional primitives; assign primitive_mapping | Extract T2 engineering claims as structured assertions |
| PROPAGATION | Emit output: SKILL.md (admitted) or FUTURE_PHASES.md entry (quarantined) | Write + commit |

---

## ARBITRATION Criteria

### T0 — Mechanically Proven → admitted=true, tier=T0
Keywords: "formally verified", "mechanically proven", "SHA-256", "hash chain",
"byte-identical", "deterministic across environments"

### T1 — Empirically Validated → admitted=true, tier=T1
Keywords: "empirically validated", "benchmark", "measurement", "observed across runs",
"production metric"

### T2 — Engineering Hypothesis → admitted=true, tier=T2
Keywords: "engineering hypothesis", "proposed", "stub", "seam", specific algorithm names
(RWKV-7, Plonky3, BLS, PBFT, LUT-KAN, zk-SNARK, Bernstein, Mersenne)

### T3 — Research Conjecture → admitted=true, tier=T3
Peer-reviewed papers, academic citations, theoretical frameworks with experimental
grounding. Admitted but cannot ground T0–T2 claims without T1 intermediate.

### T4/T5 — QUARANTINED → admitted=false
Keywords triggering quarantine:
- "planetary autonomy", "civilizational", "planetary coordination"
- "sovereign consciousness", "omnipotent", "unrestricted AGI"
- "subquantum", "quantum vacuum substrate", "information-to-energy ratio"
- "Compute Bonds staking", "autopoietic closure", "natural selection of mutations"
- "metabolic computing", "thermodynamic overload", "heat-sink module"
- Any claim grounding T0 behavior in T4/T5 framing without evidence review

---

## Output Formats

### Admitted (T2–T3): SKILL.md entry
```markdown
---
name: [derived from document title, kebab-case]
description: Invoked when the user asks about [domain]. Source: [document title], tier T[N].
---
# [Title]
## Constitutional Claim
[Single sentence: what T2/T3 engineering pattern this document grounds]
## Key Invariants
- [Concrete, falsifiable claim 1]
- [Concrete, falsifiable claim 2]
## Source
`corpus_lineage_hash: [hash]` · Drive ID: `[drive_id]`
```

### Quarantined (T4/T5): FUTURE_PHASES.md entry
```markdown
## [Document Title]
- Drive ID: `[drive_id]`
- Tier: T4/T5
- admitted: false
- Quarantine reason: [specific T4/T5 keyword triggered]
- Latent potential: [if any T2 engineering claims survive ARBITRATION after stripping T4/T5 framing]
```

---

## Batch Processing — Fibonacci Cadence

For corpus batches >50 documents, Fibonacci pacing between batch runs:
```
Batch 1: immediate
Batch 2: 1 unit wait
Batch 3: 2 units wait
Batch 5: 5 units wait
...
Batch n≥11: 89 units cap
```

Prevents context flooding. Each batch completes a full RALPH epoch before the next fires.

---

## Agent-Mesh Integration

Corpus ingestion for non-trivial proposals routes through the triad:

```
PROPOSAL: Admit [document title] as T[N] corpus entry
TIER: T[N]
SCOPE: .claude/skills/[skill-name]/SKILL.md
```

- **Guardian**: classifies tier; vetoes if T4/T5 framing contaminates T0–T2 claim
- **Verifier**: checks that the emitted skill file doesn't introduce Guarantee Inflation
  (document claims X → skill must claim exactly X, not more)
- **Implementer**: writes SKILL.md with CorpusLineageRecord hash

For simple Gemini-pre-summarized documents: skip guardian/verifier, run ARBITRATION
inline, write the skill file directly. The agent-mesh triad is reserved for documents
where the tier classification is genuinely ambiguous.

---

## Recurring Processing — Loop Configuration

To set up recurring corpus ingestion (add to `.claude/settings.json`):
```json
{
  "hooks": {
    "SessionStart": [{
      "hooks": [{
        "type": "command",
        "command": "echo 'CORPUS: Check for new Drive files not yet in CORPUS_MINDMAP.md'"
      }]
    }]
  }
}
```

Invoke `/loop` to run corpus ingestion on a recurring schedule within a session.

---

## The AEGIS-SOVEREIGN PDF Batch — Pre-ARBITRATION Results

The following PDFs were pre-summarized by Gemini (INTERPRETATION phase complete).
ARBITRATION results:

| Document | Admitted Claims (T2) | Quarantined Framing (T4/T5) |
|---|---|---|
| AEGIS-SOVEREIGN OS Blueprint | RWKV-7 O(1) memory; Plonky3 Mersenne-31 <10ms; BLS threshold aggregation; PBFT 1/3-fault | Planetary autonomy; subquantum heat-sink; Compute Bonds staking |
| From Metaphysics to Production | Polyglot microservices: Rust/Python/C++/Go; PBFT Merkle sharding; 5s Darwin Prover timeout; Matter-Hash load-shedding | Thermodynamic overload framing |
| From Intent to Execution | ICA/NMF for non-stationary telemetry streams; execution boundary equation k·C_eval ≤ B_max | Goal mis-specification / autopoietic framing |
| AEGIS OMEGA Deployment-Certifiable | eBPF sandbox boundaries; SGM Hoeffding LCB bounds; TimescaleDB hypertable 2ms SLA | Civilizational evolution; self-improving |
| AEGIS Autopoietic Engine | ICA/NMF spatial attribution; recursive containment via non-differentiable monitoring | Autopoietic closure; metabolic computing; subquantum anchor |

Admitted T2 engineering claims ready for skill file extraction:
- RWKV-7 wave-logic engine (O(1) memory, replaces Transformer)
- Plonky3 over Mersenne-31 field for ZK proof compression
- BLS threshold signature aggregation with Merkle cross-shard reconciliation
- ICA/NMF for non-stationary multi-occupant telemetry disentanglement
- Execution boundary equation k·C_eval ≤ B_max (combinatorial proof budget)
- INT4 LUT-KAN for cache-local inference (eliminates spline overhead)

---

## Source

`sovereign-omega-v2/docs/CORPUS_PROCESSING_DIRECTIVE.md` ·
`docs/CORPUS_MINDMAP.md` · `src/corpus-engine/pipeline.ts` ·
`sovereign-omega-v2/CLAUDE.md §Corpus Sovereignty`
