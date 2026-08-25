"""Scaling: P[random k-partition yields an acyclic quotient] vs subgraph size n,
at fixed k=8. Induced subgraphs drawn uniformly from the two large real graphs."""
import json, sys
from pathlib import Path
import numpy as np
from experiment import build, topo_order, shard_schedule, SEED

graphs = json.loads(Path(sys.argv[1]).read_text())
K = 8; R = 300
rows = []
for gname in ("ts_sovereign", "rust_cl_psi"):
    g = graphs[gname]
    nodes = g["nodes"]; N = len(nodes)
    eset = [tuple(e) for e in g["edges"]]
    print(f"=== {gname} (full n={N}), k={K}, {R} draws per size ===")
    for frac in (0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.60, 0.80, 1.00):
        sz = max(K + 1, int(N * frac))
        if sz > N: sz = N
        ok = 0; m_tot = 0; trials = 0
        for r in range(R):
            rng = np.random.default_rng(SEED + 31_000_000 + 1000 * sz + r)
            sub = set(rng.choice(N, size=sz, replace=False).tolist())
            subnodes = [nodes[i] for i in sorted(sub)]
            keep = set(subnodes)
            subedges = [list(e) for e in eset if e[0] in keep and e[1] in keep]
            n, succ, pred = build(subnodes, subedges)
            order, ncyc = topo_order(n, succ, pred)
            if ncyc: continue           # only score acyclic source graphs
            trials += 1; m_tot += len(subedges)
            c, _ = shard_schedule(n, succ, pred, rng.integers(0, K, size=n), K)
            ok += (c is not None)
        p = ok / trials if trials else float("nan")
        rows.append(dict(graph=gname, n=sz, k=K, p_acyclic=p, trials=trials,
                         mean_m=m_tot / max(1, trials)))
        print(f"    n={sz:4d}  mean_edges={m_tot/max(1,trials):7.1f}  P={p:6.4f}  ({ok}/{trials})")
    print()
Path(sys.argv[2]).write_text(json.dumps(rows, indent=1))
print(f"written: {sys.argv[2]}")
