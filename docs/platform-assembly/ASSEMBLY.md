# AEGIS Omega Labs: existing platform assembly

Observed 2026-10-16. This is a source-bound assembly candidate, not a production release.

## Existing spine to reuse

| Layer | Existing source | Connection |
|---|---|---|
| Web entry and paid products | `hub/`, `platform-picker/`, `hook-generator/`, `content-calendar/` | Existing Hub routes, AccessGate and payment edge functions |
| Cross-platform API | `packages/shared/lib/platform-contract.ts`, `platform-client.ts` | Authenticated `/platform/status`, `/platform/executions`, result retrieval and SSE |
| Execution | `sovereign-omega-v2/python/bridge.py`, `vertex/serve.py`, `worker-src/index.ts` | Existing HTTP execution services; actual serving revision must be checked |
| Provider routing | `packages/shared/lib/inference-router.ts`, PR #598 native mesh | Keep server credentials on server; Apple model is an additional device adapter |
| Persistence | `supabase/migrations/` | Existing customer/access, activities, memory, fitness and signed control-plane events |
| Native devices | `clients/gemma-edge-ios/`, `clients/gemma-holon/`, Go/Python/Shell/Sheets clients | Reuse protocols and API; native Gemma implementation currently documented as fail-closed/unimplemented |
| Memory continuity | PR #729 | Existing IndexedDB EventStore + WorkspaceMemorySpine; not cross-device sync |
| Evidence | Existing envelopes, offline verifier, Python receipts PR #743 | Bind actual outcomes and artifacts, not model declarations |

## Exact candidates inspected

| PR | Exact source head | Integration role | Current boundary |
|---|---|---|---|
| #725 | `413394727972e31dcce4e4c127596da25c881d9d` | Product routing/build/release base for this candidate | Draft, unsigned; production routing still wrong |
| #723 | `249763ec9330a379b99cdabbd831378b49e7c61c` | Authenticated console; isolate demo writes; chain validation before persistence | Prior independent exact-file replay reported; no live execution admission |
| #724 | `957ef8a235ffec320f03c9a423f85c4a68291c26` | Runtime capability truth endpoint | Source implementation; hosted execution pending |
| #729 | `e059bb892ba0a3ae96630d0393295eb993fb7b2a` | Durable local workspace memory | Same-origin persistence, not global memory |
| #598 | `0030ef8114073b82cff2cfb5095d6cf1e0f227d1` | Native SDK provider mesh | Different stacked base; cannot blindly merge into main |

These changes have NOT all been merged or jointly tested. Integrate by dependency closure and run their actual tests before release. 656 fetched remote refs are indexed by the generator; their presence is not a review of all branch contents. The organization connector returned nine repositories; private source findings must not be copied into public snapshots.

## SQL already exists

Repository migration declarations include `purchases`, `revenue_cycles`, `platform_api_keys`, `agent_activity`, `api_key_store`, `swarm_memory`, `department_fitness_tracking`, `dept_graces`, `grace_events`, `agent_api_profiles`, `github_sponsors`, `scale_os_event_envelopes_v1`, and `scale_os_approval_projection_v1`. Some migrations redeclare the same public table. Do not create parallel replacement tables. The generated snapshot records migration/blob provenance. Actual applied schema, backups, row counts and live provider availability remain UNKNOWN.

## Concrete production findings and delta

- Fresh public HTTP probes returned Hub HTML on both product domains. The existing product-surface gate independently returns WRONG_PRODUCT; see adjacent receipt. HTTP 200 is not a working product.
- Public API `/platform/status` and `/telemetry` returned HTTP 403 from this host. This does not prove the API is down or that no customer can access it.
- Issue #736 records an earlier missing server-side provider key. Current secret configuration was not inspected; do not assume the older observation remains current.
- Release script previously copied DASHSCOPE_KEY into VITE_DASHSCOPE_API_KEY for public deployment. This candidate removes that forwarding and rejects four provider-key environment variables before builds. It does not inspect or change existing Vercel secrets, old bundles or credentials; historical exposure is not established.
- Existing frontend router still has legacy direct-provider paths. Their removal/migration to the existing authenticated server is a separate required production gate. Removing key forwarding alone does not establish secure inference or working inference.
- Removed stale Lemon Squeezy setup instructions from this release script. Existing PayPal/Stripe/Sponsors handlers require a real bounded checkout/access/inference test before revenue can be asserted.

## Repeatable inventory

`python3 scripts/platform_inventory.py --output /tmp/aegis-platform-inventory.json`

Stdlib only. Inventories tracked files, npm package scripts, SQL table declarations with Git blob IDs, native-client manifests and fetched remote refs. Records base head/tree and dirty state. No DB connection, secrets, inference, deploy, payment, or production writes. This complements `scripts/integration_ledger.py`; it does not replace capability authorization or claim deployed readiness.

## Validation and release gates

- Existing product-surface tests: 8/8 pass.
- Real release-shell behavior in isolated fake-command environment: 5/5 pass (no credential forwarding, reject public provider key, stop on npm failure, stop on deployment failure, reject wrong public surface).
- Shell syntax and diff whitespace checks pass.
- Actual paid checkout, live model call, durable provider DB write, full frontend build and integrated branch replay: NOT PERFORMED by this candidate.
- Protected main and RH branches remain untouched. Candidate is reviewable; signed source admission, required checks and the final explicit production release decision still apply. No billing unlock or paid usage was enabled.

## Cross-repository catalog — implemented and locally exercised

`public-sources-20261016.json` records 4,586 file references across five public repositories, each with exact source revision and blob identity. Source references are connected without copying code into a new monolith. This snapshot covers selected default branches, not every branch or every private repository.

```bash
python3 scripts/source_catalog.py --database /tmp/aegis-sources.sqlite \
  --snapshot docs/platform-assembly/public-sources-20261016.json
python3 scripts/source_catalog.py --database /tmp/aegis-sources.sqlite --search platform-client
```

The local metadata database contains `source_snapshots` and `source_assets`; these are an offline search index, not replacement production/customer tables. Duplicate file content remains linked to each original source. Searches open SQLite read-only and parameterize user queries. Incomplete trees, duplicate source/path identities, invalid revision/blob IDs and traversal paths are rejected before the previous index can be replaced. Private metadata requires explicit local opt-in and is not included in this public snapshot. Manifest hashes establish source identity, not authorization or semantic correctness.

Catalog tests: 3 test methods pass, including five rejection subcases and cross-repository duplicate-content identity. Combined with five release-shell behavior tests and eight existing product-surface tests: 16 methods pass. All external calls in release tests are isolated doubles; the separate public product-surface receipt is a real HTTP observation.

Protocol targets for adapters: reuse existing MCP/A2A lanes (#756/#716/#767), negotiate explicit supported versions, and separate resource/tool discovery from execution authorization. Official references reviewed: https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/basic/index.mdx and https://github.com/a2aproject/A2A/blob/main/docs/specification.md . No protocol compliance or current frontier superiority is claimed from this catalog alone.

## Recovered existing AlphaEvolve estate

The prior AlphaEvolve inventory has been located, rather than replaced: `docs/AEGIS_ALPHAEVOLVE_CORPUS_WIDE_V1.md` on PR #773 at `e8ef80ec6d99aa4bb645da3aa5bb10fecec7590f` records **67,445 indexed objects**, **32,841 unique evaluated representation assets**, **34,476 aliases**, **67 sensitive metadata-only records**, and **61 quarantined records**. The archived Global Coverage V1 note records 8,805 nondependency research assets and 59,256 planned work slots. These are historical source-scoped observations, not a new execution of the original DB.

The public metadata snapshot now additionally includes the entire #773 source tree: **6,554 source-file references across six revisions of five repositories**, including existing AlphaEvolve evaluators, frontier router and generation ledger. Counts include source references across revisions, not 6,554 distinct content hashes.

`source_catalog.py --alpha-corpus /authorized/local/corpus.sqlite --search QUERY --database /tmp/aegis-sources.sqlite` queries the original master `objects` table alongside Git references. It does not copy corpus bytes, change import/quarantine status, schedule experiments or create another evolution engine. The adapter validates the known column schema and opens the supplied SQLite DB read-only. Two additional tests verify existing-schema lookup, preserved quarantine, unchanged DB bytes, literal query handling, and refusal of missing/unsupported input. Total focused test methods: **18**. Adapter tests use a fixture until the actual archived DB is materialized and inspected.

### Actual archive connection verified

Recovered `AEGIS_AlphaEvolve_Full_Corpus_Evidence_v1.zip` (SHA-256 `1b5ba31d5c8cc99970ae8aaef9860318cc889ef9bac51bf613e720f78174dfac`) and inspected its existing `AEGIS_evolution_67445.sqlite` database. Actual read-only queries returned 32,841 assets, 67,445 coverage records and 98,418 trial records; `PRAGMA integrity_check` returned `ok`. A real adapter query returned five quantum metadata matches, and full DB SHA-256 was unchanged afterward. This is a new database integrity/count/query check, not a replay of the historical 98,418 trials or source bytes. Aggregate-only receipt: `alpha-catalog-connection-20261016.json`. Raw DB and source names remain outside Git.

The same adapter supports the original master `objects` schema and the existing evaluated `assets` + `coverage` schema. It preserves representation status separately from scientific evaluation status and retains alias counts. Catalog tests are now 6 methods; total focused release/catalog/product tests are **19**. The earlier fixture-only limitation is superseded for this specific archived database connection; live production integration remains unperformed.


## Connector-aware local source snapshots (UWP-08, Issue #756)

This extends the EXISTING local SQLite source catalog in scripts/source_catalog.py,
not a second registry, database or runtime. Authorized provider reads are made
separately by connected tools. This code only ingests a bounded, explicit local
JSON metadata snapshot; it cannot fetch remote data or grant tool authority.

Supported input fields: schema_version=1, observed_at (timezone required), and
connectors[] with provider, resource_kind, source_ref, visibility, status and
source_revision. A resource reference must be an OPAQUE sha256:<64 lower-case
hex digits> token, never a provider-native ID, name, URL or credential.
source_revision is null or a 40-character git commit SHA. For connector-level
denials or empty organization lists, source_ref may be null.

States: CONNECTED_AND_VERIFIED, AVAILABLE_UNTESTED, NOT_CONNECTED, DENIED,
STALE. A successful metadata lookup does NOT establish a working model call,
paid service, MCP OAuth, remote execution, approval or production readiness.
The local search computes effective_status=STALE when evidence is older than
the specified freshness window (default 24 h) or timestamp is in the future.

Example CLI (only explicit local SQLite files may be written):

    python3 scripts/source_catalog.py --database /tmp/aegis-sources.sqlite --snapshot docs/platform-assembly/public-sources-20261016.json
    python3 scripts/source_catalog.py --database /tmp/aegis-sources.sqlite --connector-snapshot /path/to/authorized-metadata-only.json --allow-private-connectors-local
    python3 scripts/source_catalog.py --database /tmp/aegis-sources.sqlite --connector-query github
    python3 -m unittest tests/test_connector_catalog.py

--allow-private-connectors-local permits PRIVATE METADATA in the caller's own
local file only. It never grants external access or consents to publishing
that file. Import rejects unknown fields, raw URLs, unrecognized states,
duplicate identities, invalid SHA, oversized manifests and absent consent,
before writing local SQLite transactionally. Search opens SQLite read-only.
Never commit live private connector manifests, raw provider IDs, OAuth keys,
customer records, emails or Drive asset names to this public repository.

This is a metadata discovery and provenance extension. Retrieval must
re-check the source provider's permission and version at use time. The
ClickHouse connector presently responds but returns zero accessible
organizations; this is AVAILABLE_UNTESTED for organization content, not a
universal absence or a denial by every ClickHouse account.

NOT INCLUDED: production data migrations, auth grants, OpenAI model
invocations, live MCP/A2A handshakes, signed admission, two-client smoke
tests, browser acceptance, production deployment, billing changes or merge.


## Multi-account Cloudflare connector boundary (2026-10-20)

The operator reports **two Cloudflare accounts connected** in ChatGPT.
A read-only GET /accounts using the Cloudflare session currently selected by
this tool returned exactly **one accessible account** (display name:
Info@aegisomega.com's Account) with one Worker called aegisomega. That
observation proves access to that single account through THIS authorization;
it does NOT establish absence or disconnection of another ChatGPT-linked
Cloudflare account. Other linked identities must be independently selected,
authorized and enumerated before their Workers can be marked verified.

Catalog record identity is (provider, resource_kind, source_ref). For provider
cloudflare and resource_kind account (or account-scoped workers), use a
locally computed, opaque SHA-256 source_ref bound to the **specific account**
(and account+resource for a worker); do not key only on provider or Worker
name, since matching names can occur in multiple accounts. Do not commit raw
account IDs or raw identity-to-hash lookup maps to the repository. When a
second account cannot be enumerated from the active session, record its
coverage as AVAILABLE_UNTESTED without claiming its Workers. Updates to
one account must not overwrite the other's state. See the synthetic
two-account isolation regression in tests/test_connector_catalog.py.

No Cloudflare account setting, DNS, Worker, billing or connection was changed.
