"""Execute vertex Cloud SQL audit contract tests without pytest."""
from __future__ import annotations

import inspect
import test_cloudsql_audit as suite


def main() -> int:
    tests = [
        (name, fn)
        for name, fn in vars(suite).items()
        if name.startswith("test_") and callable(fn)
    ]
    tests.sort(key=lambda pair: pair[0])
    failed = []
    for name, fn in tests:
        if inspect.signature(fn).parameters:
            failed.append((name, "test requires unsupported fixture parameters"))
            continue
        try:
            fn()
            print(f"PASS {name}")
        except Exception as exc:  # noqa: BLE001
            failed.append((name, f"{type(exc).__name__}: {exc}"))
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
    print(f"executed={len(tests)} passed={len(tests)-len(failed)} failed={len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
