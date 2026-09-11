#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,subprocess
from pathlib import Path
import yaml
def expected_frontier(root:Path)->dict: return yaml.safe_load((Path(root)/"TOOLCHAIN.lock").read_text(encoding="utf-8"))["frontier"]
def forbidden_manual_paths(): return (".claude.json",)
def git(*args,cwd): return subprocess.check_output(["git",*args],cwd=cwd,text=True,stderr=subprocess.STDOUT).strip()
def audit(root,repo):
    exp=expected_frontier(root); report={"expected_frontier":exp,"repository_detected":False,"authority_effect":"NONE","rh_status":"NOT_PROVEN"}
    if not (repo/".git").exists(): return report
    report["repository_detected"]=True; report["head"]=git("rev-parse","HEAD",cwd=repo)
    dirty=git("status","--porcelain",cwd=repo).splitlines(); report["dirty_paths"]=[x[3:] for x in dirty if len(x)>=4]
    report["forbidden_manual_path_dirty"]=[p for p in forbidden_manual_paths() if any(x==p or x.endswith("/"+p) for x in report["dirty_paths"])]
    try: subprocess.check_call(["git","merge-base","--is-ancestor",exp["sha"],"HEAD"],cwd=repo,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); report["frontier_is_ancestor"]=True
    except subprocess.CalledProcessError: report["frontier_is_ancestor"]=False
    return report
def main():
    p=argparse.ArgumentParser(); p.add_argument("--root",default=str(Path(__file__).resolve().parents[1])); p.add_argument("--repo",default="."); a=p.parse_args(); r=audit(Path(a.root),Path(a.repo).resolve()); print(json.dumps(r,sort_keys=True,indent=2)); return 1 if r.get("repository_detected") and (not r.get("frontier_is_ancestor") or r.get("forbidden_manual_path_dirty")) else 0
if __name__=="__main__": raise SystemExit(main())
