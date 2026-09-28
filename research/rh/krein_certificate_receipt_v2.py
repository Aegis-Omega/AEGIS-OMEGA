#!/usr/bin/env python3
"""Fail-closed metadata binding for committed Krein Arb certificate receipts.

This does NOT rerun Arb and does NOT elevate the mathematical claim. It binds
the already-committed certificate metadata to exact repository/head/blob
identities and rejects mutations of those anchors.

RH_PROVEN=false; authority_effect=NONE.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

SCHEMA = "aegis.rh.krein-certificate-receipt.v2"
HEAD = "163304475c6141d05c64ab773a5eb4fbf66addcc"
REPOSITORY = "Aegis-Omega/AEGIS-OMEGA"
VERIFIER_PATH = "research/rh/verify_krein_arb_v1.py"
VERIFIER_BLOB = "84453dbcbce67087fb46fbd63cdd7e1e9f88576a"
LP_GENERATOR_PATH = "research/rh/krein_lp_cutting_plane_v1.py"
LP_GENERATOR_BLOB = "ff3f12dd29d446af0559e31110020ff4f86725ef"

ANCHORS = {
    "L0.98": {
        "certificate_path": "research/rh/KREIN_ARB_CERTIFICATE_L0.98.json",
        "certificate_blob": "f08a3c7ec06918290dbc3c6c8d78ae84388b1e2d",
        "lp_path": "research/rh/krein_lp_L0.98.json",
        "lp_blob": "1a253779b1df1a0245b8a41956144d212597ae54",
        "L": 0.98,
        "L_exact": "2206763817411543/2251799813685248",
        "m_certified": "0.005",
        "hat_bound": 1_000_000.0,
        "delta_bound": 1_000_000.0,
        "span": 8.0,
        "zero_cell": "0.004",
        "tail_start": "3000",
        "cells": 12157,
        "zero_cell_lower_prefix": "0.0001304919734561549976760717572249348521273023860184687893630273",
        "tail_lower_prefix": "3.696148152628815205549060105016740468012357853104460327251282571556592625541",
    },
    "L1.0": {
        "certificate_path": "research/rh/KREIN_ARB_CERTIFICATE_L1.0.json",
        "certificate_blob": "5d5933d716179f3750ca41172f3347d1166c6150",
        "lp_path": "research/rh/krein_lp_L1.0.json",
        "lp_blob": "b44296a5864978e4cfdf4796213114acd26fbde5",
        "L": 1.0,
        "L_exact": "1/1",
        "m_certified": "0.0015",
        "hat_bound": 1_000_000.0,
        "delta_bound": 10_000_000.0,
        "span": 8.0,
        "zero_cell": "0.004",
        "tail_start": "3000",
        "cells": 12186,
        "zero_cell_lower_prefix": "0.0001247108245301879293338303183767709209453631999256551964851253",
        "tail_lower_prefix": "3.792104378370854040667093697334418867001409542121331641417870393823906828621",
    },
}


class ReceiptError(ValueError):
    pass


def canonical_sha256(obj: dict) -> str:
    data = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(data).hexdigest()


def make_receipt(name: str) -> dict:
    if name not in ANCHORS:
        raise ReceiptError(f"unknown anchor {name}")
    a = ANCHORS[name]
    core = {
        "schema": SCHEMA,
        "status": "BOUND_COMMITTED_CERTIFICATE_METADATA",
        "authority_effect": "NONE",
        "rh_proven": False,
        "repository": REPOSITORY,
        "exact_head": HEAD,
        "certificate": {
            "path": a["certificate_path"],
            "git_blob_sha": a["certificate_blob"],
            "upstream_schema": "aegis.rh.krein-arb-certificate.v1",
        },
        "lp_candidate": {
            "path": a["lp_path"],
            "git_blob_sha": a["lp_blob"],
            "generator_path": LP_GENERATOR_PATH,
            "generator_git_blob_sha": LP_GENERATOR_BLOB,
        },
        "verifier": {
            "path": VERIFIER_PATH,
            "git_blob_sha": VERIFIER_BLOB,
            "precision_bits": 256,
        },
        "parameters": {
            "L": a["L"],
            "L_exact": a["L_exact"],
            "m_certified": a["m_certified"],
            "hat_bound": a["hat_bound"],
            "delta_bound": a["delta_bound"],
            "span": a["span"],
            "zero_cell": a["zero_cell"],
            "tail_start": a["tail_start"],
        },
        "observed_committed_result": {
            "cells": a["cells"],
            "zero_cell_lower_prefix": a["zero_cell_lower_prefix"],
            "tail_lower_prefix": a["tail_lower_prefix"],
        },
        "limitations": [
            "metadata binding only; this file does not rerun Arb",
            "the Arb inequality is not Lean-kernel checked",
            "no width >= L claim",
            "no RH claim",
        ],
    }
    out = dict(core)
    out["binding_sha256"] = canonical_sha256(core)
    return out


def validate_receipt(receipt: dict, name: str) -> None:
    expected = make_receipt(name)
    if set(receipt) != set(expected):
        raise ReceiptError("top-level field set mismatch")
    if receipt.get("binding_sha256") != canonical_sha256(
        {k: v for k, v in receipt.items() if k != "binding_sha256"}
    ):
        raise ReceiptError("binding_sha256 mismatch")
    if receipt != expected:
        raise ReceiptError("receipt differs from exact committed anchor")
    if receipt["authority_effect"] != "NONE" or receipt["rh_proven"] is not False:
        raise ReceiptError("authority/RH boundary violated")


def run_falsifiers(name: str) -> dict:
    base = make_receipt(name)
    mutations = {
        "wrong_head": ("exact_head", "0" * 40),
        "wrong_verifier_blob": ("verifier.git_blob_sha", "1" * 40),
        "wrong_lp_blob": ("lp_candidate.git_blob_sha", "2" * 40),
        "wrong_cell_count": (
            "observed_committed_result.cells",
            base["observed_committed_result"]["cells"] + 1,
        ),
        "authority_escalation": ("authority_effect", "WRITE"),
        "rh_escalation": ("rh_proven", True),
    }
    results = {}
    for label, (path, value) in mutations.items():
        bad = copy.deepcopy(base)
        cur = bad
        keys = path.split(".")
        for key in keys[:-1]:
            cur = cur[key]
        cur[keys[-1]] = value
        bad["binding_sha256"] = canonical_sha256(
            {k: v for k, v in bad.items() if k != "binding_sha256"}
        )
        try:
            validate_receipt(bad, name)
        except ReceiptError:
            results[label] = "PASS_REJECTED"
        else:
            results[label] = "FAIL_ACCEPTED"
    if any(v != "PASS_REJECTED" for v in results.values()):
        raise SystemExit(json.dumps(results, indent=2))
    return {
        "schema": "aegis.rh.krein-certificate-receipt-falsifiers.v2",
        "anchor": name,
        "status": "PASS",
        "authority_effect": "NONE",
        "rh_proven": False,
        "results": results,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("anchor", choices=sorted(ANCHORS))
    ap.add_argument("--out")
    ap.add_argument("--falsify", action="store_true")
    args = ap.parse_args()
    receipt = make_receipt(args.anchor)
    validate_receipt(receipt, args.anchor)
    payload = run_falsifiers(args.anchor) if args.falsify else receipt
    text = json.dumps(payload, indent=2, sort_keys=True)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
