#!/usr/bin/env python3
"""
AEGIS-Ω — the domain-agnostic verifiable envelope (T2)
======================================================
Constitutional law: AdaptivePower(T) <= ReplayVerifiability(T)

This is the reusable core the genomics proof (genomics/replay_pipeline.py) inlines
for zero-dependency portability. Promoted here to shared infra so a SECOND domain
can consume the *same* primitive by import — making "the envelope is stage-agnostic"
a fact you can test (see verifiable/test_generality.py, which cross-checks that this
implementation is byte-identical to the genomics inline one), not a claim.

Any pipeline whose intermediate state can be canonicalized — genomics, regulated
decision-audit, materials screening, financial model runs — folds into this chain and
gets: reproducible terminal hash, tamper-evidence with stage localization, and
cross-stage lineage binding. The stages are the only domain-specific part.

Dependency-free: stdlib only (hashlib, json, unicodedata).
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass, field

GENESIS = "0" * 64


def canon(value) -> bytes:
    """RFC 8785-style canonical bytes: sorted keys, NFC strings, no whitespace,
    UTF-8. Rejects float — integers and strings only in hashed state, exactly as
    the runtime forbids float in hash inputs (a non-determinism source)."""
    def check(v):
        if isinstance(v, float):
            raise TypeError("float in hashed state is forbidden (non-deterministic)")
        if isinstance(v, dict):
            for k in v:
                check(v[k])
        elif isinstance(v, (list, tuple)):
            for x in v:
                check(x)
    check(value)
    s = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    s = unicodedata.normalize("NFC", s)
    return s.encode("utf-8")


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@dataclass
class StageRecord:
    stage: str
    output: dict
    previous_hash: str
    sequence: int
    stage_hash: str = ""

    def compute(self) -> str:
        payload = {
            "stage": self.stage,
            "sequence": self.sequence,
            "previous_hash": self.previous_hash,
            "output": self.output,
        }
        self.stage_hash = sha256_hex(canon(payload))
        return self.stage_hash


@dataclass
class LineageChain:
    records: list = field(default_factory=list)

    def append(self, stage: str, output: dict) -> str:
        prev = self.records[-1].stage_hash if self.records else GENESIS
        rec = StageRecord(stage=stage, output=output,
                          previous_hash=prev, sequence=len(self.records))
        rec.compute()
        self.records.append(rec)
        return rec.stage_hash

    def terminal_hash(self) -> str:
        return self.records[-1].stage_hash if self.records else GENESIS

    def certify(self) -> dict:
        """Re-walk the chain; any tamper flips is_valid False and localizes it."""
        prev = GENESIS
        for i, rec in enumerate(self.records):
            recomputed = StageRecord(rec.stage, rec.output, prev, rec.sequence)
            recomputed.compute()
            if recomputed.stage_hash != rec.stage_hash or rec.previous_hash != prev:
                return {"is_valid": False, "broken_at": rec.stage, "sequence": i}
            prev = rec.stage_hash
        return {"is_valid": True, "broken_at": None, "terminal_hash": self.terminal_hash()}
