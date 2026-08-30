"""AEGIS-Ω CLI — aegis <command> [options]

Commands:
  status                          Check platform health
  collaborate <objective>         Synchronous 39-dept swarm
  execute <objective>             Async execution with live SSE stream
  get <execution_id>              Fetch a completed execution by ID
  delete <execution_id>           Remove a stored execution

Environment:
  AEGIS_API_KEY                   Your API key (or pass via --key)
  AEGIS_BASE_URL                  Override base URL (default: production)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from .client import AegisClient, AegisError, CollaborationResult, BASE_URL

_GREEN  = "\033[32m"
_YELLOW = "\033[33m"
_RED    = "\033[31m"
_CYAN   = "\033[36m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_RESET  = "\033[0m"
_NO_COLOR = not sys.stdout.isatty()


def _c(color: str, text: str) -> str:
    return text if _NO_COLOR else f"{color}{text}{_RESET}"


def _print_result(result: CollaborationResult, *, json_out: bool = False) -> None:
    if json_out:
        print(json.dumps({
            "cycle_id": result.cycle_id,
            "objective": result.objective,
            "mode": result.mode,
            "departments_collaborated": result.departments_collaborated,
            "artifacts": [{"role": a.role, "output": a.output} for a in result.artifacts],
            "constitutional_audit": {
                "verdict": result.constitutional_audit.verdict,
                "concerns": result.constitutional_audit.concerns,
            },
            "chain_valid": result.chain_valid,
            "audit_chain_hash": result.audit_chain_hash,
            "execution_id": result.execution_id,
            "projection": result.projection,
        }, indent=2))
        return

    verdict = result.constitutional_audit.verdict
    verdict_color = _GREEN if verdict == "APPROVED" else _RED if verdict == "QUARANTINE" else _YELLOW

    print()
    print(_c(_BOLD, f"  {result.objective}"))
    print(_c(_DIM, f"  mode={result.mode}  departments={result.departments_collaborated}  execution_id={result.execution_id}"))
    print()

    for art in result.artifacts:
        print(f"  {_c(_CYAN, art.role):>18}  {art.output}")

    print()
    print(f"  {_c(_BOLD, 'Constitutional audit:')}  {_c(verdict_color, verdict)}")
    if result.constitutional_audit.concerns:
        for c in result.constitutional_audit.concerns:
            print(f"    {_c(_YELLOW, '⚠')} {c}")
    print(f"  {'chain_valid':>18}  {_c(_GREEN, 'true') if result.chain_valid else _c(_RED, 'false')}")
    print(f"  {'audit_chain_hash':>18}  {_c(_DIM, result.audit_chain_hash[:20])}…")
    if result.projection:
        arr = result.projection.get("first_year_arr_usd")
        if arr:
            print(f"  {'projection (T2)':>18}  ${arr:,.0f} ARR Y1")
    print()


def _cmd_status(client: AegisClient, args: argparse.Namespace) -> int:
    try:
        s = client.status()
    except AegisError as exc:
        print(_c(_RED, f"error [{exc.code}]: {exc}"), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({
            "version": s.version,
            "contract_version": s.contract_version,
            "total_agents": s.total_agents,
            "chain_valid": s.chain_valid,
            "available": s.available,
        }, indent=2))
    else:
        avail = _c(_GREEN, "available") if s.available else _c(_RED, "unavailable")
        chain = _c(_GREEN, "intact") if s.chain_valid else _c(_RED, "broken")
        print(f"\n  AEGIS-Ω Platform  v{s.version}  contract={s.contract_version}")
        print(f"  status={avail}  audit_chain={chain}  agents={s.total_agents}\n")
    return 0


def _cmd_collaborate(client: AegisClient, args: argparse.Namespace) -> int:
    obj = " ".join(args.objective)
    if not obj:
        print(_c(_RED, "error: objective is required"), file=sys.stderr)
        return 1
    print(_c(_DIM, f"  activating {args.mode} swarm…"), file=sys.stderr)
    try:
        result = client.collaborate(obj, mode=args.mode, live=args.live)
    except AegisError as exc:
        print(_c(_RED, f"error [{exc.code}]: {exc}"), file=sys.stderr)
        return 1
    _print_result(result, json_out=args.json)
    return 0


def _cmd_execute(client: AegisClient, args: argparse.Namespace) -> int:
    obj = " ".join(args.objective)
    if not obj:
        print(_c(_RED, "error: objective is required"), file=sys.stderr)
        return 1
    print(_c(_DIM, f"  starting async execution…"), file=sys.stderr)
    try:
        handle = client.start_execution(obj, mode=args.mode, live=args.live)
    except AegisError as exc:
        print(_c(_RED, f"error [{exc.code}]: {exc}"), file=sys.stderr)
        return 1

    print(f"  {_c(_CYAN, 'execution_id')}  {handle.execution_id}", file=sys.stderr)
    print(_c(_DIM, "  streaming events…"), file=sys.stderr)
    print()

    final: dict[str, Any] | None = None
    try:
        for event in handle.stream():
            etype = event.get("type", "")
            payload = event.get("payload", {})
            if etype == "dag_step":
                role = payload.get("dept_name", payload.get("dept_id", ""))
                idx  = payload.get("step_index", "?")
                tot  = payload.get("total_steps", "?")
                print(f"  {_c(_CYAN, f'[{idx}/{tot}]')} {role}")
            elif etype == "agent_event":
                role    = payload.get("role", "")
                preview = payload.get("output_preview", "")
                print(f"  {_c(_DIM, role):>18}  {preview}")
            elif etype == "error":
                print(_c(_RED, f"  stream error: {payload.get('message', event)}"), file=sys.stderr)
                return 1
            elif etype == "completion":
                final = payload
    except AegisError as exc:
        print(_c(_RED, f"error [{exc.code}]: {exc}"), file=sys.stderr)
        return 1

    if final and not args.json:
        verdict = final.get("constitutional_audit", {}).get("verdict", "?")
        v_color = _GREEN if verdict == "APPROVED" else _RED
        chain   = _c(_GREEN, "true") if final.get("chain_valid") else _c(_RED, "false")
        print()
        print(f"  {_c(_BOLD, 'verdict')}  {_c(v_color, verdict)}  chain_valid={chain}")
        print()
    elif final and args.json:
        print(json.dumps(final, indent=2))
    return 0


def _cmd_get(client: AegisClient, args: argparse.Namespace) -> int:
    try:
        result = client.get_execution(args.execution_id)
    except AegisError as exc:
        print(_c(_RED, f"error [{exc.code}]: {exc}"), file=sys.stderr)
        return 1
    _print_result(result, json_out=args.json)
    return 0


def _cmd_delete(client: AegisClient, args: argparse.Namespace) -> int:
    try:
        client.delete_execution(args.execution_id)
    except AegisError as exc:
        print(_c(_RED, f"error [{exc.code}]: {exc}"), file=sys.stderr)
        return 1
    print(_c(_GREEN, f"  deleted {args.execution_id}"))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="aegis",
        description="AEGIS-Ω CLI — governed multi-agent AI with constitutional audit trail",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--key",     metavar="API_KEY", help="API key (default: $AEGIS_API_KEY)")
    parser.add_argument("--base",    metavar="URL",     help="Base URL override (default: production)")
    parser.add_argument("--json",    action="store_true", help="Output raw JSON")
    parser.add_argument("--timeout", type=int, default=60, metavar="SECS")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Check platform health (no auth required)")

    p_collab = sub.add_parser("collaborate", help="Synchronous 39-dept swarm")
    p_collab.add_argument("objective", nargs="+", help="Business objective (e.g. 'Enter EU fintech Q4 2026')")
    p_collab.add_argument("--mode", default="analysis", choices=["revenue","analysis","gtm","retention","competitive","technical","regulatory","fundraising"])
    p_collab.add_argument("--live", action="store_true", help="Live Claude inference (uses run credits)")

    p_exec = sub.add_parser("execute", help="Async execution with live SSE stream")
    p_exec.add_argument("objective", nargs="+")
    p_exec.add_argument("--mode", default="analysis", choices=["revenue","analysis","gtm","retention","competitive","technical","regulatory","fundraising"])
    p_exec.add_argument("--live", action="store_true")

    p_get = sub.add_parser("get", help="Fetch a completed execution by ID")
    p_get.add_argument("execution_id")

    p_del = sub.add_parser("delete", help="Remove a stored execution")
    p_del.add_argument("execution_id")

    args = parser.parse_args(argv)

    api_key  = args.key or os.environ.get("AEGIS_API_KEY", "")
    base_url = args.base or os.environ.get("AEGIS_BASE_URL", BASE_URL)

    if args.command != "status" and not api_key:
        print(_c(_RED, "error: API key required. Pass --key or set AEGIS_API_KEY."), file=sys.stderr)
        print(_c(_DIM, "  Get a free explorer key at https://aegisomega.com/pricing"), file=sys.stderr)
        return 1

    client = AegisClient(api_key or "no-key-status-only", base_url=base_url, timeout=args.timeout)

    dispatch = {
        "status":      _cmd_status,
        "collaborate": _cmd_collaborate,
        "execute":     _cmd_execute,
        "get":         _cmd_get,
        "delete":      _cmd_delete,
    }
    return dispatch[args.command](client, args)


if __name__ == "__main__":
    sys.exit(main())
