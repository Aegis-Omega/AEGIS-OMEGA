"""
AEGIS-Ω Managed Agents Registration
=====================================
Creates all 34 department agents as Anthropic Managed Agents (beta).
Run once — stores agent IDs in agent_registry.json.

Usage:
    python -m agents.register_managed [--force-recreate] [--department <id>]

Environment:
    ANTHROPIC_API_KEY  — required
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import yaml

REGISTRY_PATH = Path(__file__).parent / "agent_registry.json"
AGENTS_YAML = Path(__file__).parent / "agents.yaml"

# Tool definitions available to all agents
CONSTITUTIONAL_TOOLS: list[dict] = [
    {
        "type": "computer_use_20250124",  # computer use for engineering agents
        "display_width_px": 1920,
        "display_height_px": 1080,
    }
]

# Lightweight tools for non-engineering agents
STANDARD_TOOLS: list[dict] = []


def load_config() -> dict:
    with open(AGENTS_YAML) as f:
        return yaml.safe_load(f)


def load_registry() -> dict[str, str]:
    """Returns {department_id: agent_id}"""
    if REGISTRY_PATH.exists():
        with open(REGISTRY_PATH) as f:
            return json.load(f)
    return {}


def save_registry(registry: dict[str, str]) -> None:
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2)
    print(f"  Registry saved → {REGISTRY_PATH}")


def register_agents(force: bool = False, only: str | None = None) -> None:
    try:
        from anthropic import Anthropic
    except ImportError:
        print("ERROR: anthropic package not installed. Run: pip install anthropic>=0.52.0")
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set.")
        sys.exit(1)

    client = Anthropic(api_key=api_key)
    config = load_config()
    registry = load_registry()

    departments = config.get("departments", {})
    default_model = (
        config.get("backends", {}).get("anthropic", {}).get("default_model")
        or os.environ.get("AEGIS_DEFAULT_MODEL", "claude-opus-4-8")
    )

    created = 0
    skipped = 0
    failed = 0

    for dept_id, dept in departments.items():
        if only and dept_id != only:
            continue

        if dept_id in registry and not force:
            print(f"  ✓ {dept_id:30s} — already registered ({registry[dept_id][:24]}...)")
            skipped += 1
            continue

        name = dept.get("name", dept_id)
        system_prompt = dept.get("system_prompt", "").strip()
        max_tokens = dept.get("max_tokens", 8192)

        # Engineering-tier agents get richer tooling
        tier = dept.get("tier", 3)
        tools = CONSTITUTIONAL_TOOLS if tier <= 1 else STANDARD_TOOLS

        print(f"  Creating: {dept_id:30s} (tier={tier}, max_tokens={max_tokens})", end="", flush=True)

        try:
            agent = client.beta.agents.create(
                name=f"AEGIS {name}",
                model=default_model,
                system=system_prompt,
                description=f"AEGIS-Ω autonomous {name} function. Constitutional governance: AdaptivePower(T) ≤ ReplayVerifiability(T).",
                metadata={
                    "department_id": dept_id,
                    "tier": str(tier),
                    "max_tokens": str(max_tokens),
                    "aegis_version": "2.0.0",
                    "constitutional_law": "AdaptivePower(T)<=ReplayVerifiability(T)",
                },
            )
            registry[dept_id] = agent.id
            save_registry(registry)
            print(f" → {agent.id}")
            created += 1

            # Rate limit: avoid hammering the API
            time.sleep(0.5)

        except Exception as exc:
            print(f" FAILED: {exc}")
            failed += 1

    print(f"\n{'─'*60}")
    print(f"  Created: {created}  |  Skipped: {skipped}  |  Failed: {failed}")
    print(f"  Registry: {REGISTRY_PATH}")

    if failed:
        sys.exit(1)


def list_agents() -> None:
    try:
        from anthropic import Anthropic
    except ImportError:
        print("ERROR: anthropic package not installed.")
        sys.exit(1)

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    registry = load_registry()

    print(f"{'Department':30s} {'Agent ID':35s} {'Status'}")
    print("─" * 80)
    for dept_id, agent_id in registry.items():
        try:
            agent = client.beta.agents.retrieve(agent_id)
            status = "active" if not getattr(agent, "archived_at", None) else "archived"
            print(f"  {dept_id:28s} {agent_id:33s} {status}")
        except Exception as e:
            print(f"  {dept_id:28s} {agent_id:33s} ERROR: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Register AEGIS Managed Agents")
    parser.add_argument("--force-recreate", action="store_true", help="Recreate even if already registered")
    parser.add_argument("--department", help="Register only this department")
    parser.add_argument("--list", action="store_true", help="List registered agents")
    args = parser.parse_args()

    print("\nAEGIS-Ω Managed Agents Registration")
    print("=" * 60)

    if args.list:
        list_agents()
    else:
        register_agents(force=args.force_recreate, only=args.department)


if __name__ == "__main__":
    main()
