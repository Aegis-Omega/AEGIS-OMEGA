"""Command-line entrypoint — RFC 0001 §11 CI integration.

Subcommands:

* ``compile``  — emit projections + canonical schema to an output directory.
* ``validate`` — run the equivalence gate in memory; exit non-zero on drift.
* ``check``    — regenerate in memory and assert the on-disk artefacts are
  byte-identical (determinism, §9.2) *and* equivalent (§8). This is the
  command CI runs to fail builds on divergence.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .compiler import CompileResult, compile_sources
from .consensus import reach_consensus
from .evolution import (
    certificate,
    certificate_json,
    classify,
    composition_proof,
    diff,
    recommend_version_bump,
)
from .ir import IR, lower
from .parser import parse
from .versioned import render_rust, render_typescript

_ARTEFACTS = {
    "rust/types.rs": "rust",
    "typescript/types.ts": "typescript",
    "python/types.py": "python",
    "schema.json": "schema_json",
}


def _read_sources(paths: list[str]) -> list[str]:
    return [Path(p).read_text(encoding="utf-8") for p in paths]


def _written_files(result: CompileResult) -> dict[str, str]:
    return {rel: getattr(result, attr) for rel, attr in _ARTEFACTS.items()}


def _cmd_compile(args: argparse.Namespace) -> int:
    result = compile_sources(_read_sources(args.wit))
    out = Path(args.out)
    for rel, content in _written_files(result).items():
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    print(f"compiled {len(args.wit)} source(s) -> {out}")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    result = compile_sources(_read_sources(args.wit))
    report = result.equivalence()
    print(report.text())
    return 0 if report.ok else 1


def _cmd_check(args: argparse.Namespace) -> int:
    result = compile_sources(_read_sources(args.wit))
    report = result.equivalence()
    if not report.ok:
        print(report.text())
        return 1

    out = Path(args.out)
    drift: list[str] = []
    for rel, content in _written_files(result).items():
        dest = out / rel
        if not dest.exists():
            drift.append(f"missing generated artefact: {dest}")
        elif dest.read_text(encoding="utf-8") != content:
            drift.append(f"stale generated artefact: {dest} (run 'compile' to regenerate)")
    if drift:
        print("CHECK FAILED — generated artefacts diverge from source:")
        for d in drift:
            print(f"  - {d}")
        return 1
    print("CHECK OK — artefacts equivalent and up to date.")
    return 0


def _ir_from(paths: list[str]) -> IR:
    doc = parse("\n".join(_read_sources(paths)))
    return lower(doc)


def _cmd_evolve(args: argparse.Namespace) -> int:
    old = _ir_from(args.from_)
    new = _ir_from(args.to)
    cert = certificate(old, new)
    verdict = cert["compatibility"]["verdict"]
    bump = cert["compatibility"]["recommended_version_bump"]
    print(f"EVOLUTION {verdict} — recommended version bump: {bump}")
    for name, o in cert["proof_obligations"].items():
        mark = "ok" if o["holds"] else "VIOLATED"
        extra = "" if o["holds"] else f" by {', '.join(o['violated_by'])}"
        print(f"  obligation {name}: {mark}{extra}")
    if args.out:
        dest = Path(args.out)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(certificate_json(old, new), encoding="utf-8")
        print(f"certificate -> {args.out}")
    return 1 if verdict == "BREAKING" else 0


def _cmd_consensus(args: argparse.Namespace) -> int:
    proposed = _ir_from(args.proposed)
    agents = [(Path(p).stem, _ir_from([p])) for p in args.agents]
    result = reach_consensus(agents, proposed, threshold=args.threshold)
    print(result.text())
    return 0 if result.committed else 1


def _cmd_compose(args: argparse.Namespace) -> int:
    s1, s2, s3 = _ir_from([args.s1]), _ir_from([args.s2]), _ir_from([args.s3])
    proof = composition_proof(s1, s2, s3)
    print(f"COMPOSITION path={proof.path_verdict} direct={proof.direct_verdict}")
    print(f"  conservative (direct ⊒ path): {proof.conservative}")
    print(f"  equivalent (no cancellation): {proof.equivalent}")
    return 0 if proof.conservative else 1


def _cmd_evolve_codegen(args: argparse.Namespace) -> int:
    old = _ir_from(args.from_)
    new = _ir_from(args.to)
    out = Path(args.out)
    (out / "rust").mkdir(parents=True, exist_ok=True)
    (out / "typescript").mkdir(parents=True, exist_ok=True)
    rs = out / "rust" / f"{args.type.lower()}_versioned.rs"
    ts = out / "typescript" / f"{args.type.lower()}_versioned.ts"
    rs.write_text(render_rust(old, new, args.type), encoding="utf-8")
    ts.write_text(render_typescript(old, new, args.type), encoding="utf-8")
    print(f"versioned codegen for {args.type} -> {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="aegis-interface", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("compile", help="emit projections + schema to --out")
    c.add_argument("wit", nargs="+", help="WIT source file(s)")
    c.add_argument("--out", required=True, help="output directory")
    c.set_defaults(func=_cmd_compile)

    v = sub.add_parser("validate", help="run the equivalence gate in memory")
    v.add_argument("wit", nargs="+", help="WIT source file(s)")
    v.set_defaults(func=_cmd_validate)

    ck = sub.add_parser("check", help="assert on-disk artefacts are equivalent and current")
    ck.add_argument("wit", nargs="+", help="WIT source file(s)")
    ck.add_argument("--out", required=True, help="output directory to verify")
    ck.set_defaults(func=_cmd_check)

    # RFC 0005 — schema evolution
    ev = sub.add_parser("evolve", help="diff two schema versions, emit certificate")
    ev.add_argument("--from", dest="from_", nargs="+", required=True, help="old WIT source(s)")
    ev.add_argument("--to", nargs="+", required=True, help="new WIT source(s)")
    ev.add_argument("--out", help="write evolution certificate JSON to this path")
    ev.set_defaults(func=_cmd_evolve)

    cs = sub.add_parser("consensus", help="multi-agent obligation consensus on a proposal")
    cs.add_argument("--proposed", nargs="+", required=True, help="proposed WIT source(s)")
    cs.add_argument("--agents", nargs="+", required=True, help="each agent's local WIT schema")
    cs.add_argument("--threshold", type=float, default=0.6180339887, help="quorum threshold (default 1/φ)")
    cs.set_defaults(func=_cmd_consensus)

    cp = sub.add_parser("compose", help="verify the composition/confluence law over 3 versions")
    cp.add_argument("s1", help="version 1 WIT")
    cp.add_argument("s2", help="version 2 WIT")
    cp.add_argument("s3", help="version 3 WIT")
    cp.set_defaults(func=_cmd_compose)

    ec = sub.add_parser("evolve-codegen", help="emit versioned Rust/TS migration artefacts (§5)")
    ec.add_argument("--from", dest="from_", nargs="+", required=True, help="old WIT source(s)")
    ec.add_argument("--to", nargs="+", required=True, help="new WIT source(s)")
    ec.add_argument("--type", required=True, help="record name to version")
    ec.add_argument("--out", required=True, help="output directory")
    ec.set_defaults(func=_cmd_evolve_codegen)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
