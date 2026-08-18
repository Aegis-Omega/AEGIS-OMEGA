# RFC: Evaluation Plane Architecture & Record Specification

**Status:** DRAFT  
**Area:** Evaluation Plane / Verification Layer

## 1. Purpose and Position

This RFC establishes the structural definition of the **Evaluation Plane** and
standardizes the format of its core output artifact: the `EvaluationRecord`.

While the Evidence Plane provides cryptographic proof of what occurred during an
execution cycle, the Evaluation Plane assesses how reliably that execution
proceeded against reproducible criteria, computing behavioral divergence before
structural state updates are finalized.

The system pipeline strictly enforces this topological execution flow:

```text
[ IntentPlane ] ──► [ AuthorityPlane ] ──► [ ExecutionPlane ] ──► [ EvaluationPlane ] ──► [ EvidencePlane ]
```

---

## 2. EvaluationPlane Responsibilities

- **Ingestion:** Consumes incoming `IntentEnvelope` records, raw execution logs
  such as `ExecutionTrace`, and deterministic filesystem or state snapshots such
  as `ReplayReference`.
- **Execution isolation:** Launches specialized verification processes across
  four foundational check profiles: Hallucination Delta, Replay Consistency,
  Policy Compliance, and Capability Misuse.
- **Artifact generation:** Compiles and signs the final `EvaluationRecord`, then
  appends these verification passes to the parent `EvidenceEnvelope`.
- **Lineage control:** Locks software stack versions, dataset version metrics,
  and runtime environmental checksum fingerprints to keep evaluation loops
  verifiable and reproducible.

---

## 3. EvaluationRecord JSON Schema Specification

```json
{
  "$id": "https://aegis.example/schemas/EvaluationRecord.json",
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "EvaluationRecord",
  "type": "object",
  "required": [
    "evaluation_id",
    "execution_id",
    "dataset_version",
    "evaluator_version",
    "metrics",
    "score",
    "timestamp"
  ],
  "properties": {
    "evaluation_id": {
      "type": "string",
      "format": "uuid"
    },
    "execution_id": {
      "type": "string",
      "format": "uuid"
    },
    "dataset_version": {
      "type": "string"
    },
    "evaluator_version": {
      "type": "string",
      "pattern": "^\\d+\\.\\d+\\.\\d+$"
    },
    "metrics": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "required": ["value", "unit"],
        "properties": {
          "value": { "type": ["number", "string", "boolean", "null"] },
          "unit": { "type": "string" },
          "description": { "type": "string" }
        },
        "additionalProperties": false
      }
    },
    "score": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0
    },
    "failures": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["failure_id", "severity"],
        "properties": {
          "failure_id": { "type": "string" },
          "description": { "type": "string" },
          "severity": { "type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"] }
        },
        "additionalProperties": false
      }
    },
    "claim_score": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
    "evidence_score": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
    "hallucination_delta": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    }
  },
  "additionalProperties": false
}
```

---

## 4. Standardized Evaluator Profiles

### Profile Alpha: Hallucination Delta Evaluator

- **Objective:** Measures structural divergence between cognitive claims and
  empirical runtime state records.
- **Strategy:** Paraphrases and maps structured operational assertions extracted
  from planning artifacts, such as `plan.md` and initial intent targets, against
  systemic log emissions recorded inside `audit.jsonl`.
- **Outputs:** Populates explicit values for `claim_score`, `evidence_score`, and
  the derived `hallucination_delta`.

### Profile Bravo: Replay Consistency Evaluator

- **Objective:** Verifies that system operations remain deterministic across
  isolated runtimes.
- **Strategy:** Starts fresh containerized sandboxes matching the original
  execution parameters, feeds identical inputs through `ReplayReference`, and
  tracks execution drift.
- **Outputs:** Attaches a cryptographic `replay_reproducibility_fingerprint` and
  registers a precision determinism score.

### Profile Charlie: Policy Compliance Evaluator

- **Objective:** Guarantees enforcement of runtime security limits and capability
  boundaries.
- **Strategy:** Compares active operational trails against original rule matrices,
  cryptographic hashes, and capability definitions.
- **Outputs:** Updates tracking flags with explicit states: `COMPLIANT`,
  `VIOLATION_TERMINATED`, or `WARNING_DRIFT`.

### Profile Delta: Capability Misuse Detector

- **Objective:** Detects anomalous runtime activities or potential tool
  exploitation vectors.
- **Strategy:** Monitors execution tracking to flag unauthorized permission
  adjustments, rapid data-harvesting runs, or access drift away from the baseline
  scope.
- **Outputs:** Generates structured security alerts with unambiguous severity
  flags.

---

## 5. Mathematical Formalization of Hallucination Delta

To guarantee objective verification, the Evaluation Plane handles agent
statements strictly as unverified claims and checks them against systemic
execution traces.

Let the agent's asserted claims be represented as a multi-dimensional binary
vector $\mathbf{C}$, and let the corresponding runtime validation facts recorded
by independent sandbox interceptors be represented as vector $\mathbf{E}$.

The scalar Hallucination Delta $\Delta_H$ evaluates this behavioral gap by
calculating weighted Manhattan distance across the operational token space:

$$
\Delta_H = \frac{\sum_{i=1}^{n} w_i \lvert C_i - E_i \rvert}{\sum_{i=1}^{n} w_i}
$$

where $w_i$ defines the structural criticality weight allocated to each task
boundary. If the target deviation exceeds policy limits, for example
$\Delta_H > 0.50$, the orchestration layer automatically drops the transaction
and halts execution.

---

## 6. Verification and Lineage Rules

- **Signature requirements:** Every compiled evaluation block must be
  cryptographically signed by an explicitly verified, content-addressed evaluator
  key.
- **Immutable append rules:** Evaluation references are injected directly into
  the `evaluation_records` field of the parent `EvidenceEnvelope`. Once
  committed, historical logs cannot be mutated or reordered.
- **Observability integration:** Production dashboards must provide unified
  access to evaluation scores, calculated hallucination deltas, explicit failure
  logs, raw source footprints, and matching replay fingerprints.

---

## 7. Protocol Repository Mapping & Implementation Roadmap

The following implementation matrix outlines the concrete repository actions
required to integrate the Authority, Evidence, and Evaluation planes into the
core architecture:

| Protocol Concept | Candidate Repository Primitive | Core Action Required |
| :--- | :--- | :--- |
| `IntentEnvelope` | `aegis-core` request wrappers; `AGP-1` schemas | Normalize into unified `IntentEnvelope.json` format; insert structural canonicalization hooks directly within the ingestion gateway. |
| `CapabilityDefinition` | `aegis-core/capability_registry` | Enforce explicit semantic version strings; require content-addressed validation hash mapping through `capability_version`. |
| `PolicyDecision` | Decision Engine pipeline outputs | Embed signed, valid `policy_hash` variables; enforce mandatory ingestion of standard `IntentEnvelope` records. |
| `EvidenceEnvelope` | Distributed audit logs; proxy engine tracers | Standardize structural fields under `EvidenceEnvelope.json`; add verification hooks to ingest tracking reference matrices through `evaluation_records`. |
| `ReplayReference` | Filesystem and image point-snapshots | Formalize baseline snapshot formats; generate deterministic verification fingerprints upon image completion. |
| `ProvenanceChain` | Content-addressed SHA-256 ledger lines | Enforce immutable linked-list integrity rules across parent and child blocks inside the `EvidenceEnvelope`. |
| `EvaluationRecord` | `cognitive-eval.js` tooling suites | Standardize structural schemas under `EvaluationRecord.json`; package and deploy versioned, independent evaluator testing engines. |

### Concrete Engineering Task Allocations

- [ ] **`packages/shared/lib/canonicalizer.{ts,py}`**  
  Develop and test the core canonical serialization routines and the three-state
  taxonomy filter rules.
- [ ] **`aegis-core/gateway`**  
  Integrate ingestion interceptors to synthesize fully populated
  `IntentEnvelope` records before exposing commands downstream.
- [ ] **`aegis-core/decision_engine`**  
  Refactor the policy core to exclusively parse incoming `IntentEnvelope` frames
  and attach immutable validation signatures.
- [ ] **`aegis-core/evaluators/`**  
  Build standalone execution harnesses for testing and validating the four
  primary verification profiles.
- [ ] **`aegis-core/audit/writer`**  
  Extend the active logging worker to inject signed `EvaluationRecord` blocks
  into the parent execution schema.
- [ ] **`aegis-governance/schemas/`**  
  Commit and lock production JSON schemas for `IntentEnvelope.json`,
  `EvaluationRecord.json`, and `EvidenceEnvelope.json`.
- [ ] **Test matrix execution**  
  Deploy integration suites for system failures, edge-case clock skews, high
  hallucination-delta threshold drops, and broken environment fingerprints.
