#!/usr/bin/env python3
"""
AEGIS Ω research pre-flight.

This command performs type-triggered structural gates and emits a deterministic
admission ticket. It does not run the expensive experiment. Downstream runners
must require the emitted ticket (or call AdmissionController directly).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from research_invariants import (
    AdmissionController,
    GateVerdict,
    spectral_coverage_gate,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-f", type=int, required=True)
    parser.add_argument("--h", type=float, required=True)
    parser.add_argument("--target-gamma-max", type=float, required=True)
    parser.add_argument("--stage-id", default="enrichment-run")
    args = parser.parse_args()

    receipt = spectral_coverage_gate(
        n_f=args.n_f,
        h=args.h,
        target_gamma_max=args.target_gamma_max,
    )
    print(json.dumps({"gate_receipt": receipt.to_dict()}, sort_keys=True))

    if receipt.verdict is not GateVerdict.PASS:
        return 2

    ticket = AdmissionController.admit(
        stage_id=args.stage_id,
        subject_digest=receipt.object_digest,
        required_gate_ids=("spectral-domain-coverage",),
        receipts=(receipt,),
    )
    payload = asdict(ticket)
    print(json.dumps({"admission_ticket": payload}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
