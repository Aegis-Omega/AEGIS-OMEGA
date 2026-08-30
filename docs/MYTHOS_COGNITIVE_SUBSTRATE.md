# Mythos Cognitive Substrate

**Epistemic Tier: T2** (engineering hypothesis) · Constitutional law: `AdaptivePower(T) ≤ ReplayVerifiability(T)`

Four Mythos-level (tier-0 apex) agents wired into one constitutionally-governed
knowledge pipeline, with the INT4 LUT-KAN scorer as the ARBITRATION gate.

```
deep-research  →  corpus-ingestion  →  batch  →  chronology
   (Stage 1)        (Stage 2 / gate)    (Stage 3)   (Stage 4 / closure)
```

These four are not departments *in* the organization — they are the cognitive
substrate the 34 departments run **on**. They map to the automaton's metacognitive
organs:

| Agent | Cognitive organ | Skill | Role in pipeline |
|-------|-----------------|-------|------------------|
| `deep_researcher` | L1–L2 (sensation/perception) | `deep-research` | Exhaustive multi-source research → candidate claims |
| `corpus_ingestor` | L2→L6 filter (ARBITRATION) | `corpus-ingestion` | 5-phase RALPH; INT4 LUT-KAN scoring + tier classification |
| `batch_processor` | L5 (executive function) | `batch` | Fibonacci-cadence batch admission |
| `chronologist` | L4+L6 (long-term memory + retrospection) | `chronology` | Narrate the lineage; close the loop |

All four are tier 0, 16K–32K max_tokens, adaptive thinking, constitutional tooling.

---

## The ARBITRATION gate — INT4 LUT-KAN

Stage 2 is the constitutional core. Every candidate claim is quantised to four
4-bit constitutional features:

```
[ evidence_strength, determinism_signal, t45_contamination, citation_quality ]
```

and scored by the INT4 LUT-KAN scorer — a faithful Python port of
`aegis-cl-psi::int4_lut_kan`, byte-identical to the Rust reference (proven by the
`fingerprint_matches_python_reference` Rust test). The decision is hash-chained
into a `KanInferenceLog`:

```
record_hash = SHA-256(prev ‖ sequence_be8 ‖ input_fingerprint ‖ score_be4)
```

`verify_chain()` re-walks the chain; tampering any score or link flips it invalid.
The admission decision is therefore **replay-certifiable** — it satisfies the root
law: no claim is admitted faster than the chain can account for the admission.

**T4/T5 contamination is a hard veto**, not a vote. Any quarantine keyword
("planetary", "civilizational", "self-improving", "sovereign consciousness", …)
forces `admitted=false` regardless of score — mirroring the constitutional rule
that T4/T5 framing must never ground T0–T2 claims.

---

## Running it

```bash
# Deterministic substrate only (no backend needed — the replay-certifiable core)
./agents/run.sh pipeline-demo
python -m agents.cognitive_pipeline run --topic "INT4 LUT-KAN viability"

# Score a single claim through the ARBITRATION gate
./agents/run.sh arbitrate "deterministic SHA-256 hash chain, byte-identical"

# Dispatch each stage to its live Mythos agent (requires a backend)
python -m agents.cognitive_pipeline run --topic "<topic>" --live

# Individual Mythos agents
./agents/run.sh deep-research "<question>"
./agents/run.sh corpus "<arbitration task>"
./agents/run.sh batch "<batch task>"
./agents/run.sh chronology "<retrospective task>"
```

The deterministic core (Stages 1 seed + Stage 2 ARBITRATION) runs with **no
inference backend** — it is pure integer arithmetic and SHA-256. The same topic
always produces the same KAN terminal hash. Live agent dispatch (Stages 1–4 via
the coordinator) overlays real Mythos-level reasoning when a backend is available.

---

## Why this is honest, not theater

The ARBITRATION gate is a real INT4 LUT-KAN forward pass over real quantised
features, hash-chained by a real SHA-256 chain that a real `verify_chain()` walk
re-validates. It is the mechanism itself running — not a mock of a score. The
Rust↔Python parity test proves the two implementations agree byte-for-byte, which
is the cross-platform determinism the skill's Tier Promotion Criterion #3 demands.

The module remains **T2**. Criterion #1 (implement + viability ring) is met;
criteria #2 (≥2× hardware benchmark) and full #3 (tri-platform ROCm/CPU/ARM) are
pending hardware. Test pass ≠ correctness — the non-equivalence invariant holds.

---

## Source

`aegis-cl-psi/src/int4_lut_kan.rs` · `agents/cognitive_pipeline.py` ·
`agents/agents.yaml` (cognitive substrate section) ·
`.claude/skills/{int4-lut-kan,corpus-ingestion,chronology}/SKILL.md`
