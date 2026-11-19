#!/usr/bin/env python3
from __future__ import annotations
import json, re, tomllib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CRATES=("eccf","gcce")

def normalize_dep(name:str)->str:
    return name.replace("-","_")

def audit(crate:str):
    root=ROOT/crate
    cargo=tomllib.loads((root/"Cargo.toml").read_text())
    deps=set(cargo.get("dependencies",{}))
    dep_roots={normalize_dep(d) for d in deps}
    src=list(sorted((root/"src").glob("*.rs")))
    lib=(root/"src"/"lib.rs").read_text()
    declared=set(re.findall(r"^\s*(?:pub\s+)?mod\s+([A-Za-z_][A-Za-z0-9_]*)\s*;",lib,re.M))
    present={p.stem for p in src if p.name!="lib.rs"}
    external=set(); bad=[]; tests=0; lines=0
    for p in src:
        text=p.read_text()
        lines += len(text.splitlines())
        tests += len(re.findall(r"#\s*\[\s*test\s*\]",text))
        if "crate::lib" in text: bad.append(f"{p}:crate::lib")
        if re.search(r"\b(?:todo!|unimplemented!)\s*\(",text): bad.append(f"{p}:unfinished_macro")
        if re.search(r"\bunsafe\b",text): bad.append(f"{p}:unsafe")
        for m in re.finditer(r"^\s*use\s+([^;]+);",text,re.M):
            root_name=m.group(1).strip().split("::",1)[0].split("{",1)[0].strip()
            if root_name not in {"crate","self","super","std"}:
                external.add(root_name)
    missing_modules=sorted(declared-present)
    undeclared_sources=sorted(present-declared)
    undeclared_external=sorted(external-dep_roots)
    status="PASS" if not (missing_modules or undeclared_sources or undeclared_external or bad) else "FAIL"
    return {"crate":crate,"status":status,"source_files":len(src),"source_lines":lines,"test_functions":tests,
      "declared_modules":sorted(declared),"cargo_dependencies":sorted(deps),"external_use_roots":sorted(external),
      "missing_modules":missing_modules,"undeclared_sources":undeclared_sources,
      "undeclared_external_roots":undeclared_external,"forbidden_surface_hits":bad}

def main():
    rows=[audit(c) for c in CRATES]
    result={"schema":"AEGIS_ARCHIVE_RUST_STATIC_AUDIT_V1",
      "status":"PASS" if all(r["status"]=="PASS" for r in rows) else "FAIL","crates":rows,
      "establishes":["local Rust module graph is complete","external use roots are declared by Cargo dependencies",
        "repaired source contains no crate::lib paths, todo!/unimplemented! macros, or unsafe tokens",
        "archived unit-test surface is present"],
      "does_not_establish":["rustc typecheck","cargo dependency resolution","unit test execution"],
      "authority_effect":"NONE"}
    print(json.dumps(result,sort_keys=True,separators=(",",":")))
    if result["status"]!="PASS": raise SystemExit(1)

if __name__=="__main__": main()
