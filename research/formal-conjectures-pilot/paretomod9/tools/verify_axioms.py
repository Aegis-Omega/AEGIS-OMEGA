#!/usr/bin/env python3
import hashlib, json, pathlib, re, sys

root = pathlib.Path(sys.argv[1]).resolve()
pins = json.loads((root / "PINS.json").read_text())
source = root / pins["candidate_file"]
log = root / "evidence/lean-kernel.log"

got_sha = hashlib.sha256(source.read_bytes()).hexdigest()
if got_sha != pins["candidate_sha256"]:
    raise SystemExit(f"SOURCE_SHA_MISMATCH expected={pins['candidate_sha256']} got={got_sha}")

text = log.read_text(errors="replace")
if "sorryAx" in text:
    raise SystemExit("SORRYAX_PRESENT")

allowed = set(pins["allowed_axioms"])
results = {}
for name in pins["theorems"]:
    escaped = re.escape(name)
    list_match = re.search(
        rf"'?{escaped}'?\s+depends on axioms:\s*\[([^\]]*)\]",
        text,
        flags=re.MULTILINE,
    )
    none_match = re.search(
        rf"'?{escaped}'?\s+does not depend on any axioms",
        text,
        flags=re.MULTILINE,
    )
    if list_match:
        axioms = sorted(x.strip() for x in list_match.group(1).split(",") if x.strip())
    elif none_match:
        axioms = []
    else:
        raise SystemExit(f"MISSING_AXIOM_REPORT {name}")
    unexpected = sorted(set(axioms) - allowed)
    if unexpected:
        raise SystemExit(f"UNEXPECTED_AXIOMS {name}: {unexpected}")
    results[name] = {"status": "KERNEL_CHECKED", "axioms": axioms}

receipt = {
    "schema": "AEGIS_PARETOMOD9_LEAN_KERNEL_RECEIPT_V1",
    "candidate_file": pins["candidate_file"],
    "candidate_sha256": pins["candidate_sha256"],
    "formal_conjectures_sha": pins["formal_conjectures_sha"],
    "lean_toolchain": pins["lean_toolchain"],
    "lean_release_commit": pins["lean_release_commit"],
    "lean_linux_asset_sha256": pins["lean_linux_asset_sha256"],
    "mathlib_sha": pins["mathlib_sha"],
    "github_run_id": __import__("os").environ.get("GITHUB_RUN_ID"),
    "github_run_attempt": __import__("os").environ.get("GITHUB_RUN_ATTEMPT"),
    "github_repository_sha": __import__("os").environ.get("GITHUB_SHA"),
    "results": results,
    "lean_log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
    "analytic_weil_formalization": "OPEN",
    "riemann_hypothesis": "NOT_PROVEN",
    "repository_admission": "NOT_GRANTED",
    "authority_effect": "NONE",
}
(root / "evidence/lean-kernel-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt, indent=2))
