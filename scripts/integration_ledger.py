#!/usr/bin/env python3
"""
Integration ledger — the truth about what's WIRED vs DORMANT, generated from code.

The point: docs lie because they're written from memory and drift. This reads the
actual repo surfaces (CI workflows, Vercel apps, cross-directory references) and
classifies every top-level area. Run it any time to get ground truth; never trust a
prose claim of "done" that this contradicts.

    python3 scripts/integration_ledger.py            # print the table
    python3 scripts/integration_ledger.py --write    # also refresh INTEGRATION_LEDGER.md

Status meaning:
    WIRED    a live entrypoint runs it — a CI workflow references it, or it ships as a
             Vercel app. This is the only status that means "connected and running."
    LINKED   imported/referenced by other code (>=3 external files) but not by a live
             entrypoint. Real, used, but not independently exercised.
    DORMANT  referenced by 1-2 external files. Idle; probably needs a wire or an archive.
    ORPHAN   nothing outside the directory references it. Sediment.
"""
from __future__ import annotations
import os, subprocess, sys

SKIP = {".git", "node_modules", "target", ".github", ".claude", ".vercel",
        "dist", "build", "__pycache__", "coverage", ".venv"}


def sh(args: list[str]) -> str:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=90).stdout
    except Exception:
        return ""


def head_sha() -> str:
    return (sh(["git", "rev-parse", "--short", "HEAD"]).strip() or "unknown")


def workflow_text() -> str:
    d = ".github/workflows"
    if not os.path.isdir(d):
        return ""
    out = []
    for f in os.listdir(d):
        try:
            with open(os.path.join(d, f), encoding="utf-8", errors="ignore") as fh:
                out.append(fh.read())
        except OSError as e:  # unreadable workflow file: skip, keep scanning
            print(f"integration_ledger: skipping {f}: {e}", file=sys.stderr)
    return "\n".join(out)


def external_refs(d: str) -> int:
    """Count files OUTSIDE directory d that reference the path `d/`."""
    out = sh(["grep", "-rIl",
              "--exclude-dir=node_modules", "--exclude-dir=.git",
              "--exclude-dir=target", "--exclude-dir=__pycache__",
              f"{d}/", "."]).splitlines()
    return sum(1 for f in out if not f.startswith(f"./{d}/") and f"/{d}/" not in f)


def classify(d: str, wf: str) -> tuple[str, str]:
    in_ci = f"{d}/" in wf or (f" {d}" in wf and len(d) > 3)
    has_vercel = os.path.exists(os.path.join(d, "vercel.json"))
    ext = external_refs(d)
    why = []
    if in_ci:
        why.append("CI")
    if has_vercel:
        why.append("vercel")
    if ext:
        why.append(f"{ext} ext-ref")
    if in_ci or has_vercel:
        return "WIRED", ", ".join(why)
    if ext >= 3:
        return "LINKED", ", ".join(why)
    if ext >= 1:
        return "DORMANT", ", ".join(why)
    return "ORPHAN", "no external reference"


def build_rows():
    wf = workflow_text()
    dirs = sorted(d for d in os.listdir(".")
                  if os.path.isdir(d) and d not in SKIP and not d.startswith("."))
    rows = [(("WIRED", "LINKED", "DORMANT", "ORPHAN").index(s), d, s, why)
            for d in dirs for (s, why) in [classify(d, wf)]]
    rows.sort(key=lambda r: (r[0], r[1]))
    return [(s, d, why) for _, d, s, why in rows]


def render_md(rows) -> str:
    from collections import Counter
    c = Counter(s for s, _, _ in rows)
    sha = head_sha()
    header = (
        f"**Generated from code at commit `{sha}`** by `scripts/integration_ledger.py`. "
        + "Do not hand-edit — regenerate with `python3 scripts/integration_ledger.py --write`. "
        + "This file is the authority on what is connected; a prose claim of \"done\" that "
        + "this contradicts is wrong."
    )
    counts = (
        f"**{c.get('WIRED',0)} WIRED · {c.get('LINKED',0)} LINKED · "
        + f"{c.get('DORMANT',0)} DORMANT · {c.get('ORPHAN',0)} ORPHAN** "
        + f"across {len(rows)} top-level areas."
    )
    lines = [
        "# Integration Ledger", "", header, "", counts, "",
        "| Status | Area | Evidence |",
        "|--------|------|----------|",
    ]
    for s, d, why in rows:
        lines.append(f"| {s} | `{d}` | {why} |")
    wired = ("- **WIRED** — a live entrypoint runs it (a CI workflow references it, or it "
             + "ships as a Vercel app). The only status that means *connected and running*.")
    linked = ("- **LINKED** — imported by other code (≥3 external files) but not exercised "
              + "by a live entrypoint of its own.")
    note = ("> A directory being WIRED does not mean every *file* in it is. New files can "
            + "dangle inside a wired directory until something calls them — check the module.")
    lines += [
        "",
        "## What the statuses mean",
        "",
        wired,
        linked,
        "- **DORMANT** — referenced by 1–2 external files. Idle; wire it or archive it.",
        "- **ORPHAN** — nothing outside the directory references it. Sediment.",
        "",
        note,
        "",
    ]
    return "\n".join(lines) + "\n"


def main():
    rows = build_rows()
    print(f"{'STATUS':8} {'AREA':26} EVIDENCE")
    print("-" * 66)
    for s, d, why in rows:
        print(f"{s:8} {d:26} {why}")
    if "--write" in sys.argv:
        with open("INTEGRATION_LEDGER.md", "w", encoding="utf-8") as f:
            f.write(render_md(rows))
        print("\nwrote INTEGRATION_LEDGER.md")


if __name__ == "__main__":
    main()
