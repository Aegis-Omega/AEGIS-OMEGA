# Exact-target proof evidence validator V1

This directory contains the `EXACT_TARGET_PROOF_RECEIPT_V1` evidence validator and its negative controls. The V2.7 replay workflow runs these tests and uses `../verify_lean_axiom_surface.py` to audit the actual four-theorem Lean output.

The receipt validator is a callable evidence check, not a Lean or independent-kernel implementation. Production receipt admission additionally needs a canonical target contract, actual comparator/proof exports and a separately pinned replay-controller observation. This change does not supply those missing inputs or convert the synthetic tests into mathematical evidence.

## Run

Linux/WSL and Python 3.10+, standard library only. From repository root:

```sh
python3 -m unittest discover -s scripts/proof_receipts_v1 -p 'test_*.py' -v
python3 -m unittest discover -s scripts -p 'test_verify_lean_axiom_surface.py' -v
python3 scripts/proof_receipts_v1/gate.py \
  --receipt receipt.json \
  --policy protected-policy.json \
  --policy-sha256 "$APPROVED_POLICY_SHA256" \
  --observation controller-observation.json \
  --observation-sha256 "$CONTROLLER_OBSERVATION_SHA256" \
  --evidence-root evidence-bundle \
  --expected-head "$EXPECTED_SOURCE_SHA"
```

Pins must come from a protected controller independently of the candidate. Hashing candidate-provided files to obtain the expected pins defeats the trust boundary. The controller must authenticate execution provenance and independently bind source/dependency revisions; this validator does not authenticate a signer or perform Git ancestry checks.

The module docstring defines the complete strict JSON contract. Every target requires ten nonempty hashed artifact roles: source manifest, toolchain, Lake manifest, elaborated type, canonical statement/definition bundle, proof export, build log, axiom report, comparator report and independent-kernel report. The policy binds the target and environment; the trusted observation binds every artifact. Reports must agree on the same target and proof export. `PASS_EVIDENCE_VALIDATED` always carries `authority_effect = NONE`.

The elaborated target contract must include the meaning of referenced definitions, binders, universes, hypotheses and coercions. Human semantic review of correspondence to informal mathematics remains separate. Default Lean-kernel replay cannot fill the independent-kernel report. The adapter and immutable evidence directory are part of the trusted execution boundary.

Mathlib-root workspaces are supported: when the Lake manifest names the root `mathlib`, its packages must exactly match the other pinned dependencies; the root revision is bound by the policy/observation environment. Otherwise, the manifest must include Mathlib as a dependency too.

The test fixtures are explicitly `TEST_ONLY`; all their policies, observations and proof bytes are synthetic. Tests cover stale heads, wrong targets, missing reports, artifact substitution, custom axioms/native trust, forged observations, JSON ambiguity, unsafe paths and Python optimization.

## Scope

The live Lean axiom audit requires exactly one record per target and only `propext`, `Classical.choice`, `Quot.sound` (or a subset). It rejects missing/duplicate records and unparsed output. Successful Lean execution is separately required by the workflow's `set -euo pipefail`.

No theorem statements or proofs change. This verifier-only transition does not establish global Weil positivity, concrete three-block coercivity or RH; it grants no repository admission or mutation authority.
