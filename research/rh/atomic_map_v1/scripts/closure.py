import sys,hashlib
from pathlib import Path
target=sys.argv[1]; roots=[Path(p) for p in sys.argv[2:]]
groups=[{p.stem:p for p in r.glob("*.lean")} for r in roots]
allm=set().union(*map(set,groups))
def chosen(n):
    for g in reversed(groups):
        if n in g: return g[n]
    raise SystemExit(f"SOURCE_MISSING:{n}")
done=set();order=[]
def visit(n):
    if n in done: return
    done.add(n)
    in_block=False
    for ln in chosen(n).read_text(encoding='utf-8').splitlines():
        # Lean imports live in the header only: stop at the first line that is
        # neither blank, a comment, nor an import (so docstring samples are ignored).
        t=ln.strip()
        if in_block:
            if "-/" in t: in_block=False
            continue
        if t.startswith("/-"):
            in_block = "-/" not in t[2:]
            continue
        t=t.split("--",1)[0].strip()
        if not t: continue
        if not t.startswith("import "): break
        for d in t[7:].split():
            if d in allm: visit(d)
            elif d.split(".")[0] not in {"Mathlib","Lean","Std","Aesop","Batteries","Qq"}:
                raise SystemExit(f"UNRESOLVED_IMPORT:{n}:{d}")
    order.append(n)
visit(target)
for n in order: print(n, chosen(n), hashlib.sha256(chosen(n).read_bytes()).hexdigest(), sep="\t")
