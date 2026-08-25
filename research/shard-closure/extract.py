"""Extract module dependency graphs from the AEGIS monorepo.

Four independent graphs, four languages, no synthetic data.
Node = source file. Edge u->v = u depends on v (u imports v).
"""
import os, re, json, sys
from pathlib import Path

ROOT = Path("/home/user/AEGIS-OMEGA")

def ts_graph(src_root):
    src_root = ROOT / src_root
    files = [p for p in src_root.rglob("*.ts") if not p.name.endswith(".test.ts")]
    idx = {p.resolve(): p.relative_to(ROOT).as_posix() for p in files}
    names = set(idx.values())
    edges = set()
    imp = re.compile(r"""(?:^|\n)\s*(?:import|export)[^;'"]*?from\s+['"]([^'"]+)['"]""")
    dyn = re.compile(r"""import\(\s*['"]([^'"]+)['"]\s*\)""")
    for p in files:
        txt = p.read_text(encoding="utf-8", errors="replace")
        u = idx[p.resolve()]
        for m in list(imp.findall(txt)) + list(dyn.findall(txt)):
            if not m.startswith("."):
                continue
            # repo convention: .js suffix on TS imports
            base = (p.parent / m).resolve()
            for cand in (base.with_suffix(".ts"), Path(str(base)[:-3] + ".ts") if str(base).endswith(".js") else base,
                         base / "index.ts"):
                try:
                    rel = cand.resolve().relative_to(ROOT).as_posix()
                except Exception:
                    continue
                if rel in names:
                    edges.add((u, rel)); break
    return sorted(names), sorted(edges)

def rust_graph(src_root):
    src_root = ROOT / src_root
    files = list(src_root.rglob("*.rs"))
    # map module path -> file
    modmap = {}
    for p in files:
        rel = p.relative_to(src_root)
        parts = list(rel.parts)
        if parts[-1] in ("mod.rs", "lib.rs", "main.rs"):
            parts = parts[:-1]
        else:
            parts[-1] = parts[-1][:-3]
        modmap["::".join(parts)] = p.relative_to(ROOT).as_posix()
    names = set(modmap.values())
    edges = set()
    use_re = re.compile(r"(?:^|\n)\s*(?:pub\s+)?use\s+crate::([A-Za-z0-9_:]+)")
    for p in files:
        txt = p.read_text(encoding="utf-8", errors="replace")
        u = p.relative_to(ROOT).as_posix()
        for path in use_re.findall(txt):
            segs = path.split("::")
            # longest prefix that names a module
            for k in range(len(segs), 0, -1):
                key = "::".join(segs[:k])
                if key in modmap and modmap[key] != u:
                    edges.add((u, modmap[key])); break
    return sorted(names), sorted(edges)

def py_graph(src_root):
    src_root = ROOT / src_root
    files = list(src_root.rglob("*.py"))
    stem = {p.stem: p.relative_to(ROOT).as_posix() for p in files}
    names = set(stem.values())
    edges = set()
    imp = re.compile(r"(?:^|\n)\s*(?:from\s+([A-Za-z0-9_.]+)\s+import|import\s+([A-Za-z0-9_.]+))")
    for p in files:
        txt = p.read_text(encoding="utf-8", errors="replace")
        u = p.relative_to(ROOT).as_posix()
        for a, b in imp.findall(txt):
            mod = (a or b).lstrip(".").split(".")[0]
            if mod in stem and stem[mod] != u:
                edges.add((u, stem[mod]))
    return sorted(names), sorted(edges)

GRAPHS = {
    "ts_sovereign":  lambda: ts_graph("sovereign-omega-v2/src"),
    "rust_cl_psi":   lambda: rust_graph("aegis-cl-psi/src"),
    "rust_runtime":  lambda: rust_graph("aegis-runtime/src"),
    "py_sovereign":  lambda: py_graph("sovereign-omega-v2/python"),
}

if __name__ == "__main__":
    out = {}
    for name, fn in GRAPHS.items():
        nodes, edges = fn()
        out[name] = {"nodes": nodes, "edges": [list(e) for e in edges]}
        print(f"{name:16s} n={len(nodes):4d}  m={len(edges):5d}  density={len(edges)/max(1,len(nodes)):.2f}")
    dest = Path(sys.argv[1] if len(sys.argv) > 1 else "graphs.json")
    dest.write_text(json.dumps(out, sort_keys=True, indent=0))
    print(f"\nwritten: {dest}")
