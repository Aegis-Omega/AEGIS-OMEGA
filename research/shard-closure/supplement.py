"""Supplementary: (0) minimal deadlock witness, (1) acyclic-partition probability
vs k, (2) k=n degeneracy, (3) oracle cost vs same-budget DAG scheduling."""
import json, sys
from pathlib import Path
import numpy as np
from experiment import build, topo_order, critical_path, list_schedule_k, shard_schedule, partition, SEED

# ---- (0) minimal witness: a DAG whose quotient is cyclic -------------------
nodes = ["a", "b", "c"]; edges = [["b", "a"], ["c", "b"]]   # b dep a, c dep b
n, succ, pred = build(nodes, edges)
order, ncyc = topo_order(n, succ, pred)
assert ncyc == 0, "witness graph must be acyclic"
part = np.array([0, 1, 0])          # a,c -> shard 0 ; b -> shard 1
cost, _ = shard_schedule(n, succ, pred, part, 2)
print("(0) minimal witness  a->b->c, partition {a,c},{b}")
print(f"    source graph acyclic: True (cyclic_nodes={ncyc})")
print(f"    shard schedule: {'DEADLOCK' if cost is None else cost}")
print("    => the quotient of a DAG by an arbitrary partition need not be a DAG\n")

graphs = json.loads(Path(sys.argv[1]).read_text())
out = []
for gname, g in sorted(graphs.items()):
    n, succ, pred = build(g["nodes"], g["edges"])
    order, ncyc = topo_order(n, succ, pred)
    D = critical_path(n, succ, pred, order)
    print(f"=== {gname}  n={n} D={D} ===")

    # ---- (1) probability a uniformly random k-partition is schedulable ----
    print("    (1) P[random k-partition is acyclic], 200 draws each")
    for k in [2, 4, 8, 16, 32, 39, 64, 128, 256]:
        if k > n: continue
        ok = 0; R = 200
        for r in range(R):
            rng = np.random.default_rng(SEED + 7_000_000 + 1000 * k + r)
            c, _ = shard_schedule(n, succ, pred, partition("random", n, k, order, rng), k)
            ok += (c is not None)
        out.append(dict(graph=gname, k=k, p_acyclic=ok / R, draws=R))
        print(f"        k={k:4d}  P={ok/R:5.3f}  ({ok}/{R})")

    # ---- (2) k = n degeneracy ----
    rng = np.random.default_rng(SEED)
    part_id = np.arange(n)
    c_id, _ = shard_schedule(n, succ, pred, part_id, n)
    t_dag_n = list_schedule_k(n, succ, pred, n)
    print(f"    (2) k=n identity partition: T_shard={c_id}  T_dag={t_dag_n}  D={D}"
          f"   -> decomposition has vanished\n")
    out.append(dict(graph=gname, k=n, identity=True, T_shard=c_id, T_dag=t_dag_n, D=D))

    # ---- (3) oracle vs same-budget node-level scheduling ----
    print("    (3) topological ORACLE partition vs node-level DAG scheduling, same k")
    for k in [2, 4, 8, 16, 32, 39, 64]:
        if k > n: continue
        rng = np.random.default_rng(SEED)
        c, rounds = shard_schedule(n, succ, pred, partition("topo", n, k, order, rng), k)
        td = list_schedule_k(n, succ, pred, k)
        pen = c / td if (c and td) else float("nan")
        out.append(dict(graph=gname, k=k, oracle=True, T_shard=c, T_dag=td, D=D,
                        penalty=pen, dag_off_opt=td / D))
        print(f"        k={k:3d}  T_shard={c:5d}  T_dag={td:4d}  D={D:3d}   "
              f"protocol penalty = {pen:5.2f}x   (T_dag is {td/D:.2f}x off optimum)")
    print()

Path(sys.argv[2]).write_text(json.dumps(out, indent=1))
print(f"written: {sys.argv[2]}")
