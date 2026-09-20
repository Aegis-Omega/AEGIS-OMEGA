#!/usr/bin/env python3
"""Classify Coq attestation receipts by what the theorem SAYS, not just its axioms.

`Print Assumptions` answers "does this proof rest on axioms?". It does not answer
"does this theorem assert anything?". A theorem of the form

    Theorem t : forall x, P x -> P x.
    Proof. intros x H. exact H. Qed.

is closed under the global context and carries no content. Counting it as a
closure overstates what an attestation bundle establishes.

This tool pairs each receipt with its source declaration and reports three
independent facts per theorem:

  axioms      CLOSED | <axiom names>        -- from the receipt
  content     TAUTOLOGY | SUBSTANTIVE       -- from the proof term's shape
  reach       which named obligations the statement mentions

Exit code is 0 for a clean audit and 1 when a receipt is counted as a closure
while its theorem is a tautology, or when a receipt has no locatable source.
"""
from __future__ import annotations

import argparse
import json
import os
import re

CLOSED = "Closed under the global context"
# A proof that only feeds a hypothesis back as the goal.
TAUTOLOGY_PROOF = re.compile(
    r"\Aintros[^.]*\.\s*(?:exact|apply|assumption)\b[^.]*\.\Z", re.S
)
DECL = r"^(?:Theorem|Lemma|Corollary|Remark|Fact)\s+{name}\b(.*?)^(Qed|Defined|Admitted)\."


def receipt_axioms(text: str) -> str | None:
    """CLOSED, or a comma-joined list of axiom names; None if unparseable."""
    if CLOSED in text:
        return "CLOSED"
    # `coqc` emits a bare "Axioms:"; an interactive `coqtop` session prefixes
    # it with the "Coq < " prompt. Both forms appear in real attestation logs.
    m = re.search(r"^(?:Coq < )?Axioms:\s*$(.*)", text, re.S | re.M)
    if not m:
        return None
    names = re.findall(r"^(?:Coq < )?([A-Za-z_][\w.']*)\s*:", m.group(1), re.M)
    return ", ".join(dict.fromkeys(names)) or None


def find_sources(roots: list[str]) -> dict[str, str]:
    """module name -> source text, preferring the longest when duplicated."""
    out: dict[str, str] = {}
    for root in roots:
        for dirpath, _, files in os.walk(root):
            for fn in files:
                if not fn.endswith(".v"):
                    continue
                path = os.path.join(dirpath, fn)
                try:
                    text = open(path, encoding="utf-8", errors="replace").read()
                except OSError:
                    continue
                mod = fn[:-2]
                if mod not in out or len(text) > len(out[mod]):
                    out[mod] = text
    return out


def classify(source: str, theorem: str) -> tuple[str, str]:
    """(content, statement) for one theorem, or ('NO-SOURCE', '')."""
    m = re.search(DECL.format(name=re.escape(theorem)), source, re.S | re.M)
    if not m:
        return "NO-SOURCE", ""
    body = m.group(1)
    statement, _, proof = body.partition("Proof.")
    squashed = " ".join(proof.split())
    content = "TAUTOLOGY" if TAUTOLOGY_PROOF.match(squashed) else "SUBSTANTIVE"
    return content, " ".join(statement.split())


def reach(statement: str, obligations: list[str]) -> list[str]:
    return [o for o in obligations if re.search(rf"\b{re.escape(o)}\b", statement)]


def audit(assumptions_dir: str, roots: list[str], obligations: list[str]) -> dict:
    sources = find_sources(roots)
    rows = []
    for fn in sorted(os.listdir(assumptions_dir)):
        if not fn.endswith(".txt"):
            continue
        parts = fn[:-4].split("__")
        if len(parts) < 3:
            continue
        module, theorem = parts[1], "__".join(parts[2:])
        text = open(os.path.join(assumptions_dir, fn), encoding="utf-8",
                    errors="replace").read()
        content, statement = classify(sources.get(module, ""), theorem)
        rows.append({
            "module": module,
            "theorem": theorem,
            "axioms": receipt_axioms(text) or "UNPARSED",
            "content": content,
            "reaches": reach(statement, obligations),
        })
    overstated = [r for r in rows
                  if r["axioms"] == "CLOSED" and r["content"] == "TAUTOLOGY"]
    unlocatable = [r for r in rows if r["content"] == "NO-SOURCE"]
    return {
        "total": len(rows),
        "closed": sum(r["axioms"] == "CLOSED" for r in rows),
        "tautologies": sum(r["content"] == "TAUTOLOGY" for r in rows),
        "substantive": sum(r["content"] == "SUBSTANTIVE" for r in rows),
        "unlocatable": len(unlocatable),
        "overstated_closures": [f"{r['module']}.{r['theorem']}" for r in overstated],
        "rows": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--assumptions", required=True,
                    help="directory of Print Assumptions receipts")
    ap.add_argument("--source-root", action="append", required=True,
                    help="directory to search for .v sources (repeatable)")
    ap.add_argument("--obligation", action="append", default=[],
                    help="named obligation to track through statements (repeatable)")
    ap.add_argument("--json", help="write the full report here")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 on overstated closures or unlocatable receipts")
    args = ap.parse_args()

    report = audit(args.assumptions, args.source_root, args.obligation)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, sort_keys=True)

    mw = max([len(r["module"]) for r in report["rows"]] + [6]) + 2
    tw = max([len(r["theorem"]) for r in report["rows"]] + [7]) + 2
    print(f"{'module':<{mw}}{'theorem':<{tw}}{'content':<13}axioms")
    print("-" * (mw + tw + 13 + 40))
    for r in report["rows"]:
        print(f"{r['module']:<{mw}}{r['theorem']:<{tw}}{r['content']:<13}{r['axioms']}")
    print()
    print(f"receipts            {report['total']}")
    print(f"closed (no axioms)  {report['closed']}")
    print(f"substantive         {report['substantive']}")
    print(f"tautologies         {report['tautologies']}")
    print(f"source not found    {report['unlocatable']}")
    if report["overstated_closures"]:
        print("\nOVERSTATED CLOSURES (axiom-free but contentless):")
        for name in report["overstated_closures"]:
            print(f"  {name}")
    for ob in args.obligation:
        supplying = [f"{r['module']}.{r['theorem']}" for r in report["rows"]
                     if ob in r["reaches"] and r["content"] == "SUBSTANTIVE"]
        print(f"\nobligation {ob}: "
              + (", ".join(supplying) if supplying
                 else "NOT DISCHARGED -- no substantive receipt proves it outright"))

    if args.strict and (report["overstated_closures"] or report["unlocatable"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
