#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest import TestCase, main, mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import repo_network_preflight as preflight  # noqa: E402
from repo_network_preflight import (  # noqa: E402
    CONNECTED_TRANSPORT,
    DIRECT_GIT,
    classify_access,
    redacted_network_environment,
)


class RepoNetworkPreflightTests(TestCase):
    def test_caas_package_only_policy_bypasses_misleading_dns_probe(self) -> None:
        result = classify_access(
            network_policy="caas_packages_only",
            dns_ok=False,
            tcp_ok=False,
            git_remote_ok=False,
        )
        self.assertEqual(result["classification"], "SANDBOX_EGRESS_RESTRICTED")
        self.assertEqual(result["recommended_transport"], CONNECTED_TRANSPORT)
        self.assertFalse(result["direct_git_available"])
        self.assertTrue(result["handoff_required"])
        self.assertFalse(result["connected_transport_invoked"])

    def test_dns_failure_is_distinct_from_tcp_egress_failure(self) -> None:
        dns = classify_access(
            network_policy=None,
            dns_ok=False,
            tcp_ok=False,
            git_remote_ok=False,
        )
        self.assertEqual(dns["classification"], "DNS_RESOLUTION_FAILED")
        self.assertEqual(dns["recommended_transport"], CONNECTED_TRANSPORT)

        tcp = classify_access(
            network_policy=None,
            dns_ok=True,
            tcp_ok=False,
            git_remote_ok=False,
        )
        self.assertEqual(tcp["classification"], "TCP_EGRESS_FAILED")
        self.assertEqual(tcp["recommended_transport"], CONNECTED_TRANSPORT)

    def test_direct_git_ready_requires_dns_tcp_and_remote(self) -> None:
        result = classify_access(
            network_policy=None,
            dns_ok=True,
            tcp_ok=True,
            git_remote_ok=True,
        )
        self.assertEqual(result["classification"], "READY")
        self.assertEqual(result["recommended_transport"], DIRECT_GIT)
        self.assertTrue(result["direct_git_available"])
        self.assertFalse(result["handoff_required"])

    def test_remote_failure_after_network_success_is_not_called_dns(self) -> None:
        result = classify_access(
            network_policy=None,
            dns_ok=True,
            tcp_ok=True,
            git_remote_ok=False,
        )
        self.assertEqual(result["classification"], "GIT_REMOTE_UNAVAILABLE")
        self.assertEqual(result["recommended_transport"], CONNECTED_TRANSPORT)

    def test_network_environment_redacts_proxy_values(self) -> None:
        env = {
            "NETWORK": "caas_packages_only",
            "HTTPS_PROXY": "https://user:secret@example.invalid:8443",
            "HTTP_PROXY": "http://another-secret.invalid:8080",
            "ALL_PROXY": "socks5://sensitive.invalid:1080",
        }
        redacted = redacted_network_environment(env)

        self.assertEqual(redacted["network_policy"], "caas_packages_only")
        self.assertTrue(redacted["https_proxy_present"])
        self.assertTrue(redacted["http_proxy_present"])
        self.assertTrue(redacted["all_proxy_present"])
        rendered = repr(redacted)
        self.assertNotIn("secret", rendered)
        self.assertNotIn("example.invalid", rendered)
        self.assertNotIn("sensitive.invalid", rendered)

    def test_restricted_probe_skips_dns_tcp_and_all_git_probes(self) -> None:
        forbidden = mock.Mock(side_effect=AssertionError("restricted path executed a forbidden network/Git probe"))
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(preflight, "_git_remote_configured", forbidden), \
             mock.patch.object(preflight, "_resolve", forbidden), \
             mock.patch.object(preflight, "_tcp_connect", forbidden), \
             mock.patch.object(preflight, "_git_remote_reachable", forbidden):
            result = preflight.probe_repository_access(
                repo_root=Path(tmp),
                host="github.com",
                port=443,
                timeout=0.1,
                env={
                    "NETWORK": "caas_packages_only",
                    "HTTPS_PROXY": "https://proxy-user:proxy-secret@proxy.invalid:8443",
                    "AEGIS_TEST_REMOTE": "https://git-user:git-secret@github.com/Aegis-Omega/AEGIS-OMEGA.git",
                },
            )

        forbidden.assert_not_called()
        self.assertEqual(result["classification"], "SANDBOX_EGRESS_RESTRICTED")
        self.assertEqual(result["dns_probe"], "SKIPPED_BY_POLICY")
        self.assertEqual(result["tcp_probe"], "SKIPPED_BY_POLICY")
        self.assertEqual(result["git_remote_probe"], "SKIPPED_BY_POLICY")
        self.assertEqual(result["git_remote_configured"], "SKIPPED_BY_POLICY")
        self.assertFalse(result["connected_transport_invoked"])
        rendered = json.dumps(result, sort_keys=True)
        self.assertNotIn("proxy-secret", rendered)
        self.assertNotIn("git-secret", rendered)
        self.assertNotIn("proxy.invalid", rendered)

    def test_ground_truth_gates_network_fetch_through_preflight(self) -> None:
        source = (ROOT / "scripts" / "ground-truth.sh").read_text(encoding="utf-8")
        preflight_pos = source.index("repo_network_preflight.py")
        fetch_pos = source.index("git fetch -q origin main")

        self.assertLess(preflight_pos, fetch_pos)
        self.assertIn("--require-direct", source)
        self.assertIn('if [ "$PREFLIGHT_RC" -eq 0 ]; then', source)
        self.assertIn("repo-access:", source)


if __name__ == "__main__":
    main()
