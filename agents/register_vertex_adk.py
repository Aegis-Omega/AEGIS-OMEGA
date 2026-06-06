"""
AEGIS-Ω Google Cloud Agent Platform (ADK) Registration
========================================================
Deploys all 34 department agents to Google Cloud Vertex AI Agent Platform
using the Agent Development Kit (ADK).

Project: aegisomegav1
ADK Console: https://console.cloud.google.com/agent-platform/adk?project=aegisomegav1

Two deployment modes:
  1. CONSTITUTIONAL PROXY MODE (default):
     Each agent calls the AEGIS constitutional proxy (Cloud Run) which wraps
     Claude via anthropic.AnthropicVertex. Full hash-chain governance preserved.

  2. DIRECT VERTEX MODE:
     Each agent calls AnthropicVertex directly. No constitutional proxy — only
     for development/testing. Production always uses constitutional proxy.

Usage:
    python -m agents.register_vertex_adk [--mode proxy|direct] [--department <id>]
    python -m agents.register_vertex_adk --validate    # health check only

Environment:
    VERTEX_PROJECT_ID   — GCP project (default: aegisomegav1)
    VERTEX_REGION       — Vertex region (default: us-east5)
    ANTHROPIC_API_KEY   — required for direct mode
    PROXY_URL           — constitutional proxy URL (required for proxy mode)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import yaml

REGISTRY_PATH = Path(__file__).parent / "vertex_agent_registry.json"
AGENTS_YAML = Path(__file__).parent / "agents.yaml"

DEFAULT_PROJECT = "aegisomegav1"
DEFAULT_REGION = "us-east5"


def load_config() -> dict:
    with open(AGENTS_YAML) as f:
        return yaml.safe_load(f)


def load_registry() -> dict[str, dict]:
    """Returns {department_id: {agent_id, endpoint, deployed_at}}"""
    if REGISTRY_PATH.exists():
        with open(REGISTRY_PATH) as f:
            return json.load(f)
    return {}


def save_registry(registry: dict) -> None:
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2)


def validate_connection(project: str, region: str) -> bool:
    """Validate Vertex AI Claude connection."""
    print(f"  Validating Vertex AI connection: project={project}, region={region}")
    try:
        import anthropic
        client = anthropic.AnthropicVertex(project_id=project, region=region)
        response = client.messages.create(
            model="claude-opus-4-8@001",
            max_tokens=32,
            messages=[{"role": "user", "content": "respond with: CONSTITUTIONAL_OK"}],
        )
        text = response.content[0].text if response.content else ""
        ok = "CONSTITUTIONAL_OK" in text
        if ok:
            print(f"  ✓ Vertex AI Claude connection: OK (model={response.model})")
        else:
            print(f"  ✗ Unexpected response: {text}")
        return ok
    except ImportError:
        print("  ERROR: anthropic[vertex] not installed. Run: pip install anthropic[vertex]")
        return False
    except Exception as exc:
        print(f"  ERROR: {exc}")
        return False


def deploy_agent_adk(
    dept_id: str,
    dept: dict,
    project: str,
    region: str,
    mode: str,
    proxy_url: str,
    registry: dict,
) -> bool:
    """
    Deploy one department agent to Google Cloud Agent Platform via ADK.

    In proxy mode: agent uses AEGIS constitutional proxy endpoint.
    In direct mode: agent calls AnthropicVertex directly.
    """
    name = dept.get("name", dept_id)
    system_prompt = dept.get("system_prompt", "").strip()
    max_tokens = dept.get("max_tokens", 8192)
    tier = dept.get("tier", 3)
    capabilities = dept.get("capabilities", [])

    # Try to use the google-cloud-aiplatform ADK if available
    try:
        import vertexai
        from vertexai import agent_builder  # type: ignore[attr-defined]

        vertexai.init(project=project, location=region)

        # Create an ADK agent configuration
        agent_config = {
            "display_name": f"AEGIS {name}",
            "description": (
                f"AEGIS-Ω autonomous {name} function. "
                f"Constitutional governance: AdaptivePower(T) ≤ ReplayVerifiability(T). "
                f"Tier {tier} | {', '.join(capabilities[:3])}"
            ),
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
        }

        # In proxy mode, the agent's inference goes through the constitutional proxy
        if mode == "proxy" and proxy_url:
            # The ADK agent extension points to our constitutional proxy
            agent_config["tools"] = [
                {
                    "function_declarations": [
                        {
                            "name": "constitutional_inference",
                            "description": "Route inference through AEGIS constitutional governance proxy",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "task": {"type": "string", "description": "The task to execute"},
                                    "tier": {"type": "string", "enum": ["T0", "T1", "T2", "T3"]},
                                },
                                "required": ["task"],
                            },
                        }
                    ]
                }
            ]

        print(f"  Deploying to ADK: {dept_id:30s} (tier={tier})", end="", flush=True)

        # Note: actual ADK agent creation API varies by SDK version.
        # Using the Reasoning Engine path as the most stable Vertex AI agent deployment.
        from vertexai.preview import reasoning_engines  # type: ignore[attr-defined]

        class ConstitutionalAgent:
            """AEGIS constitutional agent wrapped for Vertex AI Reasoning Engine."""

            def __init__(self, dept_id: str, system_prompt: str, proxy_url: str, mode: str):
                self.dept_id = dept_id
                self.system_prompt = system_prompt
                self.proxy_url = proxy_url
                self.mode = mode

            def query(self, task: str) -> dict:
                import httpx

                if self.mode == "proxy" and self.proxy_url:
                    resp = httpx.post(
                        f"{self.proxy_url}/v1/messages",
                        json={
                            "model": "claude-opus-4-8",
                            "max_tokens": max_tokens,
                            "system": self.system_prompt,
                            "messages": [{"role": "user", "content": task}],
                            "thinking": {"type": "adaptive"},
                        },
                        timeout=120,
                    )
                    resp.raise_for_status()
                    return resp.json()
                else:
                    import anthropic
                    client = anthropic.AnthropicVertex(
                        project_id=project, region=region
                    )
                    response = client.messages.create(
                        model="claude-opus-4-8@001",
                        max_tokens=max_tokens,
                        system=self.system_prompt,
                        messages=[{"role": "user", "content": task}],
                        thinking={"type": "adaptive"},
                    )
                    return {
                        "content": [{"type": "text", "text": b.text}
                                    for b in response.content
                                    if hasattr(b, "text")],
                        "model": response.model,
                        "usage": {"input_tokens": response.usage.input_tokens,
                                  "output_tokens": response.usage.output_tokens},
                    }

        agent_instance = ConstitutionalAgent(
            dept_id=dept_id,
            system_prompt=system_prompt,
            proxy_url=proxy_url,
            mode=mode,
        )

        engine = reasoning_engines.ReasoningEngine.create(
            agent_instance,
            requirements=["anthropic[vertex]>=0.52.0", "httpx>=0.27.0"],
            display_name=f"aegis-{dept_id.replace('_', '-')}",
            description=agent_config["description"],
        )

        registry[dept_id] = {
            "reasoning_engine_id": engine.resource_name,
            "project": project,
            "region": region,
            "mode": mode,
            "tier": tier,
            "deployed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        save_registry(registry)
        print(f" → {engine.resource_name.split('/')[-1]}")
        return True

    except ImportError:
        # Fallback: register as constitutional proxy client (no actual ADK deployment)
        print(f" → proxy-client (ADK SDK not available)")
        registry[dept_id] = {
            "mode": "proxy_client",
            "proxy_url": proxy_url,
            "project": project,
            "region": region,
            "tier": tier,
            "dept_id": dept_id,
            "deployed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        save_registry(registry)
        return True

    except Exception as exc:
        print(f" FAILED: {exc}")
        return False


def register_all(mode: str, only: str | None, force: bool) -> None:
    project = os.environ.get("VERTEX_PROJECT_ID", DEFAULT_PROJECT)
    region = os.environ.get("VERTEX_REGION", DEFAULT_REGION)
    proxy_url = os.environ.get("PROXY_URL", "http://localhost:8080")

    print(f"\nAEGIS-Ω Vertex AI ADK Registration")
    print(f"Project: {project}  |  Region: {region}  |  Mode: {mode}")
    print("=" * 60)

    # Validate connection first
    if not validate_connection(project, region):
        print("\nERROR: Vertex AI connection failed. Check VERTEX_PROJECT_ID and credentials.")
        sys.exit(1)

    config = load_config()
    departments = config.get("departments", {})
    registry = load_registry()

    created = 0
    skipped = 0
    failed = 0

    for dept_id, dept in departments.items():
        if only and dept_id != only:
            continue
        if dept_id in registry and not force:
            print(f"  ✓ {dept_id:30s} — already deployed")
            skipped += 1
            continue

        ok = deploy_agent_adk(dept_id, dept, project, region, mode, proxy_url, registry)
        if ok:
            created += 1
        else:
            failed += 1

        time.sleep(1.0)  # avoid quota exhaustion

    print(f"\n{'─'*60}")
    print(f"  Deployed: {created}  |  Skipped: {skipped}  |  Failed: {failed}")
    print(f"  Registry: {REGISTRY_PATH}")
    print(f"  ADK Console: https://console.cloud.google.com/agent-platform/adk?project={project}")

    if failed:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Register AEGIS agents on Vertex AI ADK")
    parser.add_argument("--mode", choices=["proxy", "direct"], default="proxy",
                        help="proxy=through constitutional proxy (default), direct=AnthropicVertex")
    parser.add_argument("--department", help="Deploy only this department")
    parser.add_argument("--force-recreate", action="store_true")
    parser.add_argument("--validate", action="store_true", help="Validate connection only")
    args = parser.parse_args()

    project = os.environ.get("VERTEX_PROJECT_ID", DEFAULT_PROJECT)
    region = os.environ.get("VERTEX_REGION", DEFAULT_REGION)

    if args.validate:
        ok = validate_connection(project, region)
        sys.exit(0 if ok else 1)

    register_all(mode=args.mode, only=args.department, force=args.force_recreate)


if __name__ == "__main__":
    main()
