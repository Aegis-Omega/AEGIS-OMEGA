"""AEGIS Ω x AlphaEvolve: bounded, deterministic, data-derived evolution for #758.

Two strictly offline domain tasks. Untrusted CSV never becomes code. No skill
promotion, agent dispatch, model API, Git mutation, or authority changes.

- agent_method_policy: choose a verified strategy for each scenario on train data;
  select by separate validation data; evaluate one frozen candidate on holdout.
- finite_bath_policy: evolve interpretable CG/Davies decision thresholds and
  evaluate on unseen physics-config groups. Neither source is laboratory data.

This is a *search algorithm*, not an LLM or Google DeepMind AlphaEvolve service.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import random
from itertools import product
from pathlib import Path
from typing import Any

KIND = "AEGIS_ALPHAEVOLVE_DATA_FUSION_V2"
BENCHMARK = "aegis_omega_benchmark_seed_results.csv"
BATH = "finite_bath_exact_unitary_crosscheck_scan_v1.csv"
PINNED = {
    BENCHMARK: "d6a492d9caeaacc2b835d39c22bfbfaeafd02d4ae5dd040e4855826dcf5a2dc1",
    BATH: "f1e1f17fd3de121f2cb3f76354f09e2d39cc336f54e5f5309f535dbbf40979b2",
}
SCENARIOS = ("blindspot", "drift", "heterogeneous", "homogeneous")
METHODS = ("A_single", "B_static_swarm", "C0_verified_static", "C_adaptive_window")
BATH_INPUTS = ("model", "J", "h", "beta", "lambda", "tau_c", "probe", "t")
MAX_BYTES = 2_000_000


def canonical(v: Any) -> bytes:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


def digest(v: Any) -> str:
    return hashlib.sha256(canonical(v)).hexdigest()


def read_csv_strict(path: str | Path, expected_sha: str, columns: tuple[str, ...]) -> tuple[list[dict[str, str]], str]:
    """Bounded, byte-pinned reader; no spreadsheet formulas or untrusted code."""
    if not isinstance(expected_sha, str) or len(expected_sha) != 64 or any(c not in "0123456789abcdef" for c in expected_sha):
        raise ValueError("INVALID_EXPECTED_SHA")
    p = Path(path)
    if p.is_symlink() or not p.is_file():
        raise ValueError("SOURCE_NOT_REGULAR_FILE")
    with p.open("rb") as f:
        raw = f.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("SOURCE_OVER_BUDGET")
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected_sha:
        raise ValueError("DATASET_SHA256_MISMATCH")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError as exc:
        raise ValueError("CSV_NOT_UTF8") from exc
    import io
    reader = csv.DictReader(io.StringIO(text), strict=True)
    if (reader.fieldnames is None or len(set(reader.fieldnames)) != len(reader.fieldnames)
            or not set(columns).issubset(reader.fieldnames)):
        raise ValueError("DATASET_SCHEMA_MISMATCH")
    rows = list(reader)
    if not rows or len(rows) > 10000 or any(None in row or any(v is None or len(v) > 1024 for v in row.values()) for row in rows):
        raise ValueError("DATASET_ROWS_INVALID")
    return rows, actual


def real(row: dict[str, str], key: str, lo: float = -math.inf, hi: float = math.inf) -> float:
    try:
        v = float(row[key])
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError("NONNUMERIC_" + key) from e
    if not math.isfinite(v) or not lo <= v <= hi:
        raise ValueError("NUMERIC_BOUND_" + key)
    return v


def load_benchmark(path: str | Path, sha: str) -> tuple[dict[tuple[str, int, str], dict], str]:
    keys = ("scenario", "seed", "method", "verified_success", "false_admission", "mean_cost")
    rows, actual = read_csv_strict(path, sha, keys)
    parsed = {}
    for row in rows:
        try:
            seed = int(row["seed"])
        except (ValueError, TypeError) as exc:
            raise ValueError("BAD_SEED") from exc
        scenario, method = row["scenario"], row["method"]
        if scenario not in SCENARIOS or method not in METHODS or not 0 <= seed < 40 or str(seed) != row["seed"]:
            raise ValueError("BENCHMARK_IDENTIFIERS_INVALID")
        k = (scenario, seed, method)
        if k in parsed:
            raise ValueError("DUPLICATE_BENCHMARK_PAIR")
        parsed[k] = {"success": real(row,"verified_success",0,1),
                     "false": real(row,"false_admission",0,1),
                     "cost": real(row,"mean_cost",0,20)}
    # Complete factorial design is essential: any missing candidate cannot win by omission.
    if len(parsed) != 4 * 40 * 4 or any((s,z,m) not in parsed for s in SCENARIOS for z in range(40) for m in METHODS):
        raise ValueError("BENCHMARK_FACTORIAL_INCOMPLETE")
    return parsed, actual


def benchmark_score(v: dict) -> float:
    # Fixed BEFORE search; penalties avoid trading success for high false admissions.
    return v["success"] - 1.5 * v["false"] - 0.03 * v["cost"]


def bench_metrics(data: dict, policy: tuple[str, ...], seeds: range) -> dict[str, float]:
    obs = [data[(s,z,policy[i])] for i,s in enumerate(SCENARIOS) for z in seeds]
    if not obs:
        raise ValueError("EMPTY_SPLIT")
    n = len(obs)
    return {"fitness": sum(benchmark_score(v) for v in obs) / n,
            "verified_success": sum(v["success"] for v in obs) / n,
            "false_admission": sum(v["false"] for v in obs) / n,
            "mean_cost": sum(v["cost"] for v in obs) / n,
            "pairs": n, "unique_seeds": len(seeds)}


def bench_search(data: dict, *, seed: int = 758, generations: int = 48) -> dict:
    if type(generations) is not int or not 1 <= generations <= 128:
        raise ValueError("INVALID_EVOLUTION_BUDGET")
    # Holdout seeds 16..39 are NEVER read while searching, selecting or tuning.
    train, valid, holdout = range(0,8),range(8,16),range(16,40)
    rng = random.Random(seed)
    baseline = ("C_adaptive_window",) * 4
    population = [baseline, ("C0_verified_static",) * 4, ("A_single",) * 4,
                  ("B_static_swarm",) * 4]
    for _ in range(12):
        population.append(tuple(rng.choice(METHODS) for _ in SCENARIOS))
    cache: dict[tuple[str, ...], tuple[float, float]] = {}
    def fitness(p):
        if p not in cache:
            t=bench_metrics(data,p,train);v=bench_metrics(data,p,valid)
            # Conservative constraints judged on train+validation only.
            base=bench_metrics(data,baseline,range(0,16))
            full=bench_metrics(data,p,range(0,16))
            penalty = 100 if full["false_admission"] > base["false_admission"]+0.005 else 0
            cache[p] = (t["fitness"]-penalty, v["fitness"]-penalty)
        return cache[p]
    traces = []
    for gen in range(generations):
        population.sort(key=lambda p:(fitness(p)[0], fitness(p)[1], tuple(p)),reverse=True)
        traces.append({"generation":gen,"training_best":round(fitness(population[0])[0],12),
                       "unique_candidates_seen":len(cache)})
        elites = population[:6]
        population = list(elites)
        while len(population) < 16:
            a,b = rng.choice(elites),rng.choice(elites)
            child=list(a[:2]+b[2:])
            for _ in range(1 if rng.random()<0.8 else 2):
                child[rng.randrange(4)] = rng.choice(METHODS)
            population.append(tuple(child))
    # Select on validation ONLY from the trained candidate set; baseline is an allowed choice.
    candidate = max(cache.keys(),key=lambda p:(fitness(p)[1],fitness(p)[0],p))
    if fitness(candidate)[1] <= fitness(baseline)[1]+1e-12:
        candidate = baseline
    # The only time test seeds are accessed.
    held_base = bench_metrics(data,baseline,holdout)
    held_new  = bench_metrics(data,candidate,holdout)
    pairs=[]
    for i,scenario in enumerate(SCENARIOS):
        for z in holdout:
            a=data[(scenario,z,baseline[i])];b=data[(scenario,z,candidate[i])]
            pairs.append({"task_id":f"{scenario}:{z}", "baseline_verified_success":a["success"],
                          "candidate_verified_success":b["success"],
                          "baseline_false_admission":a["false"],"candidate_false_admission":b["false"],
                          "baseline_cost":a["cost"],"candidate_cost":b["cost"],
                          "baseline_fitness":benchmark_score(a),"candidate_fitness":benchmark_score(b)})
    cluster_effects = []
    for z in holdout:
        deltas=[x["candidate_fitness"]-x["baseline_fitness"] for x in pairs
                if x["task_id"].endswith(":"+str(z))]
        cluster_effects.append(sum(deltas)/len(deltas))
    wins=sum(v>0 for v in cluster_effects)
    losses=sum(v<0 for v in cluster_effects)
    nz=wins+losses
    sign_p=sum(math.comb(nz,k) for k in range(wins,nz+1))/(2**nz) if nz else 1.0
    # Check each scenario: aggregate averages must never hide a risk regression.
    scenario_risk = []
    for i, scenario in enumerate(SCENARIOS):
        base_rows = [data[(scenario, z, baseline[i])] for z in holdout]
        candidate_rows = [data[(scenario, z, candidate[i])] for z in holdout]
        base_risk = sum(v["false"] for v in base_rows) / len(base_rows)
        candidate_risk = sum(v["false"] for v in candidate_rows) / len(candidate_rows)
        scenario_risk.append({"scenario": scenario, "baseline_false_admission": base_risk,
                              "candidate_false_admission": candidate_risk,
                              "delta_false_admission": candidate_risk-base_risk,
                              "safety_regression": candidate_risk > base_risk + 1e-12})
    # Independent exhaustive oracle for this bounded policy class (4^4=256).
    # It is trained/selected ONLY on train and validation splits.
    all_policies = list(product(METHODS, repeat=len(SCENARIOS)))
    validation_oracle = max(all_policies, key=lambda p: (
        bench_metrics(data, p, valid)["fitness"],
        bench_metrics(data, p, train)["fitness"], p))
    selected_valid = bench_metrics(data, candidate, valid)["fitness"]
    oracle_valid = bench_metrics(data, validation_oracle, valid)["fitness"]
    # Descriptive cluster bootstrap, not evidence of source independence.
    fixed_rng = random.Random(758_20261012)
    draws = []
    for _ in range(2000):
        sampled = [cluster_effects[fixed_rng.randrange(len(cluster_effects))]
                   for _ in range(len(cluster_effects))]
        draws.append(sum(sampled)/len(sampled))
    draws.sort()
    bootstrap = {"method": "seed_cluster_percentile_bootstrap_descriptive",
                 "resamples": len(draws), "lower_95": draws[49], "upper_95": draws[1949],
                 "limited_independence": True}
    no_regression=held_new["false_admission"]<=held_base["false_admission"]
    strict_safety = no_regression and not any(x["safety_regression"] for x in scenario_risk)
    screen=("NEEDS_EXTERNAL_REVIEW" if len(cluster_effects) >= 30
            and sign_p<=0.01 and strict_safety
            and held_new["fitness"]>held_base["fitness"] else "NOT_ADMITTED")
    return {"task":"AGENT_METHOD_POLICY","baseline_policy":dict(zip(SCENARIOS,baseline)),
            "selected_policy":dict(zip(SCENARIOS,candidate)),
            "search":"deterministic_16_population_elitist_genetic_search",
            "generations":generations,"mutations":"one_or_two_scenario_method_substitutions",
            "train_seeds":list(train),"validation_seeds":list(valid),"holdout_seeds":list(holdout),
            "train_validation_candidates_examined":len(cache),"training_trace":traces,
            "holdout_baseline":held_base,"holdout_candidate":held_new,
            "holdout_delta_fitness":held_new["fitness"]-held_base["fitness"],
            "holdout_delta_false_admission":held_new["false_admission"]-held_base["false_admission"],
            "paired_holdout":pairs,
            "seed_cluster_sign_test":{"positive":wins,"negative":losses,"ties":len(cluster_effects)-nz,
                                      "one_sided_p":sign_p,"threshold":0.01,
                                      "observational_non_independence_warning":"24 seed clusters across 4 scenarios"},
            "screen":screen,
            "scenario_safety": scenario_risk,
            "scenario_regression_veto": not strict_safety,
            "holdout_independent_cluster_count": len(cluster_effects),
            "issue758_minimum_independent_pairs": 30,
            "issue758_minimum_pairs_met": len(cluster_effects) >= 30,
            "cluster_bootstrap": bootstrap,
            "oracle_train_validation_only": {"policy": dict(zip(SCENARIOS, validation_oracle)),
                                               "policies_enumerated":len(all_policies),
                                               "candidate_validation_fitness": selected_valid,
                                               "oracle_validation_fitness": oracle_valid,
                                               "validation_gap": oracle_valid-selected_valid},
            "metric_preregistration":"success - 1.5*false_admission - 0.03*cost; candidate pre-holdout false_admission <= baseline + 0.005",
            "candidate_promotion":"DENIED", "independent_reproduction":"NOT_PERFORMED"}


def load_bath(path: str | Path, sha: str) -> tuple[list[dict], str]:
    cols=BATH_INPUTS+("exact_vs_CG_trace_distance","exact_vs_Davies_trace_distance","winner")
    rows,actual=read_csv_strict(path,sha,cols)
    out=[];seen=set()
    for row in rows:
        for key in ("J","h","beta","lambda","tau_c","t"):
            real(row,key,0)
        c=real(row,"exact_vs_CG_trace_distance",0,2)
        d=real(row,"exact_vs_Davies_trace_distance",0,2)
        if row["model"] not in {"near_degenerate","intermediate"} or row["winner"] not in {"CG","DAVIES"}:
            raise ValueError("BATH_LABEL_INVALID")
        if row["winner"] != ("CG" if c < d else "DAVIES"):
            # Exact tie is not an admitted winner; only check strict unequal rows.
            if abs(c-d)>1e-15:
                raise ValueError("BATH_WINNER_MISMATCH")
        key=tuple(row[k] for k in BATH_INPUTS)
        if key in seen:
            raise ValueError("BATH_DUPLICATE_EXPERIMENT")
        seen.add(key)
        physics_key=tuple(row[k] for k in ("model","J","h","beta","lambda"))
        out.append({"feature":{"t":float(row["t"]),"lambda":float(row["lambda"]),
                                "beta":float(row["beta"]),"tau_c":float(row["tau_c"])},
                    "group":physics_key,"cg":c,"davies":d,"key":key})
    if len(out)!=240 or len({r["group"] for r in out})!=12:
        raise ValueError("BATH_GRID_INCOMPLETE")
    return out,actual


def bath_decision(policy: tuple, r: dict) -> str:
    if policy == ("constant","CG"):
        return "CG"
    if type(policy) is not tuple or len(policy)!=4:
        raise ValueError("INVALID_BATH_POLICY")
    feature, op, threshold, option=policy
    if feature not in {"t","lambda","beta","tau_c"} or op not in {"<=",">"} or option!="DAVIES" or type(threshold) not in (float,int) or not math.isfinite(threshold):
        raise ValueError("INVALID_BATH_POLICY")
    x=r["feature"][feature]
    return "DAVIES" if (x<=threshold if op=="<=" else x>threshold) else "CG"


def bath_score(rows: list[dict], policy: tuple) -> dict:
    if not rows:raise ValueError("EMPTY_BATH_SLICE")
    distances=[r["cg"] if bath_decision(policy,r)=="CG" else r["davies"] for r in rows]
    return {"mean_trace_distance":sum(distances)/len(distances),"rows":len(rows),
            "unique_physics_groups":len({r["group"] for r in rows}),
            "davies_selected":sum(bath_decision(policy,r)=="DAVIES" for r in rows)}


def bath_search(rows: list[dict], *, seed: int=20261012, generations:int=48) -> dict:
    if type(generations) is not int or not 1<=generations<=128:raise ValueError("INVALID_EVOLUTION_BUDGET")
    # 12 complete physical configurations, not randomly intermingled times/probes.
    groups=sorted({r["group"] for r in rows})
    train_g=set(groups[i] for i in range(12) if i%4 in (0,1))
    val_g=set(groups[i] for i in range(12) if i%4==2)
    test_g=set(groups[i] for i in range(12) if i%4==3)
    train=[r for r in rows if r["group"] in train_g]
    val=[r for r in rows if r["group"] in val_g]
    test=[r for r in rows if r["group"] in test_g]
    baseline=("constant","CG")
    # Bounded grammatical search over interpretable real-valued guards.
    policies={baseline}
    rng=random.Random(seed)
    features=("t","lambda","beta","tau_c")
    thresholds={f:sorted({r["feature"][f] for r in train}) for f in features}
    trace=[]
    for gen in range(generations):
        for _ in range(16):
            f=rng.choice(features);op=rng.choice(("<=",">"));threshold=rng.choice(thresholds[f])
            policies.add((f,op,threshold,"DAVIES"))
        winner=min(policies,key=lambda p:(bath_score(train,p)["mean_trace_distance"],str(p)))
        trace.append({"generation":gen,"train_best_error":bath_score(train,winner)["mean_trace_distance"],
                      "candidate_count":len(policies)})
    # Explicit validation selection; test untouched above.
    proposal=min(policies,key=lambda p:(bath_score(val,p)["mean_trace_distance"],
                                        bath_score(train,p)["mean_trace_distance"],str(p)))
    if bath_score(val,proposal)["mean_trace_distance"] >= bath_score(val,baseline)["mean_trace_distance"]:
        proposal=baseline
    base_test=bath_score(test,baseline)
    cand_test=bath_score(test,proposal)
    # Guard: no auto-admission even if a heldout improvement happens.
    pairs=[{"task_id":"bath:"+str(i),"baseline_distance":r["cg"],
            "candidate_distance":r["cg"] if bath_decision(proposal,r)=="CG" else r["davies"],
            "decision":bath_decision(proposal,r)} for i,r in enumerate(test)]
    return {"task":"FINITE_BATH_CG_DAVIES_POLICY", "baseline_policy":baseline,
            "selected_policy":proposal,"selection":"grammar_search_validation_then_frozen_holdout",
            "generations":generations,"proposals_examined":len(policies),
            "train_physics_groups":[list(x) for x in sorted(train_g)],
            "validation_physics_groups":[list(x) for x in sorted(val_g)],
            "holdout_physics_groups":[list(x) for x in sorted(test_g)],
            "train_trace":trace,"holdout_baseline":base_test,"holdout_candidate":cand_test,
            "holdout_delta_error":cand_test["mean_trace_distance"]-base_test["mean_trace_distance"],
            "holdout_release_verdict":"REJECTED_REGRESSION" if cand_test["mean_trace_distance"] > base_test["mean_trace_distance"]+1e-14 else "REVIEW_REQUIRED",
            "paired_holdout":pairs,"independent_physics_groups":len(test_g),
            "lab_validation":"NOT_PERFORMED","candidate_promotion":"DENIED"}


def evolve(datasets: str | Path, *, generations: int=48) -> dict:
    p=Path(datasets)
    bench,h1=load_benchmark(p/BENCHMARK,PINNED[BENCHMARK])
    bath,h2=load_bath(p/BATH,PINNED[BATH])
    b=bench_search(bench,generations=generations)
    q=bath_search(bath,generations=generations)
    body={"schema":KIND,"issue":"Aegis-Omega/AEGIS-OMEGA#758",
          "dependent_evaluation_issue":"Aegis-Omega/AEGIS-OMEGA#757",
          "data_sources":[{"filename":BENCHMARK,"sha256":h1,"rows":640,"epistemic_scope":"RECORDED_SIMULATION_RESULTS"},
                          {"filename":BATH,"sha256":h2,"rows":240,"epistemic_scope":"FINITE_NUMERICAL_SIMULATION"}],
          "evolution":{"agent_policy":b,"quantum_policy":q},
          "reproducibility":"DETERMINISTIC_LOCAL_REPLAY",
          "historical_heldout_note":"Holdout refers to held-out rows in existing files, not future external acquisition",
          "training_data_leakage":"SEPARATE_SEED_AND_PHYSICS_GROUP_SPLITS",
          "issue758_delivery_gate":"EXPERIMENT_ONLY_NO_TRIAL_PROMOTION_WHILE_CLUSTER_N_BELOW_30",
          "commercial_roi":"UNMEASURED_NO_DOLLAR_CLAIM",
          "source_head_binding":"NOT_ATTESTED_IN_THIS_LOCAL_RUN",
          "external_benchmark":"NOT_PERFORMED", "independent_review":"NOT_PERFORMED",
          "scientific_proof":"NOT_CLAIMED", "skill_promotion":"DENIED",
          "production_admission":"DENIED", "authority_effect":"NONE","execution_effect":"LOCAL_READ_ONLY"}
    return {**body,"receipt_hash":digest(body)}


def main() -> None:
    ap=argparse.ArgumentParser(description="AEGIS #758 two-domain local AlphaEvolve candidate search")
    ap.add_argument("--datasets",type=Path,required=True)
    ap.add_argument("--generations",type=int,default=48)
    ap.add_argument("--output",type=Path)
    args=ap.parse_args()
    result=evolve(args.datasets,generations=args.generations)
    encoded=json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+"\n"
    if args.output:
        if args.output.is_symlink():raise ValueError("OUTPUT_SYMLINK_REJECTED")
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(encoded,encoding="utf-8")
    else:print(encoded)

if __name__=="__main__":main()