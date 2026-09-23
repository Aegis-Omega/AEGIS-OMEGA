"""Offline CLI for the Tameion OpenMeter -> Arc evidence demo.

The CLI is deliberately non-networked:
- no OpenMeter API call
- no Circle API call
- no Arc RPC
- no key loading
- no signing
- no broadcast

It accepts already-observed usage plus an already-produced AEGIS policy decision
and emits deterministic pre-settlement evidence. If an already-observed
settlement is supplied, it can also close the metered evidence chain.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from harness.sdk.arc_erc20_call import build_unsigned_transfer_call
from harness.sdk.arc_treasury_execution import plan_arc_testnet_transfer
from harness.sdk.arc_treasury_witness import ArcSettlementObservation, bind_arc_settlement
from harness.sdk.sovereign_execution import (
    SCHEMA_VERSION,
    PolicyDecision,
    SovereignExecutionError,
    canonical_bytes,
)
from harness.sdk.tameion_metered_evidence_chain import build_tameion_metered_evidence_chain
from harness.sdk.tameion_openmeter_bridge import (
    OpenMeterSettlementPolicy,
    OpenMeterUsageObservation,
    build_openmeter_arc_intent,
    build_openmeter_payment_obligation,
)
from harness.sdk.tameion_presettlement_bundle import build_tameion_pre_settlement_bundle


def _require_mapping(name: str, value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SovereignExecutionError(f"{name}:MAPPING_REQUIRED")
    return value


def _require_text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise SovereignExecutionError(f"{name}:TEXT_REQUIRED")
    return value


def _require_int(name: str, value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise SovereignExecutionError(f"{name}:INTEGER_REQUIRED")
    return value


def _policy_decision(raw: Mapping[str, Any]) -> PolicyDecision:
    try:
        return PolicyDecision(**dict(raw))
    except TypeError as exc:
        raise SovereignExecutionError("TAMEION_CLI_POLICY_DECISION_INVALID") from exc


def build_demo_packet(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build a deterministic dry-run packet, optionally closing settlement evidence."""

    usage_raw = _require_mapping("usage", payload.get("usage"))
    policy_raw = _require_mapping("settlement_policy", payload.get("settlement_policy"))
    decision_raw = _require_mapping("policy_decision", payload.get("policy_decision"))

    usage = OpenMeterUsageObservation(
        schema_version=SCHEMA_VERSION,
        meter_slug=_require_text("usage.meter_slug", usage_raw.get("meter_slug")),
        event_id=_require_text("usage.event_id", usage_raw.get("event_id")),
        subject=_require_text("usage.subject", usage_raw.get("subject")),
        usage_units=_require_int("usage.usage_units", usage_raw.get("usage_units")),
    )

    policy_kwargs: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "meter_slug": _require_text("settlement_policy.meter_slug", policy_raw.get("meter_slug")),
        "unit_price_microunits": _require_int(
            "settlement_policy.unit_price_microunits",
            policy_raw.get("unit_price_microunits"),
        ),
        "destination": _require_text("settlement_policy.destination", policy_raw.get("destination")),
    }
    if "max_amount_microunits" in policy_raw:
        policy_kwargs["max_amount_microunits"] = _require_int(
            "settlement_policy.max_amount_microunits",
            policy_raw.get("max_amount_microunits"),
        )
    policy = OpenMeterSettlementPolicy(**policy_kwargs)

    decision = _policy_decision(decision_raw)
    mutation_receipt_root = _require_text(
        "mutation_receipt_root",
        payload.get("mutation_receipt_root"),
    )
    sender = _require_text("sender", payload.get("sender"))

    obligation = build_openmeter_payment_obligation(usage=usage, policy=policy)
    intent, source_binding = build_openmeter_arc_intent(
        obligation=obligation,
        authority_decision_root=decision.decision_root,
        mutation_receipt_root=mutation_receipt_root,
    )
    plan = plan_arc_testnet_transfer(
        intent=intent,
        decision=decision,
        sender=sender,
    )
    unsigned_call = build_unsigned_transfer_call(plan)
    pre = build_tameion_pre_settlement_bundle(
        obligation=obligation,
        source_binding=source_binding,
        plan=plan,
        unsigned_call=unsigned_call,
    )

    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "PRE_SETTLEMENT_READY",
        "authority_effect": "NONE",
        "network_effect": "NONE",
        "usage_root": usage.root,
        "settlement_policy_root": policy.root,
        "obligation_root": obligation.root,
        "treasury_intent_root": intent.root,
        "source_binding_root": source_binding.root,
        "transfer_plan_root": plan.root,
        "unsigned_call_root": unsigned_call.root,
        "pre_settlement_bundle_root": pre.root,
        "unsigned_call": {
            "network": unsigned_call.network,
            "chain_id": unsigned_call.chain_id,
            "to": unsigned_call.to,
            "value": unsigned_call.value,
            "data": unsigned_call.data,
            "broadcast_allowed": unsigned_call.broadcast_allowed,
            "signer_attached": unsigned_call.signer_attached,
        },
    }

    observation_raw = payload.get("settlement_observation")
    if observation_raw is None:
        return result

    observation_map = _require_mapping("settlement_observation", observation_raw)
    observation = ArcSettlementObservation(
        schema_version=SCHEMA_VERSION,
        chain_id=_require_text("settlement_observation.chain_id", observation_map.get("chain_id")),
        tx_hash=_require_text("settlement_observation.tx_hash", observation_map.get("tx_hash")),
        block_number=_require_int(
            "settlement_observation.block_number",
            observation_map.get("block_number"),
        ),
        amount_microunits=_require_int(
            "settlement_observation.amount_microunits",
            observation_map.get("amount_microunits"),
        ),
        destination=_require_text(
            "settlement_observation.destination",
            observation_map.get("destination"),
        ),
        status=_require_text("settlement_observation.status", observation_map.get("status")),
    )
    witness = bind_arc_settlement(intent, observation)

    claimed = payload.get("claimed_correctness_micros", 1_000_000)
    claimed_correctness_micros = _require_int("claimed_correctness_micros", claimed)
    final_chain, calibration = build_tameion_metered_evidence_chain(
        pre_settlement=pre,
        plan=plan,
        witness=witness,
        claimed_correctness_micros=claimed_correctness_micros,
    )

    result.update(
        {
            "status": "SETTLEMENT_RECONCILED",
            "settlement_observation_root": observation.root,
            "settlement_witness_root": witness.root,
            "calibration_root": calibration.root,
            "hallucination_delta_micros": calibration.hd_micros,
            "metered_evidence_chain_root": final_chain.root,
        }
    )
    return result


def _read_payload(path: str | None) -> Mapping[str, Any]:
    try:
        if path is None:
            raw = json.load(__import__("sys").stdin)
        else:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SovereignExecutionError("TAMEION_CLI_INPUT_INVALID") from exc
    return _require_mapping("payload", raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build offline Tameion Arc evidence packets")
    parser.add_argument("--input", help="JSON input file; defaults to stdin")
    parser.add_argument("--output", help="JSON output file; defaults to stdout")
    args = parser.parse_args(argv)

    packet = build_demo_packet(_read_payload(args.input))
    encoded = canonical_bytes(packet) + b"\n"

    if args.output:
        Path(args.output).write_bytes(encoded)
    else:
        __import__("sys").stdout.buffer.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
