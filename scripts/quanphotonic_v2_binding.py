#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

EXIT_FAIL_CLOSED = 78
MAX_SAFE_INTEGER = 9007199254740991


class FailClosed(RuntimeError):
    pass


def _utf16_sort_key(s: str) -> bytes:
    return s.encode('utf-16-be', 'surrogatepass')


def _jcs(obj: Any) -> str:
    if obj is None:
        return 'null'
    if obj is True:
        return 'true'
    if obj is False:
        return 'false'
    if isinstance(obj, int) and not isinstance(obj, bool):
        if abs(obj) > MAX_SAFE_INTEGER:
            raise FailClosed('CANONICALIZATION_UNSAFE_INTEGER')
        return str(obj)
    if isinstance(obj, float):
        raise FailClosed('CANONICALIZATION_FLOAT_FORBIDDEN')
    if isinstance(obj, str):
        return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
    if isinstance(obj, list):
        return '[' + ','.join(_jcs(v) for v in obj) + ']'
    if isinstance(obj, dict):
        if not all(isinstance(k, str) for k in obj):
            raise FailClosed('CANONICALIZATION_NON_STRING_KEY')
        return '{' + ','.join(
            json.dumps(k, ensure_ascii=False, separators=(',', ':')) + ':' + _jcs(obj[k])
            for k in sorted(obj, key=_utf16_sort_key)
        ) + '}'
    raise FailClosed('CANONICALIZATION_UNSUPPORTED_TYPE')


def digest_without_field(obj: dict, field: str) -> str:
    if field not in obj:
        raise FailClosed(f'DIGEST_FIELD_MISSING:{field}')
    material = dict(obj)
    material.pop(field)
    return hashlib.sha256(_jcs(material).encode('utf-8')).hexdigest()


def load_object(path: Path, code: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise FailClosed(f'{code}:{exc}') from exc
    if not isinstance(value, dict):
        raise FailClosed(f'{code}:TOP_LEVEL_NOT_OBJECT')
    return value


def verify_context(context: dict) -> str:
    if context.get('schema_version') != 'QUANPHOTONIC_BIOLOGICAL_CONTEXT_MANIFEST_V1':
        raise FailClosed('BIOLOGICAL_CONTEXT_SCHEMA_UNSUPPORTED')
    expected = context.get('biological_context_digest')
    actual = digest_without_field(context, 'biological_context_digest')
    if expected != actual:
        raise FailClosed('BIOLOGICAL_CONTEXT_MISMATCH')
    context_id = context.get('biological_context_id')
    if not isinstance(context_id, str) or not context_id:
        raise FailClosed('BIOLOGICAL_CONTEXT_ID_INVALID')
    return actual


def verify_measurement(measurement: dict, context_digest: str) -> str:
    schema = measurement.get('schema_version')
    if schema == 'QUANPHOTONIC_MEASUREMENT_BATCH_V1':
        raise FailClosed('V1_DOWNGRADE_FORBIDDEN')
    if schema != 'QUANPHOTONIC_MEASUREMENT_BATCH_V2':
        raise FailClosed('MEASUREMENT_SCHEMA_UNSUPPORTED')
    expected = measurement.get('measurement_batch_digest')
    actual = digest_without_field(measurement, 'measurement_batch_digest')
    if expected != actual:
        raise FailClosed('MEASUREMENT_BATCH_DIGEST_MISMATCH')
    if measurement.get('biological_context_digest') != context_digest:
        raise FailClosed('BIOLOGICAL_CONTEXT_MISMATCH')
    return actual


def verify_registry(context: dict, registry_path: Path | None) -> None:
    if registry_path is None:
        return
    registry = load_object(registry_path, 'CONTEXT_REGISTRY_INVALID')
    context_id = context['biological_context_id']
    prior = registry.get(context_id)
    if prior is not None and prior != context['biological_context_digest']:
        raise FailClosed('STALE_CONTEXT_REPLAY')


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument('--biological-context', type=Path)
    p.add_argument('--measurement', required=True, type=Path)
    p.add_argument('--context-registry', type=Path)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.biological_context is None or not args.biological_context.is_file():
        raise FailClosed('BIOLOGICAL_CONTEXT_MISSING')
    if not args.measurement.is_file():
        raise FailClosed('MEASUREMENT_MISSING')

    context = load_object(args.biological_context, 'BIOLOGICAL_CONTEXT_INVALID')
    context_digest = verify_context(context)
    verify_registry(context, args.context_registry)
    measurement = load_object(args.measurement, 'MEASUREMENT_INVALID')
    measurement_digest = verify_measurement(measurement, context_digest)

    print(
        'QP_PD_V2_BINDING_OK '
        f'context_id={context["biological_context_id"]} '
        f'biological_context_digest={context_digest} '
        f'measurement_batch_digest={measurement_digest}'
    )
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except FailClosed as exc:
        print(f'FAIL_CLOSED:{exc}', file=sys.stderr)
        raise SystemExit(EXIT_FAIL_CLOSED)
