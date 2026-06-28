#!/usr/bin/env python3
"""
sign.py
Produce a signed record envelope the verifiers can check. Generates a fresh
Ed25519 keypair every run (no key is ever committed). Signs the SHA-256 digest
of the canonical payload — the same scheme both verifiers expect.

Usage:
  python sign.py > signed_record.json
"""

import json
import sys
import hashlib
import base64
import nacl.signing
import nacl.encoding

from aegis_verifier import canonical_bytes

# Payload deliberately includes the characters AEGIS uses everywhere — φ, the
# ≤ in the root law, and the operator's name — because that is exactly where
# Python/Node canonicalization used to diverge.
PAYLOAD = {
    "event_id": "evt-0001",
    "timestamp": "2026-06-28T00:00:00Z",
    "operator": "Tarik Skalić",
    "law": "AdaptivePower(T) ≤ ReplayVerifiability(T)",
    "phi": "φ = 0.6180339887",
    "cotangent_hash": "deadbeef",
}


def make_record(payload: dict) -> dict:
    sk = nacl.signing.SigningKey.generate()
    digest = hashlib.sha256(canonical_bytes(payload)).digest()
    signature = sk.sign(digest).signature
    return {
        "payload": payload,
        "signature": base64.b64encode(signature).decode(),
        "public_key": sk.verify_key.encode(encoder=nacl.encoding.Base64Encoder).decode(),
    }


if __name__ == "__main__":
    json.dump(make_record(PAYLOAD), sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
