"""AEGIS issue #758: bounded AlphaEvolve-style experiment for existing evolution spine.
Known schoolbook/Strassen seeds, exact integer tensor evaluator, deterministic
mutations and paired held-out checks. No independent review, skill promotion,
wallet, deployment, billing, model API, or autonomous authority.
"""
from __future__ import annotations
import hashlib
import json
import random
import re

def hash_object(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")).hexdigest()

def seeds():
    baseline = [[[0] * 8 for _ in range(4)] for _ in range(3)]
    q = 0
    for i in range(2):
        for j in range(2):
            for k in range(2):
                baseline[0][2*i+j][q] = 1
                baseline[1][2*j+k][q] = 1
                baseline[2][2*k+i][q] = 1
                q += 1
    u = [[1,0,0,1],[0,0,1,1],[1,0,0,0],[0,0,0,1],
         [1,1,0,0],[-1,0,1,0],[0,1,0,-1]]
    v = [[1,0,0,1],[1,0,0,0],[0,1,0,-1],[-1,0,1,0],
         [0,0,0,1],[1,1,0,0],[0,0,1,1]]
    z = [[1,0,0,1],[0,0,1,-1],[0,1,0,1],[1,0,1,0],
         [-1,1,0,0],[0,0,0,1],[1,0,0,0]]
    # Output tensor indices C11,C21,C12,C22, matching AEGIS contract.
    published = [list(map(list, zip(*rows))) for rows in
                 (u, v, [[r[0],r[2],r[1],r[3]] for r in z])]
    return baseline, published

def exact(factors):
    if type(factors) is not list or len(factors) != 3 or any(
        type(f) is not list or len(f) != 4 for f in factors
    ):
        raise ValueError("INVALID_FACTORS")
    if any(type(row) is not list for f in factors for row in f):
        raise ValueError("INVALID_ROWS")
    widths = {len(row) for f in factors for row in f}
    if len(widths) != 1:
        raise ValueError("NONRECTANGULAR_FACTORS")
    rank = widths.pop()
    if not 1 <= rank <= 32 or any(
        type(v) is not int or abs(v) > 128 for f in factors
        for row in f for v in row
    ):
        raise ValueError("INVALID_COEFFICIENTS")
    a,b,c = factors
    for x in range(4):
        for y in range(4):
            for z in range(4):
                i,j = divmod(x,2)
                jj,k = divmod(y,2)
                target = int(j == jj and z == 2*k+i)
                actual = sum(a[x][h]*b[y][h]*c[z][h] for h in range(rank))
                if actual != target:
                    raise ValueError("EXACT_TENSOR_MISMATCH")
    return rank

def compress(factors):
    fs = [[row[:] for row in f] for f in factors]
    while True:
        rank = exact(fs)
        changed = False
        for i in range(rank):
            for j in range(i+1, rank):
                matches = [k for k in range(3) if all(
                    fs[k][p][i] == fs[k][p][j] for p in range(4))]
                if len(matches) < 2:
                    continue
                other = next(k for k in range(3) if k not in matches[:2])
                for p in range(4):
                    fs[other][p][i] += fs[other][p][j]
                for f in fs:
                    for row in f:
                        row.pop(j)
                changed = True
                break
            if changed:
                break
        if not changed:
            return fs

def mutate(factors, rng):
    rank = exact(factors)
    fs = [[row[:] for row in f] for f in factors]
    action = rng.randrange(3)
    if action == 0:
        j = rng.randrange(rank)
        for f in (fs[0], fs[2]):
            for row in f:
                row[j] = -row[j]
    elif action == 1:
        order = list(range(rank))
        rng.shuffle(order)
        fs = [[[row[j] for j in order] for row in f] for f in fs]
    else:
        j = rng.randrange(rank)
        for k,f in enumerate(fs):
            for row in f:
                row.append(row[j])
                if k == 2:
                    row[j] *= 2
                    row[-1] *= -1
        fs = compress(fs)
    exact(fs)
    return fs

def experiment(*, generations=48):
    if type(generations) is not int or not 0 <= generations <= 256:
        raise ValueError("INVALID_BUDGET")
    baseline, published = seeds()
    if exact(baseline) != 8 or exact(published) != 7:
        raise ValueError("SEED_IDENTITY_FAIL")
    bank = [baseline, published]
    seen = {hash_object(f) for f in bank}
    rng = random.Random(20261012)
    added = 0
    for _ in range(generations):
        proposal = mutate(bank[rng.randrange(min(len(bank),8))], rng)
        fp = hash_object(proposal)
        if fp not in seen:
            seen.add(fp)
            bank.append(proposal)
            added += 1
    champion = min(bank, key=lambda f:(exact(f), hash_object(f)))
    heldout_rng = random.Random(7582026)
    inputs = []
    pairs = []
    for i in range(32):
        a = [heldout_rng.randint(-6,6) for _ in range(4)]
        b = [heldout_rng.randint(-6,6) for _ in range(4)]
        inputs.append((a,b))
        target = [a[0]*b[0]+a[1]*b[2],a[2]*b[0]+a[3]*b[2],
                  a[0]*b[1]+a[1]*b[3],a[2]*b[1]+a[3]*b[3]]
        for fs in (baseline,champion):
            r = exact(fs)
            computed = [sum(
                sum(fs[0][p][h]*a[p] for p in range(4)) *
                sum(fs[1][q][h]*b[q] for q in range(4)) *
                fs[2][z][h] for h in range(r)
            ) for z in range(4)]
            if computed != target:
                raise ValueError("HELDOUT_IDENTITY_FAIL")
        pairs.append({"task_id":f"pair-{i:02d}",
                      "baseline_score":int(exact(baseline) <= 7),
                      "candidate_score":int(exact(champion) <= 7),
                      "safety_regression":False})
    body = {
        "schema":"AEGIS_ALPHAEVOLVE_ISSUE758_EXPERIMENT_V1",
        "issue":"Aegis-Omega/AEGIS-OMEGA#758",
        "baseline_factor_digest":hash_object(baseline),
        "champion_factor_digest":hash_object(champion),
        "baseline_rank":exact(baseline),"champion_rank":exact(champion),
        "seed_provenance":"PUBLISHED_STRASSEN_AND_SCHOOLBOOK",
        "generations":generations,"new_exact_candidates":added,
        "holdout_sha256":hash_object(inputs),"paired_results":pairs,
        "novel_discovery":False,"independent_review":"NOT_PERFORMED",
        "promotion":"DENIED","admission":"DENIED","authority_effect":"NONE"
    }
    return {**body,"receipt_hash":hash_object(body)}

def attach_to_existing_spine(graph, *, baseline_head, source_head, generations=48):
    """Only existing issue reducer/contract spine may interpret the trial.

    Commit labels are caller supplied and NOT publisher authentication.
    Thus even 32 positive pairs cannot grant authority or skill promotion.
    """
    if not all(isinstance(s,str) and re.fullmatch(r"[0-9a-f]{40}",s)
               for s in (baseline_head,source_head)) or baseline_head == source_head:
        raise ValueError("INVALID_HEADS")
    from agents.issue_evolution import evolve_issues
    from agents.evolution_contract_spine import compose_spine
    result = experiment(generations=generations)
    trial = {
        "schema":"AEGIS_ISSUE_EVOLUTION_TRIAL_V1",
        "issue":result["issue"],"baseline":baseline_head,
        "candidate":source_head,"pre_registered_metric":"task_success",
        "holdout_digest":result["holdout_sha256"],
        "paired_results":result["paired_results"],"rollback_ref":baseline_head
    }
    round_result = evolve_issues(graph,[trial])
    spine = compose_spine(graph=graph,trials=[trial],source_head=source_head)
    if (round_result.get("promotion") != "DENIED"
        or spine.get("improvement_admission") != "DENIED"
        or spine.get("authority_effect") != "NONE"):
        raise ValueError("AUTHORITY_BOUNDARY_BROKEN")
    return {"experiment":result,"trial":trial,
            "issue_round_hash":round_result["receipt_hash"],
            "spine_hash":spine["receipt_hash"],
            "head_labels":"OPERATOR_DECLARED_NOT_SOURCE_AUTHENTICATED",
            "independent_review":"NOT_PERFORMED",
            "admission":"DENIED","skill_promotion":"DENIED"}

if __name__ == "__main__":
    print(json.dumps(experiment(),sort_keys=True,indent=2))
