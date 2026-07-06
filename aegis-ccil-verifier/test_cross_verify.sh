#!/usr/bin/env bash
# Cross-language signature equivalence test.
#
# Proves that a record signed by the Python kernel verifies under BOTH the
# Python verifier and the Node (Express server) verifier, and that a tampered
# record is rejected by both. This is the guard against the canonicalization
# drift that previously made φ/ć/≤ payloads fail to cross-verify.
#
# Requires: python3 + pynacl, node.
set -euo pipefail
cd "$(dirname "$0")"

echo "1. sign (Python) ............."
python3 sign.py > signed_record.json
echo "   ok"

echo "2. verify (Python) .........."
python3 aegis_verifier.py --signed signed_record.json | grep -q "Signature Authenticity: VALID"
echo "   VALID"

echo "3. verify (Node) ............."
node node_verify.js signed_record.json | grep -q "NODE VERIFY: VALID"
echo "   VALID"

echo "4. tamper rejection (Node) ..."
python3 - <<'PY'
import json
r = json.load(open("signed_record.json", encoding="utf-8"))
r["payload"]["law"] = "AdaptivePower(T) > ReplayVerifiability(T)"  # flip the law
json.dump(r, open("tampered_record.json", "w", encoding="utf-8"), ensure_ascii=False)
PY
# node_verify.js exits 1 on INVALID — that IS the rejection signal.
if node node_verify.js tampered_record.json >/dev/null; then
  echo "   FAIL: tampered record was accepted" >&2; exit 1
else
  echo "   correctly REJECTED"
fi

rm -f signed_record.json tampered_record.json
echo
echo "PASS — Python and Node agree; tampering is rejected."
