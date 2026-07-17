"""Server-side provider selection, commercial controls, and common usage ledger."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Awaitable, Callable


class PolicyError(Exception):
    def __init__(self, code: str, status_code: int = 403):
        super().__init__(code)
        self.code, self.status_code = code, status_code


@dataclass(frozen=True)
class ModelCatalogEntry:
    provider: str
    model: str
    input_usd_per_million: Decimal
    output_usd_per_million: Decimal
    capabilities: frozenset[str]
    regions: frozenset[str]
    latency_target_ms: int
    min_gross_margin: Decimal


# Pricing is deliberately an operational assumption, versioned in source and not
# supplied by callers. Review this catalog when provider pricing changes.
MODEL_CATALOG = {
    "anthropic:claude-opus-4-8": ModelCatalogEntry("anthropic", "claude-opus-4-8", Decimal("15"), Decimal("75"), frozenset({"chat", "tools", "vision"}), frozenset({"global"}), 8000, Decimal("0.35")),
    "vertex:claude-opus-4-8": ModelCatalogEntry("vertex", "claude-opus-4-8", Decimal("15"), Decimal("75"), frozenset({"chat", "tools", "vision"}), frozenset({"us-central1", "us-east5"}), 9000, Decimal("0.35")),
    "foundry:gpt-4.1": ModelCatalogEntry("foundry", "gpt-4.1", Decimal("2"), Decimal("8"), frozenset({"chat", "tools", "vision", "json"}), frozenset({"eastus2", "swedencentral"}), 6000, Decimal("0.40")),
}


@dataclass(frozen=True)
class Deployment:
    alias: str
    provider: str
    catalog_key: str
    region: str
    endpoint: str  # Loaded only from a deployment secret; never from a request.
    deployment_name: str  # Loaded only from a deployment secret; never from a request.
    failover_alias: str | None = None


@dataclass(frozen=True)
class TenantPolicy:
    tenant_id: str
    allowed_aliases: frozenset[str]
    allowed_regions: frozenset[str]
    budget_usd: Decimal
    sell_price_usd: Decimal
    allow_downgrade: bool = True


@dataclass(frozen=True)
class SelectedDeployment:
    deployment: Deployment
    catalog: ModelCatalogEntry
    estimated_cost_usd: Decimal


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def catalog_for(provider: str, model: str) -> ModelCatalogEntry | None:
    exact = MODEL_CATALOG.get(f"{provider}:{model}")
    if exact:
        return exact
    return next((entry for entry in MODEL_CATALOG.values() if entry.provider == provider and model.startswith(entry.model)), None)


def estimate_cost(catalog: ModelCatalogEntry, input_tokens: int, output_tokens: int) -> Decimal:
    return _money((Decimal(input_tokens) * catalog.input_usd_per_million + Decimal(output_tokens) * catalog.output_usd_per_million) / Decimal(1_000_000))


class ProviderPolicy:
    def __init__(self, deployments: dict[str, Deployment], tenants: dict[str, TenantPolicy], usage_usd: dict[str, Decimal] | None = None):
        self.deployments, self.tenants, self.usage_usd = deployments, tenants, usage_usd if usage_usd is not None else {}

    @classmethod
    def from_environment(cls) -> "ProviderPolicy":
        # Both values are injected from a secret manager deployment alias; they
        # intentionally contain all endpoint/deployment details server-side.
        raw_deployments = json.loads(os.environ.get("FOUNDRY_DEPLOYMENTS_JSON", "{}"))
        raw_tenants = json.loads(os.environ.get("FOUNDRY_TENANT_POLICIES_JSON", "{}"))
        deployments = {alias: Deployment(alias=alias, provider="foundry", catalog_key=value["catalog_key"], region=value["region"], endpoint=value["endpoint"], deployment_name=value["deployment_name"], failover_alias=value.get("failover_alias")) for alias, value in raw_deployments.items()}
        tenants = {tenant: TenantPolicy(tenant, frozenset(value["allowed_aliases"]), frozenset(value["allowed_regions"]), Decimal(str(value["budget_usd"])), Decimal(str(value["sell_price_usd"])), bool(value.get("allow_downgrade", True))) for tenant, value in raw_tenants.items()}
        return cls(deployments, tenants)

    def select(self, tenant_id: str, alias: str, input_tokens: int, output_tokens: int, capabilities: set[str] | None = None) -> SelectedDeployment:
        tenant = self.tenants.get(tenant_id)
        if tenant is None:
            raise PolicyError("tenant_not_entitled")
        attempted: set[str] = set()
        while alias and alias not in attempted:
            attempted.add(alias)
            deployment = self.deployments.get(alias)
            if deployment is None or deployment.provider != "foundry" or alias not in tenant.allowed_aliases:
                raise PolicyError("deployment_not_allowed")
            catalog = MODEL_CATALOG.get(deployment.catalog_key)
            if catalog is None or deployment.region not in tenant.allowed_regions or deployment.region not in catalog.regions:
                raise PolicyError("region_not_allowed")
            if capabilities and not capabilities.issubset(catalog.capabilities):
                raise PolicyError("capability_not_available")
            cost = estimate_cost(catalog, input_tokens, output_tokens)
            margin = (tenant.sell_price_usd - cost) / tenant.sell_price_usd if tenant.sell_price_usd else Decimal("-1")
            if self.usage_usd.get(tenant_id, Decimal("0")) + cost <= tenant.budget_usd and margin >= catalog.min_gross_margin:
                return SelectedDeployment(deployment, catalog, cost)
            if tenant.allow_downgrade:
                alias = deployment.failover_alias
                continue
            raise PolicyError("budget_or_margin_exceeded", 402)
        raise PolicyError("budget_or_margin_exceeded", 402)

    def record_usage(self, tenant_id: str, cost: Decimal) -> None:
        self.usage_usd[tenant_id] = _money(self.usage_usd.get(tenant_id, Decimal("0")) + cost)


async def append_metering(append: Callable[[dict], Awaitable[dict]], *, provider: str, model: str, region: str, tenant_id: str | None, input_tokens: int, output_tokens: int, cost_usd: Decimal, deployment_alias: str | None = None) -> dict:
    """Write every provider to the same immutable chain ledger schema."""
    return await append({"layer": "METERING", "provider": provider, "model": model, "region": region, "tenant_id": tenant_id, "deployment_alias": deployment_alias, "input_tokens": input_tokens, "output_tokens": output_tokens, "actual_cost_usd": str(_money(cost_usd))}, tier="T1")
