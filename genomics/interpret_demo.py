#!/usr/bin/env python3
"""
AEGIS-Ω — full-stack genomics demo: deterministic caller + governed, cached,
verifiable AI interpretation.

Offline (default): uses the deterministic fixture interpretation. No credits.
    python3 interpret_demo.py
Live (real governed Claude call + prompt caching): requires ANTHROPIC_API_KEY.
    AEGIS_LIVE=1 python3 interpret_demo.py

What it proves, in one run:
  A. The deterministic pipeline still yields its reproducible terminal hash.
  B. A governed interpretation is produced and FOLDED into the same lineage;
     the extended chain still certifies.
  C. Prompt caching engaged — call 2 (identical stable prefix) reports
     cache_read_input_tokens > 0 (live mode only).
  D. Tamper-evidence extends to the AI output: editing the stored interpretation
     text makes certify() fail and localize broken_at="INTERPRET".
"""
import os

from replay_pipeline import run_pipeline, SAMPLE_REFERENCE, SAMPLE_READS
from interpret import interpret_variants, fold_interpretation


def _variants(chain):
    # VARIANT_CALL is stage index 3; ANNOTATE (index 4) holds annotated variants.
    return chain.records[4].output["annotated_variants"]


def main() -> int:
    live = os.environ.get("AEGIS_LIVE") == "1"
    client = None
    model = "claude-opus-4-8"
    if live:
        import sys
        here = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, os.path.abspath(os.path.join(here, "..", "sovereign-omega-v2", "python")))
        from anth_client import get_client
        client = get_client()
        model = os.environ.get("AEGIS_SWARM_MODEL", "claude-opus-4-8")

    print("AEGIS-Ω Genomics — deterministic caller + governed cached interpretation")
    print("=" * 72)

    # A. Deterministic pipeline (the T2 proof from replay_pipeline.py).
    chain = run_pipeline(SAMPLE_REFERENCE, SAMPLE_READS)
    variants = _variants(chain)
    det_terminal = chain.terminal_hash()
    print(f"[A] deterministic terminal hash : {det_terminal[:24]}…  (variants called: {len(variants)})")

    # B + C. Governed interpretation with prompt caching. Two calls with an
    # identical stable prefix; the second should hit the cache.
    interp = interpret_variants(variants, client=client, model=model)
    if live:
        interp2 = interpret_variants(variants, client=client, model=model)
        print(f"[C] call 1  cache_creation={interp['cache_creation_tokens']:>5}  "
              f"cache_read={interp['cache_read_tokens']:>5}  in={interp['input_tokens']} out={interp['output_tokens']}")
        print(f"    call 2  cache_creation={interp2['cache_creation_tokens']:>5}  "
              f"cache_read={interp2['cache_read_tokens']:>5}  in={interp2['input_tokens']} out={interp2['output_tokens']}")
        hit = interp2["cache_read_tokens"] > 0
        print(f"    prompt cache {'HIT — stable frame served at 10% cost' if hit else 'MISS — prefix under min cacheable length'}")
    else:
        print("[C] offline fixture mode (no credits spent) — run with AEGIS_LIVE=1 for live cache numbers")

    fold_interpretation(chain, variants, interp)
    cert = chain.certify()
    print(f"[B] interpretation folded into lineage; chain certifies: {cert['is_valid']}  "
          f"(model={interp['model']}, live={interp['live']})")
    assert cert["is_valid"], "extended chain must certify"

    # D. Tamper-evidence over the AI output.
    rec = chain.records[-1]  # INTERPRET
    rec.output["interpretation"] = rec.output["interpretation"] + " [SILENTLY EDITED]"
    tampered = chain.certify()
    assert tampered["is_valid"] is False and tampered["broken_at"] == "INTERPRET", tampered
    print(f"[D] edited stored interpretation → certify is_valid={tampered['is_valid']}, "
          f"broken_at={tampered['broken_at']}")

    print("=" * 72)
    print("RESULT: the AI interpretation is now auditable evidence — provenance and")
    print("        integrity are cryptographically bound, even though generation is")
    print("        stochastic. Determinism lives in the envelope, not the model.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
