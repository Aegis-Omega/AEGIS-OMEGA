# Zero-Discretion Type Gates v1

Status: DRAFT IMPLEMENTATION SPEC  
Scope: AEGIS Ω research / mathematical execution admission  
Non-scope: runtime mutation authority (`python/gate.py`) and external-effect authority.

## 1. Law

A generator may choose a construction. It may not choose which registered
type-implied falsifiers that construction must survive.

For every admitted research object `o`:

\[
GateSet(o) = Registry(NominalType(o), TypeParameters(o)).
\]

All registered gates execute before a downstream stage can receive an
admission ticket. `FAIL`, `ERROR`, missing receipt, stale object digest, or
receipt splicing blocks admission.

No relevance judgment is permitted between object construction and gate
execution.

## 2. Type-to-invariant registry

The registry is finite and versioned. The phrase "cheap gate" means bounded
verification relative to the expensive downstream stage; it does **not** claim
that every gate is literally O(1) in matrix dimension.

| Nominal type | Mandatory gate | Defect class |
|---|---|---|
| `DiscretizedSpectralBasisV1(N_F,h,gamma_max)` | `N_F*pi/h >= gamma_max` | target oscillation outside represented spectral domain |
| `OperatorDecompositionV1(A,{B_e})` | `||sum B_e - A||_F <= tol` | omitted/misweighted operator term |
| `RealSkewSymmetricMatrixV1` | `||A+A^T||_F <= tol`; witness `x^T A x` | false positive quadratic form from a skew/commutator object |
| `CombinatorialLaplacianV1` | `||L 1||_inf <= tol` | broken kernel / row-sum convention |
| `LinearDualCertificateV1` | `||A^T y-c||_inf`, `y>=0`, gap | optimality claimed without a valid supplied certificate |
| `ExponentialAsymptoticFamilyV1` | negative exponential rate vs positive uniform lower bound | hidden asymptotic collapse such as `c0 ~ exp(-0.27 h)` |

A generic asymptotic expression is not automatically decidable. The v1 gate
therefore covers only explicitly registered asymptotic families; unregistered
types fail closed rather than being interpreted by an LLM.

## 3. Mechanical trigger

The type registry is code, not prose. An unregistered type cannot silently
inherit a nearby gate.

`SpectralBasis(...)` executes its coverage gate in `__post_init__` before any
downstream experiment. Failure raises `InvariantViolationError` carrying the
failed `GateReceipt`.

This is assert-by-construction, not an optional test convention.

## 4. Receipt binding

Each `GateReceipt` binds:

- `gate_id` and `gate_version`;
- exact nominal `type_signature`;
- deterministic `object_digest`;
- `PASS | FAIL | ERROR`;
- observed margin/residual;
- deterministic `witness_sha256`;
- measured `elapsed_ns` as telemetry only.

Timing is excluded from the deterministic witness hash.

Changing any object parameter changes the object digest and invalidates old
receipts. A receipt from a different object cannot satisfy admission.

## 5. Execution lock

A costly stage MUST obtain an `AdmissionTicket`.

\[
ADMIT(stage,o) \iff
\forall g \in GateSet(o):
Receipt(g,o).verdict = PASS.
\]

The controller is fail-closed on:

- missing gate receipt;
- `FAIL`;
- `ERROR`;
- duplicate required gate receipt;
- subject/object digest mismatch.

The model or researcher has no `skip_irrelevant_gate` operation.

## 6. Criterion epochs

Pre-registered criteria are frozen as literal UTF-8 strings:

\[
criterion\_sha256 = SHA256(exact\_bytes(T)).
\]

No canonicalization is performed. A whitespace edit, renamed symbol,
normalization change, threshold change, sample-set change, or stopping-rule
edit creates a distinct criterion hash and therefore a new research epoch.

"Clarification" is not a privileged edit class.

## 7. [STATUS] protocol

`VERIFIED` is intentionally absent as a free-form label.

Allowed records:

- `[CONJECTURED]`: no evidentiary authority.
- `[TYPE_CHECKED: evidence_sha256]`: one or more type gates returned `PASS`.
- `[COMPUTED: output_sha256, criterion_sha256, N, tol, verifier_id]`: a concrete
  computation is bound to exact output and pre-registered criterion.
- `[THEOREM: evidence_sha256, verifier_id]`: requires both a proof-artifact hash
  and an independent checker-receipt hash.

A prose proof with no checker receipt cannot be promoted to `[THEOREM]` by this
runtime.

## 8. Canonical regression: spectral under-resolution

The regression case is:

\[
N_F = 12,\quad h=3.5,\quad \gamma_{\max}=14.13,
\]

so

\[
N_F\pi/h = 10.7711748\ldots < 14.13.
\]

The constructor must fail before a c-sweep or downstream integration receives
execution authority.

The gate is not justified because the system predicts that it will fail. It
runs because its nominal type requires it.

## 9. N=200--300 enrichment pre-flight

The pre-flight requirement is mechanical:

\[
N_F \ge \left\lceil \frac{h\,\gamma_{\max}}{\pi}\right\rceil.
\]

`gamma_max` must come from the exact zero set used by the run; do not hard-code
an approximate `gamma_300` into the gate if the experiment supplies a more
precise value.

After type admission, the enrichment experiment may evaluate only the frozen
criterion for `z(N)`.

A change to the scaling criterion (for example, changing `b ~ 0.5`, the fit
window, normalization, null, or stopping rule) creates a new criterion epoch
and may not be pooled with prior results as if it were another sample.

## 10. Audit metrics are retrospective

`N_avoidable` and `C_waste` are audit metrics, not runtime controls.

They may be computed only after a decisive cheap gate is known. They MUST NOT
be used to decide whether a registered gate should execute.

The control path is the registry. The audit path asks afterward how much work
occurred before a gate that should have been available.

This preserves the distinction:

- registry/gate execution controls;
- `N_avoidable`, `C_waste`, and missed-gate analysis score the control system.

## 11. Source layout

- `python/research_invariants.py` — registry, gate executors, receipts,
  literal criterion epochs, status records, relation bindings, append-only
  status transitions, and admission controller.
- `python/research_preflight.py` — CLI pre-flight for spectral coverage.
- `python/tests/test_research_invariants.py` — executable regressions.
- `.github/workflows/zero-discretion-type-gates.yml` — CI admission check.

The existing `python/gate.py` remains mutation authority. The research gate
layer is separate so a mathematical `PASS` cannot be confused with authority
to mutate system state or perform an external effect.

## 12. Late-bound relations and status history

Some invariants become meaningful only after independently constructed objects
are related. `RelationBindingV1` binds a named relation to a role-sensitive set
of participant digests. Participant ordering is canonicalized, but role names
are semantic: swapping `basis` and `gamma`, for example, creates a different
relation digest.

Relational verification does not create a second receipt or authority system.
`relation_gate_receipt(...)` reuses ordinary `GateReceipt` with
`object_digest == relation_digest`, so the existing `AdmissionController`
anti-splicing check remains the authority boundary. A receipt for one
counterpart cannot authorize a relation against another counterpart.

Claim status is no longer limited to isolated point records. `StatusJournalV1`
adds an append-only, hash-chained transition history. Each transition binds the
claim id, previous and next status, evidence receipt digests, criterion epoch,
reason, and previous transition digest. Promotion and demotion are both
permitted; history is never silently rewritten.

The journal proves only the integrity and ordering of recorded status
transitions. It does **not** prove the underlying scientific or mathematical
claim. Likewise, execution duration is telemetry only and has no authority in
relation or status hashes.
