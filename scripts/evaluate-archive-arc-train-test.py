#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path
from typing import Any
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ARC = ROOT / "swarm_os" / "arc"
if str(ARC) not in sys.path:
    sys.path.insert(0, str(ARC))
from dsl.vm import DSLVM
from dsl.vocab import TOKENS

VM = DSLVM()
OPS = tuple(op for op in sorted(TOKENS) if op != 0)

def grid_key(grid: np.ndarray):
    arr=np.asarray(grid,dtype=np.int64)
    return tuple(arr.shape),arr.tobytes()

def state_key(grids):
    return tuple(grid_key(grid) for grid in grids)

def exhaustive_train_program(train_pairs,max_depth,max_states):
    inputs=[np.asarray(pair["input"],dtype=np.int64) for pair in train_pairs]
    outputs=[np.asarray(pair["output"],dtype=np.int64) for pair in train_pairs]
    target=state_key(outputs); initial=state_key(inputs)
    if initial==target:
        return [],0,1,False
    frontier=[(inputs,[])]; visited={initial}
    for depth in range(1,max_depth+1):
        nxt=[]
        for grids,program in frontier:
            for op in OPS:
                transformed=[VM.run([op],grid) for grid in grids]
                key=state_key(transformed)
                if key in visited:
                    continue
                visited.add(key)
                candidate=program+[op]
                if key==target:
                    return candidate,depth,len(visited),False
                nxt.append((transformed,candidate))
                if len(visited)>=max_states:
                    return None,depth,len(visited),True
        frontier=nxt
        if not frontier:
            break
    return None,max_depth,len(visited),False

def evaluate_task(path,max_depth,max_states):
    payload=json.loads(path.read_text())
    train=payload.get("train",[]); test=payload.get("test",[])
    if not train or not test or not all("output" in pair for pair in test):
        return {"task_id":path.stem,"status":"UNUSABLE_TASK_RECORD"}
    program,depth,states,truncated=exhaustive_train_program(train,max_depth,max_states)
    if program is None:
        return {"task_id":path.stem,"status":"NO_TRAIN_EXACT_PROGRAM_WITHIN_BOUND","states_explored":states,"search_truncated":truncated,"max_depth":max_depth}
    test_exact=[]
    for pair in test:
        prediction=VM.run(program,np.asarray(pair["input"],dtype=np.int64))
        target=np.asarray(pair["output"],dtype=np.int64)
        test_exact.append(bool(np.array_equal(prediction,target)))
    return {"task_id":path.stem,"status":"TRAIN_PROGRAM_FOUND","program":program,"program_names":[TOKENS[op] for op in program],"depth":depth,"states_explored":states,"search_truncated":truncated,"test_exact":all(test_exact),"test_pair_results":test_exact}

def canonical_sha256(value:Any)->str:
    raw=json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--data",default=str(ARC/"data"/"arc_data"))
    ap.add_argument("--limit",type=int,default=50)
    ap.add_argument("--max-depth",type=int,default=8)
    ap.add_argument("--max-states",type=int,default=50000)
    args=ap.parse_args()
    paths=sorted(Path(args.data).glob("*.json"))[:args.limit]
    results=[evaluate_task(path,args.max_depth,args.max_states) for path in paths]
    found=[r for r in results if r.get("status")=="TRAIN_PROGRAM_FOUND"]
    exact=[r for r in found if r.get("test_exact") is True]
    truncated=[r for r in results if r.get("search_truncated") is True]
    summary={
      "schema":"AEGIS_ARCHIVE_ARC_TRAIN_TEST_EXACT_V1","status":"PASS","task_count":len(results),
      "selection_uses_test_outputs":False,"dsl_vocab":{str(k):v for k,v in TOKENS.items()},
      "search":{"kind":"semantic_state_exhaustive_bfs","max_depth":args.max_depth,"max_states_per_task":args.max_states,"non_nop_ops":list(OPS),"truncated_task_count":len(truncated)},
      "train_exact_program_found_count":len(found),"test_exact_solve_count":len(exact),
      "test_exact_solve_rate":(len(exact)/len(results)) if results else 0.0,
      "found_task_ids":[r["task_id"] for r in found],"test_exact_task_ids":[r["task_id"] for r in exact],
      "results_digest":canonical_sha256(results),
      "interpretation":"BOUNDED_PRIMITIVE_DSL_TRAIN_TO_TEST_EXACT_REPLAY_NOT_GENERAL_ARC_CAPABILITY",
      "historical_evaluator_disposition":{"arc_held_out_eval_py":"NOT_ADMISSIBLE_AS_GENERALIZATION_PROOF","reasons":[
        "candidate selection scores against the same example output rather than locking on train and evaluating test",
        "TRANSFORMATION_PROGRAMS operation IDs are inconsistent with dsl/vocab.py"]},
      "authority_effect":"NONE"}
    summary["receipt_sha256"]=canonical_sha256(summary)
    print(json.dumps(summary,sort_keys=True,separators=(",",":")))

if __name__=="__main__":
    main()
