#!/usr/bin/env python3
"""
aegis_verifier.py
Verify a signed record envelope against the active Ed25519 public key.

Requirements:
  pip install pynacl

Usage:
  python aegis_verifier.py --signed signed_record.json --payload payload.json
"""

import argparse
import json
import hashlib
import unicodedata
import base64
import sys
import nacl.signing
import nacl.encoding

def canonical_bytes(payload: dict) -> bytes:
    """
    Serializes a dictionary to deterministic UTF-8 bytes.

    Must produce byte-identical output to the Node verifier (server.js). Two
    rules make that hold across Python and JavaScript:
      - ensure_ascii=False: emit literal UTF-8 (φ, ć, ≤) instead of \\uXXXX
        escapes. Node's JSON.stringify never escapes non-ASCII, so Python must
        not either, or the SHA-256 digests diverge and signatures fail to
        cross-verify.
      - NFC normalization: collapse Unicode to a single canonical form so the
        same logical string hashes identically regardless of input encoding.
    """
    s = json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    return unicodedata.normalize("NFC", s).encode("utf-8")

def main():
    parser = argparse.ArgumentParser(description="AEGIS CCIL v5 Cryptographic Verifier Utility")
    parser.add_argument("--signed", required=True, help="Path to signed record JSON file")
    parser.add_argument("--payload", required=False, help="Optional canonical payload JSON file to verify matching parameters")
    args = parser.parse_args()

    # Load the signed record
    try:
        with open(args.signed, "r", encoding="utf-8") as f:
            signed_record = json.load(f)
    except FileNotFoundError:
        print(f"Error: Signed record file '{args.signed}' not found.", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Signed record file is not valid JSON. {e}", file=sys.stderr)
        sys.exit(1)

    payload = signed_record.get("payload")
    sig_b64 = signed_record.get("signature")
    pub_b64 = signed_record.get("public_key")

    if not payload or not sig_b64 or not pub_b64:
        print("Error: Signed record is missing payload, signature, or public_key envelope structures.", file=sys.stderr)
        sys.exit(2)

    try:
        # Decode base64 inputs
        sig_bytes = base64.b64decode(sig_b64)
        verify_key = nacl.signing.VerifyKey(pub_b64, encoder=nacl.encoding.Base64Encoder)

        # Hash canonicalized form
        payload_bytes = canonical_bytes(payload)
        digest = hashlib.sha256(payload_bytes).digest()

        # Cryptographically verify signature
        verify_key.verify(digest, sig_bytes)
        print("====================================")
        print("Signature Authenticity: VALID")
        print("====================================")

    except Exception as e:
        print("====================================")
        print("Signature Authenticity: INVALID", file=sys.stderr)
        print(f"Verification Detail: {e}", file=sys.stderr)
        print("====================================")
        sys.exit(3)

    # Perform physical parameters integrity crosschecks
    if args.payload:
        try:
            with open(args.payload, "r", encoding="utf-8") as pf:
                external_payload = json.load(pf)
        except Exception as e:
            print(f"Error: Unable to load comparison payload file. {e}", file=sys.stderr)
            sys.exit(1)

        # Confirm cotangent hash matches to prevent system state spoofing
        incoming_hash = payload.get("cotangent_hash")
        expected_hash = external_payload.get("cotangent_hash")

        if incoming_hash and expected_hash:
            if incoming_hash == expected_hash:
                print("Telemetry State Verification: MATCH")
            else:
                print("Warning: Cotangent Hash MISMATCH detected!", file=sys.stderr)
                sys.exit(4)
        else:
            print("Notice: Skip hash comparison step due to missing parameters.")

    print("Success: System security checks verified complete.")

if __name__ == "__main__":
    main()
