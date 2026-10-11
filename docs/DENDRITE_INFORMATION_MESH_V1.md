# AEGIS Dendrite Information Mesh v1 (candidate)

Read-only, deterministic, subscription-filtered propagation across existing AEGIS agent roles. This is an information plane, **not** an agent execution plane. It reuses the multi-hop TTL/dedup concepts already in `aegis-cl-psi/src/gossip_router.rs`, which handles fixed-size telemetry; it does not replace or change that Rust router.

## Actual integration

- Producer: `agents/cognitive_pipeline.py` ARBITRATION records (`record_hash`, `sequence`, `kan_terminal_hash`).
- Broker: `agents/dendrite_mesh.py` converts them into content-bound claim events and routes them deterministically across declared dendrites.
- Consumers: existing AEGIS agent role **names**, represented as deterministic per-role in-memory inbox packets containing the claim text, source hashes and routing hop. **No live agent invocation or external delivery is asserted.**
- Authority: existing Automaton-3/coordinator remains the only operational decision source. Every mesh receipt states `authority_effect=NONE` and `execution_effect=NONE`.
- Quarantined claims reach only corpus ingestion, cybersecurity and chronology, not research/business nodes.
- Every claim remains `UNVERIFIED_SOURCE_CLAIM`, even if the pipeline's heuristic scorer accepts it. A digest detects alteration but does not authenticate the publisher or prove truth.

## Reproduce from repository root

```sh
python3 -m unittest agents.tests.test_dendrite_mesh -v
python3 -m agents.cognitive_pipeline demo --dendrite --source-head <EXACT_REPOSITORY_SHA>
```

`--dendrite` is opt-in; the ordinary pipeline is unchanged. Both offline demo and mediated propagation are passive. No API/Redis/keys/network/money required. Live model invocation remains controlled by the pre-existing `--live` switch and is **not** enabled by dendrite routing.

## Safety and limitations

No persistence, external transport, authentication, independent fact-checking, durable dedup across processes, concurrency, operator approval, or production integration. Delivery means **read-only, in-memory packet materialization for named roles**, not calls to those agents. Events remain untrusted data, never instructions. Native CI, signed commits, independent review, actual transport authorization and integration with canonical `EventEnvelope` are future gates before live use.

Implementation bounds: max 32 nodes; max eight out-neighbors per node; TTL max eight; max 64 messages per pipeline cycle; max text 4096 UTF-8 bytes. Deterministic sorted-topology traversal. Each event and pipeline routing batch gets a content-addressed receipt. Cycles cannot cause duplicate deliveries. No implied authorization or epistemic promotion.

## Relationship to related work

- [#734](https://github.com/Aegis-Omega/AEGIS-OMEGA/issues/734): existing firm-of-agents coordination; **not** replaced.
- [#765](https://github.com/Aegis-Omega/AEGIS-OMEGA/issues/765): research intake; richer evidence and authenticity checks remain separate.
- [#747](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/747): exact-head gate; no merge without protected-main admission.
- [#730](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/730): capability ranking after central authorization; dendrite paths do **not** select or authorize tools.


## Cross-domain connection (current PR branch)

The multi-domain adapter in `agents/dendrite_system.py` builds on the original `agents/dendrite_mesh.py`, not another coordinator. It has 19 nodes drawn from existing `agents/agents.yaml` and six typed informational topics:

| Source lane | Ingress contract | Roles reached (subject to topic, fan-out and TTL) |
| --- | --- | --- |
| Cognitive | Existing `run_pipeline` result, verified-in-memory KAN chain shape | corpus ingestion, research, safety, science, product, strategy |
| Formal | Explicit JSON record with `source=formal` | applied science, research, engineering, chronology, safety |
| Engineering | Explicit JSON record with `source=engineering` | engineering, DevEx, platform, product, safety |
| Security | Explicit JSON record with `source=security` | cybersecurity, AI safety, compliance, engineering, chronology |
| Revenue | Existing `RevenueCycleResult` artifacts with lineage root | strategy, product, business development, finance, sales |
| Operations | Explicit JSON record with `source=operations` | platform engineering, cybersecurity, chronology |

The cross-domain model *does not* decide who is authorized to read confidential data; do not supply secrets/private datasets. Receipt-level `source_authenticity=NOT_VERIFIED` means source SHA and digests are externally claimed, not independently authenticated. Also, `source_record` hashes do **not** imply a theorem proof or revenue settlement.

### Reproduce (candidate branch checkout)

```sh
python3 -m unittest agents.tests.test_dendrite_mesh agents.tests.test_dendrite_system -v
python3 -m agents.cognitive_pipeline demo --dendrite --source-head "$(git rev-parse HEAD)"
python3 -m agents.revenue_engine demo --dendrite --source-head "$(git rev-parse HEAD)"
python3 -m agents.dendrite_system examples/dendrite_formal_observation.json
```

**CAUTION:** Existing `revenue_engine.demo` writes `agents/adaptive_lineage.json` and may update the existing skill tree through the pre-existing evolution tick. The new dendrite adapter does not itself write to disk, but this producer already does. Run revenue demos in a disposable worktree/sandbox, not in the protected checkout. The cognitive offline demo and external-record ingress require no paid model call.

### External source record schema

Exactly six fields: `source`, `source_head`, `source_record`, `sequence`, `text`, `channel` (`CANDIDATE` or `QUARANTINE`). The record file is read with an 8 KiB cap. Claims are in-memory and remain inert data. Any additional executable instruction field is rejected. `QUARANTINE` routes only through designated security/chronology subscriptions; no business or engineering delivery.

### Trust/authority limits

This is **information routing, not operational federation**. There is no durable transport, authenticated sender, message-bus delivery, cross-process replay cache, signature attestation, economic action, formal proof check, automatic tier promotion, or canonical `EventEnvelope V2` admission. Existing `AuthorityEvaluator` continues to govern any tool execution. Porting to Redis, Temporal, MCP/A2A or cross-repo consumers requires an independent design and authorization review. Do not treat the generated inboxes as agent executions.

### Exact-head verification standard

Locally exercised synthetic unit tests may show the candidate code operates, but hosted CI is required for repository-native proof at the exact SHA. A skipped check or zero-step failure is `NOT_VERIFIED`, never a PASS. The PR stays draft while signed commits, independent review, trusted execution and protected-main admission remain unresolved.
