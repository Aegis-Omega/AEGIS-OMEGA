"""Read-only corpus-native autonomous *candidate discovery*, for existing AEGIS #758.

No operator-selected files or target column: introspects corpus.sqlite, discovers
schema cohorts, chooses the highest-support executable scientific hypothesis,
then runs a bounded evolutionary search against distinct source-group splits.
Generates observational evidence ONLY. This is not DeepMind's hosted AlphaEvolve,
not a general AI scientific oracle, and never promotes or grants authority.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import random
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

KIND = "AEGIS_AUTONOMOUS_CORPUS_DISCOVERY_V1"
MAX_CSV = 256
MAX_BYTES = 6_000_000
MAX_COLUMNS = 64
MAX_RECORDS_PER_FILE = 4000
MAX_GENERATIONS = 160
TARGET_HORIZON = 8  # preregistered before held-out evaluation
GROUP_RE = re.compile(r"(?:^|[_/\\-])gamma[_=-]?([0-9]+(?:\.[0-9]+)?)", re.I)
SAFE_HEX = re.compile(r"[0-9a-f]{64}\Z")


def canon(x: Any) -> bytes:
    return json.dumps(x, sort_keys=True, separators=(",", ":"), allow_nan=False,
                      ensure_ascii=True).encode("ascii")


def dig(x: Any) -> str:
    return hashlib.sha256(canon(x)).hexdigest()


def safe_path(root: Path, candidate: str) -> Path:
    """No escaping catalog root or symlink traversal."""
    if not isinstance(candidate, str) or candidate.startswith(("/", "\\")) or "\x00" in candidate:
        raise ValueError("CATALOG_PATH_INVALID")
    path = root / candidate
    # Reject symlinks in every component (also catches symlink to outside root).
    current = root
    for part in Path(candidate).parts:
        if part in ("..", "", "."):
            raise ValueError("CATALOG_PATH_TRAVERSAL")
        current = current / part
        if current.is_symlink():
            raise ValueError("CATALOG_SYMLINK_REJECTED")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("CATALOG_PATH_ESCAPE")
    return path


def inspect_index(catalog: Path, root: Path, *, max_csv: int = MAX_CSV) -> dict:
    """Inventory every indexed category, inspect deduplicated real CSV bytes.

    Files whose metadata is catalogued but whose bytes cannot be safely read
    remain NOT_EVALUATED; they are not silently erased.
    """
    if type(max_csv) is not int or not 1 <= max_csv <= MAX_CSV:
        raise ValueError("INVALID_SCAN_BUDGET")
    if not catalog.is_file() or catalog.is_symlink():
        raise ValueError("CATALOG_UNAVAILABLE")
    if not root.is_dir() or root.is_symlink():
        raise ValueError("CORPUS_ROOT_INVALID")
    conn = sqlite3.connect(f"file:{catalog.resolve()}?mode=ro", uri=True)
    try:
        categories = dict(conn.execute("SELECT category,COUNT(*) FROM objects GROUP BY category").fetchall())
        indexed = int(conn.execute("SELECT COUNT(*) FROM objects").fetchone()[0])
        unique = int(conn.execute("SELECT COUNT(DISTINCT sha256) FROM objects").fetchone()[0])
        rows = conn.execute("""SELECT member,extracted_path,sha256,bytes,category FROM objects
            WHERE format='.csv' AND status='IMPORTED_BYTES_VERIFIED'
            AND extracted_path IS NOT NULL GROUP BY sha256 ORDER BY sha256 LIMIT ?""", (max_csv+1,)).fetchall()
    finally:
        conn.close()
    if len(rows) > max_csv:
        raise ValueError("CSV_SCAN_INCOMPLETE_BUDGET")
    groups: dict[tuple[str, ...], list[dict]] = defaultdict(list)
    skip = Counter()
    for member, rel, sha, declared_bytes, category in rows:
        if not isinstance(sha, str) or not SAFE_HEX.fullmatch(sha):
            skip["INVALID_SOURCE_DIGEST"] += 1; continue
        if type(declared_bytes) is not int or not 0 < declared_bytes <= MAX_BYTES:
            skip["SIZE_OUT_OF_BOUNDS"] += 1; continue
        try:
            file = safe_path(root, rel)
            if not file.is_file():
                skip["SOURCE_BYTES_MISSING"] += 1; continue
            raw = file.read_bytes()
            if len(raw) != declared_bytes or hashlib.sha256(raw).hexdigest() != sha:
                raise ValueError("SOURCE_BYTES_HASH_MISMATCH")
            with io.StringIO(raw.decode("utf-8-sig")) as stream:
                reader = csv.reader(stream, strict=True)
                names = next(reader)
                if not names or len(names) > MAX_COLUMNS or len(set(names)) != len(names):
                    skip["INVALID_HEADER"] += 1; continue
                parsed = []
                for i, row in enumerate(reader):
                    if i >= MAX_RECORDS_PER_FILE:
                        parsed=[];skip["ROW_BUDGET_EXCEEDED"]+=1;break
                    if len(row) != len(names):
                        parsed=[];skip["INVALID_ROW_WIDTH"]+=1;break
                    parsed.append(row)
                if len(parsed) < 40:
                    skip["TOO_FEW_ROWS"] += 1;continue
        except (UnicodeError, csv.Error, OSError, ValueError, StopIteration) as exc:
            if str(exc)=="SOURCE_BYTES_HASH_MISMATCH":raise
            skip["UNREADABLE_OR_UNSAFE_CSV"]+=1;continue
        groups[tuple(names)].append({"member":member,"source_sha256":sha,
                                     "path":str(file),"declared_bytes":declared_bytes,
                                     "rows":parsed,"category":category})
    families = []
    for names, items in groups.items():
        observed = _detect_simplex(names, items)
        families.append({"schema_sha256":dig(names),"schema_columns":len(names),"names":names,
                         "file_count":len(items),"candidate_kind": observed or "EVALUATOR_MISSING",
                         "sources":items})
    families.sort(key=lambda f: (f["candidate_kind"]!="SIMPLEX_DYNAMICS_FORECAST", -f["file_count"], f["schema_sha256"]))
    return {"indexed_records":indexed,"unique_byte_contents":unique,
            "category_counts":categories,"csv_unique_considered":len(rows),
            "csv_skip_reasons":dict(sorted(skip.items())),"families":families}


def _detect_simplex(names: tuple[str, ...], items: list[dict]) -> str | None:
    """Discover simplex-structured data from *numbers*, not file names."""
    if len(items) < 12 or len(names) < 4:
        return None
    # Infer contiguous probability-like columns from measured values, not P_0 names.
    try:
        for item in items[:3]:
            arr = np.asarray(item["rows"][:35], dtype=str)
            candidates = []
            for j, name in enumerate(names):
                if name.startswith("classical_"): continue
                try:
                    vec = np.asarray([float(s) for s in arr[:, j]],dtype=float)
                except (ValueError, TypeError):continue
                if np.isfinite(vec).all() and np.all((vec >= -1e-10)&(vec <= 1+1e-10)):
                    candidates.append(j)
            if len(candidates) < 2: return None
            # Automatically test all contiguous groups of length 2..8 for simplex conservation.
            found=False
            for start in candidates:
                for end in range(start+2, min(len(names),start+8)+1):
                    indices=list(range(start,end))
                    if not set(indices).issubset(candidates):continue
                    sub=np.asarray([[float(row[k]) for k in indices] for row in item["rows"][:35]])
                    if np.max(np.abs(np.sum(sub,axis=1)-1))<1e-7:
                        found=True;break
                if found:break
            if not found or not _has_time_axis(names,item):return None
        return "SIMPLEX_DYNAMICS_FORECAST"
    except (ValueError, TypeError, OverflowError):return None


def _has_time_axis(names: tuple[str, ...], item: dict) -> bool:
    """Ensure forecasting actually has a monotone, almost-uniform time coordinate."""
    rows = item["rows"]
    for j,name in enumerate(names):
        if not ("time" in name.lower() or name.lower() in ("t","step","iteration")):
            continue
        try:
            t = np.asarray([float(row[j]) for row in rows],dtype=float)
        except (ValueError,TypeError):continue
        if not np.isfinite(t).all():continue
        d=np.diff(t)
        if len(d) and np.all(d>0) and np.max(abs(d-np.median(d))) <= max(1e-10,abs(np.median(d))*1e-6):
            return True
    return False


def _extract_simplex(names: tuple[str, ...], item: dict) -> np.ndarray:
    # Enumerate valid groups using the real file values; longest group wins.
    if not _has_time_axis(names,item):raise ValueError("TIME_AXIS_INVALID")
    matrix = []
    for j,name in enumerate(names):
        if name.startswith("classical_"):
            matrix.append(None);continue
        try:
            col = np.asarray([float(row[j]) for row in item["rows"]], dtype=float)
        except (ValueError, TypeError):col=None
        if col is not None and (not np.isfinite(col).all() or np.min(col)<-1e-8 or np.max(col)>1+1e-8): col=None
        matrix.append(col)
    best = None
    for start in range(len(names)):
        if matrix[start] is None:continue
        for end in range(start+2,min(start+9,len(names)+1)):
            cols=matrix[start:end]
            if len(cols)<2 or any(c is None for c in cols):break
            probs=np.column_stack(cols)
            if np.max(np.abs(probs.sum(axis=1)-1)) < 1e-6:
                if best is None or probs.shape[1]>best.shape[1]:best=probs
    if best is None or best.shape[1]<2:raise ValueError("SIMPLEX_INVARIANT_NOT_FOUND")
    return best


def _physical_project(x: np.ndarray) -> np.ndarray:
    """Deterministic bounded probability projection; no learned truth claims."""
    v=np.maximum(x,0.0)
    total=np.sum(v,axis=1,keepdims=True)
    # zero vectors replaced by uniform distribution, tracked as legal projection.
    return np.divide(v,total,out=np.full_like(v,1.0/v.shape[1]),where=total>1e-15)


def _series_loss(x: np.ndarray, a: float, b: float, *, horizon: int = TARGET_HORIZON) -> float:
    """Forecast horizon-ahead probabilities using only available past snapshots."""
    if len(x)<horizon+20: raise ValueError("SERIES_TOO_SHORT")
    t=x[2:-horizon]
    d=t-x[1:-horizon-1]
    d2=t-2*x[1:-horizon-1]+x[:-horizon-2]
    y=x[2+horizon:]
    if len(t)!=len(y):raise ValueError("SERIES_INDEX_MISMATCH")
    pred=_physical_project(t+a*d+b*d2)
    return float(np.mean((pred-y)**2))


def _group_tag(name: str, sha: str) -> str:
    m=GROUP_RE.search(name)
    return f"gamma={float(m.group(1)):.9g}" if m else "source="+sha[:16]


def _split(groups: list[str]) -> dict[str,list[str]]:
    if len(groups)<6:raise ValueError("INDEPENDENT_GROUPS_INSUFFICIENT")
    # Predefined deterministic cohort split by source label, no outcome inspection.
    ordered=sorted(groups,key=lambda s:hashlib.sha256(("AEGIS-758-v1:"+s).encode()).hexdigest())
    n=len(ordered)
    nv=max(2,n//5); nh=max(2,n//5)
    return {"train":ordered[:n-nv-nh],"validation":ordered[n-nv-nh:n-nh],"holdout":ordered[-nh:]}


def _loss_for_group(items:list[tuple[str,np.ndarray]], a:float,b:float)->float:
    per=[_series_loss(arr,a,b) for _,arr in items]
    return float(np.mean(per))


def _fitness(data:dict[str,list[tuple[str,np.ndarray]]], labels:list[str],a:float,b:float)->float:
    # Compare group-level geometric ratios to persistence, stabilizing scale.
    scores=[]
    for label in labels:
        observed=_loss_for_group(data[label],a,b)
        baseline=_loss_for_group(data[label],0,0)
        scores.append(observed/max(baseline,1e-20))
    return float(np.mean(scores))


def evolve_family(family: dict, *, generations:int=64, seed:int=758) -> dict:
    if type(generations) is not int or not 1<=generations<=MAX_GENERATIONS:
        raise ValueError("EVOLUTION_BUDGET_INVALID")
    names=tuple(family.get("names",[]))
    # Unlike the catalog, family receipt carries the schema so evaluator is source-bound.
    if not names:raise ValueError("FAMILY_SCHEMA_MISSING")
    data=defaultdict(list)
    for item in family["sources"]:
        arr=_extract_simplex(names,item)
        if arr.shape[1]<2:raise ValueError("SIMPLEX_SHAPE_INVALID")
        data[_group_tag(item["member"],item["source_sha256"])].append((item["source_sha256"],arr))
    partitions=_split(list(data))
    candidates={(0.0,0.0), (1.0,0.0), (4.0,0.0), (float(TARGET_HORIZON),0.0),
                (float(TARGET_HORIZON),float(TARGET_HORIZON*(TARGET_HORIZON+1)/2))}
    rng=random.Random(seed)
    trace=[]; best=(0.0,0.0)
    best_validation=1.0; observed=set()
    for iteration in range(generations):
        if iteration<len(candidates):
            proposal=sorted(candidates)[iteration]
        else:
            parent = best if rng.random()<0.70 else rng.choice(sorted(candidates))
            step=rng.choice((0.25,0.5,1.0,2.0,4.0))
            proposal=(round(max(-8,min(16,parent[0]+rng.choice((-1,0,1))*step)),4),
                      round(max(-40,min(80,parent[1]+rng.choice((-1,0,1))*step*3)),4))
        if proposal in observed: continue
        observed.add(proposal)
        train_loss=_fitness(data,partitions["train"],*proposal)
        val_loss=_fitness(data,partitions["validation"],*proposal)
        if not (math.isfinite(train_loss) and math.isfinite(val_loss)):continue
        # Validation best with tiny model-complexity penalty, not train-only reward.
        selection = val_loss+0.00001*(abs(proposal[0])+abs(proposal[1]))
        if selection < best_validation-1e-12:
            best,best_validation=proposal,selection
        trace.append({"generation":iteration,"candidate":list(proposal),
                      "train_relative_mse":train_loss,"validation_relative_mse":val_loss,
                      "selected":proposal==best})
        candidates.add(proposal)
    # Evaluate the frozen champion on entirely unseen group tags ONCE.
    holdout=[]
    for label in partitions["holdout"]:
        base=_loss_for_group(data[label],0,0)
        new=_loss_for_group(data[label],*best)
        holdout.append({"group":label,"series_count":len(data[label]),
                        "baseline_mse":base,"candidate_mse":new,
                        "relative_mse":new/max(base,1e-20),
                        "regression":new>base+1e-16})
    improve=sum(x["candidate_mse"]<x["baseline_mse"] for x in holdout)
    veto=any(x["regression"] for x in holdout)
    body={"schema":"AEGIS_DISCOVERED_SIMPLEX_HYPOTHESIS_V1",
          "hypothesis":"Bounded finite-difference dynamics improve horizon-ahead simplex forecasts over persistence",
          "horizon_steps":TARGET_HORIZON,"family_schema_sha256":family["schema_sha256"],
          "source_file_count":len(family["sources"]),"source_sha256":sorted(x["source_sha256"] for x in family["sources"]),
          "source_group_partition":partitions,
          "generator":"FINITE_DIFFERENCE_ALPHA_BETA_MUTATION_V1",
          "baseline":{"alpha":0.0,"beta":0.0},
          "champion":{"alpha":best[0],"beta":best[1]},
          "population_evaluated":len(observed),"generations_requested":generations,
          "training_relative_mse":_fitness(data,partitions["train"],*best),
          "validation_relative_mse":_fitness(data,partitions["validation"],*best),
          "holdout":holdout,"holdout_group_improvements":improve,
          "holdout_group_count":len(holdout),
          "safety_or_error_regression_veto":veto,
          "full_physics_model_validation":"NOT_EVALUATED",
          "inference_only_not_scientific_discovery":True,
          "independent_group_threshold_for_issue758_met":len(holdout)>=30,
          "external_reproduction":"NOT_PERFORMED", "admission":"DENIED",
          "agent_promotion":"DENIED","authority_effect":"NONE", "execution_effect":"LOCAL_READ_ONLY",
          "trace":trace}
    return {**body,"receipt_hash":dig(body)}


def run(*, catalog:Path, root:Path, generations:int=64, seed:int=758)->dict:
    if type(seed) is not int or type(generations) is not int:raise ValueError("INVALID_SEED_OR_BUDGET")
    if not 1<=generations<=MAX_GENERATIONS:raise ValueError("EVOLUTION_BUDGET_INVALID")
    inventory=inspect_index(catalog,root)
    f=inventory.pop("families")
    discovered=[{k:v for k,v in d.items() if k not in ("sources","names")} for d in f]
    selectable=[d for d in f if d["candidate_kind"]=="SIMPLEX_DYNAMICS_FORECAST"]
    experiments=[]
    for family in selectable[:2]:
        if family["file_count"]<12:continue
        try:
            experiments.append(evolve_family(family,generations=generations,seed=seed))
        except (ValueError,ArithmeticError) as e:
            experiments.append({"family":family["schema_sha256"],"status":"NOT_EVALUATED",
                                "reason":type(e).__name__+":"+str(e)[:90]})
    body={"schema":KIND,"corpus_db_sha256":hashlib.sha256(catalog.read_bytes()).hexdigest(),
          "corpus_index_records":inventory["indexed_records"],
          "unique_byte_contents":inventory["unique_byte_contents"],
          "category_counts":inventory["category_counts"],
          "csv_unique_considered":inventory["csv_unique_considered"],
          "csv_skip_reasons":inventory["csv_skip_reasons"],
          "detected_csv_families":discovered,
          "auto_selected_families":[x["schema_sha256"] for x in selectable[:2]],
          "experiments":experiments,
          "unevaluated_domains":"ALL_OTHER_CATEGORIES_REQUIRE_DOMAIN_EVALUATORS",
          "novel_physical_discovery":False,"independent_review":"NOT_PERFORMED",
          "production_admission":"DENIED","skill_promotion":"DENIED","authority_effect":"NONE"}
    return {**body,"receipt_hash":dig(body)}


def main()->None:
    p=argparse.ArgumentParser(description="Run source-discovered AlphaEvolve-style research, no hand-picked datasets")
    p.add_argument("--corpus-sqlite",type=Path,required=True)
    p.add_argument("--corpus-root",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--generations",type=int,default=64)
    ns=p.parse_args()
    if ns.output.exists():p.error("OUTPUT_ALREADY_EXISTS")
    result=run(catalog=ns.corpus_sqlite,root=ns.corpus_root,generations=ns.generations)
    ns.output.write_bytes(canon(result))
    print(json.dumps({"receipt":str(ns.output),"experiments":len(result["experiments"]),
                      "indexed_records":result["corpus_index_records"],
                      "receipt_hash":result["receipt_hash"]}))

if __name__=="__main__":main()
