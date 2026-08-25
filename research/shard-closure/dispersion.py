"""Why both closed forms fail as bounds: is the reciprocal-pair count Poisson?
Poisson requires Var/Mean = 1. Measure it directly."""
import json, sys
from pathlib import Path
import numpy as np
from experiment import build, topo_order, SEED

def recip_count(n, succ, pred, part, k):
    """Number of distinct reciprocated shard pairs {a,b} in the quotient."""
    fwd = set()
    for p in range(n):
        for q in succ[p]:
            if part[p] != part[q]:
                fwd.add((int(part[p]), int(part[q])))
    return sum(1 for (a, b) in fwd if (b, a) in fwd) // 2

graphs = json.loads(Path(sys.argv[1]).read_text())
K = 8; R = 2000
print(f"{'graph':14s} {'n':>4s} {'mean N':>8s} {'var N':>8s} {'var/mean':>9s} "
      f"{'P[N=0] obs':>11s} {'exp(-mean)':>11s}")
print("-" * 70)
for gname, sizes in (("ts_sovereign", (19, 28, 38, 57)), ("rust_cl_psi", (42, 63, 84, 126))):
    g = graphs[gname]; nodes = g["nodes"]; N = len(nodes)
    eset = [tuple(e) for e in g["edges"]]
    for sz in sizes:
        vals = []
        for r in range(R):
            rng = np.random.default_rng(SEED + 55_000_000 + 1000 * sz + r)
            sub = set(rng.choice(N, size=sz, replace=False).tolist())
            subnodes = [nodes[i] for i in sorted(sub)]; keep = set(subnodes)
            subedges = [list(e) for e in eset if e[0] in keep and e[1] in keep]
            n, succ, pred = build(subnodes, subedges)
            order, ncyc = topo_order(n, succ, pred)
            if ncyc: continue
            vals.append(recip_count(n, succ, pred, rng.integers(0, K, size=n), K))
        v = np.array(vals, dtype=float)
        mu, var = v.mean(), v.var(ddof=1)
        p0 = float((v == 0).mean())
        print(f"{gname:14s} {sz:4d} {mu:8.3f} {var:8.3f} {var/mu:9.3f} "
              f"{p0:11.4f} {np.exp(-mu):11.4f}")
print("-" * 70)
print("Var/Mean > 1 => over-dispersed => P[N=0] > exp(-E[N]).")
print("Reciprocation events share edges and vertices, so they are positively")
print("correlated; the Poisson step, not the combinatorics, is what fails.")
