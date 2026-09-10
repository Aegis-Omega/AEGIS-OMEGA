# AEGIS C* Kernel v0.1

Finite-dimensional C*-algebra, sheaf-coherence, Postnikov-holonomy, and spectral-phantom verification kernel derived from the AEGIS CSTAR specification diagrams.

## Verification

```bash
python -m pip install -e . pytest
python -m pytest -q
python tools/fuzz_stress_v1.py
```

The randomized stress corpus is deterministic (`MASTER_SEED = 20260910`).

## Epistemic boundary

Passing this package's unit, adversarial, and deterministic fuzz tests establishes only the tested finite-dimensional software behavior. It does not establish general or infinite-dimensional C*-algebra theorems, physical truth, repository admission, merge authority, or production authority.
