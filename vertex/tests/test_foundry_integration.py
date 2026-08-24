"""Mocked integration coverage for Foundry policy and common metering parity."""
from decimal import Decimal
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import asyncio

from provider_policy import (
    Deployment, PolicyError, ProviderPolicy, TenantPolicy, append_metering,
)


def policy(*, budget="1.00", regions=frozenset({"eastus2"}), aliases=frozenset({"primary", "secondary"}), downgrade=True):
    return ProviderPolicy(
        {"primary": Deployment("primary", "foundry", "foundry:gpt-4.1", "eastus2", "https://server-only.example", "hidden-primary", "secondary"),
         "secondary": Deployment("secondary", "foundry", "foundry:gpt-4.1", "eastus2", "https://server-only.example", "hidden-secondary")},
        {"tenant-a": TenantPolicy("tenant-a", aliases, regions, Decimal(budget), Decimal("1.00"), downgrade)},
    )


def test_deployment_allowlist_and_server_secret_provenance():
    selected = policy().select("tenant-a", "primary", 100, 100)
    assert selected.deployment.endpoint == "https://server-only.example"
    assert selected.deployment.deployment_name == "hidden-primary"
    with pytest.raises(PolicyError, match="deployment_not_allowed"):
        policy(aliases=frozenset()).select("tenant-a", "primary", 1, 1)


def test_region_and_tenant_policy_enforced():
    with pytest.raises(PolicyError, match="tenant_not_entitled"):
        policy().select("unknown", "primary", 1, 1)
    with pytest.raises(PolicyError, match="region_not_allowed"):
        policy(regions=frozenset({"swedencentral"})).select("tenant-a", "primary", 1, 1)


def test_budget_exhaustion_rejects_after_configured_failover_is_exhausted():
    p = policy(budget="0.0001")
    p.record_usage("tenant-a", Decimal("0.0001"))
    with pytest.raises(PolicyError, match="budget_or_margin_exceeded"):
        p.select("tenant-a", "primary", 1, 1)


def test_common_metering_schema_has_anthropic_vertex_foundry_parity():
    async def run():
        entries = []
        async def append(observation, tier):
            entries.append((observation, tier))
            return {"entry_hash": str(len(entries))}
        for provider, region in (("anthropic", "global"), ("vertex", "us-central1"), ("foundry", "eastus2")):
            await append_metering(append, provider=provider, model="model", region=region, tenant_id="tenant-a", input_tokens=12, output_tokens=7, cost_usd=Decimal("0.01"), deployment_alias="primary" if provider == "foundry" else None)
        return entries
    entries = asyncio.run(run())
    assert all(set(entry[0]) == set(entries[0][0]) for entry in entries)
    assert [entry[0]["provider"] for entry in entries] == ["anthropic", "vertex", "foundry"]
