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
