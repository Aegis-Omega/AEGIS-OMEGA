"""Negative replay checks against independent Node and already-built Rust binaries."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
fixture = json.loads((HERE / "stages.json").read_text(encoding="utf-8"))
commands = [
    ["node", str(HERE / "rechain.mjs")],
    [str(HERE / "rust_rechain" / "target" / "release" / "rechain")],
]


def changed(label, mutate):
    candidate = copy.deepcopy(fixture)
    mutate(candidate)
    return label, json.dumps(candidate, ensure_ascii=True)


def malformed_unicode(label, value):
    # Supply the digest Node would compute if it escaped the invalid surrogate.
    # Hash mismatch therefore cannot mask a missing scalar-validity check.
    raw = json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return changed(label, lambda f: f["canonical_vectors"][0].update(value=value, sha256=digest))


cases = [
    changed("missing profile", lambda f: f.pop("canonicalization")),
    changed("wrong profile", lambda f: f.update(canonicalization="legacy")),
    changed("tampered stage", lambda f: f["stages"][0]["output"].update(length=17)),
    changed("normalized Unicode", lambda f: f["canonical_vectors"][1].update(value={"text": "é"})),
    changed("unsafe integer", lambda f: f["stages"][0]["output"].update(length=9007199254740993)),
    # This rounds to the original 16 in JS, so all expected hashes still match.
    ("rounded fractional integer", json.dumps(fixture).replace('"length": 16', '"length": 16.0000000000000001', 1)),
    malformed_unicode("unpaired surrogate value", {"text": "\ud800"}),
    malformed_unicode("unpaired surrogate key", {"\ud800": "invalid key"}),
]

with tempfile.TemporaryDirectory(prefix="aegis-replay-negative-") as directory:
    target = Path(directory) / "fixture.json"
    checks = 0
    for label, raw in cases:
        assert raw != json.dumps(fixture), f"ineffective mutation: {label}"
        target.write_text(raw, encoding="utf-8")
        for command in commands:
            result = subprocess.run([*command, str(target)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            assert result.returncode != 0, f"{command[0]} accepted {label}"
            checks += 1
print(f"PASS: {checks} negative profile/tamper/numeric replay checks")
