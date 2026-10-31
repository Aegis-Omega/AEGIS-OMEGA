#!/usr/bin/env python3
"""Read-only cross-language verifier for AEGIS Apple receipt schemas 1.0.0/1.1.0.

Integrity + optional content matching, NOT model/issuer authentication or admission.
No network, dependencies, keys, paid services, or side effects.
"""
import argparse
import hashlib
import json
import math
import re
import struct
import sys
from pathlib import Path

MAX_RECEIPT_BYTES = 65536
REQUIRED = {
    'schema_version', 'provider_id', 'model_id', 'prompt_sha256',
    'output_sha256', 'prompt_bytes', 'output_bytes', 'max_tokens',
    'temperature_milli', 'outcome', 'authority_effect', 'receipt_sha256',
}
SHA256_HEX = re.compile(r'[0-9a-f]{64}\Z')
FLOAT_HEX = re.compile(r'[0-9a-f]{8}\Z')

class InvalidReceipt(ValueError):
    pass


def strict_pairs(pairs):
    obj = {}
    for k, v in pairs:
        if k in obj:
            raise InvalidReceipt('duplicate field: ' + k)
        obj[k] = v
    return obj


def read_receipt(data):
    if len(data) > MAX_RECEIPT_BYTES:
        raise InvalidReceipt('receipt too large')
    try:
        obj = json.loads(data, object_pairs_hook=strict_pairs,
                         parse_constant=lambda _: (_ for _ in ()).throw(InvalidReceipt('nonfinite JSON number')))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise InvalidReceipt('invalid JSON or UTF-8') from e
    if not isinstance(obj, dict):
        raise InvalidReceipt('receipt must be a JSON object')
    return obj


def canonical_preimage(r):
    fields = {k: v for k, v in r.items() if k != 'receipt_sha256'}
    return json.dumps(fields, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def verify_integrity(r):
    if not isinstance(r, dict):
        raise InvalidReceipt('not an object')
    v = r.get('schema_version')
    if v not in ('1.0.0', '1.1.0'):
        raise InvalidReceipt('unsupported receipt schema')
    expected = REQUIRED | ({'temperature_float_bits_hex'} if v == '1.1.0' else set())
    if set(r) != expected:
        raise InvalidReceipt('missing or unexpected fields: ' + ', '.join(sorted(set(r) ^ expected)))
    consts = {'provider_id': 'apple-foundation-models',
              'model_id': 'apple-system-language-model-default',
              'outcome': 'SUCCEEDED', 'authority_effect': 'NONE'}
    for k, value in consts.items():
        if r[k] != value or not isinstance(r[k], str):
            raise InvalidReceipt('invalid constant field: ' + k)
    for k in ('prompt_sha256', 'output_sha256', 'receipt_sha256'):
        if not isinstance(r[k], str) or not SHA256_HEX.fullmatch(r[k]):
            raise InvalidReceipt('invalid digest: ' + k)
    for k in ('prompt_bytes', 'output_bytes', 'max_tokens', 'temperature_milli'):
        if type(r[k]) is not int:
            raise InvalidReceipt('not an integer: ' + k)
    if not (1 <= r['prompt_bytes'] <= 16384 and r['output_bytes'] >= 0
            and 1 <= r['max_tokens'] <= 1024
            and 0 <= r['temperature_milli'] <= 1000):
        raise InvalidReceipt('out-of-bounds parameters')
    if v == '1.1.0':
        bits = r['temperature_float_bits_hex']
        if not isinstance(bits, str) or not FLOAT_HEX.fullmatch(bits):
            raise InvalidReceipt('invalid Float32 bits')
        temp = struct.unpack('>f', bytes.fromhex(bits))[0]
        if not (math.isfinite(temp) and 0.0 <= temp <= 1.0):
            raise InvalidReceipt('out-of-range Float32 temperature')
        if math.floor(float(temp) * 1000.0 + 0.5) != r['temperature_milli']:
            raise InvalidReceipt('Float32 temperature does not match temperature_milli')
    actual = hashlib.sha256(canonical_preimage(r)).hexdigest()
    if actual != r['receipt_sha256']:
        raise InvalidReceipt('receipt SHA-256 mismatch')
    return True


def verify_file(file_path, expected_bytes, expected_digest):
    digest = hashlib.sha256()
    total = 0
    with open(file_path, 'rb') as fh:
        while block := fh.read(65536):
            total += len(block)
            digest.update(block)
    if total != expected_bytes or digest.hexdigest() != expected_digest:
        raise InvalidReceipt('content bytes or SHA-256 mismatch: ' + str(file_path))
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('receipt', help='JSON receipt path, or - to read stdin')
    parser.add_argument('--prompt-file', type=Path, help='optional UTF-8 prompt to verify')
    parser.add_argument('--output-file', type=Path, help='optional UTF-8 model output to verify')
    args = parser.parse_args(argv)
    if (args.prompt_file is None) != (args.output_file is None):
        parser.error('--prompt-file and --output-file must be supplied together')
    try:
        raw = sys.stdin.buffer.read(MAX_RECEIPT_BYTES + 1) if args.receipt == '-' else Path(args.receipt).read_bytes()
        receipt = read_receipt(raw)
        verify_integrity(receipt)
        if args.prompt_file is not None:
            verify_file(args.prompt_file, receipt['prompt_bytes'], receipt['prompt_sha256'])
            verify_file(args.output_file, receipt['output_bytes'], receipt['output_sha256'])
        print('VERIFIED: hash and receipt schema integrity; content ' +
              ('matched' if args.prompt_file else 'NOT checked') +
              '. NO issuer authentication or governance authority.')
        return 0
    except (InvalidReceipt, OSError, ValueError) as exc:
        print('INVALID RECEIPT: ' + str(exc), file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
