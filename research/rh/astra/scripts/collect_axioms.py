#!/usr/bin/env python3
import argparse,re,subprocess
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument("lean_file"); p.add_argument("--cwd",default="."); a=p.parse_args(); path=Path(a.lean_file)
if not path.exists(): raise SystemExit("DENY lean file missing")
theorems=re.findall(r"(?m)^(?:theorem|lemma)\s+([A-Za-z0-9_'.]+)",path.read_text())
if not theorems: raise SystemExit("DENY no theorem/lemma declarations found")
audit=Path(a.cwd)/"AEGIS_AxiomAudit.lean"; audit.write_text(f"import {path.stem}\n"+"\n".join(f"#print axioms {t}" for t in theorems)+"\n"); proc=subprocess.run(["lake","env","lean",str(audit)],cwd=a.cwd,text=True,capture_output=True); print(proc.stdout); print(proc.stderr,end="")
if proc.returncode or "sorryAx" in proc.stdout+proc.stderr: raise SystemExit(1)
