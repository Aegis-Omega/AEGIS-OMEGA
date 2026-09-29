"""Evidence Passport contract tests. All vectors are synthetic, not live receipts."""
from __future__ import annotations

import copy
import hashlib
import json
import runpy
import os
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
try:
    from harness.sdk import tameion_evidence_passport as ep
except ImportError:
    ep = None

BASE_ROOTS = (
    'usage_root', 'settlement_policy_root', 'obligation_root',
    'treasury_intent_root', 'source_binding_root', 'transfer_plan_root',
    'unsigned_call_root', 'pre_settlement_bundle_root',
)
FINAL_ROOTS = (
    'settlement_observation_root', 'settlement_witness_root',
    'calibration_root', 'metered_evidence_chain_root',
)


def fixture_packet():
    return {
        'schema_version': '1.0.0', 'status': 'PRE_SETTLEMENT_READY',
        'authority_effect': 'NONE', 'network_effect': 'NONE',
        **{key: hashlib.sha256(key.encode()).hexdigest() for key in BASE_ROOTS},
        'unsigned_call': {
            'network': 'ARC-TESTNET', 'chain_id': '5042002',
            'to': '0x3600000000000000000000000000000000000000', 'value': 0,
            'data': '0xa9059cbb' + '0' * 24 + '22' * 20 + f'{100:064x}',
            'broadcast_allowed': False, 'signer_attached': False,
        },
    }


def fixture_context():
    return {
        'schema_version': '1.0',
        'subject': {'type': 'treasury_demo', 'id': 'synthetic-fixture',
                    'label': 'Synthetic fixture — not live execution'},
        'source': {'repository': 'example/test-fixture', 'commit': 'a' * 40,
                   'ref': 'test/fixture'},
        'preflight': {
            'schema_version': '1.0.0', 'capability': 'arc.testnet.transfer',
            'authority_domain': 'treasury.testnet', 'action_class': 'D3',
            'tool': 'arc-plan', 'evidence_root': 'e' * 64,
            'outcome': 'NOT_ADMITTED', 'denial_codes': ['OPERATOR_APPROVAL_MISSING'],
            'authority_effect': 'NONE',
        },
    }


class PassportTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(ep, 'Evidence Passport feature is not implemented')
        self.packet = fixture_packet()
        self.context = fixture_context()

    def build(self):
        return ep.build_passport(self.packet, self.context)

    def test_demo_cli_exposes_explicit_passport_flags(self):
        source = (REPO_ROOT / 'harness/sdk/tameion_demo_cli.py').read_text()
        self.assertIn('"--passport-dir"', source)
        self.assertIn('"--passport-context"', source)

    def test_round_trip_integrity_and_exact_hash(self):
        result = self.build()
        root = result['passport_root']
        body = {key: value for key, value in result.items() if key != 'passport_root'}
        self.assertEqual(root, hashlib.sha256(ep.canonical_bytes(body)).hexdigest())
        self.assertEqual(ep.verify_passport(result, expected_root=root), root)
        self.assertEqual(ep.load_json(ep.canonical_bytes(result)), result)

    def test_mapping_order_is_not_semantic(self):
        first = self.build()
        self.packet = dict(reversed(list(self.packet.items())))
        self.context = dict(reversed(list(self.context.items())))
        self.assertEqual(ep.canonical_bytes(first), ep.canonical_bytes(self.build()))
        self.assertEqual(ep.render_html(first), ep.render_html(self.build()))

    def test_input_is_not_mutated_or_aliased(self):
        before = copy.deepcopy((self.packet, self.context))
        result = self.build()
        self.assertEqual(before, (self.packet, self.context))
        self.context['source']['commit'] = 'b' * 40
        self.assertEqual(result['source']['commit'], 'a' * 40)

    def test_every_source_root_changes_passport_root(self):
        original = self.build()['passport_root']
        for field in BASE_ROOTS:
            with self.subTest(field=field):
                packet = copy.deepcopy(self.packet)
                packet[field] = 'f' * 64
                self.assertNotEqual(ep.build_passport(packet, self.context)['passport_root'], original)

    def test_source_commit_denial_amount_and_destination_are_bound(self):
        original = self.build()['passport_root']
        for mutation in ('commit', 'denial', 'amount', 'destination', 'label'):
            with self.subTest(mutation=mutation):
                packet, context = copy.deepcopy((self.packet, self.context))
                if mutation == 'commit':
                    context['source']['commit'] = 'b' * 40
                elif mutation == 'denial':
                    context['preflight']['denial_codes'] = ['HOSTED_REPLAY_NOT_EXECUTED']
                elif mutation == 'label':
                    context['subject']['label'] += ' changed'
                elif mutation == 'amount':
                    packet['unsigned_call']['data'] = packet['unsigned_call']['data'][:-64] + f'{101:064x}'
                else:
                    packet['unsigned_call']['data'] = '0xa9059cbb' + '0' * 24 + '33' * 20 + f'{100:064x}'
                self.assertNotEqual(ep.build_passport(packet, context)['passport_root'], original)

    def test_tamper_is_rejected(self):
        passport = self.build()
        passport['source']['commit'] = 'b' * 40
        with self.assertRaisesRegex(ep.PassportError, 'HASH_MISMATCH'):
            ep.verify_passport(passport)

    def test_rehashed_projection_lie_is_rejected(self):
        passport = self.build()
        passport['governance']['outcome'] = 'ADMITTED'
        passport['passport_root'] = hashlib.sha256(ep.canonical_bytes(
            {k: v for k, v in passport.items() if k != 'passport_root'})).hexdigest()
        with self.assertRaisesRegex(ep.PassportError, 'PROJECTION_MISMATCH'):
            ep.verify_passport(passport)

    def test_expected_root_is_required_to_detect_complete_replacement(self):
        root = self.build()['passport_root']
        self.context['subject']['label'] += ' replacement'
        replacement = self.build()
        self.assertEqual(ep.verify_passport(replacement), replacement['passport_root'])
        with self.assertRaisesRegex(ep.PassportError, 'EXPECTED_ROOT_MISMATCH'):
            ep.verify_passport(replacement, expected_root=root)

    def test_not_admitted_never_promoted(self):
        result = self.build()
        text = ep.render_html(result).decode()
        self.assertEqual(result['governance']['outcome'], 'NOT_ADMITTED')
        self.assertIn('NOT_ADMITTED', text)
        self.assertIn('OPERATOR_APPROVAL_MISSING', text)
        for phrase in ('approved', 'ready to execute', 'production ready', 'authorized'):
            self.assertNotIn(phrase, text.lower())
        self.assertEqual(result['governance']['authority_effect'], 'NONE')
        self.assertFalse(result['governance']['mainnet_allowed'])

    def test_ready_for_evaluation_is_not_admission(self):
        self.context['preflight']['outcome'] = 'READY_FOR_AUTHORITY_EVALUATION'
        self.context['preflight']['denial_codes'] = []
        text = ep.render_html(self.build()).decode()
        self.assertIn('READY_FOR_AUTHORITY_EVALUATION', text)
        self.assertIn('does not authorize or execute a transfer', text)

    def test_root_presence_is_never_verified_evidence(self):
        result = self.build()
        statuses = {item['status'] for item in result['evidence']}
        self.assertEqual(statuses, {'PRESENT_UNVERIFIED', 'MISSING'})
        self.assertIn('not authenticate', ep.render_html(result).decode())

    def test_missing_stages_stay_visible(self):
        result = self.build()
        for key in FINAL_ROOTS:
            row = next(item for item in result['evidence'] if item['id'] == key)
            self.assertEqual(row['status'], 'MISSING')
            self.assertIsNone(row['root'])
            self.assertIn(key, ep.render_html(result).decode())

    def test_settlement_packet_binds_all_optional_roots(self):
        self.packet['status'] = 'SETTLEMENT_RECONCILED'
        self.packet['hallucination_delta_micros'] = 100000
        self.packet.update({key: 'c' * 64 for key in FINAL_ROOTS})
        result = self.build()
        for key in FINAL_ROOTS:
            self.assertEqual(next(x for x in result['evidence'] if x['id'] == key)['root'], 'c' * 64)
        self.assertEqual(result['governance']['outcome'], 'NOT_ADMITTED')

    def test_partial_settlement_claim_is_rejected(self):
        self.packet['status'] = 'SETTLEMENT_RECONCILED'
        with self.assertRaises(ep.PassportError):
            self.build()

    def test_unknown_packet_schema_is_rejected(self):
        self.packet['schema_version'] = '999'
        with self.assertRaisesRegex(ep.PassportError, 'SCHEMA'):
            self.build()

    def test_unknown_context_schema_is_rejected(self):
        self.context['schema_version'] = '999'
        with self.assertRaisesRegex(ep.PassportError, 'SCHEMA'):
            self.build()

    def test_bad_hashes_and_commit_are_rejected(self):
        for bad in ('g' * 64, 'a' * 63, 'A' * 64, None, 12):
            with self.subTest(value=bad):
                packet = copy.deepcopy(self.packet)
                packet['usage_root'] = bad
                with self.assertRaises(ep.PassportError):
                    ep.build_passport(packet, self.context)
        self.context['source']['commit'] = 'main'
        with self.assertRaises(ep.PassportError):
            self.build()

    def test_non_mapping_and_missing_provenance_are_rejected(self):
        for bad in ([], None, 'x', True):
            with self.assertRaises(ep.PassportError):
                ep.build_passport(bad, self.context)
        del self.context['source']['commit']
        with self.assertRaises(ep.PassportError):
            self.build()

    def test_unknown_fields_are_not_silently_dropped(self):
        self.packet['unknown_new_root'] = 'a' * 64
        with self.assertRaisesRegex(ep.PassportError, 'FIELDS'):
            self.build()

    def test_nested_secret_key_variants_are_rejected_before_projection(self):
        for key in ('private_key', 'PRIVATE-KEY', 'privateKey', 'mnemonic',
                    'api_key', 'APIKey', 'authorization', 'secret',
                    'access_token', 'refresh_token', 'clientSecret', 'password'):
            with self.subTest(key=key):
                packet = copy.deepcopy(self.packet)
                packet['ignored'] = [{'nested': {key: 'DO_NOT_PERSIST_SENTINEL'}}]
                with self.assertRaisesRegex(ep.PassportError, 'SECRET_KEY') as raised:
                    ep.build_passport(packet, self.context)
                self.assertNotIn('DO_NOT_PERSIST_SENTINEL', str(raised.exception))

    def test_html_is_inert_and_has_no_network_or_execution_controls(self):
        self.context['subject']['label'] = '<script>alert(1)</script><img src="https://bad.invalid/x">'
        text = ep.render_html(self.build()).decode()
        class Tags(HTMLParser):
            def __init__(self):
                super().__init__(); self.tags = []; self.attrs = []
            def handle_starttag(self, tag, attrs):
                self.tags.append(tag); self.attrs.extend(attrs)
        tags = Tags(); tags.feed(text)
        self.assertNotIn('script', tags.tags)
        self.assertNotIn('img', tags.tags)
        self.assertNotIn('button', tags.tags)
        self.assertNotIn('form', tags.tags)
        self.assertFalse(any(key in ('href', 'src', 'onclick') for key, _ in tags.attrs))
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', text)
        self.assertIn('default-src', text)

    def test_authority_escalation_is_rejected(self):
        for field, value in (('broadcast_allowed', True), ('signer_attached', True),
                             ('chain_id', '5042'), ('network', 'ARC-MAINNET'),
                             ('broadcast_allowed', 0)):
            with self.subTest(field=field, value=value):
                packet = copy.deepcopy(self.packet)
                packet['unsigned_call'][field] = value
                with self.assertRaises(ep.PassportError):
                    ep.build_passport(packet, self.context)
        self.context['preflight']['outcome'] = 'ADMITTED'
        with self.assertRaises(ep.PassportError):
            self.build()

    def test_duplicate_keys_nonfinite_floats_and_depth_fail_closed(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}',
                    b'{"a":1.25}', b'[]', b'\xff', b'[' * 80 + b'0' + b']' * 80):
            with self.subTest(raw=raw[:40]):
                with self.assertRaises(ep.PassportError):
                    ep.load_json(raw)

    def test_output_files_roundtrip_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / 'passport'
            passport = self.build()
            ep.write_passport(passport, directory)
            stored = ep.load_json((directory / 'evidence-passport.json').read_bytes())
            self.assertEqual(ep.verify_passport(stored), passport['passport_root'])
            self.assertEqual((directory / 'evidence-passport.html').read_bytes(), ep.render_html(passport))
            with self.assertRaises(ep.PassportError):
                ep.write_passport(passport, directory)

    def test_validation_failure_leaves_no_directory(self):
        passport = self.build(); passport['passport_root'] = '0' * 64
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / 'passport'
            with self.assertRaises(ep.PassportError):
                ep.write_passport(passport, directory)
            self.assertFalse(directory.exists())
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_write_failure_cleans_staging(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / 'passport'
            with patch.object(ep.os, 'rename', side_effect=OSError('test failure')):
                with self.assertRaisesRegex(ep.PassportError, 'OUTPUT'):
                    ep.write_passport(self.build(), directory)
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_three_hashseed_replays_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as temp:
            packet, context = Path(temp) / 'packet.json', Path(temp) / 'context.json'
            packet.write_bytes(ep.canonical_bytes(self.packet))
            context.write_bytes(ep.canonical_bytes(self.context))
            results = []
            for seed in ('1', '7', '101'):
                directory = Path(temp) / seed
                run = subprocess.run([
                    sys.executable, '-m', 'harness.sdk.tameion_evidence_passport',
                    'render', '--packet', str(packet), '--context', str(context),
                    '--output-dir', str(directory),
                ], cwd=REPO_ROOT, env={**os.environ, 'PYTHONHASHSEED': seed},
                    capture_output=True, timeout=15)
                self.assertEqual(run.returncode, 0, run.stderr.decode())
                results.append(tuple(hashlib.sha256((directory / f'evidence-passport.{ext}').read_bytes()).hexdigest()
                                     for ext in ('json', 'html')))
            self.assertEqual(len(set(results)), 1)

    def test_offline_verify_command_and_expected_root(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'passport.json'
            result = self.build(); path.write_bytes(ep.canonical_bytes(result))
            command = [sys.executable, '-m', 'harness.sdk.tameion_evidence_passport', 'verify', str(path)]
            run = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, timeout=15)
            self.assertEqual(run.returncode, 0)
            self.assertEqual(run.stdout.decode().strip(), 'VALID ' + result['passport_root'])
            run = subprocess.run(command + ['--expected-root', 'f' * 64],
                                 cwd=REPO_ROOT, capture_output=True, timeout=15)
            self.assertEqual(run.returncode, 2)
            self.assertIn('EXPECTED_ROOT_MISMATCH', run.stderr.decode())

    def test_invalid_cli_input_leaks_no_secret_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as temp:
            packet, context = Path(temp) / 'packet.json', Path(temp) / 'context.json'
            packet.write_text('{"private_key":"DO_NOT_PERSIST_SENTINEL"}')
            context.write_bytes(ep.canonical_bytes(self.context))
            directory = Path(temp) / 'out'
            run = subprocess.run([
                sys.executable, '-m', 'harness.sdk.tameion_evidence_passport',
                'render', '--packet', str(packet), '--context', str(context),
                '--output-dir', str(directory),
            ], cwd=REPO_ROOT, capture_output=True, timeout=15)
            self.assertEqual(run.returncode, 2)
            self.assertNotIn(b'DO_NOT_PERSIST_SENTINEL', run.stdout + run.stderr)
            self.assertFalse(directory.exists())


class PassportIntegrationTests(unittest.TestCase):
    """Run against the actual repository producer and admission preflight, not mocks."""

    def fixture(self):
        from dataclasses import asdict
        from harness.sdk.tameion_admission_preflight import (
            TameionAdmissionEvidence, evaluate_tameion_admission_preflight,
        )
        symbols = runpy.run_path(str(REPO_ROOT / 'sovereign-omega-v2/python/tests/test_tameion_demo_cli.py'))
        payload = symbols['TameionDemoCliTests']().payload()
        context = fixture_context()
        preflight = evaluate_tameion_admission_preflight(TameionAdmissionEvidence(
            schema_version='1.0.0', source_commit=context['source']['commit'],
            validated_runs=0, openmeter_observation_root=None, operator_approval_root=None,
            hosted_replay_executed=False, runner_pre_step_failures=0,
        ))
        context['preflight'] = json.loads(json.dumps(asdict(preflight)))
        return payload, context

    def test_actual_producer_to_passport_to_verifier(self):
        from harness.sdk.tameion_demo_cli import build_demo_packet
        payload, context = self.fixture()
        packet = build_demo_packet(payload)
        passport = ep.build_passport(packet, context)
        self.assertEqual(ep.verify_passport(passport), passport['passport_root'])
        self.assertEqual(passport['governance']['outcome'], 'NOT_ADMITTED')
        for key, value in packet.items():
            if key.endswith('_root'):
                self.assertEqual(next(row for row in passport['evidence'] if row['id'] == key)['root'], value)

    def test_cli_default_stdout_is_identical_with_and_without_passport(self):
        from harness.sdk.sovereign_execution import canonical_bytes
        from harness.sdk.tameion_demo_cli import build_demo_packet
        payload, context = self.fixture()
        expected = canonical_bytes(build_demo_packet(payload)) + b'\n'
        with tempfile.TemporaryDirectory() as temp:
            inp, ctx, out = Path(temp) / 'input.json', Path(temp) / 'context.json', Path(temp) / 'report'
            inp.write_bytes(ep.canonical_bytes(payload)); ctx.write_bytes(ep.canonical_bytes(context))
            cmd = [sys.executable, '-m', 'harness.sdk.tameion_demo_cli', '--input', str(inp)]
            for extra in ([], ['--passport-dir', str(out), '--passport-context', str(ctx)]):
                run = subprocess.run(cmd + extra, cwd=REPO_ROOT, capture_output=True, timeout=15)
                self.assertEqual(run.returncode, 0, run.stderr.decode())
                self.assertEqual(run.stdout, expected)
            passport = ep.read_json(out / 'evidence-passport.json')
            self.assertEqual(passport['governance']['outcome'], 'NOT_ADMITTED')
            self.assertIn('OPERATOR_APPROVAL_MISSING', passport['missing_requirements'])

    def test_cli_requires_context_and_rejects_secrets_without_output(self):
        payload, context = self.fixture()
        with tempfile.TemporaryDirectory() as temp:
            inp, ctx, out = Path(temp) / 'input.json', Path(temp) / 'context.json', Path(temp) / 'report'
            payload['privateKey'] = 'NEVER_WRITE_THIS_SENTINEL'
            inp.write_text(json.dumps(payload)); ctx.write_bytes(ep.canonical_bytes(context))
            cmd = [sys.executable, '-m', 'harness.sdk.tameion_demo_cli', '--input', str(inp), '--passport-dir', str(out)]
            for extra in ([], ['--passport-context', str(ctx)]):
                run = subprocess.run(cmd + extra, cwd=REPO_ROOT, capture_output=True, timeout=15)
                self.assertEqual(run.returncode, 2)
                self.assertEqual(run.stdout, b'')
                self.assertNotIn(b'NEVER_WRITE_THIS_SENTINEL', run.stderr)
                self.assertFalse(out.exists())

    def test_cli_rejects_report_output_path_collision(self):
        payload, context = self.fixture()
        with tempfile.TemporaryDirectory() as temp:
            inp, ctx, out = Path(temp) / 'input.json', Path(temp) / 'context.json', Path(temp) / 'report'
            inp.write_bytes(ep.canonical_bytes(payload)); ctx.write_bytes(ep.canonical_bytes(context))
            run = subprocess.run([
                sys.executable, '-m', 'harness.sdk.tameion_demo_cli', '--input', str(inp),
                '--passport-dir', str(out), '--passport-context', str(ctx),
                '--output', str(out / 'evidence-passport.json'),
            ], cwd=REPO_ROOT, capture_output=True, timeout=15)
            self.assertEqual(run.returncode, 2)
            self.assertIn(b'OUTPUT_PATH_COLLISION', run.stderr)
            self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
