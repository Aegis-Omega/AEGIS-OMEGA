#!/usr/bin/env python3
"""Fail-closed repository access preflight.

Distinguishes repository configuration failures, DNS failures, TCP egress
failures, and explicit sandbox egress policy before callers attempt network Git.
No credential-bearing proxy or remote values are emitted.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
from pathlib import Path
from typing import Mapping

CONNECTED_TRANSPORT = "CONNECTED_GITHUB_TRANSPORT"
DIRECT_GIT = "DIRECT_GIT"
RESTRICTED_NETWORK_POLICIES = frozenset({"caas_packages_only"})


def redacted_network_environment(env: Mapping[str, str]) -> dict[str, object]:
    """Return only policy state and proxy-presence bits, never proxy values."""
    policy = env.get("NETWORK")
    return {
        "network_policy": policy if policy else None,
        "https_proxy_present": bool(env.get("HTTPS_PROXY") or env.get("https_proxy")),
        "http_proxy_present": bool(env.get("HTTP_PROXY") or env.get("http_proxy")),
        "all_proxy_present": bool(env.get("ALL_PROXY") or env.get("all_proxy")),
        "no_proxy_present": bool(env.get("NO_PROXY") or env.get("no_proxy")),
    }


def classify_access(
    *,
    network_policy: str | None,
    dns_ok: bool,
    tcp_ok: bool,
    git_remote_ok: bool,
) -> dict[str, object]:
    policy = (network_policy or "").strip().casefold()
    if policy in RESTRICTED_NETWORK_POLICIES:
        return {
            "classification": "SANDBOX_EGRESS_RESTRICTED",
            "direct_git_available": False,
            "recommended_transport": CONNECTED_TRANSPORT,
        }
    if not dns_ok:
        return {
            "classification": "DNS_RESOLUTION_FAILED",
            "direct_git_available": False,
            "recommended_transport": CONNECTED_TRANSPORT,
        }
    if not tcp_ok:
        return {
            "classification": "TCP_EGRESS_FAILED",
            "direct_git_available": False,
            "recommended_transport": CONNECTED_TRANSPORT,
        }
    if not git_remote_ok:
        return {
            "classification": "GIT_REMOTE_UNAVAILABLE",
            "direct_git_available": False,
            "recommended_transport": CONNECTED_TRANSPORT,
        }
    return {
        "classification": "READY",
        "direct_git_available": True,
        "recommended_transport": DIRECT_GIT,
    }


def _resolve(host: str, port: int) -> tuple[bool, tuple[str, ...]]:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError:
        return False, ()
    addresses = tuple(dict.fromkeys(info[4][0] for info in infos if info[4]))
    return bool(addresses), addresses


def _tcp_connect(addresses: tuple[str, ...], port: int, timeout: float) -> bool:
    for address in addresses:
        family = socket.AF_INET6 if ":" in address else socket.AF_INET
        sock = socket.socket(family, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            target = (address, port, 0, 0) if family == socket.AF_INET6 else (address, port)
            sock.connect(target)
            return True
        except OSError:
            continue
        finally:
            sock.close()
    return False


def _git_remote_configured(repo_root: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "config", "--get", "remote.origin.url"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and bool(result.stdout.strip())


def _git_remote_reachable(repo_root: Path, timeout: float) -> bool:
    if not _git_remote_configured(repo_root):
        return False
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "ls-remote", "--exit-code", "origin", "HEAD"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=max(1.0, timeout),
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def probe_repository_access(
    *,
    repo_root: Path,
    host: str,
    port: int,
    timeout: float,
    env: Mapping[str, str],
) -> dict[str, object]:
    network = redacted_network_environment(env)
    policy = network["network_policy"]
    policy_text = str(policy).strip().casefold() if policy else ""

    remote_configured = _git_remote_configured(repo_root)
    if policy_text in RESTRICTED_NETWORK_POLICIES:
        classification = classify_access(
            network_policy=str(policy),
            dns_ok=False,
            tcp_ok=False,
            git_remote_ok=False,
        )
        return {
            "schema_version": "1.0.0",
            **classification,
            "dns_probe": "SKIPPED_BY_POLICY",
            "tcp_probe": "SKIPPED_BY_POLICY",
            "git_remote_probe": "SKIPPED_BY_POLICY",
            "git_remote_configured": remote_configured,
            "network_environment": network,
        }

    dns_ok, addresses = _resolve(host, port)
    tcp_ok = _tcp_connect(addresses, port, timeout) if dns_ok else False
    git_remote_ok = _git_remote_reachable(repo_root, timeout) if dns_ok and tcp_ok else False
    classification = classify_access(
        network_policy=str(policy) if policy else None,
        dns_ok=dns_ok,
        tcp_ok=tcp_ok,
        git_remote_ok=git_remote_ok,
    )
    return {
        "schema_version": "1.0.0",
        **classification,
        "dns_probe": "PASS" if dns_ok else "FAIL",
        "tcp_probe": "PASS" if tcp_ok else "FAIL",
        "git_remote_probe": "PASS" if git_remote_ok else "FAIL",
        "git_remote_configured": remote_configured,
        "resolved_address_count": len(addresses),
        "network_environment": network,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify direct repository access without leaking network credentials.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--host", default="github.com")
    parser.add_argument("--port", type=int, default=443)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-direct", action="store_true")
    args = parser.parse_args()

    result = probe_repository_access(
        repo_root=Path(args.repo_root).resolve(),
        host=args.host,
        port=args.port,
        timeout=max(0.1, args.timeout),
        env=os.environ,
    )
    if args.json:
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    else:
        print(f"classification={result['classification']}")
        print(f"recommended_transport={result['recommended_transport']}")
        print(f"direct_git_available={str(result['direct_git_available']).lower()}")
        print(f"dns_probe={result['dns_probe']}")
        print(f"tcp_probe={result['tcp_probe']}")
        print(f"git_remote_probe={result['git_remote_probe']}")

    if args.require_direct and not result["direct_git_available"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
