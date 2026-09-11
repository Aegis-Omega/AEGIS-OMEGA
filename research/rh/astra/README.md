# AEGIS Ω — Astra RH Research Environment V1

This directory is a fail-closed research workspace for the current AEGIS RH proof frontier. It is designed for Codex/Astra-style repository work, but every evidence claim remains bound to the exact underlying proof checker and source coordinate.

## What is pinned

- AEGIS frontier: `proof/rh-zero-counting-bound-v1@c85a58ca753e5d99fc9f117e0dc481e1f2cf0bde`
- Parent Mellin checkpoint: `6ec8bb0ee39c462a5b544620b5ad2648c52ecb1e`
- Lean: `4.33.1`
- Mathlib: `0df444a360eaa60ab8c11dca51a86af692955474`
- External Li/Hadamard provider: `nicholasbulka/li-criterion-rh-equivalence-lean@35df682f3b709ffe5fbcfdd452dfa964bd622b87`
- Formal Conjectures statement pin: `74b736b53ce688f57bad186b5dd862daaeeb708e`
- Supporting Coq stack: Coq 8.20.1 / CoRN 9.0.0 / Coquelicot 3.4.2

The current #481 theorem is hosted exact-head compile verified, not receipt-grade repository admission. The exact candidate commit is unsigned and no dedicated artifact was emitted by run `34626508680`.

## First commands

```bash
cd research/rh/astra
python scripts/doctor.py
make verify
```

For a clean Python environment:

```bash
./scripts/bootstrap.sh
```

For non-authoritative symbolic/numerical exploration:

```bash
./scripts/bootstrap.sh --discovery
```

For the exact-pinned external Lean provider, install the exact elan release declared in `TOOLCHAIN.lock`, then run:

```bash
./scripts/bootstrap-lean-frontier.sh
```

## Files

- `ASTRA_MASTER_PROMPT.md`: operating contract for the research agent.
- `PROOF_OBLIGATIONS.yaml`: current proof DAG and open frontier.
- `ASSUMPTION_CENSUS.yaml`: explicit formal trust surface.
- `NORMALIZATION_FREEZE.md`: what is and is not yet convention-bound.
- `TOOLCHAIN.lock`: exact formal dependency pins.
- `scripts/validate_obligations.py`: semantic + JSON-Schema validator.
- `scripts/run_falsifiers.py`: deliberate invalid-state mutations that must be rejected.
- `scripts/audit_frontier.py`: ancestry and forbidden-manual-write check.
- `scripts/snapshot_receipt.py`: deterministic content receipt for this environment.
- `scripts/collect_axioms.py`: helper for Lean `#print axioms` audits.
- `tests/`: fail-closed unit tests.

## Non-negotiable boundaries

`RH_STATUS = NOT_PROVEN`, `execution_release = BLOCKED`, and `authority_effect = NONE` until the proof DAG actually closes. This directory never authorizes a merge or an execution release. `.claude.json` is not a manual writer target.
