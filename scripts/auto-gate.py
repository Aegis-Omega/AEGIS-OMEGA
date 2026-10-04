#!/usr/bin/env python3
"""AEGIS fail-closed auto-gate builder.

Generates one or more deterministic Rust gossip-monitor modules, compiles and
verifies them, and optionally commits/pushes only the files created by this run.
Model output is treated as untrusted candidate code until the static boundary,
module test, and full crate test all pass.

Examples:
  python3 scripts/auto-gate.py --count 2 --budget 0.50
  python3 scripts/auto-gate.py --gate 423 --count 1 --budget 0.25 --commit
  python3 scripts/auto-gate.py --count 2 --budget 0.50 --commit --push --yes
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import anthropic

REPO_ROOT = Path(__file__).resolve().parent.parent
CRATE_ROOT = REPO_ROOT / "aegis-cl-psi"
LIB_RS = CRATE_ROOT / "src" / "lib.rs"
SRC_DIR = CRATE_ROOT / "src"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
CHECKPOINT_PATH = REPO_ROOT / "scripts" / ".auto-gate-checkpoint.json"

MODEL = "claude-sonnet-4-6"
_INPUT_PRICE_PER_TOKEN = 3.00 / 1_000_000
_OUTPUT_PRICE_PER_TOKEN = 15.00 / 1_000_000
_EST_INPUT_TOKENS_PER_GATE = 3_800
_EST_OUTPUT_TOKENS_PER_GATE = 1_600
# Conservative authorization reservation per provider call. A configured budget
# must be able to cover this reservation before a call is made.
_MAX_CALL_RESERVATION_USD = 0.10
MAX_ATTEMPTS = 3

SAFE_MODEL_OUTPUT_DENYLIST = (
    "unsafe {",
    "std::process",
    "Command::new",
    "std::net",
    "TcpStream",
    "UdpSocket",
    "include_bytes!",
    "include_str!",
    "env!(",
    "option_env!(",
    "fs::",
    "std::fs",
    "extern \"C\"",
)

SYSTEM_PROMPT = """You are generating a pure Rust data-structure module for AEGIS.
The module is a SHA-256 hash-chained per-epoch metric log.
STRICT RULES:
- pure in-memory deterministic computation only; no filesystem, process, network, env, FFI, unsafe, include_* macros, or side effects
- to_be_bytes() for integer hash inputs
- BTreeMap/BTreeSet only if a collection map/set is needed; never HashMap/HashSet
- saturating integer arithmetic where overflow is possible
- bool in hash as [flag as u8]
- rate = (primary * 100) / max(secondary, 1), capped at 100
- genesis hash is [0u8; 32]
- no f32/f64 in hash inputs
- verify_chain must verify prev_hash linkage and recompute entry_hash
- exactly 19 tests in #[cfg(test)] mod tests
Return only the complete Rust source file, with no markdown fences or explanation."""

METRICS: tuple[tuple[str, str, str, str, int, str], ...] = (
    ("batch", "under_filled_batches", "total_batches", "under_filled", 50, "<"),
    ("duplicate", "duplicate_count", "total_received", "high_duplication", 10, ">"),
    ("peer_latency", "high_latency_peers", "total_peers", "excessive_latency", 20, ">"),
    ("retry", "retry_count", "total_sent", "high_retry_rate", 8, ">"),
    ("fragmentation", "fragmented_msgs", "total_msgs", "high_fragmentation", 25, ">"),
    ("loss", "lost_msgs", "total_sent", "high_loss", 3, ">"),
    ("congestion", "congested_epochs", "total_epochs", "congested", 30, ">"),
    ("fanout", "low_fanout_msgs", "total_msgs", "low_fanout", 40, "<"),
    ("propagation", "slow_propagations", "total_msgs", "slow_propagation", 10, ">"),
    ("collision", "collision_count", "total_received", "high_collision", 5, ">"),
    ("timeout", "timed_out_msgs", "total_sent", "high_timeout_rate", 4, ">"),
    ("jitter", "high_jitter_epochs", "total_epochs", "high_jitter", 15, ">"),
    ("backpressure", "backpressured_peers", "total_peers", "under_backpressure", 20, ">"),
    ("window_miss", "missed_windows", "total_windows", "high_miss_rate", 10, ">"),
    ("epoch_gap", "epoch_gaps", "total_epochs", "frequent_gaps", 5, ">"),
    ("ack_timeout", "unacknowledged_msgs", "total_sent", "high_ack_timeout", 8, ">"),
    ("peer_churn", "churned_peers", "total_peers", "high_churn", 25, ">"),
    ("broadcast_drop", "dropped_broadcasts", "total_broadcasts", "high_drop_rate", 2, ">"),
    ("queue_overflow", "overflow_events", "total_enqueued", "high_overflow", 3, ">"),
    ("sync_lag", "lagging_peers", "total_peers", "high_sync_lag", 30, ">"),
    ("nack_rate", "nack_count", "total_received", "high_nack_rate", 6, ">"),
    ("bandwidth_exceed", "over_limit_epochs", "total_epochs", "bandwidth_exceeded", 20, ">"),
    ("peer_drift", "drifted_peers", "total_peers", "high_peer_drift", 15, ">"),
    ("epoch_stall", "stalled_epochs", "total_epochs", "epoch_stalling", 5, ">"),
    ("rebroadcast", "rebroadcast_count", "total_sent", "high_rebroadcast", 12, ">"),
    ("partial_delivery", "partial_deliveries", "total_delivered", "high_partial_rate", 8, ">"),
    ("peer_rejection", "rejected_peers", "total_peers", "high_rejection", 10, ">"),
    ("msg_ordering", "out_of_order_msgs", "total_received", "high_disorder", 5, ">"),
    ("epoch_overlap", "overlapping_epochs", "total_epochs", "high_overlap", 3, ">"),
    ("peer_isolation", "isolated_peers", "total_peers", "peer_isolated", 10, ">"),
    ("ttl_exceeded", "ttl_exceeded_msgs", "total_sent", "high_ttl_exceed", 4, ">"),
    ("flood_rate", "flooded_msgs", "total_sent", "high_flood", 15, ">"),
    ("dedup_miss", "dedup_misses", "total_received", "high_dedup_miss", 3, ">"),
    ("capacity_breach", "capacity_breaches", "total_epochs", "over_capacity", 5, ">"),
    ("peer_timeout", "timed_out_peers", "total_peers", "high_peer_timeout", 10, ">"),
)


class CreditsExhausted(RuntimeError):
    pass


class SafetyBoundaryViolation(RuntimeError):
    pass


def _run(argv: list[str], *, cwd: Path = REPO_ROOT, check: bool = False) -> subprocess.CompletedProcess[str]:
    """Run an exact argv vector. Shell execution is intentionally impossible."""
    return subprocess.run(
        argv,
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
    )


def current_branch() -> str:
    result = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], check=True)
    branch = result.stdout.strip()
    if not branch or branch == "HEAD":
        raise SafetyBoundaryViolation("detached HEAD: commit/push is not authorized")
    return branch


def current_gate_number() -> int:
    match = re.search(r"Gates complete: (\d+)", CLAUDE_MD.read_text(encoding="utf-8"))
    return int(match.group(1)) if match else 422


def current_test_count() -> int:
    result = _run(["cargo", "test"], cwd=CRATE_ROOT)
    match = re.search(r"(\d+) passed", result.stdout + result.stderr)
    return int(match.group(1)) if match else 0


def run_cargo_test(module_name: str) -> tuple[bool, str]:
    result = _run(["cargo", "test", module_name], cwd=CRATE_ROOT)
    output = result.stdout + result.stderr
    return result.returncode == 0 and "19 passed" in output, output


def run_full_test() -> tuple[int, bool, str]:
    result = _run(["cargo", "test"], cwd=CRATE_ROOT)
    output = result.stdout + result.stderr
    match = re.search(r"(\d+) passed", output)
    return (int(match.group(1)) if match else 0, result.returncode == 0, output)


def token_cost(input_tokens: int, output_tokens: int) -> float:
    return input_tokens * _INPUT_PRICE_PER_TOKEN + output_tokens * _OUTPUT_PRICE_PER_TOKEN


def estimate_cost(count: int) -> tuple[float, float]:
    per_attempt = (
        _EST_INPUT_TOKENS_PER_GATE * _INPUT_PRICE_PER_TOKEN
        + _EST_OUTPUT_TOKENS_PER_GATE * _OUTPUT_PRICE_PER_TOKEN
    )
    return count * per_attempt, count * MAX_ATTEMPTS * per_attempt


def write_checkpoint(start_gate: int, built: list[int], total_spent: float) -> None:
    import datetime

    payload = {
        "schema_version": "2.0.0",
        "gate_start": start_gate,
        "gates_built": built,
        "next_gate": built[-1] + 1 if built else start_gate,
        "total_spent": round(total_spent, 8),
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z"),
    }
    CHECKPOINT_PATH.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def load_checkpoint() -> dict | None:
    if not CHECKPOINT_PATH.is_file():
        return None
    try:
        value = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def clear_checkpoint() -> None:
    CHECKPOINT_PATH.unlink(missing_ok=True)


def next_metric(gate_num: int) -> tuple[str, str, str, str, int, str]:
    offset = gate_num - 423
    if offset < 0:
        raise SafetyBoundaryViolation("gate number must be >= 423")
    base_idx = offset % len(METRICS)
    epoch = offset // len(METRICS) + 1
    suffix, primary, secondary, flag, threshold, op = METRICS[base_idx]
    if epoch > 1:
        suffix = f"{suffix}_e{epoch}"
        flag = f"{flag}_e{epoch}"
    return suffix, primary, secondary, flag, threshold, op


def module_for_gate(gate_num: int) -> tuple[str, Path, str, str, str, int, str]:
    suffix, primary, secondary, flag, threshold, op = next_metric(gate_num)
    module_name = f"gossip_broadcast_{suffix}"
    if not re.fullmatch(r"[a-z0-9_]+", module_name):
        raise SafetyBoundaryViolation("derived module name is not safe")
    module_path = (SRC_DIR / f"{module_name}.rs").resolve()
    if module_path.parent != SRC_DIR.resolve():
        raise SafetyBoundaryViolation("derived module path escaped source directory")
    return module_name, module_path, primary, secondary, flag, threshold, op


def _rate_field(primary: str) -> str:
    stem = primary
    for suffix in ("_count", "_msgs", "_peers", "_propagations", "_epochs", "_batches", "_windows", "_events", "_broadcasts", "_deliveries"):
        stem = stem.removesuffix(suffix)
    return f"{stem}_rate_pct"


def _prompt(gate_num: int) -> tuple[str, str, str]:
    module_name, module_path, primary, secondary, flag, threshold, op = module_for_gate(gate_num)
    suffix = module_name.removeprefix("gossip_broadcast_")
    type_stem = "".join(part.title() for part in suffix.split("_"))
    genesis = f"{suffix.upper()}_GENESIS_HASH"
    threshold_const = f"{flag.upper()}_THRESHOLD"
    rate_field = _rate_field(primary)
    prompt = f"""Write Gate {gate_num} as a complete Rust source file.
Module: {module_name}
Purpose: deterministic in-memory gossip metric hash-chain monitor.

Constants:
pub const {genesis}: [u8; 32] = [0u8; 32];
pub const {threshold_const}: u32 = {threshold};

Entry type: Gossip{type_stem}Entry
Required public fields, in this logical order:
- epoch_end: u64
- {primary}: u32
- {secondary}: u32
- {rate_field}: u32
- {flag}: bool
- entry_hash: [u8; 32]
- prev_hash: [u8; 32]

Log type: Gossip{type_stem}Log with public entries Vec and methods:
- new() and Default
- record(epoch_end, {primary}, {secondary}) -> &Entry
- {flag}_count() -> usize
- total_{primary}() -> u64
- mean_rate_pct() -> u32
- verify_chain() -> (bool, Option<usize>)

Rate: (({primary} as u64).saturating_mul(100) / max({secondary}, 1)) capped at 100.
Flag: rate {op} {threshold}.
Hash: SHA-256(prev_hash || epoch_end_be || {primary}_be || {secondary}_be || rate_be || flag_byte).
Use sha2::{{Digest, Sha256}}.

Exactly 19 tests must cover normal record fields, exact threshold boundary, cap at 100,
zero denominator, threshold constant, nonzero hash, genesis prev hash, second-link hash,
empty/one/three-entry verification, tamper detection at entry 0 and 1, deterministic hash,
flag count, total primary sum, empty mean, multi-entry mean, and Default.

Header must identify Gate {gate_num} and state T2. Return only Rust source."""
    return module_name, str(module_path), prompt


def validate_candidate_source(code: str) -> None:
    if not code.strip():
        raise SafetyBoundaryViolation("model returned empty source")
    if len(code.encode("utf-8")) > 128_000:
        raise SafetyBoundaryViolation("candidate source exceeds 128 KiB")
    lowered = code.lower()
    hits = [needle for needle in SAFE_MODEL_OUTPUT_DENYLIST if needle.lower() in lowered]
    if hits:
        raise SafetyBoundaryViolation(f"candidate source violates pure-module boundary: {hits}")
    if code.count("#[test]") != 19:
        raise SafetyBoundaryViolation("candidate source must contain exactly 19 #[test] functions")


def _registration_line(gate_num: int, module_name: str) -> str:
    description = module_name.removeprefix("gossip_broadcast_").replace("_", " ").title()
    return f"\n// Gate {gate_num} — Gossip Broadcast {description} Monitor (T2)\npub mod {module_name};"


def _ensure_registration(gate_num: int, module_name: str) -> bool:
    content = LIB_RS.read_text(encoding="utf-8")
    marker = f"pub mod {module_name};"
    if marker in content:
        return False
    LIB_RS.write_text(content + _registration_line(gate_num, module_name), encoding="utf-8")
    return True


def _remove_registration(gate_num: int, module_name: str) -> None:
    content = LIB_RS.read_text(encoding="utf-8")
    LIB_RS.write_text(content.replace(_registration_line(gate_num, module_name), ""), encoding="utf-8")


def update_claude_md(new_gate: int, new_tests: int) -> None:
    content = CLAUDE_MD.read_text(encoding="utf-8")
    content = re.sub(r"Gates complete: \d+", f"Gates complete: {new_gate}", content)
    content = re.sub(r"aegis-cl-psi \(\d+ tests\)", f"aegis-cl-psi ({new_tests} tests)", content)
    content = re.sub(r"aegis-cl-psi/src/, \d+ gate modules", f"aegis-cl-psi/src/, {new_gate} gate modules", content)
    CLAUDE_MD.write_text(content, encoding="utf-8")


def build_gate(gate_num: int, client: anthropic.Anthropic, budget_remaining: float | None) -> tuple[bool, float, Path]:
    module_name, module_path_text, prompt = _prompt(gate_num)
    module_path = Path(module_path_text)

    if module_path.exists():
        ok, _ = run_cargo_test(module_name)
        if ok:
            print(f"Gate {gate_num}: existing {module_name} passes 19 tests; no provider call")
            return True, 0.0, module_path
        raise SafetyBoundaryViolation(f"existing module fails its test boundary: {module_path}")

    gate_cost = 0.0
    last_code = ""
    last_error = ""
    registration_added = False

    try:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            remaining = None if budget_remaining is None else budget_remaining - gate_cost
            if remaining is not None and remaining < _MAX_CALL_RESERVATION_USD:
                print(
                    f"Budget boundary: ${remaining:.4f} remains, below "
                    f"${_MAX_CALL_RESERVATION_USD:.2f} provider-call reservation"
                )
                return False, gate_cost, module_path

            messages: list[dict[str, str]] = [{"role": "user", "content": prompt}]
            if attempt > 1:
                messages.extend(
                    [
                        {"role": "assistant", "content": last_code},
                        {
                            "role": "user",
                            "content": "Previous candidate failed local verification. Fix only the reported errors and return the complete file.\n"
                            + last_error[-3000:],
                        },
                    ]
                )

            print(f"Gate {gate_num}: provider attempt {attempt}/{MAX_ATTEMPTS}")
            try:
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=4096,
                    system=SYSTEM_PROMPT,
                    messages=messages,
                )
            except anthropic.APIStatusError as exc:
                if exc.status_code == 402 or "credit_balance_too_low" in str(exc):
                    raise CreditsExhausted(str(exc)) from exc
                raise

            call_cost = token_cost(response.usage.input_tokens, response.usage.output_tokens)
            gate_cost += call_cost
            if budget_remaining is not None and gate_cost > budget_remaining:
                raise SafetyBoundaryViolation(
                    f"provider returned after budget cap was crossed: spent ${gate_cost:.4f}, allowed ${budget_remaining:.4f}"
                )

            code = response.content[0].text.strip()
            code = re.sub(r"^```(?:rust)?\s*\n", "", code)
            code = re.sub(r"\n```\s*$", "", code)
            try:
                validate_candidate_source(code)
            except SafetyBoundaryViolation as exc:
                last_code = code
                last_error = str(exc)
                print(f"Gate {gate_num}: static candidate DENIED: {exc}")
                continue

            module_path.write_text(code + ("" if code.endswith("\n") else "\n"), encoding="utf-8")
            registration_added = _ensure_registration(gate_num, module_name) or registration_added
            passed, output = run_cargo_test(module_name)
            if passed:
                print(f"Gate {gate_num}: 19/19 module tests passed")
                return True, gate_cost, module_path

            last_code = code
            last_error = output
            module_path.unlink(missing_ok=True)
            if registration_added:
                _remove_registration(gate_num, module_name)
                registration_added = False
            print(f"Gate {gate_num}: candidate failed module tests")

        return False, gate_cost, module_path
    finally:
        # A failed generation must not leave candidate code or a lib.rs export.
        if not module_path.exists():
            _remove_registration(gate_num, module_name)


def commit_exact_files(built: list[int], module_paths: list[Path]) -> None:
    if not built:
        return
    branch = current_branch()
    if branch in {"main", "master"}:
        raise SafetyBoundaryViolation("refusing to commit generated code directly on canonical branch")

    _, full_ok, output = run_full_test()
    if not full_ok:
        raise SafetyBoundaryViolation("full cargo test failed; refusing commit\n" + output[-3000:])

    relative_paths = [str(path.relative_to(REPO_ROOT)) for path in module_paths]
    exact_paths = [*relative_paths, str(LIB_RS.relative_to(REPO_ROOT)), str(CLAUDE_MD.relative_to(REPO_ROOT))]
    _run(["git", "add", "--", *exact_paths], check=True)
    staged = _run(["git", "diff", "--cached", "--name-only"], check=True).stdout.splitlines()
    unexpected = sorted(set(staged) - set(exact_paths))
    if unexpected:
        _run(["git", "reset"], check=True)
        raise SafetyBoundaryViolation(f"unexpected staged paths: {unexpected}")

    gate_range = f"{built[0]}-{built[-1]}" if len(built) > 1 else str(built[0])
    message = f"feat(gates): generate verified gates {gate_range}"
    _run(["git", "commit", "-m", message], check=True)


def push_current_branch() -> None:
    branch = current_branch()
    if branch in {"main", "master"}:
        raise SafetyBoundaryViolation("refusing to push generated code to canonical branch")
    _run(["git", "push", "-u", "origin", branch], check=True)


def _confirmed(prompt: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    try:
        answer = input(prompt).strip().lower()
    except EOFError:
        return False
    return answer in {"y", "yes"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed AEGIS gate generator")
    parser.add_argument("--count", type=int, default=2)
    parser.add_argument("--gate", type=int)
    parser.add_argument("--budget", type=float, required=True, help="Hard provider spend cap in USD")
    parser.add_argument("--commit", action="store_true", help="Commit only verified generated files")
    parser.add_argument("--push", action="store_true", help="Push current non-canonical branch; requires --commit")
    parser.add_argument("--yes", "-y", action="store_true", help="Approve requested generation/commit/push non-interactively")
    args = parser.parse_args()

    if args.count < 1 or args.count > 32:
        raise SafetyBoundaryViolation("--count must be in [1, 32]")
    if args.budget <= 0:
        raise SafetyBoundaryViolation("--budget must be > 0")
    if args.push and not args.commit:
        raise SafetyBoundaryViolation("--push requires --commit")

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise SafetyBoundaryViolation("ANTHROPIC_API_KEY must be supplied via environment")

    start_gate = args.gate or (current_gate_number() + 1)
    best, estimated_worst = estimate_cost(args.count)
    reservation_worst = args.count * MAX_ATTEMPTS * _MAX_CALL_RESERVATION_USD
    print(f"AEGIS Auto-Gate v2: Gates {start_gate}..{start_gate + args.count - 1}")
    print(f"Estimated provider cost: ${best:.3f} best / ${estimated_worst:.3f} empirical worst")
    print(f"Hard budget: ${args.budget:.3f}; conservative call reservation ceiling: ${reservation_worst:.3f}")

    if args.budget < _MAX_CALL_RESERVATION_USD:
        raise SafetyBoundaryViolation(
            f"budget must reserve at least ${_MAX_CALL_RESERVATION_USD:.2f} for one provider call"
        )
    if not _confirmed("Proceed with provider calls? [y/N] ", args.yes):
        print("Aborted; no provider call made")
        return 0

    client = anthropic.Anthropic(api_key=api_key)
    built: list[int] = []
    module_paths: list[Path] = []
    total_spent = 0.0

    checkpoint = load_checkpoint()
    if checkpoint:
        print("Checkpoint exists; automatic resume is disabled in v2 to avoid stale-authority continuation.")
        print(f"Checkpoint: {CHECKPOINT_PATH}")
        raise SafetyBoundaryViolation("review/remove checkpoint explicitly before a new run")

    try:
        for offset in range(args.count):
            gate_num = start_gate + offset
            remaining = args.budget - total_spent
            if remaining < _MAX_CALL_RESERVATION_USD:
                print(f"Stopping before Gate {gate_num}: insufficient authorized budget reservation")
                break

            ok, gate_cost, module_path = build_gate(gate_num, client, remaining)
            total_spent += gate_cost
            if not ok:
                print(f"Gate {gate_num}: DENIED after local/provider attempts")
                break

            built.append(gate_num)
            module_paths.append(module_path)
            test_count, full_ok, full_output = run_full_test()
            if not full_ok:
                raise SafetyBoundaryViolation(
                    f"Gate {gate_num}: full crate regression failed\n{full_output[-3000:]}"
                )
            update_claude_md(gate_num, test_count)
            write_checkpoint(start_gate, built, total_spent)
            print(f"Gate {gate_num}: full crate passed; spend=${total_spent:.4f}")
    except CreditsExhausted as exc:
        write_checkpoint(start_gate, built, total_spent)
        print(f"Provider credits exhausted; progress checkpointed: {exc}", file=sys.stderr)
        return 3
    except Exception:
        if built:
            write_checkpoint(start_gate, built, total_spent)
        raise

    if not built:
        print("No gate admitted")
        return 1

    _, full_ok, full_output = run_full_test()
    if not full_ok:
        raise SafetyBoundaryViolation("final full test failed\n" + full_output[-3000:])

    if args.commit:
        if not _confirmed("Commit exact verified files? [y/N] ", args.yes):
            raise SafetyBoundaryViolation("commit requested but not authorized")
        commit_exact_files(built, module_paths)
        print("Committed verified generated files only")

    if args.push:
        if not _confirmed("Push current non-canonical branch? [y/N] ", args.yes):
            raise SafetyBoundaryViolation("push requested but not authorized")
        push_current_branch()
        print("Pushed current branch")

    clear_checkpoint()
    print(f"ADMITTED gates={built} spend=${total_spent:.4f}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SafetyBoundaryViolation as exc:
        print(f"DENIED: {exc}", file=sys.stderr)
        raise SystemExit(2)
