# AEGIS Canonical Ontology
## Epistemic Tier: T0
## Adversarial audit: ChatGPT (CONFIDENCE 0.95) — applied 2026-05-19

Every term used across the AEGIS monorepo is defined exactly once here.
When a term appears in code, documentation, or an agent instruction, its meaning
is the definition in this file — nothing else.

Adding a new term requires a PR with a Guardian-approved rationale.
Renaming an existing term requires updating every site of use in the same commit.
Semantic overload (one term, two meanings) is a T0 violation.

---

## Governing Principle

"Every layer of the architecture is epistemically anchored to an underlying research holon."

More precisely: "The system is a recursively compositional holonic architecture in which
every operational layer is backed by a corresponding research substrate stored within
the knowledge corpus."

The Drive corpus is not reference material. It is the epistemic backbone — the research
substrate that grounds every T0–T2 claim. Implementation without provenance is conjecture.

---

## Core Terms

### Holon
A unit that is simultaneously complete in itself and a component of a larger structure.
(Koestler, 1967.) In AEGIS: every file, module, subsystem, and product is a holon.
No component exists in isolation. Every component has parent holons it must not violate
and child holons whose invariants it must preserve.

### HolonicScale
The abstraction level at which a holon primarily operates. One of six ordered levels:

| Scale | Scope | Examples |
|-------|-------|---------|
| SUBATOMIC | Byte-level invariants, arithmetic precision | Q16.16 encoding, SHA-256 chaining |
| ATOMIC | Individual files and functions | core_matrix.py, canonicalize.ts |
| MOLECULAR | Modules and pipelines | core/, event/, gate/ directories |
| CELLULAR | Subsystems with emergent capabilities | E3 substrate, VCG calibration, Python Core Matrix |
| ORGANISM | Full runtime products | sovereign-omega-v2, cockpit |
| FIELD | The sociotechnical ecosystem | Claude + ChatGPT + Qwen + operators + Drive corpus |

Invariants at a lower scale are unconditionally binding on all higher scales.
A SUBATOMIC violation (e.g. non-deterministic arithmetic) invalidates every scale above it.

### EpistemicTier
The epistemic status of a claim or component. One of six ordered tiers:

| Tier | Status | Grounding requirement |
|------|--------|-----------------------|
| T0 | Mechanically proven | Formal proof or exhaustive test suite |
| T1 | Empirically validated | Repeated empirical measurement with statistical bounds |
| T2 | Engineering hypothesis | Design rationale with testable predictions |
| T3 | Research conjecture | Published research (may be contested) |
| T4 | Speculative systems vision | Internal whitepaper, not yet tested |
| T5 | Creative / worldbuilding | No empirical grounding |

**Migration rule:** No T4/T5 construct may ground a T0–T2 claim without an explicit
evidence review step. Violating this rule corrupts the epistemic hierarchy.

### Invariant
A condition that must hold at all times within a holon's scope. Invariants are stated
in the form "P must hold where Q" and are mechanically enforced where possible (via
type constraints, runtime assertions, or test gates). An invariant is either:
- **T0**: enforced by the type system or a verified test — violation is a compile/test failure
- **T1**: verified by empirical measurement — violation is a calibration alert
- **T2+**: documented expectation — violation is a design review trigger

### Provenance
The set of Drive document IDs that epistemically ground a component. Every T0–T2 holon
must have provenance pointing to at least one T0–T2 source document. Provenance is
stored in `HolonMetadata.provenance`. Provenance absence at T0–T2 is a migration rule
violation and must be flagged in AUDIT_FINDINGS.md.

### Ralph Loop
The iterative self-improvement protocol: **R**eview → **A**nalyze → **L**ink →
**P**atch → **H**armonize. Each cycle targets one HolonicScale and elevates it without
violating any invariant at a lower scale. A cycle is coherent if and only if:
- Gate 8 passes (T0 enforcement)
- No T0 invariant violations remain after the patch
- The target scale's entropy is non-increasing (system is more ordered, not less)

### Entropy (system)
Shannon entropy of the gate acceptance distribution: H = -p·log₂(p) - (1-p)·log₂(1-p)
where p is the gate acceptance rate. Perfect order (p=1 or p=0): H=0. Maximum disorder
(p=0.5): H=1. Ralph Loop cycles must reduce or maintain system entropy. An increase in
entropy after a cycle indicates the patch introduced disorder and must be reverted.

### Constitutional File
One of {gate.py, dna.py, router.py}. These files are frozen — their SHA-256 hashes are
recorded in CLAUDE.md and verified by `node scripts/verify-hashes.mjs`. Modification
requires a /guardian APPROVED verdict. They are the mutation authority, type genome,
and execution router respectively — the three pillars of Layer B constitutional semantics.

### VCG (Vickrey–Clarke–Groves) Calibration
The calibration layer that measures whether claimed confidence matches empirical outcomes.
VCG error = |claimed_confidence - actual_outcome|. The long-run mean VCG error must
converge toward 0 (perfect calibration). V4/V5 verifiers are excluded from VCG
computation — only V1/V2/V3 results have ground-truth grounding.

### Bernstein Bound
The anytime-valid confidence sequence used in the E4 gate, implementing the estimator
from Waudby-Smith & Ramdas (2024). "Bernstein" not "Hoeffding" — the distinction matters:
Hoeffding bounds are fixed-sample; Bernstein bounds are valid at every stopping time.
The file is named `hoeffding.ts` for historical reasons; the implementation is Bernstein.

### PGCS (Persistent Governance Compression Substrate)
The memory management layer that prevents Layer B from consuming swap. Success criterion:
disk_swap_bytes_in = 0 AND disk_swap_bytes_out = 0 across the entire stress test duration.
If PGCS fails, TGCS telemetry is invalid (memory pressure corrupts timing measurements).

### TGCS (Thermal-Gated Cycle Stretching)
The thermal management layer that prevents AMD RX 570 throttling from introducing
timing variance. Success criterion: run-to-run variance σ² = 0 (sequence-number variance,
not wall-clock — wall-clock is non-deterministic).

### AFSE (Asymmetric Flux Scaling Engine)
Validates that governance behavior on consumer hardware (AMD RX 570) generalises to
distributed topologies. Success criterion: R² ≥ 0.98 (throughput stability coefficient).

### Epoch
A logical time unit in Layer B. An epoch increments every 100 processed events.
Epoch state snapshots are taken for the failsafe. The epoch failsafe criterion is
corruption_count = 0 across all epochs.

### M1 / M2 / M3
The three functional regions of the contiguous 4GB byte array in core_matrix.py:
- **M1** (2GB): State management — append-only event log with hash chaining
- **M2** (1.2GB): Calibration gate data — VCG errors and LCB values
- **M3** (0.8GB): Inference context — context token projections with W_scale correction

### W_scale
A Q16.16 fixed-point correction factor computed by GradientAnchorCalibrator.
Represents how far the observed distribution of anchor token weights has drifted from
the expected distribution. W_scale = INT_SCALE (65536) means zero drift.

---

## Non-Equivalence Table (canonical — memorise before modifying any T0 file)

| What it is | What it is NOT |
|------------|---------------|
| Replayability | Correctness |
| Auditability | Safety |
| Calibration | Truthfulness |
| Governance | Alignment |
| Determinism | Correctness |
| High entropy → uncertainty | High entropy → error |

A perfectly replayable system can replay catastrophic reasoning flawlessly.
A perfectly calibrated system can be calibrated to harmful predictions.

---

## Ontology Governance Rules

1. **One definition per term.** A term with two meanings is two terms. Split it.
2. **Canonical term in code.** `HolonMetadata.ontology_term` must reference a term
   defined in this file. Undefined terms are lint errors.
3. **Provenance required at T0–T2.** Every `HolonMetadata` instance at T0/T1/T2
   must include at least one Drive document ID in `.provenance`.
4. **Migration rule enforced.** Any term introduced at T4/T5 that is referenced in
   T0–T2 code without an intervening evidence review is a violation.
5. **Entropy non-increasing.** Adding a new term must reduce, not increase, the total
   conceptual entropy of the system. If the term introduces ambiguity, it is rejected.
6. **Interoperability by default.** Every new abstraction must be explainable in one
   sentence using only terms already in this document.
