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
    for ln in chosen(n).read_text(encoding='utf-8').splitlines():
        ln=ln.split("--",1)[0].strip()
        if ln.startswith("import "):
            for d in ln[7:].split():
                if d in allm: visit(d)
                elif d.split(".")[0] not in {"Mathlib","Lean","Std","Aesop","Batteries","Qq"}: print("UNRESOLVED",n,d,file=sys.stderr)
    order.append(n)
visit(target)
for n in order: print(n, chosen(n), hashlib.sha256(chosen(n).read_bytes()).hexdigest(), sep="\t")
