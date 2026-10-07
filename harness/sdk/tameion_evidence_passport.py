"""Deterministic, offline Evidence Passport v1; projection, never authority.

Input: a tameion_demo_cli packet (schema 1.0.0) plus an explicit context:
{"schema_version":"1.0", "subject":{"type":"treasury_demo","id":...,"label":...},
 "source":{"repository":"owner/repo","commit":"<40 lowercase hex>","ref":...},
 "preflight": <JSON form of an existing TameionAdmissionPreflight>}

A digest binds bytes, NOT the truth or authenticity of the supplied claims.
The verifier checks integrity and projection consistency. Pin --expected-root
from a separately trusted channel to detect complete artifact replacement.
Canonical encoding: UTF-8, sorted object keys, no whitespace, no floats; array
order is significant. No clocks, randomness or telemetry enter artifact bytes.
Output requires a new directory under an existing, trusted parent directory.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import html
import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Any

SCHEMA_VERSION = '1.0'
KIND = 'AEGIS_EVIDENCE_PASSPORT_V1'
MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_DEPTH = 32
SHA256 = re.compile(r'[0-9a-f]{64}\Z')
COMMIT = re.compile(r'[0-9a-f]{40}\Z')
SECRET_KEYS = frozenset({
    'privatekey', 'mnemonic', 'apikey', 'authorization', 'secret',
    'accesstoken', 'refreshtoken', 'clientsecret', 'password', 'seedphrase',
})
BASE_ROOTS = (
    'usage_root', 'settlement_policy_root', 'obligation_root',
    'treasury_intent_root', 'source_binding_root', 'transfer_plan_root',
    'unsigned_call_root', 'pre_settlement_bundle_root',
)
FINAL_ROOTS = (
    'settlement_observation_root', 'settlement_witness_root',
    'calibration_root', 'metered_evidence_chain_root',
)
NON_CLAIMS = (
    'This artifact does not authorize or execute a transfer.',
    'No signer, broadcast, custody or mainnet authority is introduced.',
    'A present digest does not authenticate upstream evidence or source identity.',
    'No live OpenMeter, Circle or Arc request is made by this renderer.',
)
FALSIFIERS = (
    'Identical canonical input produces different output bytes.',
    'Substantive input changes without changing the passport root.',
    'The presentation strengthens the supplied admission outcome.',
    'Missing evidence is concealed, or secret-bearing input reaches output.',
)


class PassportError(ValueError):
    """Stable error code only: never echo untrusted input or credential values."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise PassportError('PASSPORT_' + code)


def inspect_input(value: Any, depth: int = 0) -> None:
    """Inspect every field before filtering; reject secrets and ambiguous JSON."""
    _require(depth <= MAX_DEPTH, 'DEPTH_LIMIT')
    if isinstance(value, dict):
        for key, item in value.items():
            _require(type(key) is str, 'KEY_TYPE')
            normalized = re.sub(r'[^a-z0-9]', '', key.lower())
            _require(normalized not in SECRET_KEYS, 'SECRET_KEY')
            inspect_input(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            inspect_input(item, depth + 1)
    elif type(value) is str:
        _require(len(value) <= MAX_INPUT_BYTES, 'STRING_LIMIT')
        _require(not any(0xD800 <= ord(ch) <= 0xDFFF for ch in value), 'UNICODE_INVALID')
    else:
        _require(value is None or type(value) in (bool, int), 'JSON_TYPE')


def canonical_bytes(value: Any) -> bytes:
    inspect_input(value)
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False,
                          sort_keys=True, separators=(',', ':')).encode('utf-8')
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise PassportError('PASSPORT_JSON_INVALID') from exc


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, 'DUPLICATE_KEY')
        result[key] = value
    return result


def load_json(raw: bytes) -> dict[str, Any]:
    _require(type(raw) is bytes and len(raw) <= MAX_INPUT_BYTES, 'INPUT_SIZE')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object)
        inspect_input(value)
    except PassportError:
        raise
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise PassportError('PASSPORT_JSON_INVALID') from exc
    _require(isinstance(value, dict), 'MAPPING_REQUIRED')
    return value


def read_json(path: str | Path | None) -> dict[str, Any]:
    try:
        if path is None:
            raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        else:
            with Path(path).open('rb') as stream:
                raw = stream.read(MAX_INPUT_BYTES + 1)
    except OSError as exc:
        raise PassportError('PASSPORT_INPUT_READ_FAILED') from exc
    return load_json(raw)


def _fields(value: Any, required: set[str]) -> None:
    _require(isinstance(value, dict), 'MAPPING_REQUIRED')
    _require(set(value) == required, 'FIELDS_INVALID')


def _text(value: Any) -> None:
    _require(type(value) is str and 0 < len(value) <= 2048, 'TEXT_INVALID')
    _require(unicodedata.normalize('NFC', value) == value and
             not any(unicodedata.category(ch).startswith('C') for ch in value), 'TEXT_AMBIGUOUS')


def _hash(value: Any) -> None:
    _require(type(value) is str and SHA256.fullmatch(value) is not None, 'HASH_INVALID')


def _validate_context(context: dict[str, Any]) -> None:
    _fields(context, {'schema_version', 'subject', 'source', 'preflight'})
    _require(context['schema_version'] == SCHEMA_VERSION, 'CONTEXT_SCHEMA_UNSUPPORTED')
    subject, source, preflight = context['subject'], context['source'], context['preflight']
    _fields(subject, {'type', 'id', 'label'})
    _require(subject['type'] == 'treasury_demo', 'SUBJECT_TYPE')
    _text(subject['id']); _text(subject['label'])
    _fields(source, {'repository', 'commit', 'ref'})
    for value in source.values():
        _text(value)
    _require(re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', source['repository']) is not None,
             'REPOSITORY_INVALID')
    _require(COMMIT.fullmatch(source['commit']) is not None, 'COMMIT_INVALID')
    _fields(preflight, {'schema_version', 'capability', 'authority_domain', 'action_class',
                        'tool', 'evidence_root', 'outcome', 'denial_codes', 'authority_effect'})
    _require(preflight['schema_version'] == '1.0.0', 'PREFLIGHT_SCHEMA_UNSUPPORTED')
    for key, expected in (('capability', 'arc.testnet.transfer'),
                          ('authority_domain', 'treasury.testnet'), ('action_class', 'D3'),
                          ('tool', 'arc-plan'), ('authority_effect', 'NONE')):
        _require(preflight[key] == expected, 'PREFLIGHT_BOUNDARY_INVALID')
    _hash(preflight['evidence_root'])
    codes = preflight['denial_codes']
    _require(isinstance(codes, list) and all(type(c) is str and
             re.fullmatch(r'[A-Z][A-Z0-9_]{0,127}', c) for c in codes), 'DENIAL_CODES_INVALID')
    _require(len(codes) == len(set(codes)), 'DENIAL_CODES_DUPLICATE')
    _require((preflight['outcome'] == 'NOT_ADMITTED' and bool(codes)) or
             (preflight['outcome'] == 'READY_FOR_AUTHORITY_EVALUATION' and not codes),
             'PREFLIGHT_OUTCOME_INVALID')


def _validate_packet(packet: dict[str, Any]) -> None:
    _require(isinstance(packet, dict), 'MAPPING_REQUIRED')
    _require(packet.get('schema_version') == '1.0.0', 'PACKET_SCHEMA_UNSUPPORTED')
    status = packet.get('status')
    _require(status in ('PRE_SETTLEMENT_READY', 'SETTLEMENT_RECONCILED'), 'PACKET_STATUS_INVALID')
    required = {'schema_version', 'status', 'authority_effect', 'network_effect', 'unsigned_call', *BASE_ROOTS}
    if status == 'SETTLEMENT_RECONCILED':
        required.update((*FINAL_ROOTS, 'hallucination_delta_micros'))
    _fields(packet, required)
    _require(packet['authority_effect'] == 'NONE' and packet['network_effect'] == 'NONE', 'EFFECT_FORBIDDEN')
    for field in (*BASE_ROOTS, *FINAL_ROOTS):
        if field in packet:
            _hash(packet[field])
    if status == 'SETTLEMENT_RECONCILED':
        delta = packet['hallucination_delta_micros']
        _require(type(delta) is int and 0 <= delta <= 1_000_000, 'CALIBRATION_INVALID')
    call = packet['unsigned_call']
    _fields(call, {'network', 'chain_id', 'to', 'value', 'data', 'broadcast_allowed', 'signer_attached'})
    _require(call['network'] == 'ARC-TESTNET' and call['chain_id'] == '5042002', 'NETWORK_FORBIDDEN')
    _require(call['broadcast_allowed'] is False and call['signer_attached'] is False, 'AUTHORITY_FORBIDDEN')
    _require(type(call['value']) is int and call['value'] == 0, 'CALL_VALUE_INVALID')
    _require(type(call['to']) is str and
             call['to'].lower() == '0x3600000000000000000000000000000000000000', 'CALL_TARGET_INVALID')
    _require(type(call['data']) is str and
             re.fullmatch(r'0xa9059cbb0{24}[0-9a-f]{40}[0-9a-f]{64}', call['data']) is not None,
             'CALL_DATA_INVALID')


def build_passport(packet: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Project explicit upstream claims; never infer admission or VERIFIED status."""
    inspect_input(packet); inspect_input(context)
    _validate_packet(packet); _validate_context(context)
    packet, context = copy.deepcopy((packet, context))
    preflight = context['preflight']
    evidence = [{'id': field, 'type': 'SOURCE_PACKET_ROOT',
                 'status': 'PRESENT_UNVERIFIED' if field in packet else 'MISSING',
                 'root': packet.get(field), 'source': 'inputs.packet.' + field}
                for field in (*BASE_ROOTS, *FINAL_ROOTS)]
    evidence.append({'id': 'preflight_evidence_root', 'type': 'SOURCE_PREFLIGHT_ROOT',
                     'status': 'PRESENT_UNVERIFIED', 'root': preflight['evidence_root'],
                     'source': 'inputs.context.preflight.evidence_root'})
    result = {
        'schema_version': SCHEMA_VERSION, 'kind': KIND,
        'subject': copy.deepcopy(context['subject']), 'source': copy.deepcopy(context['source']),
        'packet_status': packet['status'],
        'governance': {**copy.deepcopy(preflight),
                       'signer_attached': packet['unsigned_call']['signer_attached'],
                       'broadcast_allowed': packet['unsigned_call']['broadcast_allowed'],
                       'mainnet_allowed': False},
        'evidence': evidence,
        'established': ['Canonical inputs and their projection are bound by the passport hash.'],
        'missing_requirements': [*preflight['denial_codes'],
                                 'INDEPENDENT_EVIDENCE_AUTHENTICATION_NOT_PERFORMED'],
        'non_claims': list(NON_CLAIMS), 'falsifiers': list(FALSIFIERS),
        'inputs': {'packet': packet, 'context': context},
    }
    result['passport_root'] = hashlib.sha256(canonical_bytes(result)).hexdigest()
    _require(len(canonical_bytes(result)) <= MAX_INPUT_BYTES, 'OUTPUT_SIZE')
    return result


def verify_passport(passport: dict[str, Any], *, expected_root: str | None = None) -> str:
    """VALID means integrity and projection only, not evidence authentication."""
    inspect_input(passport)
    _require(isinstance(passport, dict), 'MAPPING_REQUIRED')
    _require(passport.get('schema_version') == SCHEMA_VERSION and passport.get('kind') == KIND,
             'SCHEMA_UNSUPPORTED')
    root = passport.get('passport_root'); _hash(root)
    actual = hashlib.sha256(canonical_bytes({k: v for k, v in passport.items()
                                           if k != 'passport_root'})).hexdigest()
    _require(root == actual, 'HASH_MISMATCH')
    if expected_root is not None:
        _hash(expected_root)
        _require(root == expected_root, 'EXPECTED_ROOT_MISMATCH')
    inputs = passport.get('inputs')
    _fields(inputs, {'packet', 'context'})
    rebuilt = build_passport(inputs['packet'], inputs['context'])
    _require(canonical_bytes(passport) == canonical_bytes(rebuilt), 'PROJECTION_MISMATCH')
    return root


_STYLE = """
:root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#f3f5f4;
color:#142e2b;font:16px/1.55 system-ui,sans-serif}main{max-width:1100px;margin:auto;padding:40px 24px}
header{border-top:6px solid #145a50;padding:28px;background:white}h1{font-size:2rem;margin:.2em 0}
h1,li{overflow-wrap:anywhere}h2{font-size:1.25rem}section,details{background:white;padding:24px;margin-top:20px;border:1px solid #d8e2de}
.status{font-weight:750;border:2px solid #91610b;background:#fff7df;padding:12px;overflow-wrap:anywhere}
.eyebrow{font-size:.8rem;letter-spacing:.1em;font-weight:700}code,pre{font-family:ui-monospace,monospace;
font-size:.8rem;overflow-wrap:anywhere;white-space:pre-wrap}dl{display:grid;grid-template-columns:180px 1fr;
gap:8px}dd{margin:0;min-width:0}.columns{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:.9rem}
caption{text-align:left;margin-bottom:12px}th,td{text-align:left;vertical-align:top;border-bottom:1px solid #dde5e1;padding:12px 8px}
th{background:#f0f5f2}td:last-child{min-width:240px}summary{cursor:pointer;font-weight:650}
@media(max-width:700px){main{padding:16px}h1{font-size:1.6rem}table{min-width:640px}.columns{display:block}dl{grid-template-columns:1fr}dd{margin-bottom:8px}}
@media print{body{background:white}main{padding:0;max-width:none}section,header,details{break-inside:avoid}
.table-wrap{overflow:visible}table{font-size:9pt}code{font-size:8pt}.columns{display:block}}
"""


def render_html(passport: dict[str, Any]) -> bytes:
    verify_passport(passport)
    esc = lambda value: html.escape(str(value), quote=True)
    def items(values: list[str]) -> str:
        return '<ul>' + ''.join('<li>' + esc(value) + '</li>' for value in values) + '</ul>'
    rows = ''.join('<tr><th scope="row"><code>' + esc(row['id']) + '</code></th><td>' +
                   esc(row['status']) + '</td><td><code>' + esc(row['root'] or 'MISSING') +
                   '</code></td></tr>' for row in passport['evidence'])
    governance = passport['governance']
    boundary = ''.join('<dt>' + esc(key) + '</dt><dd><code>' + esc(
        json.dumps(governance[key]) if isinstance(governance[key], bool) else governance[key]) +
        '</code></dd>' for key in ('authority_effect', 'action_class', 'authority_domain',
                                  'capability', 'signer_attached', 'broadcast_allowed', 'mainnet_allowed'))
    source = passport['source']
    document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>AEGIS Evidence Passport</title><style>{_STYLE}</style></head><body><main>
<header><p class="eyebrow">AEGIS Ω / EVIDENCE PASSPORT V1</p>
<h1>{esc(passport['subject']['label'])}</h1>
<p class="status">{esc(governance['outcome'])} — EVIDENCE ONLY</p>
<p>Packet status: <code>{esc(passport['packet_status'])}</code>. This is not an admission decision.</p>
<p>This artifact does not authorize or execute a transfer.</p>
<dl><dt>Source repository</dt><dd><code>{esc(source['repository'])}</code></dd>
<dt>Source commit</dt><dd><code>{esc(source['commit'])}</code></dd>
<dt>Source ref</dt><dd><code>{esc(source['ref'])}</code></dd>
<dt>Passport root</dt><dd><code>{esc(passport['passport_root'])}</code></dd></dl></header>
<div class="columns"><section><h2>Established by this artifact</h2>{items(passport['established'])}
<p>Hash integrity does not authenticate evidence, source identity, hosted execution or settlement.
Every supplied evidence root remains PRESENT_UNVERIFIED.</p></section>
<section><h2>Not established / still required</h2>{items(passport['missing_requirements'])}</section></div>
<section><h2>Evidence lineage</h2><div class="table-wrap"><table>
<caption>Source-reported roots. Missing stages remain visible; presence is not verification.</caption>
<thead><tr><th scope="col">Stage</th><th scope="col">Evidence state</th><th scope="col">SHA-256 root</th></tr></thead>
<tbody>{rows}</tbody></table></div></section>
<section><h2>Governance boundary</h2><dl>{boundary}</dl>{items(passport['non_claims'])}</section>
<section><h2>Offline verification</h2><p>Use the companion JSON and an independently trusted expected root.
VALID reports integrity and projection consistency only.</p>
<pre>python -m harness.sdk.tameion_evidence_passport verify evidence-passport.json --expected-root {esc(passport['passport_root'])}</pre>
<p>Verify an HTML copy by regenerating it from the verified JSON and comparing bytes; the JSON root does not sign arbitrary HTML.</p>
<h2>Falsifiers</h2>{items(passport['falsifiers'])}</section>
<details><summary>Canonical raw JSON — untrusted source claims included</summary>
<pre>{esc(canonical_bytes(passport).decode('utf-8'))}</pre></details>
</main></body></html>
'''
    return document.encode('utf-8')


def write_passport(passport: dict[str, Any], directory: str | Path) -> None:
    """Build first, then publish both files via one same-filesystem directory rename.

    Never overwrite a pre-existing output. Parent must be trusted (no concurrent
    hostile directory writers); symlinks at the output path are rejected.
    """
    verify_passport(passport)
    encoded, rendered = canonical_bytes(passport) + b'\n', render_html(passport)
    target = Path(directory)
    _require(not target.exists() and not target.is_symlink(), 'OUTPUT_EXISTS')
    staging: Path | None = None
    try:
        staging = Path(tempfile.mkdtemp(prefix='.aegis-passport-', dir=target.parent))
        (staging / 'evidence-passport.json').write_bytes(encoded)
        (staging / 'evidence-passport.html').write_bytes(rendered)
        _require(not target.exists() and not target.is_symlink(), 'OUTPUT_EXISTS')
        os.rename(staging, target)
        staging = None
    except OSError as exc:
        raise PassportError('PASSPORT_OUTPUT_FAILED') from exc
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    verify = commands.add_parser('verify', help='Check integrity, not evidence authenticity')
    verify.add_argument('path')
    verify.add_argument('--expected-root')
    render = commands.add_parser('render', help='Project existing packet and preflight context offline')
    render.add_argument('--packet', required=True)
    render.add_argument('--context', required=True)
    render.add_argument('--output-dir', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'verify':
            print('VALID ' + verify_passport(read_json(args.path), expected_root=args.expected_root))
        else:
            passport = build_passport(read_json(args.packet), read_json(args.context))
            write_passport(passport, args.output_dir)
            print('PASSPORT ' + passport['passport_root'])
    except PassportError as exc:
        print('INVALID ' + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
