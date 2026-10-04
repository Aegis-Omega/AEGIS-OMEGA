from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from repo_network_preflight import (  # noqa: E402
    CONNECTED_TRANSPORT,
    DIRECT_GIT,
    classify_access,
    redacted_network_environment,
)


def test_caas_package_only_policy_bypasses_misleading_dns_probe() -> None:
    result = classify_access(
        network_policy="caas_packages_only",
        dns_ok=False,
        tcp_ok=False,
        git_remote_ok=False,
    )
    assert result["classification"] == "SANDBOX_EGRESS_RESTRICTED"
    assert result["recommended_transport"] == CONNECTED_TRANSPORT
    assert result["direct_git_available"] is False


def test_dns_failure_is_distinct_from_tcp_egress_failure() -> None:
    dns = classify_access(
        network_policy=None,
        dns_ok=False,
        tcp_ok=False,
        git_remote_ok=False,
    )
    assert dns["classification"] == "DNS_RESOLUTION_FAILED"
    assert dns["recommended_transport"] == CONNECTED_TRANSPORT

    tcp = classify_access(
        network_policy=None,
        dns_ok=True,
        tcp_ok=False,
        git_remote_ok=False,
    )
    assert tcp["classification"] == "TCP_EGRESS_FAILED"
    assert tcp["recommended_transport"] == CONNECTED_TRANSPORT


def test_direct_git_ready_requires_dns_tcp_and_remote() -> None:
    result = classify_access(
        network_policy=None,
        dns_ok=True,
        tcp_ok=True,
        git_remote_ok=True,
    )
    assert result["classification"] == "READY"
    assert result["recommended_transport"] == DIRECT_GIT
    assert result["direct_git_available"] is True


def test_remote_failure_after_network_success_is_not_called_dns() -> None:
    result = classify_access(
        network_policy=None,
        dns_ok=True,
        tcp_ok=True,
        git_remote_ok=False,
    )
    assert result["classification"] == "GIT_REMOTE_UNAVAILABLE"
    assert result["recommended_transport"] == CONNECTED_TRANSPORT


def test_network_environment_redacts_proxy_values(monkeypatch) -> None:
    monkeypatch.setenv("NETWORK", "caas_packages_only")
    monkeypatch.setenv("HTTPS_PROXY", "https://user:secret@example.invalid:8443")
    monkeypatch.setenv("HTTP_PROXY", "http://another-secret.invalid:8080")
    monkeypatch.setenv("ALL_PROXY", "socks5://sensitive.invalid:1080")

    env = redacted_network_environment(os.environ)

    assert env["network_policy"] == "caas_packages_only"
    assert env["https_proxy_present"] is True
    assert env["http_proxy_present"] is True
    assert env["all_proxy_present"] is True
    rendered = repr(env)
    assert "secret" not in rendered
    assert "example.invalid" not in rendered
    assert "sensitive.invalid" not in rendered
