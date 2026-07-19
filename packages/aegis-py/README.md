# aegis-omega

Python SDK and `aegis` CLI for the AEGIS-Ω Platform — governed multi-agent AI
with a constitutional audit trail. Every call returns a
[`PlatformEnvelope`](https://aegisomega.com/platform) (contract version `1.0.0`)
carrying an `audit_chain_hash` and a `chain_valid` flag.

- Zero required dependencies — the synchronous client uses only the standard
  library (`urllib`).
- Optional `aiohttp`-based async client (`pip install aegis-omega[async]`).
- Python 3.10+.

## Install

```bash
pip install -e .            # from this directory
# or, with the async client:
pip install -e ".[async]"
```

This registers the `aegis` console script.

## CLI

```
aegis <command> [options]

Commands:
  status                     Check platform health (no auth required)
  collaborate <objective>    Synchronous 39-department swarm
  execute <objective>        Async execution with a live SSE event stream
  get <execution_id>         Fetch a completed execution by ID
  delete <execution_id>      Remove a stored execution

Global options:
  --key API_KEY              API key (default: $AEGIS_API_KEY)
  --base URL                 Base URL override (default: $AEGIS_BASE_URL or production)
  --json                     Output raw JSON
  --timeout SECS             Request timeout (default: 60)
```

`collaborate` and `execute` accept `--mode` (one of `revenue`, `analysis`,
`gtm`, `retention`, `competitive`, `technical`, `regulatory`, `fundraising`;
default `analysis`) and `--live` (live Claude inference instead of demo mode).

### Environment

| Variable          | Purpose                                                        |
|-------------------|----------------------------------------------------------------|
| `AEGIS_API_KEY`   | API key for authenticated commands (or pass `--key`).          |
| `AEGIS_BASE_URL`  | Override the platform base URL (default: production endpoint).  |

`status` is public and needs no key; all other commands require one.

### Examples

```bash
aegis status
aegis collaborate "Enter EU fintech market Q4 2026" --mode gtm
aegis execute "Design a retention program" --mode retention
aegis get <execution_id>
```

## Library

Synchronous client (standard library only):

```python
from aegis import AegisClient

client = AegisClient("aegis_your_key")            # or AEGIS_API_KEY via CLI
status = client.status()                          # public, no key needed
result = client.collaborate("Enter EU fintech market Q4 2026", mode="gtm")

print(result.constitutional_audit.verdict)        # "APPROVED" | "FLAG" | "QUARANTINE"
print(result.departments_collaborated)            # 39
print(result.chain_valid, result.audit_chain_hash)
```

Async client (requires `aiohttp`):

```python
from aegis import AsyncAegisClient

async with AsyncAegisClient("aegis_your_key") as client:
    result = await client.collaborate("Enter EU fintech market Q4 2026", mode="gtm")
    print(result.constitutional_audit.verdict)
```

Both clients target the same `/platform/*` endpoints and validate the
`PlatformEnvelope` contract version on every response; a mismatch raises
`AegisError`.

## License

MIT
