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
  work validate|plan|simulate|verify|export [pack]

Global options:
  --key API_KEY              API key (default: $AEGIS_API_KEY)
  --base URL                 Base URL override (default: $AEGIS_BASE_URL or production)
  --json                     Output raw JSON
  --timeout SECS             Request timeout (default: 60)
```

`collaborate` and `execute` accept `--mode` (one of `revenue`, `analysis`,
`gtm`, `retention`, `competitive`, `technical`, `regulatory`, `fundraising`;
default `analysis`) and `--live` (live Claude inference instead of demo mode).

### Offline workflow packs

The local `aegis work` commands need no API key and make no network requests.
They accept a bundled `code`, `data`, or `science` sample, or a path to a local
JSON pack. All pack permissions are `read_only`; the CLI never executes steps
or writes files. `simulate` marks steps `NOT_EXECUTED` and criteria
`NOT_EVALUATED`. `verify` checks embedded artifact SHA-256 digests only; it
does not establish source authenticity, scientific validity, or task success.
`export` writes deterministic compact JSON to standard output.

```bash
unset AEGIS_API_KEY
aegis work validate code
aegis work plan data
aegis work simulate science
aegis work verify code
aegis work export data
```

The JSON contract uses `schema: "aegis.workflow-pack/1"` and fields `pack_id`,
`domain`, `permissions`, `objective`, `steps`, `acceptance`, and `artifacts`.
Each artifact embeds text content and its lowercase SHA-256 digest. The
`migrate_pack()` Python API upgrades the legacy
`aegis.workflow-pack/0` shape by adding only `permissions: "read_only"`; it
refuses a v0 pack that already declares permissions.

The corresponding TypeScript shape is:

```ts
type WorkflowPackV1 = {
  schema: "aegis.workflow-pack/1";
  pack_id: string;
  domain: "code" | "data" | "science";
  permissions: "read_only";
  objective: string;
  steps: { id: string; description: string }[];
  acceptance: { id: string; criterion: string }[];
  artifacts: {
    id: string; media_type: string; content: string; sha256: string;
  }[];
};
```

Python callers can import `get_pack`, `validate_pack`, `plan_pack`,
`simulate_pack`, `export_pack`, and `migrate_pack` from `aegis.work`; samples
are importable from `aegis.packs`. Packs and sample observations are
synthetic, and no new runtime dependencies are introduced.

CLI output is plain JSON with no color or interactive prompts, suitable for
redirection and assistive-technology workflows. This documentation does not
claim WCAG conformance or user-tested accessibility; the command interface is
not a graphical UI.

The SDK's package metadata declares MIT and has no required runtime
dependencies (`packages/aegis-py/pyproject.toml`); this workflow feature uses
only the Python standard library. The repository root is separately licensed
AGPL-3.0, so confirm the intended distribution license before republishing
files outside this package.

### Environment

| Variable          | Purpose                                                        |
|-------------------|----------------------------------------------------------------|
| `AEGIS_API_KEY`   | API key for authenticated commands (or pass `--key`).          |
| `AEGIS_BASE_URL`  | Override the platform base URL (default: production endpoint).  |

`status` and offline `work` commands need no key; authenticated service
commands require one.

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
