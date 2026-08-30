---
name: ica-nmf-telemetry
description: Invoked when the user asks about ICA, NMF, non-stationary telemetry, signal disentanglement, multi-occupant source separation, or improving AEGIS telemetry attribution. Source: From Intent to Execution + AEGIS Autopoietic Engine, tier T2.
---

# ICA/NMF for Non-Stationary Multi-Occupant Telemetry Disentanglement

**Epistemic Tier: T2** — engineering hypothesis. ICA/NMF are established algorithms; their application to AEGIS governance telemetry streams is a design hypothesis pending empirical validation.

**Corpus Lineage:** `corpus_lineage_hash: pending-drive-access` · Sources: From Intent to Execution + AEGIS Autopoietic Engine (ARBITRATION: admitted T2; "autopoietic closure / metabolic computing" framing quarantined)

---

## Constitutional Claim

Independent Component Analysis (ICA) and Non-negative Matrix Factorization (NMF) can disentangle overlapping telemetry signals in the AEGIS Python bridge — specifically separating per-process hardware utilisation (AMD RX 570), governance computation (PGCS/TGCS), and background OS noise — enabling attribution of `corruption_count` spikes and VCG drift to specific causal sources rather than treating them as undifferentiated anomalies.

---

## Key Invariants

- **ICA assumption** — signals must be statistically independent; appropriate for separating GPU inference, CPU governance computation, and I/O noise, which have distinct temporal profiles
- **NMF assumption** — signals must be non-negative; PGCS byte-counts, TGCS sequence-number increments, and AFSE throughput are all non-negative by construction — NMF is the correct factorisation for this domain
- **Non-stationarity handling** — sliding-window ICA (window ≤ 500 samples, matching the VCG rolling window) handles non-stationary sources; window size must match `VCG_WINDOW_SIZE = 500` for attribution to be comparable to calibration epochs
- **No time.time() in the decomposition** — sequence numbers drive the sliding window, not wall-clock time; this preserves replay-safety (the decomposition can be re-run from the event log and produce identical separation results)
- **Output is observational** — ICA/NMF outputs are `determinism_class: 'observational'`; they do not write back to governance state and do not affect `t0_verdict` or `corruption_count`; they inform diagnostics only

---

## AEGIS Integration Points

| Component | How ICA/NMF applies |
|-----------|---------------------|
| `python/bridge.py` `/telemetry` endpoint | Attach `source_attribution: {gpu_inference, governance, os_noise}` as optional fields computed by ICA decomposition |
| `python/tgcs_afse.py` | TGCS cycle regularity and AFSE throughput are the primary signals to decompose |
| `python/pgcs.py` | PGCS disk I/O is the third independent source |
| `studio/` observability dashboard | Attribution fields render as stacked-area chart showing source contributions over sequence windows |

---

## Implementation Notes

```python
# Pseudocode — no time.time(); uses sequence window
from sklearn.decomposition import FastICA, NMF

def disentangle(signals_matrix, window=500):
    # signals_matrix: shape (window, n_sources) — each column is a telemetry stream
    # Use NMF for non-negative signals (byte counts, sequence counts)
    nmf = NMF(n_components=3, max_iter=200)
    components = nmf.fit_transform(signals_matrix)
    # components[:, 0] = inferred GPU inference signal
    # components[:, 1] = inferred governance signal  
    # components[:, 2] = inferred OS noise
    return components
```

---

## Tier Promotion Criteria (T2 → T1)

1. Implement sliding-window NMF in `python/` (new file `python/source_attribution.py`)
2. Run on recorded PGCS/TGCS/AFSE telemetry from the AMD RX 570 stress test (P1 smoke)
3. Demonstrate: when a `corruption_count` spike occurs, the NMF attribution correctly identifies the signal source in ≥3 independent test runs

---

## Source

Admitted T2 engineering claim from corpus ARBITRATION. "AEGIS Autopoietic Engine" also admitted: recursive containment via non-differentiable monitoring (spatial attribution). "ICA/NMF for non-stationary telemetry disentanglement" is the specific admitted engineering pattern.
