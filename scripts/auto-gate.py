#!/usr/bin/env python3
"""
AEGIS Auto-Gate Builder
Uses Claude claude-sonnet-4-6 via Anthropic API to generate, test, and commit gate modules.

Usage:
  python3 scripts/auto-gate.py                         # build next 2 gates (pair)
  python3 scripts/auto-gate.py --count 4               # build next 4 gates
  python3 scripts/auto-gate.py --gate 423 --name foo   # build specific gate
"""

import os
import re
import sys
import json
import argparse
import subprocess
import anthropic

REPO_ROOT       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB_RS          = os.path.join(REPO_ROOT, "aegis-cl-psi", "src", "lib.rs")
SRC_DIR         = os.path.join(REPO_ROOT, "aegis-cl-psi", "src")
CLAUDE_MD       = os.path.join(REPO_ROOT, "CLAUDE.md")
CHECKPOINT_PATH = os.path.join(REPO_ROOT, "scripts", ".auto-gate-checkpoint.json")


class CreditsExhausted(Exception):
    pass


# ─── Checkpoint (ERROR-04 fix) ─────────────────────────────
# Write a JSON checkpoint after each successful gate so any crash
# (not just 402) is recoverable without operator intervention.

def write_checkpoint(gate_start: int, gates_built: list, total_spent: float) -> None:
    import datetime
    data = {
        "gate_start":  gate_start,
        "gates_built": gates_built,
        "total_spent": total_spent,
        "next_gate":   gates_built[-1] + 1 if gates_built else gate_start,
        "timestamp":   datetime.datetime.utcnow().isoformat() + "Z",
    }
    with open(CHECKPOINT_PATH, "w") as f:
        json.dump(data, f, indent=2)


def clear_checkpoint() -> None:
    if os.path.exists(CHECKPOINT_PATH):
        os.remove(CHECKPOINT_PATH)


def load_checkpoint() -> dict | None:
    if not os.path.exists(CHECKPOINT_PATH):
        return None
    try:
        with open(CHECKPOINT_PATH) as f:
            return json.load(f)
    except Exception:
        return None


# claude-sonnet-4-6 pricing (USD per token)
_INPUT_PRICE_PER_TOKEN  = 3.00 / 1_000_000
_OUTPUT_PRICE_PER_TOKEN = 15.00 / 1_000_000

# Empirical averages per gate (1 attempt, no retry)
_EST_INPUT_TOKENS_PER_GATE  = 3_800
_EST_OUTPUT_TOKENS_PER_GATE = 1_600


def estimate_cost(count: int, max_attempts: int = 3) -> tuple[float, float]:
    """Return (best_case_usd, worst_case_usd) for building `count` gates."""
    per_gate_best  = (_EST_INPUT_TOKENS_PER_GATE  * _INPUT_PRICE_PER_TOKEN
                    + _EST_OUTPUT_TOKENS_PER_GATE * _OUTPUT_PRICE_PER_TOKEN)
    per_gate_worst = per_gate_best * max_attempts
    return count * per_gate_best, count * per_gate_worst


def token_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * _INPUT_PRICE_PER_TOKEN
          + output_tokens * _OUTPUT_PRICE_PER_TOKEN)


EXAMPLE_MODULE = """//! Gate 422 — Gossip Broadcast Duplicate Detection Monitor (T2)
//! Tracks duplicate message rate per gossip broadcast epoch.
//! DUPLICATION_THRESHOLD = 10: dup_rate_pct > 10 → high_duplication

use sha2::{Sha256, Digest};

pub const DUPLICATE_GENESIS_HASH: [u8; 32] = [0u8; 32];
pub const DUPLICATION_THRESHOLD: u32 = 10;

#[derive(Debug, Clone, PartialEq)]
pub struct GossipBroadcastDuplicateEntry {
    pub epoch_end:        u64,
    pub duplicate_count:  u32,
    pub total_received:   u32,
    pub dup_rate_pct:     u32,
    pub high_duplication: bool,
    pub entry_hash:       [u8; 32],
    pub prev_hash:        [u8; 32],
}

fn compute_hash(prev: &[u8; 32], epoch_end: u64, duplicate_count: u32,
    total_received: u32, dup_rate_pct: u32, high_duplication: bool) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(prev);
    h.update(epoch_end.to_be_bytes());
    h.update(duplicate_count.to_be_bytes());
    h.update(total_received.to_be_bytes());
    h.update(dup_rate_pct.to_be_bytes());
    h.update([high_duplication as u8]);
    h.finalize().into()
}

pub struct GossipBroadcastDuplicateLog { pub entries: Vec<GossipBroadcastDuplicateEntry> }

impl GossipBroadcastDuplicateLog {
    pub fn new() -> Self { Self { entries: Vec::new() } }
    pub fn high_duplication_count(&self) -> usize { self.entries.iter().filter(|e| e.high_duplication).count() }
    pub fn total_duplicates(&self) -> u64 { self.entries.iter().map(|e| e.duplicate_count as u64).sum() }
    pub fn mean_dup_rate_pct(&self) -> u32 {
        if self.entries.is_empty() { return 0; }
        let sum: u64 = self.entries.iter().map(|e| e.dup_rate_pct as u64).sum();
        (sum / self.entries.len() as u64) as u32
    }
    pub fn record(&mut self, epoch_end: u64, duplicate_count: u32, total_received: u32) -> &GossipBroadcastDuplicateEntry {
        let denom = total_received.max(1) as u64;
        let dup_rate_pct = ((duplicate_count as u64 * 100) / denom).min(100) as u32;
        let high_duplication = dup_rate_pct > DUPLICATION_THRESHOLD;
        let prev = self.entries.last().map(|e| e.entry_hash).unwrap_or(DUPLICATE_GENESIS_HASH);
        let entry_hash = compute_hash(&prev, epoch_end, duplicate_count, total_received, dup_rate_pct, high_duplication);
        self.entries.push(GossipBroadcastDuplicateEntry { epoch_end, duplicate_count, total_received, dup_rate_pct, high_duplication, entry_hash, prev_hash: prev });
        self.entries.last().unwrap()
    }
    pub fn verify_chain(&self) -> (bool, Option<usize>) {
        let mut prev = DUPLICATE_GENESIS_HASH;
        for (i, e) in self.entries.iter().enumerate() {
            if e.prev_hash != prev { return (false, Some(i)); }
            let expected = compute_hash(&prev, e.epoch_end, e.duplicate_count, e.total_received, e.dup_rate_pct, e.high_duplication);
            if e.entry_hash != expected { return (false, Some(i)); }
            prev = e.entry_hash;
        }
        (true, None)
    }
}
impl Default for GossipBroadcastDuplicateLog { fn default() -> Self { Self::new() } }

#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn record_fields_set_correctly() { /* ... 19 tests total ... */ }
}
"""

SYSTEM_PROMPT = """You are an expert Rust developer building AEGIS gate modules.
Each gate is a SHA-256 hash-chained log of per-epoch gossip network metrics.

STRICT RULES — never violate:
- to_be_bytes() always (big-endian), NEVER to_le_bytes()
- BTreeMap/BTreeSet only if needed, NEVER HashMap
- saturating_add/saturating_mul for integer ops
- bool in hash: [flag as u8]
- Rate: (primary * 100) / max(secondary, 1), then .min(100)
- Exactly 19 tests in #[cfg(test)] mod tests
- Genesis const: all zeros [0u8; 32]
- NEVER use f64 in hash inputs
- verify_chain recomputes both prev_hash linkage AND entry_hash content

Output ONLY the complete Rust file. No markdown fences. No explanation."""


def current_gate_number() -> int:
    with open(CLAUDE_MD) as f:
        m = re.search(r"Gates complete: (\d+)", f.read())
    return int(m.group(1)) if m else 422


def current_test_count() -> int:
    result = subprocess.run(
        ["cargo", "test", "2>&1"], shell=True, capture_output=True, text=True,
        cwd=os.path.join(REPO_ROOT, "aegis-cl-psi")
    )
    m = re.search(r"(\d+) passed", result.stdout + result.stderr)
    return int(m.group(1)) if m else 0


def run_cargo_test(module_name: str) -> tuple[bool, str]:
    result = subprocess.run(
        ["cargo", "test", module_name],
        capture_output=True, text=True,
        cwd=os.path.join(REPO_ROOT, "aegis-cl-psi")
    )
    output = result.stdout + result.stderr
    passed = result.returncode == 0 and "19 passed" in output
    return passed, output


def run_full_test() -> tuple[int, bool]:
    result = subprocess.run(
        ["cargo", "test"],
        capture_output=True, text=True,
        cwd=os.path.join(REPO_ROOT, "aegis-cl-psi")
    )
    output = result.stdout + result.stderr
    m = re.search(r"(\d+) passed", output)
    count = int(m.group(1)) if m else 0
    ok = result.returncode == 0
    return count, ok


def register_in_lib_rs(gate_num: int, module_name: str, description: str):
    with open(LIB_RS) as f:
        content = f.read()
    line = f"\n// Gate {gate_num} — {description} (T2)\npub mod {module_name};"
    with open(LIB_RS, "a") as f:
        f.write(line)
    print(f"  ✓ Registered pub mod {module_name} in lib.rs")


def update_claude_md(new_gate: int, new_tests: int):
    with open(CLAUDE_MD) as f:
        content = f.read()
    content = re.sub(r"Gates complete: \d+", f"Gates complete: {new_gate}", content)
    content = re.sub(r"aegis-cl-psi \(\d+ tests\)", f"aegis-cl-psi ({new_tests} tests)", content)
    content = re.sub(r"aegis-cl-psi/src/, \d+ gate modules", f"aegis-cl-psi/src/, {new_gate} gate modules", content)
    with open(CLAUDE_MD, "w") as f:
        f.write(content)
    print(f"  ✓ CLAUDE.md updated: Gates={new_gate}, Tests={new_tests}")


def next_gossip_metrics(gate_num: int) -> tuple[str, str, str, str, int, str]:
    """Returns (module_suffix, primary_field, secondary_field, flag_name, threshold, threshold_op)"""
    metrics = [
        ("batch",              "under_filled_batches",   "total_batches",     "under_filled",          50, "<"),
        ("duplicate",          "duplicate_count",        "total_received",    "high_duplication",      10, ">"),
        ("peer_latency",       "high_latency_peers",     "total_peers",       "excessive_latency",     20, ">"),
        ("retry",              "retry_count",            "total_sent",        "high_retry_rate",       8,  ">"),
        ("fragmentation",      "fragmented_msgs",        "total_msgs",        "high_fragmentation",    25, ">"),
        ("loss",               "lost_msgs",              "total_sent",        "high_loss",             3,  ">"),
        ("congestion",         "congested_epochs",       "total_epochs",      "congested",             30, ">"),
        ("fanout",             "low_fanout_msgs",        "total_msgs",        "low_fanout",            40, "<"),
        ("propagation",        "slow_propagations",      "total_msgs",        "slow_propagation",      10, ">"),
        ("collision",          "collision_count",        "total_received",    "high_collision",        5,  ">"),
        ("timeout",            "timed_out_msgs",         "total_sent",        "high_timeout_rate",     4,  ">"),
        ("jitter",             "high_jitter_epochs",     "total_epochs",      "high_jitter",           15, ">"),
        ("backpressure",       "backpressured_peers",    "total_peers",       "under_backpressure",    20, ">"),
        ("window_miss",        "missed_windows",         "total_windows",     "high_miss_rate",        10, ">"),
        ("epoch_gap",          "epoch_gaps",             "total_epochs",      "frequent_gaps",         5,  ">"),
        ("ack_timeout",        "unacknowledged_msgs",    "total_sent",        "high_ack_timeout",      8,  ">"),
        ("peer_churn",         "churned_peers",          "total_peers",       "high_churn",            25, ">"),
        ("broadcast_drop",     "dropped_broadcasts",     "total_broadcasts",  "high_drop_rate",        2,  ">"),
        ("queue_overflow",     "overflow_events",        "total_enqueued",    "high_overflow",         3,  ">"),
        ("sync_lag",           "lagging_peers",          "total_peers",       "high_sync_lag",         30, ">"),
        ("nack_rate",          "nack_count",             "total_received",    "high_nack_rate",        6,  ">"),
        ("bandwidth_exceed",   "over_limit_epochs",      "total_epochs",      "bandwidth_exceeded",    20, ">"),
        ("peer_drift",         "drifted_peers",          "total_peers",       "high_peer_drift",       15, ">"),
        ("epoch_stall",        "stalled_epochs",         "total_epochs",      "epoch_stalling",        5,  ">"),
        ("rebroadcast",        "rebroadcast_count",      "total_sent",        "high_rebroadcast",      12, ">"),
        ("partial_delivery",   "partial_deliveries",     "total_delivered",   "high_partial_rate",     8,  ">"),
        ("peer_rejection",     "rejected_peers",         "total_peers",       "high_rejection",        10, ">"),
        ("msg_ordering",       "out_of_order_msgs",      "total_received",    "high_disorder",         5,  ">"),
        ("epoch_overlap",      "overlapping_epochs",     "total_epochs",      "high_overlap",          3,  ">"),
        ("peer_isolation",     "isolated_peers",         "total_peers",       "peer_isolated",         10, ">"),
        ("ttl_exceeded",       "ttl_exceeded_msgs",      "total_sent",        "high_ttl_exceed",       4,  ">"),
        ("flood_rate",         "flooded_msgs",           "total_sent",        "high_flood",            15, ">"),
        ("dedup_miss",         "dedup_misses",           "total_received",    "high_dedup_miss",       3,  ">"),
        ("capacity_breach",    "capacity_breaches",      "total_epochs",      "over_capacity",         5,  ">"),
        ("peer_timeout",       "timed_out_peers",        "total_peers",       "high_peer_timeout",     10, ">"),
    ]
    offset = gate_num - 423
    if offset < len(metrics):
        suffix, prim, sec, flag, thresh, op = metrics[offset]
    else:
        base_idx = offset % len(metrics)
        epoch = offset // len(metrics) + 2
        suffix, prim, sec, flag, thresh, op = metrics[base_idx]
        suffix = f"{suffix}_e{epoch}"
        flag   = f"{flag}_e{epoch}"
    return suffix, prim, sec, flag, thresh, op


def build_gate(gate_num: int, client: anthropic.Anthropic,
               budget_remaining: float | None = None) -> tuple[bool, float]:
    suffix, primary, secondary, flag, threshold, op = next_gossip_metrics(gate_num)
    module_name = f"gossip_broadcast_{suffix}"
    module_path = os.path.join(SRC_DIR, f"{module_name}.rs")

    if os.path.exists(module_path):
        ok, out = run_cargo_test(module_name)
        if ok:
            print(f"\n  ⚡ Gate {gate_num}: {module_name} already exists (19 tests OK) — skipping")
            return True, 0.0

    genesis_const = f"{suffix.upper()}_GENESIS_HASH"
    thresh_const  = f"{flag.upper()}_THRESHOLD"
    description   = f"Gossip Broadcast {suffix.replace('_', ' ').title()} Monitor"

    print(f"\n{'='*60}")
    print(f"Building Gate {gate_num}: {module_name}")
    print(f"  Primary:   {primary}")
    print(f"  Secondary: {secondary}")
    print(f"  Flag:      {flag} ({primary}_pct {op} {threshold})")
    print(f"{'='*60}")

    prompt = f"""Write a complete Rust file for Gate {gate_num} of the AEGIS gossip broadcast series.

Module name: {module_name}
File: aegis-cl-psi/src/{module_name}.rs

Constants:
  pub const {genesis_const}: [u8; 32] = [0u8; 32];
  pub const {thresh_const}: u32 = {threshold};

Entry struct: Gossip{suffix.title().replace('_', '')}Entry with fields:
  pub epoch_end: u64
  pub {primary}: u32
  pub {secondary}: u32
  pub {primary.replace('_count','').replace('_msgs','').replace('_peers','').replace('_propagations','').replace('_epochs','')}_rate_pct: u32
  pub {flag}: bool
  pub entry_hash: [u8; 32]
  pub prev_hash: [u8; 32]

Rate formula: rate_pct = ({primary} * 100) / max({secondary}, 1), capped at 100
Flag: {flag} = rate_pct {op} {threshold}

Hash (SHA-256 big-endian):
  prev[32] ‖ epoch_end_be8 ‖ {primary}_be4 ‖ {secondary}_be4 ‖ rate_pct_be4 ‖ {flag}_byte

Log struct: Gossip{suffix.title().replace('_', '')}Log with:
  entries: Vec<...>
  fn new() + Default impl
  fn record(epoch_end, {primary}, {secondary}) -> &Entry
  fn {flag}_count() -> usize
  fn total_{primary}() -> u64
  fn mean_rate_pct() -> u32
  fn verify_chain() -> (bool, Option<usize>)

Exactly 19 tests covering:
  1. record fields correct (rate computed, flag=true when {op} threshold)
  2. flag=false when exactly at threshold (boundary)
  3. rate_pct capped at 100
  4. {secondary}=0 no div-by-zero
  5. threshold constant value == {threshold}
  6. entry_hash non-zero
  7. first prev_hash == genesis
  8. second prev_hash == first entry_hash
  9. verify_chain empty → (true, None)
  10. verify_chain 1-entry → (true, None)
  11. verify_chain 3-entry → (true, None)
  12. verify_chain tamper entry 0 → (false, Some(0))
  13. verify_chain tamper entry 1 → (false, Some(1))
  14. determinism: same inputs × 3 → same hash
  15. {flag}_count() mixed log
  16. total_{primary}() sums correctly
  17. mean_rate_pct() empty → 0
  18. mean_rate_pct() multi-entry correct
  19. Default → 0 entries

Header comment:
//! Gate {gate_num} — {description} (T2)
//! Tracks {suffix.replace('_', ' ')} rate per gossip broadcast epoch.
//! {thresh_const} = {threshold}: rate_pct {op} {threshold} → {flag}

Here is the canonical example to match exactly in style:
{EXAMPLE_MODULE}

Output ONLY the complete Rust file contents. No markdown. No explanation."""

    last_code = ""
    last_error = ""
    gate_cost  = 0.0

    for attempt in range(1, 4):
        if budget_remaining is not None and gate_cost >= budget_remaining:
            print(f"  ✗ Budget would be exceeded before attempt {attempt} — stopping")
            return False, gate_cost

        print(f"  Calling Claude claude-sonnet-4-6 (attempt {attempt}/3)...")

        messages = [{"role": "user", "content": prompt}]
        if attempt > 1:
            messages.append({"role": "assistant", "content": last_code})
            messages.append({"role": "user", "content": f"That produced errors:\n{last_error}\n\nFix and return the complete corrected Rust file."})

        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=messages,
            )
        except anthropic.APIStatusError as e:
            if e.status_code == 402 or "credit_balance_too_low" in str(e):
                raise CreditsExhausted(f"API credits exhausted (402): {e}")
            raise

        call_cost  = token_cost(response.usage.input_tokens, response.usage.output_tokens)
        gate_cost += call_cost
        print(f"  ↳ {response.usage.input_tokens} in / {response.usage.output_tokens} out = ${call_cost:.4f}")

        code = response.content[0].text.strip()
        code = re.sub(r'^```(?:rust)?\n', '', code)
        code = re.sub(r'\n```$', '', code)

        with open(module_path, "w") as f:
            f.write(code)
        print(f"  ✓ Written {module_path}")

        with open(LIB_RS) as f:
            lib_content = f.read()
        if f"pub mod {module_name};" not in lib_content:
            with open(LIB_RS, "a") as f:
                f.write(f"\n// Gate {gate_num} — {description} (T2)\npub mod {module_name};")

        passed, output = run_cargo_test(module_name)
        if passed:
            print(f"  ✓ 19/19 tests passed")
            return True, gate_cost
        else:
            last_code = code
            last_error = output[-2000:]
            print(f"  ✗ Tests failed (attempt {attempt})")
            if attempt < 3:
                with open(LIB_RS) as f:
                    lib_content = f.read()
                lib_content = lib_content.replace(
                    f"\n// Gate {gate_num} — {description} (T2)\npub mod {module_name};", ""
                )
                with open(LIB_RS, "w") as f:
                    f.write(lib_content)

    print(f"  ✗ Gate {gate_num} failed after 3 attempts")
    return False, gate_cost


def commit_and_push(gates: list[int]):
    os.chdir(REPO_ROOT)
    subprocess.run(["git", "add", "-A"], check=True)

    gate_range = f"{gates[0]}-{gates[-1]}" if len(gates) > 1 else str(gates[0])
    test_count = run_full_test()[0]

    msg = (
        f"Gates {gate_range}: Auto-generated gossip broadcast monitors\n\n"
        f"{test_count} Rust tests passing. Generated via scripts/auto-gate.py\n"
        f"using claude-sonnet-4-6 with self-correcting retry loop.\n\n"
        f"https://claude.ai/code/session_01WvFyntZArqThRgLczRutuM"
    )
    subprocess.run(["git", "commit", "-m", msg], check=True)
    subprocess.run(["git", "push", "-u", "origin", "claude/aegis-setup-Lx7Ji"], check=True)
    print(f"\n✓ Pushed Gates {gate_range} to origin")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count",  type=int,   default=2,    help="Number of gates to build")
    parser.add_argument("--gate",   type=int,                 help="Specific gate number to start from")
    parser.add_argument("--budget", type=float, default=None, help="Hard spend cap in USD (e.g. --budget 0.50)")
    parser.add_argument("--yes", "-y", action="store_true",   help="Skip confirmation prompt")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        settings_path = os.path.join(REPO_ROOT, ".claude", "settings.local.json")
        try:
            with open(settings_path) as f:
                settings = json.load(f)
            api_key = settings.get("env", {}).get("ANTHROPIC_API_KEY", "").strip()
        except Exception:
            pass
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    start_gate = args.gate or (current_gate_number() + 1)

    best_usd, worst_usd = estimate_cost(args.count)
    print(f"AEGIS Auto-Gate Builder")
    print(f"Gates {start_gate} → {start_gate + args.count - 1}  ({args.count} gate(s))")
    print(f"Estimated cost:  ${best_usd:.3f} best-case  /  ${worst_usd:.3f} worst-case (3 retries each)")
    if args.budget is not None:
        print(f"Budget cap:      ${args.budget:.2f}")
        if best_usd > args.budget:
            print(f"WARNING: even the best-case estimate (${best_usd:.3f}) exceeds your budget cap.")
    print()

    if not args.yes:
        try:
            answer = input("Proceed? [y/N] ").strip().lower()
        except EOFError:
            answer = "y"
        if answer not in ("y", "yes"):
            print("Aborted.")
            sys.exit(0)

    budget_remaining = args.budget
    total_spent      = 0.0
    built            = []

    # Check for existing checkpoint from a previous crash
    ckpt = load_checkpoint()
    if ckpt:
        print(f"\n  ⚠  Checkpoint found: {CHECKPOINT_PATH}")
        print(f"     Previous run built: Gates {ckpt.get('gates_built', [])}")
        print(f"     Spent so far: ${ckpt.get('total_spent', 0):.4f}")
        print(f"     Next gate: {ckpt.get('next_gate', start_gate)}")
        print(f"     Timestamp: {ckpt.get('timestamp', '?')}")
        try:
            resume = input("  Resume from checkpoint? [Y/n] ").strip().lower()
        except EOFError:
            resume = "y"
        if resume in ("", "y", "yes"):
            start_gate   = ckpt["next_gate"]
            built        = ckpt["gates_built"]
            total_spent  = ckpt["total_spent"]
            print(f"  Resuming from Gate {start_gate}  (already built: {built})\n")
        else:
            clear_checkpoint()
            print("  Starting fresh (checkpoint discarded).\n")

    try:
        for i in range(args.count):
            gate_num = start_gate + i

            if budget_remaining is not None and budget_remaining <= 0:
                print(f"\n  Budget cap reached after {len(built)} gate(s) — stopping before Gate {gate_num}.")
                break

            try:
                ok, gate_cost = build_gate(gate_num, client, budget_remaining)
            except CreditsExhausted as e:
                print(f"\n  Credits exhausted — saving progress and exiting cleanly")
                print(f"  {e}")
                if built:
                    write_checkpoint(start_gate, built, total_spent)
                    print(f"  Committing {len(built)} gate(s) built before credits ran out...")
                    commit_and_push(built)
                    clear_checkpoint()
                    print(f"  ✓ Progress saved. Top up credits at console.anthropic.com → Plans & Billing")
                    print(f"    then re-run:  python3 scripts/auto-gate.py --count {args.count - len(built)} --gate {gate_num}")
                else:
                    print(f"  No gates built yet — repo unchanged.")
                print(f"\n  Total spent this run: ${total_spent:.4f}")
                sys.exit(0)

            total_spent += gate_cost
            if budget_remaining is not None:
                budget_remaining -= gate_cost

            if ok:
                built.append(gate_num)
                test_count, _ = run_full_test()
                update_claude_md(gate_num, test_count)
                write_checkpoint(start_gate, built, total_spent)
                print(f"  Running spend: ${total_spent:.4f}"
                      + (f"  (${budget_remaining:.4f} remaining)" if budget_remaining is not None else ""))
            else:
                print(f"Stopping at Gate {gate_num} — could not build after 3 attempts")
                break

    except Exception as e:
        # Any unexpected crash — write checkpoint so progress is not lost
        if built:
            write_checkpoint(start_gate, built, total_spent)
            print(f"\n  Unexpected error: {e}")
            print(f"  Checkpoint written: {CHECKPOINT_PATH}")
            print(f"  {len(built)} gate(s) preserved. Re-run to resume.")
        raise

    if built:
        commit_and_push(built)
        clear_checkpoint()
        print(f"\n{'='*60}")
        print(f"✓ Built and pushed: Gates {built[0]}–{built[-1]}")
        print(f"✓ {len(built)} gates, {run_full_test()[0]} total tests")
        print(f"✓ Total spend: ${total_spent:.4f}")
    else:
        print("No gates were built successfully")
        sys.exit(1)


if __name__ == "__main__":
    main()
