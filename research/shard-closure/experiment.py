"""Cut-set admissibility predicate: does shard-closure sharding buy parallelism?

Cost model (deliberately FAVOURABLE to the sharding thesis):
  - unit cost per node, unlimited workers within a round
  - zero communication cost, zero serialization cost, zero orchestrator cost
  - perfect scheduler with full global knowledge

Protocols compared at the SAME parallelism budget k:
  T1        monolith, sequential            = n
  T_dag(k)  node-level list scheduling, k workers (no shard protocol)
  T_shard(k) P2 protocol: shard atomic, admissible iff all cross-shard
             incoming deps finalized
  T_inf     critical-path depth (unit cost lower bound)

Determinism: all randomness from numpy default_rng(seed) with recorded seed.
No wall-clock anywhere.
"""
import json, sys
from pathlib import Path
import numpy as np

def build(nodes, edges):
    idx = {u: i for i, u in enumerate(nodes)}
    n = len(nodes)
    succ = [[] for _ in range(n)]
    pred = [[] for _ in range(n)]
    for u, v in edges:
        a, b = idx[u], idx[v]
        # u depends on v  =>  v must finish before u  =>  edge v -> u
        succ[b].append(a); pred[a].append(b)
    return n, succ, pred

def topo_order(n, succ, pred):
    """Kahn. Returns (order, n_cyclic) where n_cyclic = nodes in cycles."""
    indeg = np.array([len(p) for p in pred])
    q = [i for i in range(n) if indeg[i] == 0]
    order = []
    while q:
        u = q.pop()
        order.append(u)
        for w in succ[u]:
            indeg[w] -= 1
            if indeg[w] == 0:
                q.append(w)
    return order, n - len(order)

def critical_path(n, succ, pred, order):
    """Longest path depth over the acyclic part; cyclic nodes get depth inf-ish."""
    d = np.ones(n, dtype=np.int64)
    for u in order:
        for w in succ[u]:
            if d[w] < d[u] + 1:
                d[w] = d[u] + 1
    return int(d.max()) if n else 0

def list_schedule_k(n, succ, pred, k):
    """Node-level list scheduling with k workers, unit cost. Greedy by round.
    Returns rounds, or None if the DAG has a cycle (never drains)."""
    indeg = np.array([len(p) for p in pred])
    done = np.zeros(n, dtype=bool)
    ready = [i for i in range(n) if indeg[i] == 0]
    rounds = 0
    finished = 0
    while ready:
        rounds += 1
        batch = ready[:k]
        ready = ready[k:]
        newly = []
        for u in batch:
            done[u] = True; finished += 1
            for w in succ[u]:
                indeg[w] -= 1
                if indeg[w] == 0:
                    newly.append(w)
        ready.extend(newly)
    return rounds if finished == n else None

def shard_schedule(n, succ, pred, part, k):
    """P2 protocol. Shard atomic; admissible iff every cross-shard incoming
    dependency is finalized. Cost of a round = max shard size in that round.
    Returns (cost, rounds) or (None, None) on deadlock."""
    sizes = np.bincount(part, minlength=k)
    # cross-shard dependency: shard a depends on shard b
    sdep = [set() for _ in range(k)]
    for u in range(n):
        for v in pred[u]:
            if part[v] != part[u]:
                sdep[part[u]].add(part[v])
    done = np.zeros(k, dtype=bool)
    cost = 0; rounds = 0
    live = [s for s in range(k) if sizes[s] > 0]
    while not all(done[s] for s in live):
        batch = [s for s in live if not done[s] and all(done[b] for b in sdep[s] if sizes[b] > 0)]
        if not batch:
            return None, None          # deadlock: cyclic shard dependency
        rounds += 1
        cost += int(max(sizes[s] for s in batch))
        for s in batch:
            done[s] = True
    return cost, rounds

def partition(strategy, n, k, order, rng):
    if strategy == "random":
        return rng.integers(0, k, size=n)
    if strategy == "topo":           # oracle: contiguous blocks in topological order
        part = np.zeros(n, dtype=np.int64)
        seq = order + [i for i in range(n) if i not in set(order)]
        for pos, node in enumerate(seq):
            part[node] = min(k - 1, pos * k // n)
        return part
    if strategy == "block":          # contiguous blocks in file order (naive but structural)
        return np.minimum(k - 1, np.arange(n) * k // n)
    raise ValueError(strategy)

SEED = 20260825
REPS = 20
KS = [2, 4, 8, 16, 32, 39, 64]

def main(gpath, outpath):
    graphs = json.loads(Path(gpath).read_text())
    results = []
    for gname, g in sorted(graphs.items()):
        n, succ, pred = build(g["nodes"], g["edges"])
        order, n_cyclic = topo_order(n, succ, pred)
        D = critical_path(n, succ, pred, order)
        m = len(g["edges"])
        print(f"\n=== {gname}  n={n} m={m} cyclic_nodes={n_cyclic} critical_path={D} ===")
        for k in KS:
            if k > n: continue
            t_dag = list_schedule_k(n, succ, pred, k)
            row_base = dict(graph=gname, n=n, m=m, n_cyclic=n_cyclic, D=D, k=k,
                            T1=n, T_dag=t_dag)
            for strat in ("random", "block", "topo"):
                reps = REPS if strat == "random" else 1
                costs, deadlocks = [], 0
                for r in range(reps):
                    rng = np.random.default_rng(SEED + 1000 * k + r)
                    part = partition(strat, n, k, order, rng)
                    c, _ = shard_schedule(n, succ, pred, part, k)
                    if c is None: deadlocks += 1
                    else: costs.append(c)
                row = dict(row_base, strategy=strat, reps=reps,
                           deadlock_rate=deadlocks / reps,
                           T_shard_mean=(float(np.mean(costs)) if costs else None),
                           T_shard_std=(float(np.std(costs, ddof=1)) if len(costs) > 1 else 0.0))
                results.append(row)
                dl = f" DEADLOCK {deadlocks}/{reps}" if deadlocks else ""
                ts = f"{row['T_shard_mean']:.1f}" if costs else "  n/a"
                sp = f"{n / row['T_shard_mean']:.2f}x" if costs else "  n/a"
                spd = f"{n / t_dag:.2f}x" if t_dag else "n/a"
                print(f"  k={k:3d} {strat:7s}  T_shard={ts:>7s} speedup={sp:>6s} | "
                      f"T_dag={str(t_dag):>5s} speedup={spd:>6s} | T_inf={D}{dl}")
    Path(outpath).write_text(json.dumps(results, indent=1))
    print(f"\nwritten: {outpath}  rows={len(results)}  seed={SEED}")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
