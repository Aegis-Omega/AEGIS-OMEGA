#!/usr/bin/env python3
"""Inspect the existing AEGIS fleet and shared connection configuration. No writes."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def probe(service):
    result = {"name": service["name"], "url": service["url"], "reachable": False}
    try:
        request = urllib.request.Request(service["url"], headers={"User-Agent": "aegis-operations/1"})
        with urllib.request.urlopen(request, timeout=12) as response:
            result["http_status"] = response.status
            result["reachable"] = response.status == 200
            if service["name"] == "bridge":
                payload = json.loads(response.read(1_048_576))
                if not isinstance(payload, dict):
                    raise ValueError("Malformed platform response")
                data = payload.get("data", payload)
                if not isinstance(data, dict):
                    raise ValueError("Malformed platform response")
                result["chain_valid"] = data.get("chain_valid")
                result["registered_agents"] = data.get("total_agents")
                result["reachable"] = result["reachable"] and data.get("chain_valid") is True
    except urllib.error.HTTPError as error:
        result["http_status"] = error.code
    except (OSError, ValueError) as error:
        result["error_class"] = type(error).__name__
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Check source bindings without network requests")
    args = parser.parse_args()
    manifest_bytes = (ROOT / "infrastructure/production.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    errors = []
    for path in list(manifest["sources"].values()) + [s["source"] for s in manifest["services"]]:
        if not (ROOT / path).exists():
            errors.append("Missing source: " + path)
    root_mcp = json.loads((ROOT / ".mcp.json").read_text())
    nested_mcp = json.loads((ROOT / "sovereign-omega-v2/.mcp.json").read_text())
    if root_mcp != nested_mcp:
        errors.append("Root and runtime MCP configurations differ")
    ids = json.loads((ROOT / manifest["sources"]["managed_agent_ids"]).read_text())
    report = {
        "repository": manifest["repository"],
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "working_tree_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "configuration_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "configuration_valid": not errors,
        "errors": errors,
        "managed_agent_ids": len(ids),
        "declared_mcp_connections": sorted(root_mcp["mcpServers"]),
        "scope": "configuration_and_http_reachability_only",
    }
    if not args.offline:
        with ThreadPoolExecutor(max_workers=5) as pool:
            report["services"] = list(pool.map(probe, manifest["services"]))
        report["all_services_reachable"] = all(s["reachable"] for s in report["services"])
    print(json.dumps(report, indent=2))
    return 0 if not errors and report.get("all_services_reachable", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
