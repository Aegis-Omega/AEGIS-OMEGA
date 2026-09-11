#!/usr/bin/env python3
import copy
from pathlib import Path
from scripts.validate_obligations import load_registry,validate_registry
root=Path(__file__).resolve().parents[1]; schema=root/"schemas/proof-obligations.schema.json"; base=load_registry(root/"PROOF_OBLIGATIONS.yaml")
mut=[]
def add(n,f): mut.append((n,f))
add("authority_leak",lambda d:d.__setitem__("authority_effect","ELEVATED")); add("false_rh_promotion",lambda d:d.__setitem__("rh_status","PROVEN"))
def unknown(d): d["nodes"][-1]["dependencies"]=["UNKNOWN_NODE"]
def missing(d): next(x for x in d["nodes"] if x["status"]=="PROVED_MACHINE_CHECKED")["proof_binding"]=None
def cycle(d): {x["id"]:x for x in d["nodes"]}["CRITICAL_STRIP_LOCALIZATION"]["dependencies"]=["RH"]
add("unknown_dependency",unknown); add("missing_binding",missing); add("cycle",cycle); failed=[]
for name,fn in mut:
    d=copy.deepcopy(base); fn(d); errs=validate_registry(d,schema); print(("EXPECTED_DENY" if errs else "UNEXPECTED_PASS"),name,(errs[0] if errs else "")); failed += ([] if errs else [name])
if failed: raise SystemExit("FALSIFIER FAILURE "+str(failed))
print(f"PASS {len(mut)}/{len(mut)} fail-closed falsifiers")
