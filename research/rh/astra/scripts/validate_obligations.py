#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any
import yaml
from jsonschema import Draft202012Validator
VERIFIED={"PROVED_MACHINE_CHECKED","HOSTED_EXACT_HEAD_COMPILE_VERIFIED"}
class ValidationError(RuntimeError): pass
def load_registry(path:Path)->dict[str,Any]:
    data=yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data,dict): raise ValidationError("registry root must be object")
    return data
def _cycle(nodes):
    state={}; stack=[]
    def visit(n):
        state[n]=1; stack.append(n)
        for d in nodes[n].get("dependencies",[]):
            if d not in nodes: continue
            if state.get(d)==1: return stack[stack.index(d):]+[d]
            if state.get(d,0)==0:
                out=visit(d)
                if out: return out
        stack.pop(); state[n]=2
    for n in nodes:
        if state.get(n,0)==0:
            out=visit(n)
            if out: return out
    return None
def _ancestors(root,nodes):
    seen=set(); todo=list(nodes[root].get("dependencies",[]))
    while todo:
        n=todo.pop()
        if n in seen or n not in nodes: continue
        seen.add(n); todo.extend(nodes[n].get("dependencies",[]))
    return seen
def validate_registry(data,schema_path:Path):
    errors=[]; schema=json.loads(Path(schema_path).read_text(encoding="utf-8"))
    for e in Draft202012Validator(schema).iter_errors(data):
        loc="/".join(str(x) for x in e.absolute_path); errors.append(f"schema:{loc}:{e.message}")
    if data.get("authority_effect")!="NONE": errors.append("authority_effect must remain NONE")
    if data.get("execution_release")!="BLOCKED": errors.append("execution_release must remain BLOCKED")
    ids=[n.get("id") for n in data.get("nodes",[]) if isinstance(n,dict)]
    if len(ids)!=len(set(ids)): errors.append("duplicate node id")
    nodes={n.get("id"):n for n in data.get("nodes",[]) if isinstance(n,dict) and isinstance(n.get("id"),str)}
    for nid,n in nodes.items():
        for dep in n.get("dependencies",[]):
            if dep not in nodes: errors.append(f"unknown dependency {dep} referenced by {nid}")
        for dep in n.get("application_requires",[]):
            if dep not in nodes: errors.append(f"unknown application requirement {dep} referenced by {nid}")
        if n.get("status") in VERIFIED:
            b=n.get("proof_binding")
            if not isinstance(b,dict): errors.append(f"{nid}: verified status requires proof_binding")
            else:
                for k in ("path","theorem","exact_head"):
                    if not b.get(k): errors.append(f"{nid}: verified status requires {k}")
                if not (b.get("run_id") or b.get("receipt_sha256")): errors.append(f"{nid}: verified status requires run_id or receipt_sha256")
            for ext in n.get("external_dependencies",[]):
                if not isinstance(ext,dict) or not ext.get("repository") or not ext.get("sha"): errors.append(f"{nid}: external formal dependency must be repository+sha pinned")
    cyc=_cycle(nodes)
    if cyc: errors.append("dependency cycle: "+" -> ".join(cyc))
    if data.get("normalization",{}).get("status")=="FROZEN":
        vals=data.get("normalization",{}).get("required_fields",{})
        if any("UNFROZEN" in str(v) or "OPEN" in str(v) for v in vals.values()): errors.append("normalization marked FROZEN while required fields remain unresolved")
    if data.get("rh_status")=="PROVEN":
        rh=nodes.get("RH")
        if not rh or rh.get("status")!="PROVED_MACHINE_CHECKED": errors.append("RH promotion forbidden: RH node is not PROVED_MACHINE_CHECKED")
        else:
            bad=[a for a in _ancestors("RH",nodes) if nodes[a].get("status")!="PROVED_MACHINE_CHECKED"]
            if bad: errors.append("RH promotion forbidden: non-machine-checked ancestors: "+",".join(sorted(bad)))
        if data.get("claim_promotion")!="ALLOWED": errors.append("RH promotion forbidden: claim_promotion is not ALLOWED")
    return sorted(set(errors))
def main():
    p=argparse.ArgumentParser(); p.add_argument("--root",default=str(Path(__file__).resolve().parents[1])); a=p.parse_args(); root=Path(a.root)
    data=load_registry(root/"PROOF_OBLIGATIONS.yaml"); errors=validate_registry(data,root/"schemas/proof-obligations.schema.json")
    if errors:
        for e in errors: print("DENY:",e)
        return 1
    print("PASS AEGIS_RH_PROOF_OBLIGATION_DAG_V1"); print(f"RH_STATUS={data['rh_status']} AUTHORITY_EFFECT={data['authority_effect']} EXECUTION_RELEASE={data['execution_release']}"); return 0
if __name__=="__main__": raise SystemExit(main())
