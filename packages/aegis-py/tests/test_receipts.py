import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aegis.receipts import Recorder, _envelope_hash, canon, verify, wrap_anthropic

VECTORS = Path(__file__).resolve().parents[3] / "sovereign-omega-v2/test/vectors/canon-vectors.json"


def test_canon_matches_cross_language_vectors():
    vectors = json.loads(VECTORS.read_text(encoding="utf-8"))["vectors"]
    assert vectors
    import hashlib
    for v in vectors:
        assert hashlib.sha256(canon(v["input"])).hexdigest() == v["sha256"], v.get("name")


def test_chain_verifies_and_resumes(tmp_path):
    path = tmp_path / "r.json"
    rec = Recorder(path)
    rec.record({"q": 1}, {"a": 0.5}, model_id="m", provider="p")
    rec.record({"q": 2}, {"a": "x"}, model_id="m", provider="p")
    assert verify(path)["valid"] and verify(path)["count"] == 2

    Recorder(path).record({"q": 3}, {}, model_id="m", provider="p")
    result = verify(path)
    assert result["valid"] and result["count"] == 3


@pytest.mark.parametrize("field,value", [
    ("request_digest", "0" * 64),
    ("model_id", "other-model"),
    ("seq", 7),
    ("prev_hash", "f" * 64),
])
def test_any_edit_breaks_the_chain(tmp_path, field, value):
    path = tmp_path / "r.json"
    rec = Recorder(path)
    for i in range(3):
        rec.record({"q": i}, {"a": i}, model_id="m", provider="p")
    pkg = json.loads(path.read_text())
    pkg["envelopes"][1][field] = value
    path.write_text(json.dumps(pkg))
    assert not verify(path)["valid"]
    with pytest.raises(ValueError):
        Recorder(path)


def test_dropping_the_last_envelope_is_detected(tmp_path):
    path = tmp_path / "r.json"
    rec = Recorder(path)
    for i in range(3):
        rec.record({"q": i}, {"a": i}, model_id="m", provider="p")
    pkg = json.loads(path.read_text())
    pkg["envelopes"].pop()
    path.write_text(json.dumps(pkg))
    assert verify(path)["error"] == "TERMINAL_MISMATCH"


def test_truncation_cannot_hide_behind_a_renamed_terminal_key(tmp_path):
    path = tmp_path / "r.json"
    rec = Recorder(path)
    for i in range(3):
        rec.record({"q": i}, {"a": i}, model_id="m", provider="p")
    pkg = json.loads(path.read_text())
    pkg["envelopes"].pop()
    pkg["expected_terminal_hasx"] = pkg.pop("expected_terminal_hash")
    path.write_text(json.dumps(pkg))
    assert not verify(path)["valid"]


def test_every_single_byte_edit_breaks_the_chain(tmp_path):
    path = tmp_path / "r.json"
    rec = Recorder(path)
    for i in range(3):
        rec.record({"q": i}, {"a": i}, model_id="m", provider="p")
    original = path.read_bytes()
    survivors = []
    for i, byte in enumerate(original):
        for new in {byte ^ 1, ord("x") if byte != ord("x") else ord("y")}:
            edited = bytearray(original)
            edited[i] = new
            path.write_bytes(bytes(edited))
            if verify(path)["valid"]:
                survivors.append((i, chr(byte), chr(new)))
    assert survivors == []


@pytest.mark.parametrize("bad_seq", [True, 1.0, "1"])
def test_seq_must_be_a_plain_integer_even_when_rehashed(tmp_path, bad_seq):
    path = tmp_path / "r.json"
    rec = Recorder(path)
    for i in range(2):
        rec.record({"q": i}, {"a": i}, model_id="m", provider="p")
    pkg = json.loads(path.read_text())
    env = pkg["envelopes"][1]
    env["seq"] = bad_seq
    if not isinstance(bad_seq, float):  # floats cannot be hashed at all
        env["envelope_hash"] = _envelope_hash(env)
        pkg["expected_terminal_hash"] = env["envelope_hash"]
    path.write_text(json.dumps(pkg))
    result = verify(path)
    assert not result["valid"]
    assert result["error"] == "SEQ_MISMATCH at 1"


@pytest.mark.parametrize("shape", ["envelope_list", "envelopes_dict", "package_list"])
def test_malformed_containers_are_invalid_not_a_crash(tmp_path, shape):
    path = tmp_path / "r.json"
    rec = Recorder(path)
    rec.record({"q": 0}, {"a": 0}, model_id="m", provider="p")
    pkg = json.loads(path.read_text())
    if shape == "envelope_list":
        pkg["envelopes"] = [list(pkg["envelopes"][0])]
    elif shape == "envelopes_dict":
        pkg["envelopes"] = {k: None for k in pkg["envelopes"][0]}
    else:
        pkg = list(pkg)
    path.write_text(json.dumps(pkg))
    assert not verify(path)["valid"]


def test_wrap_anthropic_records_each_call(tmp_path):
    calls = []
    fake = SimpleNamespace(messages=SimpleNamespace(
        create=lambda **kw: calls.append(kw) or {"content": [{"type": "text", "text": "hi"}]}))
    path = tmp_path / "r.json"
    client = wrap_anthropic(fake, Recorder(path))
    out = client.messages.create(model="claude-x", max_tokens=8, messages=[])
    assert out["content"][0]["text"] == "hi" and len(calls) == 1
    env = json.loads(path.read_text())["envelopes"][0]
    assert env["model_id"] == "claude-x" and env["provider"] == "anthropic"
    assert verify(path)["valid"]
