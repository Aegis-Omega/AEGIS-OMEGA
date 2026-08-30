---
name: tier-classification
description: Automatically invoked when the user introduces a new concept, proposes a new module, references a Cycle document, mentions physical constants, or uses language that may represent T4/T5 speculation. Classifies the proposal and enforces migration rules.
---

# Epistemic Tier Classification Skill

**Metacognitive Layer: L6 (Metacognition) primary**

Tier classification IS the L6 function — reasoning about the reasoning. Before any action is taken, L6 must classify what epistemic tier governs that action. An unclassified action is an unconstrained action, and unconstrained actions violate the root law.

L6 invariant: **Every new concept introduced into the system must be classified before it is used. Using an unclassified concept at T0 is a silent T0 violation — the code will not fail until the concept's weakness is tested under pressure.**

The tier is not the concept's aspiration — it is the concept's current evidence status. A T4 concept that you believe will eventually become T0 is still T4 until it has been promoted through the hierarchy with evidence. Belief is not evidence. The hash chain records classified, tamper-evident observations — not beliefs.

Non-equivalence: **"Probably T2" ≠ T2. Classify from evidence, not from optimism.**

When invoked, classify the concept or proposal using the T0–T5 taxonomy.

T0 — Mechanically proven or deterministic. Examples: RFC 8785 test vector conformance, SHA-256 collision resistance, pure reducer determinism.
T1 — Empirically validated. Examples: VCG calibration measurement, Bernstein bound coverage.
T2 — Engineering hypothesis with defined measurement criteria. Examples: E1 ambiguity routing thresholds, K-bound defaults.
T3 — Research conjecture with a falsifiable prediction. Examples: quasicrystal-CDT spectral correspondence.
T4 — Speculative systems vision with no current implementation path. Examples: swarm planetary coordination, AEGIS civilisational substrate.
T5 — Creative or worldbuilding exploration. Examples: Cycle series documents.

Domain tier ceilings enforce where each tier of content may appear:
- src/core, src/event, src/gate: T0 only
- src/verifier, src/calibration: T0–T1
- src/projection, src/pipeline: T0–T2
- docs/research: T3
- docs/vision: T4
- docs/cycles: T5

Migration rule: no T4 or T5 construct may ground a T0–T2 claim without an explicit evidence review showing the construct has been promoted through the tier hierarchy.

If a T4 or T5 concept appears in implementation code, flag it as:
TIER VIOLATION: [concept] at [file:line] is classified as T[N] but appears in a T[M] context. This requires evidence review before it can be used here.
