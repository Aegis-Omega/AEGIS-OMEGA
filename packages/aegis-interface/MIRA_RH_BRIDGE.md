# AEGIS MIRA-RH bridge v2 (research, not an RH proof)

**Source:** Local MIRA-RH v1 ZIP SHA256 `a4d06687cad4add4c5169214282d9ce96df495853ef088f5b5dd1a5d94e5e2ca`.
**Status:** `LOCAL_EXACT` for rational arithmetic, **OPEN** for new Lean kernel checks and global RH. No theorem is admitted by this feature.

## End-to-end path

`typed JSON request -> math_rh.compile_statement -> independent replay
 -> project_wit_receipt -> mira_bridge.verify_wit_contract
 -> original aegis_interface.compiler.compile_source
 -> AST/IR -> Rust/TS/Python readback -> source-scoped bridge receipt`

`MIRA` does not replace the RFC-0001 compiler, bypass its equivalence gate,
or import the historical closed RH PR into protected main.

## Running in the actual repository

From `packages/aegis-interface`:

```sh
python -m pytest -q tests/test_math_rh.py tests/test_mira_rh_projection.py tests/test_mira_repo_integration.py
python -m aegis_interface.cli validate wit/mira_rh_proof.wit
python -m aegis_interface.cli compile wit/mira_rh_proof.wit --out /tmp/mira-rh-generated
python -m aegis_interface.cli check wit/mira_rh_proof.wit --out /tmp/mira-rh-generated
python -m aegis_interface.math_rh compile tests/fixtures/v7_reflection.json --out /tmp/v7-receipt.json
python -m aegis_interface.math_rh verify /tmp/v7-receipt.json
python -m aegis_interface.math_rh project /tmp/v7-receipt.json
node tools/mira_rh_node/verify.js tests/fixtures/receipts/*_receipt.json
node tools/mira_rh_node/adversarial.js
```

The source-bound bridge is accessed as a library method. For example:

```python
from pathlib import Path
import json
from aegis_interface.mira_bridge import build_bridge
receipt = json.loads(Path('/tmp/v7-receipt.json').read_text())
bridge = build_bridge(receipt, Path('wit/mira_rh_proof.wit'))
assert bridge['wit']['equivalence'] == 'PASS_ORIGINAL_COMPILER'
assert bridge['lean_kernel_checked'] is False
assert bridge['riemann_hypothesis_proven'] is False
```

The optional third parameter `lean_directory` to `build_bridge` checks **all
four** exact SHA-1 Git blob pins against PR #493 head
`f10d066152dd07fcbe6497566213d91f29e68c5a`. With no Lean files it
returns `lean_source_binding=UNKNOWN_NOT_PRESENT`, not false source verification.
A byte-identical source match is still not a Lean theorem replay.

## Exact Weil dependency (historical, not merged)

- `WeilCriterionCompactSmoothV1.lean`: blob `48039592aa281da1aa514586e09aab09720dd679`; defines `WeilMomentConditionsV1`, `WeilAutocorrelationV1` with **dy**, `WeilPrimeTermV1` and `WeilCompactSmoothNegativityV1`.
- `WeilPrimeSummabilityV1.lean`: blob `5952cac81f515a5ac784cd51e9b3c187d1727d8a`.
- `WeilAutocorrelationRealityV1.lean`: blob `84d389c16b46427d1432f16a3f76baf031fba67c`.
- `WeilAutocorrelationClosureV1.lean`: blob `8a578da0d379d2a643c2ce436a97a4ff5e3531eb`.

The ratio-support and reality theorems exist on the historical PR and do not prove the signed Archimedean inequality. No finite SOS result covers the full class of admissible Weil functions.

## Required next proof boundary

The exact target is global and unchanged: a kernel-checked proof of
`RiemannHypothesis`, with the original Mathlib/FormalConjectures definitions.
To connect the V7 polynomial to the full criterion, separately prove:

1. The constructed Mellin test belongs to original `WeilCompactSmoothGV1` with both moment conditions.
2. The full Mellin/autocorrelation and explicit-formula identity **with `dy`**.
3. Universal real sign for every admissible test, not just a finite Gram matrix or one V7 witness.
4. A real Lean proof term plus exact source, `--trust=0` and `#print axioms` audit.

The WIT receipt never confers kernel authority: `lean_kernel_checked` and
`riemann_hypothesis_proven` remain hard-coded `false`. `authority_class=NONE`.

The Node verifier replays the rational algorithms independently using BigInt; its receipts are self-consistency artifacts only. They are not source-authenticated proof terms.
