"""Structure-aware deadlock model, replacing the refuted uniform model.

Execution edge p->q means p must finish before q. A 2-cycle in the quotient
needs edges e1=(p->q), e2=(r->s) with part(p)=part(s), part(q)=part(r),
part(p)!=part(q). Case analysis over how e1,e2 share vertices:

  disjoint (4 distinct)  P = (1/k)(1/k)((k-1)/k) = (k-1)/k^3
  2-path   (q=r or p=s)  P = (1/k)((k-1)/k)      = (k-1)/k^2      <-- k x larger
  shared source (p=r)    requires part(q)=part(p): contradiction   P = 0
  shared target (q=s)    same contradiction                        P = 0

  lambda = N_2path * (k-1)/k^2 + N_disjoint * (k-1)/k^3
  P[schedulable] <= exp(-lambda)      (longer cycles uncounted)

Hub-structured graphs put most edge pairs in the two ZERO cases, which is why
the uniform C(m,2) model over-predicted lambda and under-predicted P.
"""
import json, sys
from collections import defaultdict
from pathlib import Path
import numpy as np
from experiment import build, topo_order, shard_schedule, SEED

def counts(n, succ, pred, m):
    # execution-space degrees
    outd = np.array([len(succ[i]) for i in range(n)])
    ind  = np.array([len(pred[i]) for i in range(n)])
    n_2path  = int((ind * outd).sum())                      # p->v->s
    n_shsrc  = int((outd * (outd - 1) // 2).sum())          # p->q, p->s
    n_shtgt  = int((ind * (ind - 1) // 2).sum())            # p->q, r->q
    total    = m * (m - 1) // 2
    n_disj   = total - n_2path - n_shsrc - n_shtgt
    return n_2path, n_shsrc, n_shtgt, max(0, n_disj), total

def lam(n2p, ndisj, k):
    return n2p * (k - 1) / k**2 + ndisj * (k - 1) / k**3

graphs = json.loads(Path(sys.argv[1]).read_text())
rows = json.loads(Path(sys.argv[2]).read_text())
K = 8; R = 300

# recompute structure counts on the SAME subgraph draws used for the measurement
print(f"{'graph':14s} {'n':>4s} {'m':>7s} {'2path':>7s} {'shSrc':>7s} {'shTgt':>7s} {'disj':>7s} "
      f"{'lam_old':>8s} {'lam_new':>8s} {'P_new<=':>8s} {'P_obs':>7s} {'gap':>7s}")
print("-" * 104)
gaps_new, gaps_old = [], []
for gname in ("ts_sovereign", "rust_cl_psi"):
    g = graphs[gname]; nodes = g["nodes"]; N = len(nodes)
    eset = [tuple(e) for e in g["edges"]]
    for row in [r for r in rows if r["graph"] == gname]:
        sz = row["n"]
        acc = np.zeros(5); trials = 0; ok = 0
        for r in range(R):
            rng = np.random.default_rng(SEED + 31_000_000 + 1000 * sz + r)
            sub = set(rng.choice(N, size=sz, replace=False).tolist())
            subnodes = [nodes[i] for i in sorted(sub)]; keep = set(subnodes)
            subedges = [list(e) for e in eset if e[0] in keep and e[1] in keep]
            n, succ, pred = build(subnodes, subedges)
            order, ncyc = topo_order(n, succ, pred)
            if ncyc: continue
            trials += 1
            acc += np.array(counts(n, succ, pred, len(subedges)))
            c, _ = shard_schedule(n, succ, pred, rng.integers(0, K, size=n), K)
            ok += (c is not None)
        n2p, shs, sht, dsj, tot = (acc / trials)
        m = row["mean_m"]
        l_new = lam(n2p, dsj, K); l_old = m * (m - 1) / (2 * K * (K - 1))
        p_new = float(np.exp(-l_new)); p_obs = ok / trials
        gaps_new.append(p_obs - p_new); gaps_old.append(p_obs - float(np.exp(-l_old)))
        print(f"{gname:14s} {sz:4d} {m:7.1f} {n2p:7.1f} {shs:7.1f} {sht:7.1f} {dsj:7.1f} "
              f"{l_old:8.3f} {l_new:8.3f} {p_new:8.4f} {p_obs:7.4f} {p_obs-p_new:+7.4f}")
gn, go = np.array(gaps_new), np.array(gaps_old)
print("-" * 104)
print(f"OLD uniform model : bound violated in {int((go > 0.02).sum())}/{len(go)} cells, "
      f"mean gap {go.mean():+.4f}, max |gap| {np.abs(go).max():.4f}")
print(f"NEW structure model: bound violated in {int((gn > 0.02).sum())}/{len(gn)} cells, "
      f"mean gap {gn.mean():+.4f}, max |gap| {np.abs(gn).max():.4f}")
