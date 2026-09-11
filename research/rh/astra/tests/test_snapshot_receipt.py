from pathlib import Path
import json
from scripts.snapshot_receipt import build_receipt, canonical_json_bytes

ROOT = Path(__file__).resolve().parents[1]

def test_receipt_is_deterministic_and_fail_closed():
    a = build_receipt(ROOT); b = build_receipt(ROOT)
    assert canonical_json_bytes(a) == canonical_json_bytes(b)
    assert a["rh_status"] == "NOT_PROVEN"
    assert a["claim_promotion"] == "BLOCKED"
    assert a["execution_release"] == "BLOCKED"
    assert a["authority_effect"] == "NONE"
    assert a["receipt_sha256"] == b["receipt_sha256"]

def test_receipt_has_no_wallclock_field():
    payload = json.dumps(build_receipt(ROOT), sort_keys=True)
    assert "generated_at" not in payload
    assert "timestamp" not in payload
