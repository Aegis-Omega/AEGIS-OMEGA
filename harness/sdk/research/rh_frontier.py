"""AEGIS research synthesis: source-bound Lean proof-frontier compiler.

Produces a truthful *conditional* proof frontier from disconnected Lean theorem
interfaces. It never treats Lean SOURCE as a kernel certificate, never infers
unconditional RH from a theorem with an unsupplied premise, and never modifies
the official target or protected branches. Stdlib-only and deterministic.

This v1 accepts an explicit, pinned, narrow real-world source corpus. It is
not a complete Lean parser or theorem prover.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
from typing import Any

KIND = "AEGIS_FORMAL_RESEARCH_FRONTIER_V1"
SOURCE_DIR = Path(__file__).resolve().parents[2] / "knowledge" / "rh" / "frontier_sources"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
THEOREM = re.compile(r"^[A-Za-z][A-Za-z0-9_']*$")
RATIONAL_PREMISE = re.compile(
    r"\(\s*(?P<arg>hLarge|h)\s*:\s*∀\s*L\s*:\s*ℝ\s*,\s*"
    r"\(?\s*(?P<num>\d+)\s*/\s*(?P<den>\d+)\s*"
    r"(?:\s*:\s*ℝ)?\s*\)?\s*(?P<op><|≤)\s*L\s*→\s*"
    r"WindowArithmeticNonpositiveV1\s+L\s*\)"
)
APPLICATION = re.compile(
    r"^\s*apply\s+(?P<callee>AEGIS\.[A-Za-z0-9_.]+)\s*$", re.M
)


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def git_blob(content: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()


def theorem_header(source: str, name: str) -> str:
    if not THEOREM.fullmatch(name):
        raise ValueError("DECLARATION_NAME_INVALID")
    # Conservative bounded textual extraction. A successful extraction is not
    # evidence of semantic Lean elaboration or a trusted kernel check.
    match = re.search(r"(?m)^theorem\s+" + re.escape(name) + r"\b", source)
    if match is None:
        raise ValueError("DECLARATION_MISSING:" + name)
    end = source.find(":=", match.end())
    if end < 0 or end - match.end() > 4096:
        raise ValueError("DECLARATION_HEADER_UNBOUNDED:" + name)
    return source[match.start():end]


def premise(header: str) -> tuple[Fraction, str, str]:
    matches = list(RATIONAL_PREMISE.finditer(header))
    if len(matches) != 1:
        raise ValueError("UNIQUE_LARGE_WINDOW_PREMISE_NOT_FOUND")
    m = matches[0]
    denominator = int(m["den"])
    if denominator == 0:
        raise ValueError("INVALID_CUTOFF")
    cutoff = Fraction(int(m["num"]), denominator)
    if not 0 < cutoff < 100:
        raise ValueError("CUTOFF_OUT_OF_RANGE")
    return cutoff, m["op"], m["arg"]


def load_sources(directory: Path = SOURCE_DIR) -> tuple[dict, dict[str, str]]:
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("SOURCE_CORPUS_MISSING")
    path = directory / "manifest.json"
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 32768:
        raise ValueError("MANIFEST_UNAVAILABLE")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(manifest, dict)
        or manifest.get("repository") != "tarikskalic33/formal-conjectures"
        or not isinstance(manifest.get("head_sha"), str)
        or not SHA40.fullmatch(manifest["head_sha"])
        or not isinstance(manifest.get("files"), dict)
        or set(manifest["files"]) != {"official", "small_window", "krein_l105"}):
        raise ValueError("MANIFEST_INVALID")
    result = {}
    for label, meta in manifest["files"].items():
        if (not isinstance(meta, dict)
            or not isinstance(meta.get("upstream_path"), str)
            or not isinstance(meta.get("git_blob"), str)
            or not SHA40.fullmatch(meta["git_blob"])
            or not isinstance(meta.get("sha256"), str)
            or not SHA64.fullmatch(meta["sha256"])):
            raise ValueError("SOURCE_IDENTITY_INVALID:" + label)
        blob = directory / (label + ".lean")
        if blob.is_symlink() or not blob.is_file() or blob.stat().st_size > 200000:
            raise ValueError("SOURCE_UNAVAILABLE:" + label)
        raw = blob.read_bytes()
        if git_blob(raw) != meta["git_blob"] or sha256(raw) != meta["sha256"]:
            raise ValueError("SOURCE_TAMPER_OR_DRIFT:" + label)
        result[label] = raw.decode("utf-8")
    return manifest, result


def analyze(directory: Path = SOURCE_DIR) -> dict:
    manifest, src = load_sources(directory)
    official_head = theorem_header(src["official"], "riemannHypothesis")
    if not re.search(r":\s*RiemannHypothesis\s*$", official_head):
        raise ValueError("OFFICIAL_RH_TYPE_CHANGED")
    # Recognise explicit unfinished `apply`, not "proved". No sorry or axiom
    # substitution is ever introduced by this analysis.
    target_body = src["official"].split(official_head + ":=", 1)
    if len(target_body) != 2:
        raise ValueError("OFFICIAL_TARGET_BODY_MISSING")
    target_body = target_body[1].split("\nend RiemannHypothesis", 1)[0]
    calls = APPLICATION.findall(target_body)
    older_name = "AEGIS.RHSmallWindowCanonicalJoinV1.riemannHypothesis_of_above_693_over_2000_v1"
    if calls != [older_name]:
        raise ValueError("OFFICIAL_TARGET_NO_LONGER_MATCHES_PINNED_BRANCH")

    small = theorem_header(src["small_window"], "riemannHypothesis_of_above_693_over_2000_v1")
    larger = theorem_header(src["krein_l105"], "rh_of_windows_from_21_40")
    old_bound, old_op, old_arg = premise(small)
    new_bound, new_op, new_arg = premise(larger)
    if "RiemannHypothesis" not in small or "RiemannHypothesis" not in larger:
        raise ValueError("CONCLUSION_NOT_RH")
    if not new_bound > old_bound:
        raise ValueError("NO_STRONGER_PRODUCER")
    if new_op != "≤" or old_op != "<":
        raise ValueError("PREMISE_COMPARISON_UNEXPECTED")
    # This proves a strict rational threshold improvement ONLY, independent
    # of any claim about Lean kernel validation of the theorem source.
    delta = new_bound - old_bound
    def ratio(frac: Fraction) -> dict:
        return {"numerator": frac.numerator, "denominator": frac.denominator}
    obligations = [
        {"kind": "SOURCE_IMPORT_RESOLUTION", "status": "UNVERIFIED"},
        {"kind": "LEAN_KERNEL_REPLAY_EXACT_HEAD", "status": "UNVERIFIED"},
        {"kind": "UNIVERSAL_LARGE_WINDOW_SIGN",
         "status": "OPEN",
         "proposition": "∀ L : ℝ, (21 / 40 : ℝ) ≤ L → WindowArithmeticNonpositiveV1 L"},
    ]
    report = {
        "schema_version": "1.0.0",
        "kind": KIND,
        "source_repository": manifest["repository"],
        "source_head_sha": manifest["head_sha"],
        "source_blobs": {name: meta["git_blob"] for name, meta in sorted(manifest["files"].items())},
        "official_target": "RiemannHypothesis.riemannHypothesis",
        "old_provider": older_name,
        "new_provider": "AEGIS.RHWindowL105FinalV1.rh_of_windows_from_21_40",
        "previous_lower_window_cutoff": ratio(old_bound),
        "candidate_lower_window_cutoff": ratio(new_bound),
        "cutoff_improvement": ratio(delta),
        "old_comparison": old_op,
        "new_comparison": new_op,
        "remaining_obligations": obligations,
        "static_compatibility": "SOURCE_HEADER_COMPATIBLE_ONLY",
        "kernel_verified_on_source_head": False,
        "unconditional_riemann_hypothesis_proven": False,
        "authority_granted": False,
        "operational_admission": "NOT_ADMITTED",
    }
    report["report_sha256"] = sha256(canonical({"domain": KIND, "body": report}))
    return report


def render_lean(report: dict) -> str:
    if (report.get("kind") != KIND
        or report.get("new_provider") != "AEGIS.RHWindowL105FinalV1.rh_of_windows_from_21_40"):
        raise ValueError("RESEARCH_REPORT_INVALID")
    return """\/-
Copyright 2026 The Formal Conjectures Authors.
SPDX-License-Identifier: Apache-2.0
Generated conditional research bridge. No unconditional RH assertion.
Requires an independent Lean kernel build at the exact source head.
-/
import RHWindowL105FinalV1

set_option autoImplicit false
namespace AEGIS.RHResearchSynthesisV1
open AEGIS.WeilWindowExhaustionV1

theorem rh_from_remaining_L105_windows
    (hLarge : ∀ L : ℝ, (21 / 40 : ℝ) ≤ L → WindowArithmeticNonpositiveV1 L) :
    RiemannHypothesis :=
  AEGIS.RHWindowL105FinalV1.rh_of_windows_from_21_40 hLarge

end AEGIS.RHResearchSynthesisV1

#print axioms AEGIS.RHResearchSynthesisV1.rh_from_remaining_L105_windows
""".replace("\\/-", "/-")


def render_model_task(report: dict) -> dict:
    """Actionable evidence-bound problem statement for any local/proprietary LLM.

    NOT a training ground-truth proof certificate. A model can suggest a lemma
    for the open goal, but can neither verify it nor self-grant its authority.
    """
    return {
        "schema_version": "1.0.0",
        "task": "SYNTHESIZE_MISSING_LEAN_PREMISE",
        "source_ref": report["source_repository"] + "@" + report["source_head_sha"],
        "source_blobs": report["source_blobs"],
        "goal": report["remaining_obligations"][-1]["proposition"],
        "known_provider": report["new_provider"],
        "required_output": "Lean theorem candidate with explicit imports and no sorry/admit",
        "acceptance": "Independent kernel typecheck + print axioms on exact source",
        "never_assume": "conditional RH theorem is unconditional RH proof",
        "model_response_state": "UNVERIFIED_CANDIDATE_ONLY",
        "report_sha256": report["report_sha256"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, default=SOURCE_DIR)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    try:
        r = analyze(args.corpus)
        if args.out.exists():
            raise ValueError("OUTPUT_ALREADY_EXISTS")
        args.out.mkdir(parents=False, exist_ok=False)
        (args.out / "frontier.json").write_bytes(canonical(r) + b"\n")
        (args.out / "conditional_bridge.lean").write_text(render_lean(r))
        (args.out / "model_task.json").write_bytes(canonical(render_model_task(r)) + b"\n")
        print(json.dumps({"status": "CONDITIONAL_FRONTIER_ONLY",
                          "report_sha256": r["report_sha256"],
                          "remaining_goal": r["remaining_obligations"][-1]["proposition"]},
                         sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, UnicodeError, KeyError) as exc:
        print("RESEARCH_SYNTHESIS_DENIED:" + type(exc).__name__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
