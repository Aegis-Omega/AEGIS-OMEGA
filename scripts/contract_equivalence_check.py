#!/usr/bin/env python3
"""
Contract-equivalence gate — RFC 0001 enforcement spike (NOT the full compiler).

Mechanically verifies that the ONE contract surface that has actually drifted —
the /platform/collaborate request shape and its mode enum — is identical between:
  - the TypeScript contract: packages/shared/lib/platform-contract.ts
  - the Python runtime:      sovereign-omega-v2/python/platform_helpers.py (+ bridge.py)

Exit 0 = surfaces agree. Exit 1 = drift (prints a deterministic diff). This is the
framework in miniature: one contract, two runtimes, mechanical equivalence, no
silent drift. Scope is intentionally narrow — it does NOT validate the whole
platform, does not touch hooks, and is not the WIT->IR projection compiler.
"""
import re
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
TS = ROOT / "packages/shared/lib/platform-contract.ts"
PY_HELPERS = ROOT / "sovereign-omega-v2/python/platform_helpers.py"
PY_BRIDGE = ROOT / "sovereign-omega-v2/python/bridge.py"


def _die(msg: str) -> "None":
    print(f"contract-equivalence: SETUP ERROR — {msg}", file=sys.stderr)
    sys.exit(2)


def ts_request_fields(text: str) -> set:
    m = re.search(r"export interface CollaborationRequest\s*\{(.*?)\n\}", text, re.S)
    if not m:
        _die("CollaborationRequest interface not found in platform-contract.ts")
    # field declarations: `readonly name?: type` — ignore // comment lines
    return set(re.findall(r"^\s*readonly\s+(\w+)\??\s*:", m.group(1), re.M))


def ts_modes(text: str) -> set:
    m = re.search(r"export type CollaborationMode\s*=(.*?)(?:\n\nexport |\n\ninterface )", text, re.S)
    if not m:
        _die("CollaborationMode union not found in platform-contract.ts")
    return set(re.findall(r"'([a-z]+)'", m.group(1)))


def py_request_fields(helpers: str, bridge: str) -> set:
    fn = re.search(r"def validate_collaboration_request\(.*?\n    return ", helpers, re.S)
    if not fn:
        _die("validate_collaboration_request not found in platform_helpers.py")
    fields = set(re.findall(r"body\.get\(['\"](\w+)['\"]", fn.group(0)))
    # autonomous + max_agents are parsed in the bridge handler, not the validator
    fields |= set(re.findall(r"data\.get\(['\"](autonomous|max_agents)['\"]", bridge))
    return fields


def py_modes(helpers: str) -> set:
    m = re.search(r"VALID_MODES\s*=\s*frozenset\(\{(.*?)\}\)", helpers, re.S)
    if not m:
        _die("VALID_MODES frozenset not found in platform_helpers.py")
    return set(re.findall(r"'([a-z]+)'", m.group(1)))


def main() -> int:
    for p in (TS, PY_HELPERS, PY_BRIDGE):
        if not p.exists():
            _die(f"missing file: {p.relative_to(ROOT)}")

    ts_txt = TS.read_text(encoding="utf-8")
    ph_txt = PY_HELPERS.read_text(encoding="utf-8")
    br_txt = PY_BRIDGE.read_text(encoding="utf-8")

    ts_req, py_req = ts_request_fields(ts_txt), py_request_fields(ph_txt, br_txt)
    ts_md, py_md = ts_modes(ts_txt), py_modes(ph_txt)

    errors = []
    if ts_req != py_req:
        errors.append(
            "request fields diverge:\n"
            f"    only in TS contract: {sorted(ts_req - py_req) or '—'}\n"
            f"    only in Python runtime: {sorted(py_req - ts_req) or '—'}"
        )
    if ts_md != py_md:
        errors.append(
            "collaboration modes diverge:\n"
            f"    only in TS contract: {sorted(ts_md - py_md) or '—'}\n"
            f"    only in Python runtime: {sorted(py_md - ts_md) or '—'}"
        )

    if errors:
        print("❌ CONTRACT DRIFT — platform-contract.ts <-> platform_helpers.py:")
        for e in errors:
            print("  - " + e)
        print("\nFix: make the TS contract and Python runtime declare the same "
              "request fields and modes. (This is the only class this gate checks.)")
        return 1

    print("✓ contract equivalence OK (platform /collaborate request surface):")
    print(f"    request fields: {sorted(ts_req)}")
    print(f"    modes: {sorted(ts_md)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
