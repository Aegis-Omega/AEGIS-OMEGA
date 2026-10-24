"""Offline provider-bound origin regression for the AEGIS repository snapshot."""
from __future__ import annotations

import subprocess
from pathlib import Path
import pytest
from harness.sdk import repository_knowledge as knowledge

REPO_ID = 1095915905
REPO_NAME = "Aegis-Omega/AEGIS-OMEGA"


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


@pytest.fixture
def foreign(tmp_path: Path):
    git(tmp_path, "init", "-q")
    (tmp_path / "foreign.txt").write_text("not AEGIS\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "-c", "user.name=Local", "-c", "user.email=local@example.invalid", "commit", "-qm", "first")
    return tmp_path, knowledge.build_snapshot(tmp_path, repository_id=REPO_ID, repository_full_name=REPO_NAME)


def provider(snapshot):
    def fake(path: str, *, timeout: float = 5.0):
        if path == "/repos/Aegis-Omega/AEGIS-OMEGA":
            return {"id": REPO_ID, "full_name": REPO_NAME}
        if path == "/repos/Aegis-Omega/AEGIS-OMEGA/commits/" + snapshot["source_head_sha"]:
            return {"sha": snapshot["source_head_sha"], "commit": {"tree": {"sha": snapshot["source_tree_sha"]}}}
        raise AssertionError(path)
    return fake


def verify(root, snapshot):
    return knowledge.verify_snapshot_github_origin(root, snapshot, expected_repository_id=REPO_ID, expected_repository_full_name=REPO_NAME)


def test_local_git_accepts_declared_identity_but_provider_unavailable_denies(foreign, monkeypatch):
    root, snapshot = foreign
    assert knowledge.verify_snapshot(root, snapshot, expected_repository_id=REPO_ID)["status"] == "ESTABLISHED"
    def unavailable(path: str, **kwargs):
        raise OSError("offline")
    monkeypatch.setattr(knowledge, "_github_api_document", unavailable)
    assert verify(root, snapshot) == {"status": "DENIED", "reason_codes": ["GITHUB_ORIGIN_UNAVAILABLE"]}


def test_provider_verified_exact_source_passes_only_as_prerequisite(foreign, monkeypatch):
    root, snapshot = foreign
    monkeypatch.setattr(knowledge, "_github_api_document", provider(snapshot))
    r = verify(root, snapshot)
    assert r["status"] == "ESTABLISHED" and r["origin_status"] == "PROVIDER_VERIFIED"
    assert r["source_head_sha"] == snapshot["source_head_sha"]


def test_wrong_provider_repo_id_denies(foreign, monkeypatch):
    root, snapshot = foreign
    good = provider(snapshot)
    def bad(path, **kwargs):
        result = good(path, **kwargs)
        return {**result, "id": 123} if path.endswith("AEGIS-OMEGA") else result
    monkeypatch.setattr(knowledge, "_github_api_document", bad)
    assert verify(root, snapshot)["reason_codes"] == ["GITHUB_ORIGIN_REPOSITORY_MISMATCH"]


def test_wrong_provider_repo_name_denies(foreign, monkeypatch):
    root, snapshot = foreign
    good = provider(snapshot)
    def bad(path, **kwargs):
        result = good(path, **kwargs)
        return {**result, "full_name": "outsider/FORK"} if path.endswith("AEGIS-OMEGA") else result
    monkeypatch.setattr(knowledge, "_github_api_document", bad)
    assert verify(root, snapshot)["reason_codes"] == ["GITHUB_ORIGIN_REPOSITORY_MISMATCH"]


def test_wrong_provider_commit_denies(foreign, monkeypatch):
    root, snapshot = foreign
    good = provider(snapshot)
    def bad(path, **kwargs):
        result = good(path, **kwargs)
        return {**result, "sha": "f" * 40} if "/commits/" in path else result
    monkeypatch.setattr(knowledge, "_github_api_document", bad)
    assert verify(root, snapshot)["reason_codes"] == ["GITHUB_ORIGIN_COMMIT_TREE_MISMATCH"]


def test_wrong_provider_tree_denies(foreign, monkeypatch):
    root, snapshot = foreign
    good = provider(snapshot)
    def bad(path, **kwargs):
        result = good(path, **kwargs)
        return {**result, "commit": {"tree": {"sha": "f" * 40}}} if "/commits/" in path else result
    monkeypatch.setattr(knowledge, "_github_api_document", bad)
    assert verify(root, snapshot)["reason_codes"] == ["GITHUB_ORIGIN_COMMIT_TREE_MISMATCH"]


def test_caller_supplied_different_name_denies_without_network(foreign, monkeypatch):
    root, snapshot = foreign
    monkeypatch.setattr(knowledge, "_github_api_document", lambda *_args, **_kw: pytest.fail("no provider call"))
    snapshot["repository_full_name"] = "outsider/FORK"
    snapshot["snapshot_digest"] = knowledge._digest({k:v for k,v in snapshot.items() if k!="snapshot_digest"})
    assert verify(root, snapshot)["reason_codes"] == ["REPOSITORY_ORIGIN_IDENTITY_MISMATCH"]


def test_wrong_expected_local_id_denies_before_network(foreign, monkeypatch):
    root, snapshot = foreign
    monkeypatch.setattr(knowledge, "_github_api_document", lambda *_args, **_kw: pytest.fail("no provider call"))
    r = knowledge.verify_snapshot_github_origin(root, snapshot, expected_repository_id=1, expected_repository_full_name=REPO_NAME)
    assert r["reason_codes"] == ["REPOSITORY_ID_MISMATCH"]


def test_stale_head_denies_before_network(foreign, monkeypatch):
    root, snapshot = foreign
    (root / "foreign.txt").write_text("changed\n")
    git(root, "add", ".")
    git(root, "-c", "user.name=Local", "-c", "user.email=local@example.invalid", "commit", "-qm", "second")
    monkeypatch.setattr(knowledge, "_github_api_document", lambda *_args, **_kw: pytest.fail("no provider call"))
    assert set(verify(root, snapshot)["reason_codes"]) == {"SOURCE_HEAD_MISMATCH", "SOURCE_TREE_MISMATCH"}


def test_checkout_changes_while_reading_provider_denies(foreign, monkeypatch):
    root, snapshot = foreign
    good = provider(snapshot)
    def change(path: str, **kwargs):
        if "/commits/" in path:
            (root / "foreign.txt").write_text("changed concurrently\n")
            git(root, "add", ".")
            git(root, "-c", "user.name=Local", "-c", "user.email=local@example.invalid", "commit", "-qm", "new")
        return good(path, **kwargs)
    monkeypatch.setattr(knowledge, "_github_api_document", change)
    assert set(verify(root, snapshot)["reason_codes"]) == {"SOURCE_HEAD_MISMATCH", "SOURCE_TREE_MISMATCH"}


def test_malformed_provider_response_denies(foreign, monkeypatch):
    root, snapshot = foreign
    monkeypatch.setattr(knowledge, "_github_api_document", lambda path, **kw: {"id": REPO_ID, "full_name": REPO_NAME} if "/commits/" not in path else {})
    assert verify(root, snapshot)["reason_codes"] == ["GITHUB_ORIGIN_COMMIT_TREE_MISMATCH"]


class _FakeHTTP:
    def __init__(self, url, payload=b"{}"):
        self.url = url
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, *_args):
        return False
    def geturl(self):
        return self.url
    def read(self, max_bytes):
        return self.payload


def test_provider_transport_uses_exact_official_https_url(monkeypatch):
    calls = []
    def fake(req, *, timeout):
        calls.append((req.full_url, timeout))
        return _FakeHTTP(req.full_url, b'{"id":1095915905}')
    monkeypatch.setattr(knowledge.urlrequest, "urlopen", fake)
    result = knowledge._github_api_document("/repos/Aegis-Omega/AEGIS-OMEGA")
    assert result["id"] == REPO_ID
    assert calls == [("https://api.github.com/repos/Aegis-Omega/AEGIS-OMEGA", 5.0)]


def test_redirect_from_provider_is_rejected(monkeypatch):
    monkeypatch.setattr(knowledge.urlrequest, "urlopen", lambda req, *, timeout: _FakeHTTP("https://untrusted.invalid/forgery"))
    with pytest.raises(ValueError, match="GITHUB_ORIGIN_REDIRECTED"):
        knowledge._github_api_document("/repos/Aegis-Omega/AEGIS-OMEGA")


def test_oversized_provider_response_is_rejected(monkeypatch):
    monkeypatch.setattr(knowledge.urlrequest, "urlopen", lambda req, *, timeout: _FakeHTTP(req.full_url, b"0" * 1_048_577))
    with pytest.raises(ValueError, match="GITHUB_ORIGIN_OVERSIZED"):
        knowledge._github_api_document("/repos/Aegis-Omega/AEGIS-OMEGA")


def test_non_object_provider_response_is_rejected(monkeypatch):
    monkeypatch.setattr(knowledge.urlrequest, "urlopen", lambda req, *, timeout: _FakeHTTP(req.full_url, b"[]"))
    with pytest.raises(ValueError, match="GITHUB_ORIGIN_DOCUMENT_INVALID"):
        knowledge._github_api_document("/repos/Aegis-Omega/AEGIS-OMEGA")
