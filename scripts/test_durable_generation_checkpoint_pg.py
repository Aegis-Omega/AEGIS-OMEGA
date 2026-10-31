#!/usr/bin/env python3
"""Isolated PostgreSQL replay for a durable high-water checkpoint contract.

CI-only fixture. Uses no production database, no paid provider, no secrets.
A missing row always denies: the fixture is explicitly preseeded by this test.
"""
from __future__ import annotations

import concurrent.futures
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "scripts/sql/isolated_durable_generation_checkpoint_v1.sql"


def psql(query: str, *, service: bool = False) -> str:
    sql = ("SET ROLE service_role;\n" if service else "") + query
    result = subprocess.run(
        ["psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-c", sql],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if result.returncode:
        raise AssertionError(
            f"isolated checkpoint query failed rc={result.returncode}: "
            + result.stderr[-600:]
        )
    return result.stdout.strip()


def expect(actual: str, expected: str, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")
    print("PASS", label, flush=True)


def observe(policy: str, generation: str) -> str:
    # The role has only SELECT/UPDATE plus the restricted function EXECUTE.
    return psql(
        "SELECT outcome || ':' || COALESCE(persisted_generation, '-') "
        "FROM public.aegis_test_observe_advance_v1("
        f"'{policy}', '{generation}');",
        service=True,
    )


def install() -> None:
    result = subprocess.run(
        ["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-f", str(FIXTURE)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if result.returncode:
        raise AssertionError("isolated fixture install failed: " + result.stderr[-900:])


def main() -> int:
    if not (
        os.getenv("AEGIS_LOCAL_PG_TEST") == "1"
        and os.getenv("PGHOST") == "127.0.0.1"
        and os.getenv("PGDATABASE") == "aegis_budget_test"
        and os.getenv("PGUSER") == "postgres"
    ):
        raise SystemExit("DENIED: isolated PostgreSQL test prerequisites absent")
    if not FIXTURE.is_file():
        raise SystemExit("DENIED: pinned checkpoint fixture missing")

    # The earlier budget job precreates anon/authenticated/service_role locally.
    install()
    fn = "'public.aegis_test_observe_advance_v1(text,text)'"
    expect(psql(f"SELECT has_function_privilege('anon',{fn},'EXECUTE');"),
           "f", "anon cannot invoke generation function")
    expect(psql(f"SELECT has_function_privilege('authenticated',{fn},'EXECUTE');"),
           "f", "authenticated cannot invoke generation function")
    expect(psql("SELECT has_table_privilege('anon',"
                "'public.aegis_test_generation_floor_v1','SELECT');"),
           "f", "anon cannot read checkpoint floor")

    expect(observe("missing-policy", "10"), "UNAVAILABLE:-",
           "missing policy row fails closed")
    # Only privileged fixture setup may preseed the row.
    psql("INSERT INTO public.aegis_test_generation_floor_v1 "
         "(policy_id,generation) VALUES ('offline-policy','100');")
    expect(observe("offline-policy", "99"), "ROLLBACK:-",
           "older generation denied")
    expect(observe("offline-policy", "100"), "ACCEPTED:100",
           "equal trusted generation admitted")
    expect(observe("offline-policy", "bad"), "UNAVAILABLE:-",
           "noncanonical generation denied")
    expect(observe("offline-policy", "0100"), "UNAVAILABLE:-",
           "leading-zero generation denied")

    generations = [str(i) for i in range(101, 117)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        observations = list(pool.map(
            lambda g: observe("offline-policy", g), generations
        ))
    if any(not (x.startswith("ACCEPTED:") or x == "ROLLBACK:-")
           for x in observations):
        raise AssertionError("unexpected concurrent checkpoint result")
    expect(psql("SELECT generation FROM public.aegis_test_generation_floor_v1 "
                "WHERE policy_id='offline-policy';"),
           "116", "16 concurrent clients cannot decrease high-water mark")
    expect(observe("offline-policy", "115"), "ROLLBACK:-",
           "post-concurrency stale generation denied")

    # Long unsigned decimal generations must not overflow fixed SQL numerics.
    huge = "9" * 100
    expect(observe("offline-policy", huge), "ACCEPTED:" + huge,
           "100-digit generation persists atomically")
    expect(observe("offline-policy", "1" + "0" * 99), "ROLLBACK:-",
           "lexicographic rollback check works for 100-digit values")
    install()  # Replaying fixture must never reset the highest saved value.
    expect(psql("SELECT generation FROM public.aegis_test_generation_floor_v1 "
                "WHERE policy_id='offline-policy';"),
           huge, "fixture replay preserves durable high-water mark")
    print("PASS isolated PostgreSQL high-water checkpoint (no paid calls)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
