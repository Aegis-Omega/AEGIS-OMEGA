#!/usr/bin/env python3
from __future__ import annotations
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
report=json.loads((ROOT/"reports/archive-restoration-integration-v1.json").read_text())

def git_object(path:str)->str:
    return subprocess.run(
        ["git","rev-parse",f"HEAD:{path}"],
        cwd=ROOT,check=True,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE
    ).stdout.strip()

failures=[]
for binding in report["exact_object_bindings"]:
    observed=git_object(binding["path"])
    if observed != binding["object_sha"]:
        failures.append({
            "path":binding["path"],
            "expected":binding["object_sha"],
            "observed":observed,
        })

if report.get("authority_effect")!="NONE":
    failures.append({"authority_effect":report.get("authority_effect")})
if report.get("deployment")!="NOT_PERFORMED":
    failures.append({"deployment":report.get("deployment")})
if report.get("merge")!="NOT_PERFORMED":
    failures.append({"merge":report.get("merge")})

if failures:
    raise SystemExit(json.dumps({"status":"FAIL","failures":failures},sort_keys=True))
print(json.dumps({
    "schema":"AEGIS_ARCHIVE_RESTORATION_INTEGRATION_VERIFY_V1",
    "status":"PASS",
    "bindings_verified":len(report["exact_object_bindings"]),
    "authority_effect":"NONE",
},sort_keys=True))
