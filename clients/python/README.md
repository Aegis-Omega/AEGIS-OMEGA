# aegis-omega — Python SDK

Python client for the **AEGIS-Ω Agent Platform**: 39 Mythos-level governed agents,
constitutional AI governance, and replay-certifiable audit chains.

## Install

```bash
pip install aegis-omega
```

Requires Python ≥ 3.10 and `httpx` ≥ 0.27.

---

## Quick start

```python
from aegis_omega import Platform

p = Platform(
    api_key="sk-your-key-here",
    base_url="https://aegis-vertex.aegisomega.com",   # Cloudflare Worker custom domain
)
```

### Collaborate — full multi-department pipeline

```python
result = p.collaborate("Launch a SaaS product targeting SMBs", mode="revenue", live=False)

print(result.cycle_id)                          # "cyc_abc123"
print(result.chain_valid)                       # True — governance chain intact
print(result.projection.first_year_arr_usd)     # 480000.0
print(result.projection.tier)                   # "growth"
print(result.projection.kan_score)              # 0.87

for stage in result.stages:
    print(f"[{stage.stage}] {stage.role}: {stage.output[:80]}")
```

### Stream — real-time SSE pipeline

```python
for event in p.stream("Generate a go-to-market strategy", live=True):
    if event.done:
        print("chain_valid:", event.chain_valid)
        break
    print(f"[stage {event.stage}] {event.role}: {event.output}")
```

### Agent — single governed agent by role

```python
result = p.agent(role="Prometheus", task="Identify the top 3 growth levers", cycles=3)

print(result.is_valid)          # True
print(result.ralph_cycles)      # 3
print(result.duration_ms)       # 2340.5
print(result.output)
print(result.governance)        # {"envelope_id": "...", "tier": "T2", ...}
```

### Certify — audit chain integrity

```python
cert = p.certify()
print(cert.is_valid)        # True
print(cert.entry_count)     # 1024
print(cert.terminal_hash)   # "a3f8c..."
```

### Catalog — agent roster

```python
cat = p.catalog()
print(cat.agent_count)      # 39
print(cat.mythos_count)     # 39
for agent in cat.agents:
    print(agent["role"], "-", agent.get("description", ""))
```

### Status — platform health

```python
info = p.status()
print(info)    # raw dict — schema is platform-version-dependent
```

### Schedule revenue — recurring run

```python
schedule = p.schedule_revenue(objective="Maximise MRR Q3 2026", live=True)
print(schedule["schedule_id"])
print(schedule["next_run"])
```

---

## Method signatures

```python
class Platform:
    def __init__(self, api_key: str, base_url: str = "https://aegis-vertex.aegisomega.com", timeout: float = 120.0) -> None: ...

    def collaborate(self, objective: str, mode: str = "revenue", live: bool = False) -> CollaborateResult: ...
    def stream(self, objective: str, live: bool = False) -> Iterator[StreamEvent]: ...
    def agent(self, role: str, task: str, cycles: int = 3) -> AgentResult: ...
    def catalog(self) -> CatalogResult: ...
    def certify(self) -> CertifyResult: ...
    def status(self) -> dict: ...
    def schedule_revenue(self, objective: str | None = None, live: bool = True) -> dict: ...

    # Context manager
    def close(self) -> None: ...
    def __enter__(self) -> Platform: ...
    def __exit__(self, *_) -> None: ...
```

### Return types

| Type | Key fields |
|------|------------|
| `CollaborateResult` | `mode`, `cycle_id`, `objective`, `departments_collaborated`, `chain_valid`, `projection`, `stages`, `live` |
| `StreamEvent` | `done`, `stage`, `role`, `output`, `envelope_id`, `projection`, `cycle_id`, `chain_valid` |
| `AgentResult` | `task_id`, `role`, `output`, `ralph_cycles`, `duration_ms`, `is_valid`, `governance` |
| `CatalogResult` | `platform`, `agent_count`, `mythos_count`, `agents`, `pricing_tiers` |
| `CertifyResult` | `is_valid`, `entry_count`, `terminal_hash` |
| `RevenueProjection` | `first_year_arr_usd`, `tier`, `kan_score`, `governed_note`, `assumptions` |
| `StageResult` | `stage`, `role`, `output`, `envelope_id` |

All types expose a `from_dict(d)` classmethod factory.

---

## Error handling

```python
from aegis_omega import PlatformError

try:
    result = p.collaborate("...")
except PlatformError as e:
    print(e.status_code)   # e.g. 401, 429, 503
    print(e.detail)        # human-readable message from the platform
```

---

## Constitutional governance

Every response from the AEGIS-Ω platform is hash-chained and replay-certifiable:

- **`chain_valid: True`** — the governance audit chain is intact end-to-end. No tampering or replay divergence was detected.
- **`tier`** tags on `RevenueProjection` and agent `governance` envelopes indicate the epistemic certainty class of the output (T0 = mechanically proven, T1 = empirically validated, T2 = engineering hypothesis).
- **`certify()`** walks the terminal hash of the entire session ledger. A `CertifyResult` with `is_valid=False` means the chain has been corrupted and the session output should not be trusted.

---

## Context manager usage

```python
with Platform(api_key="sk-...", base_url="https://aegis-vertex.aegisomega.com") as p:
    result = p.collaborate("Build a governed revenue pipeline")
    print(result.chain_valid)
# HTTP client is automatically closed
```

---

## Links

- Platform: <https://aegisomega.com>
- API reference: <https://aegisomega.com/docs/api>
- Constitutional governance spec: <https://aegisomega.com/docs/governance>
