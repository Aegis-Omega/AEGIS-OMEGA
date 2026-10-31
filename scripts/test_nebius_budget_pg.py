#!/usr/bin/env python3
"""Execute the actual Nebius SQL budget in an isolated local Postgres service.

No network access to Nebius, no API keys, no production database changes.
Running outside the dedicated aegis_budget_test database is forbidden.
"""
from __future__ import annotations

import concurrent.futures
import os
from pathlib import Path
import subprocess
import sys

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "supabase/migrations/20261031010000_nebius_attempt_budget_v1.sql"
)


def psql(sql: str, *, role: str | None = None) -> str:
    if role not in (None, "service_role"):
        raise ValueError("unsupported test role")
    query = ("SET ROLE service_role;\n" if role else "") + sql
    process = subprocess.run(
        ["psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-c", query],
        capture_output=True, text=True, check=False, timeout=30,
    )
    if process.returncode != 0:
        raise AssertionError(
            f"local Postgres assertion failed: returncode={process.returncode}; "
            f"stderr={process.stderr[-1000:]}"
        )
    return process.stdout.strip()


def check(actual: str, expected: str, description: str) -> None:
    if actual != expected:
        raise AssertionError(f"{description}: got {actual!r}, expected {expected!r}")
    print(f"PASS {description}", flush=True)


def main() -> int:
    # Refuse use with production credentials, even by accident.
    if not (
        os.environ.get("AEGIS_LOCAL_PG_TEST") == "1"
        and os.environ.get("PGHOST") == "127.0.0.1"
        and os.environ.get("PGDATABASE") == "aegis_budget_test"
        and os.environ.get("PGUSER") == "postgres"
    ):
        raise SystemExit("DENIED: isolated local postgres test environment not established")
    if not MIGRATION.is_file():
        raise SystemExit("DENIED: pinned budget migration source is missing")

    psql("CREATE ROLE anon NOLOGIN; CREATE ROLE authenticated NOLOGIN; "
         "CREATE ROLE service_role NOLOGIN BYPASSRLS;")
    migration = subprocess.run(
        ["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-f", str(MIGRATION)],
        capture_output=True, text=True, check=False, timeout=30,
    )
    if migration.returncode != 0:
        raise AssertionError(
            "budget migration failed: " + migration.stderr[-1500:]
        )
    print("PASS real migration applied to isolated Postgres", flush=True)

    check(
        psql("SELECT enabled::text || ':' || max_attempts::text || ':' || "
             "attempts_used::text FROM public.nebius_inference_budget_v1;"),
        "false:0:0",
        "default deny with zero attempts",
    )
    check(
        psql("SELECT public.reserve_nebius_inference_attempt_v1();", role="service_role"),
        "f",
        "service-only RPC denies without explicit budget",
    )
    check(
        psql("SELECT has_function_privilege('anon',"
             "'public.reserve_nebius_inference_attempt_v1()', 'EXECUTE')::text;"),
        "false", "anon cannot reserve an attempt",
    )
    check(
        psql("SELECT has_function_privilege('authenticated',"
             "'public.reserve_nebius_inference_attempt_v1()', 'EXECUTE')::text;"),
        "false", "authenticated cannot reserve an attempt",
    )
    check(
        psql("SELECT has_table_privilege('anon',"
             "'public.nebius_inference_budget_v1', 'SELECT')::text;"),
        "false", "anon cannot inspect budget",
    )
    psql("UPDATE public.nebius_inference_budget_v1 SET enabled=true, max_attempts=3;")
    # Independent sessions hit the same SQL UPDATE concurrently.
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(
            lambda _: psql(
                "SELECT public.reserve_nebius_inference_attempt_v1();",
                role="service_role",
            ),
            range(12),
        ))
    check(str(results.count("t")), "3", "exactly 3 of 12 concurrent reservations pass")
    check(str(results.count("f")), "9", "remaining 9 concurrent reservations deny")
    check(
        psql("SELECT attempts_used::text || ':' || max_attempts::text "
             "FROM public.nebius_inference_budget_v1;"),
        "3:3", "ledger never exceeds budget",
    )
    check(
        psql("SELECT public.reserve_nebius_inference_attempt_v1();", role="service_role"),
        "f", "exhaustion keeps denying",
    )
    psql("UPDATE public.nebius_inference_budget_v1 SET enabled=false;")
    check(
        psql("SELECT public.reserve_nebius_inference_attempt_v1();", role="service_role"),
        "f", "kill switch denies after budget enabled then disabled",
    )
    # Migration must not silently re-enable nor reset the consumed counter.
    twice = subprocess.run(
        ["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-f", str(MIGRATION)],
        capture_output=True, text=True, check=False, timeout=30,
    )
    if twice.returncode != 0:
        raise AssertionError("idempotent migration replay failed: " + twice.stderr[-1000:])
    check(
        psql("SELECT enabled::text || ':' || max_attempts::text || ':' || "
             "attempts_used::text FROM public.nebius_inference_budget_v1;"),
        "false:3:3", "migration replay preserves operator state and ledger",
    )
    print("PASS PostgreSQL budget isolation suite (no paid calls)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
