# AegisQ IFG: signed calibration to independent numerical verification

This package integrates the previously tested NumPy/SciPy IFG into AEGIS. The
TypeScript boundary authenticates a research request and calibration receipt,
binds the raw observations, model, policy and verifier, then runs the pinned
Python checker. The result is `PASS_RESEARCH_ONLY` or `DENY`; clinical admission
is always false.

Base: `414b04ea2969ae56208949e7923f0ec1e094be24`. The six imported QuanPhotonic
source/schema/test files come byte-for-byte from the recovered local research
commit `7874bd4743d164a28632b90653c73b9449a85755`. Their paths and SHA-256 hashes
are in `IMPORT_PROVENANCE.json`. The existing governance writer and frozen
hardware files are outside this change.

## Run

```bash
python -m pip install -r packages/aegisq-ifg/requirements.txt
cd packages/aegisq-ifg
python -m unittest discover -s tests -v
python -I run_ifg.py < examples/stationary_one_photon.json
```

The example contains a synthetic stationary one-photon state and an
informationally complete six-element Pauli POVM. It is physical despite its
negative Wigner value. The wire runner does not accept a precomputed result.

From `sovereign-omega-v2`, run the real TypeScript-to-Python integration:

```bash
npm ci --ignore-scripts --no-audit --no-fund
npm run test -- test/unit/aegisq-admission.test.ts test/integration/aegisq-python.test.ts
```

The integration test resolves `python3` by default. A controlled absolute
executable can be supplied through `AEGISQ_PYTHON_EXECUTABLE`. Missing numerical
dependencies or executables fail the test; they do not enable a mock or a skip.

## Trusted configuration and request

`src/research/aegisq-python.ts` provides `inspectPythonVerifier` and
`createPinnedPythonVerifier`. Inspection measures the candidate executable and
four Python source hashes, plus Python/NumPy/SciPy versions. The operator must
review and pin that identity before accepting requests. The factory requires
both `expectedIdentity` (the approved manifest) and `expectedIdentityDigest`;
source and executable hashes are checked before any candidate code runs.
Inspection itself executes the candidate and is only for trusted installations.
Measuring a new
identity from untrusted request content would not be authorization.

`src/research/aegisq-admission.ts` provides `AegisQAdmissionGate`, configured with
trusted calibration and producer keys, approved model/policy digests, and the
pinned verifier. A request signature binds:

| Binding | What is recomputed |
|---|---|
| Raw batch | Canonical digest of the observations sent to Python |
| Calibration | Existing receipt digest and actual Ed25519 signature |
| Measurement envelope | Batch ID, detector/configuration, epoch, sequence and receipt link |
| Model | Hamiltonian, effective jump operators and POVM |
| Policy | Every physical tolerance; no silently supplied policy defaults |
| Verifier | Operator-pinned executable/source/version identity |

The producer signs the domain-separated string
`AEGISQ_INFERENCE_REQUEST_V1:<payload_digest>`. This binds the producer's
declaration about the raw batch; the calibration signature alone cannot
authenticate a subsequently acquired measurement. A producer signature does
not prove that the source was a real instrument or that the calibration
parameters were measured correctly.

All request objects are validated, copied and frozen before asynchronous work.
The wrapper restricts its transport domain to portable JSON with ASCII keys
and strings and finite supported numbers. This avoids the inherited v1
canonicalizer's Unicode ordering/surrogate limitations without changing
historical canonical bytes. General Unicode JCS migration remains separate.
The Python wire parser independently rejects duplicate keys, unsupported
schema versions, nonfinite values, complex-component broadcasting and missing
policy fields.

## Numerical contract

Wire input has exactly `raw`, `model` and `policy`. The supplied example is the
complete concrete schema instance. `rho`, Hamiltonian, jumps and POVM use
separate identically shaped `real`/`imag` arrays.

- `times_seconds` is strictly increasing and uses seconds.
- Hamiltonian is `H_physical / hbar`, with units `s^-1`.
- Each effective jump is `sqrt(rate_k) L_k`, with units `s^-1/2`.
- Hamiltonian and jumps are constant across the evaluated interval.
- All sampled density matrices must satisfy the configured Hermiticity,
  trace and PSD tolerances.
- The declared POVM must identify the full trace-one state family and agree
  with the supplied observations.
- Midpoint finite-difference and independently constructed matrix-exponential
  transition residuals must satisfy their separate bounds.

These checks establish finite numerical consistency with a declared model.
They do not perform tomography, independently measure biology, prove
continuous-time physicality, or bound omitted continuous-variable Fock tails.
Coarse sampling can fail a midpoint tolerance for an otherwise exact Lindblad
trajectory; the reason is a discretization/model-contract mismatch.

The Gaussian scalar CMI implementation and its existing tests are included as
an offline research evaluator. CMI is not recomputed for a new patient's
unknown label inside this online path. Its IID/Gaussian/fixed-feature
assumptions remain explicit, and a CMI result is not causal identification.

## Replay and effect boundary

The default replay scope is the lifetime of one admission gate instance,
reported as `IN_PROCESS_ONLY`. The imported IndexedDB authority can supply an
external atomic calibration replay transaction. A missing/unavailable
configured authority fails closed.

Calibration admission consumes the batch before the Python verification run.
A failed, timed-out or physically rejected verification does not clear its
replay marker. Re-execution requires an explicitly governed recovery/new
measurement policy; recreating the in-memory gate is not durable replay
protection. This change does not claim an atomic transaction spanning
calibration consumption, Python execution and a durable audit append.

The returned receipt is content-addressed. It is not a signed EffectReceipt,
an EHR write or a claim-ledger promotion. Input authentication here is
**Ed25519**, using the existing repository implementation. PQC signing,
TLS negotiation, clinical validation and the earlier 0.1 ms latency claim
are not established by these tests.

Source/executable pins are checked before execution and around each Python run. This protects
against ordinary drift in a trusted local installation; dependency versions
are recorded, while all native dependency bytes, OS integrity and concurrent
host compromise are not attested. Use a controlled installation for real
research workloads.

## Verification

`.github/workflows/aegisq-ifg.yml` checks the pull request head directly,
executes the Python suite and real cross-language tests, verifies the frozen
membrane and typechecks the integration. It has read-only repository access.
The repository-wide Gate 8 remains the separate test/typecheck/build gate.
