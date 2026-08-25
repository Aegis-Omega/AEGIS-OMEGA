"""Closed-form prediction vs measurement.

A shard-quotient deadlock occurs iff the quotient multigraph contains a directed
cycle. The dominant mode is a 2-cycle: some pair (S_a,S_b) carries an edge in
each direction. Under a uniform random k-partition each of the m edges lands on
an ordered pair of distinct shards with probability (k-1)/k, uniformly over the
k(k-1) ordered pairs. The expected number of reciprocated pairs is

    lambda(m,k) = C(m,2) * 2 * (1/(k(k-1)))^1 * (1/(k(k-1))) * k(k-1)
                = m(m-1) / (2 k (k-1))        [two given edges reciprocate
                                               with prob 1/(k(k-1))]

and, treating reciprocations as approximately Poisson,

    P[schedulable] <= P[no 2-cycle] ~ exp(-lambda).

This is an UPPER bound on P: longer cycles also deadlock and are not counted.
"""
import json, sys
from pathlib import Path
import numpy as np

rows = json.loads(Path(sys.argv[1]).read_text())
print(f"{'graph':14s} {'n':>4s} {'m_mean':>8s} {'lambda':>8s} {'P_pred<=':>9s} {'P_obs':>7s} {'gap':>7s}")
print("-" * 62)
gaps = []
for r in rows:
    k = r["k"]; m = r["mean_m"]
    lam = m * (m - 1) / (2 * k * (k - 1)) if m > 1 else 0.0
    pred = float(np.exp(-lam))
    obs = r["p_acyclic"]
    gaps.append(obs - pred)
    print(f"{r['graph']:14s} {r['n']:4d} {m:8.1f} {lam:8.3f} {pred:9.4f} {obs:7.4f} {obs-pred:+7.4f}")
g = np.array(gaps)
print("-" * 62)
print(f"bound violated (P_obs > P_pred) in {int((g > 0.02).sum())}/{len(g)} cells")
print(f"mean signed gap = {g.mean():+.4f}   max |gap| = {np.abs(g).max():.4f}")
# where does the model put the safety boundary?
print("\nDesign rule implied by the model: P >= 0.95 requires lambda <= 0.051,")
for k in (8, 16, 39, 64):
    mmax = 0.5 * (1 + np.sqrt(1 + 8 * 0.051 * k * (k - 1)))
    print(f"    k={k:3d}  ->  m <= {mmax:5.1f} cross-shard-eligible edges")
