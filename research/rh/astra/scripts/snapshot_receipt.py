#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
CORE_FILES=("TOOLCHAIN.lock","PROOF_OBLIGATIONS.yaml","ASSUMPTION_CENSUS.yaml","NORMALIZATION_FREEZE.md","ASTRA_MASTER_PROMPT.md")
def sha256(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical_json_bytes(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
def build_receipt(root):
    root=Path(root); body={"schema":"AEGIS_RH_ASTRA_ENV_RECEIPT_V1","files":{f:sha256(root/f) for f in CORE_FILES},"rh_status":"NOT_PROVEN","claim_promotion":"BLOCKED","execution_release":"BLOCKED","authority_effect":"NONE","frontier_sha":"c85a58ca753e5d99fc9f117e0dc481e1f2cf0bde"}; out=dict(body); out["receipt_sha256"]=hashlib.sha256(canonical_json_bytes(body)).hexdigest(); return out
def main():
    p=argparse.ArgumentParser(); p.add_argument("--root",default=str(Path(__file__).resolve().parents[1])); p.add_argument("--output"); a=p.parse_args(); r=build_receipt(Path(a.root)); t=json.dumps(r,sort_keys=True,indent=2,ensure_ascii=False)+"\n"; Path(a.output).write_text(t,encoding="utf-8") if a.output else None; print(t,end=""); return 0
if __name__=="__main__": raise SystemExit(main())
