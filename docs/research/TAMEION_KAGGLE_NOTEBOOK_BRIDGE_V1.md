# TAMEION_KAGGLE_NOTEBOOK_BRIDGE_V1

Status: **DRAFT / EVIDENCE_ONLY**  
Authority effect: **NONE**

## Why this bridge exists

The Tameion / Arc lane needs two things AEGIS already developed elsewhere:

1. a way to measure whether an agent's confidence matched reality; and
2. a disciplined pattern for turning narrative experiments into machine-checkable evidence.

The historical Kaggle Hallucination Delta (HD) line provides the first primitive.
The Colab / IPYNB corpus provides experiment containers. The external
`mathematical_results.ipynb` copy provides useful examples of a
construct-then-verify notebook style.

None of those artifacts may bypass the existing AEGIS D3/D4 authority gate.

## Canonical Kaggle boundary

The canonical repository lineage in `docs/evidence/kaggle-2026/` defines:

```
HD = |claimed_correctness - actual_correctness|
```

The April archive and outputs are hash-pinned historical artifacts. Their model
scores are not treated as freshly reproduced results, and the repository
explicitly separates this HD lineage from later unsupported claims.

For the Tameion lane, HD is reused only as a **post-settlement calibration
measurement**:

```
agent declares claimed correctness / confidence
                 ↓
AEGIS D3/D4 authority decision
                 ↓
Arc Testnet transfer plan
                 ↓
external settlement + reconciliation evidence
                 ↓
actual correctness
                 ↓
HD = |claimed - actual|
                 ↓
TreasuryCalibrationRecord
```

A low or high HD does not itself authorize money movement.

## Notebook evidence boundary

Working Colab notebooks are useful because they preserve code, narrative,
outputs, and experiment history in one object. They are also unsafe to treat as
trusted executable authority.

`harness/sdk/notebook_evidence.py` therefore:

- hashes the complete notebook bytes;
- counts code and markdown cells;
- catalogs function/class names;
- scans source cells for credential-like material;
- records only secret categories/counts, never secret values;
- hashes the private source locator instead of storing it;
- hard-codes `authority_effect = NONE`.

Two AGI Metacognition working notebooks found in the private Drive corpus contain
credential-like assignments and are therefore classified
`REDACTION_REQUIRED`. Their credential values are intentionally excluded from
this repository.

## Verifier-book pattern

The private Drive corpus also contains a copy of `mathematical_results.ipynb`
with 129 cells and multiple explicit verifier functions such as tensor
decomposition, construction, packing, and sequence checks.

AEGIS uses only the pattern:

```
candidate construction
      ↓
explicit verifier
      ↓
PASS / FAIL evidence
      ↓
content-addressed receipt
```

The mathematical content itself is not imported as proof of any treasury,
stablecoin, accounting, or AEGIS claim.

## Product consequence for Tameion

This gives the financial-agent demo four independently bounded layers:

1. **Notebook / experiment evidence** — reproducible analysis container.
2. **Metacognitive calibration** — historical HD metric applied post hoc.
3. **AEGIS authority** — D3/D4 approval, lease/fencing, idempotency.
4. **Arc settlement evidence** — on-chain observation and replayable witness.

That is stronger than a notebook demo because the notebook can explain and
reproduce an experiment while the authority and payment paths remain separately
machine-enforced.
