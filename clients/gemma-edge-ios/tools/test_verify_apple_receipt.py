#!/usr/bin/env python3
"""Independent Python verification against immutable Swift SHA-256 golden fixtures."""
import hashlib
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from verify_apple_receipt import (InvalidReceipt, canonical_preimage,
                                  read_receipt, verify_integrity, verify_file)

OLD_HASH = '167cb2cdc67d04b374b68a851783dc3ec0a63ba20a0619550676535b3c8211eb'
NEW_HASH = '119c321bc677117cc1f7672fde05a8c4b8a5539033eb7e5bf105946411425ce9'

def fixture(schema='1.1.0', t=0.1):
    r = {
        'schema_version': schema,
        'provider_id': 'apple-foundation-models',
        'model_id': 'apple-system-language-model-default',
        'prompt_sha256': hashlib.sha256(b'hello').hexdigest(),
        'output_sha256': hashlib.sha256(b'world').hexdigest(),
        'prompt_bytes': 5,
        'output_bytes': 5,
        'max_tokens': 32,
        'temperature_milli': int(float(struct.unpack('>f', struct.pack('>f', t))[0])*1000 + 0.5),
        'outcome': 'SUCCEEDED',
        'authority_effect': 'NONE',
    }
    if schema == '1.1.0':
        r['temperature_float_bits_hex'] = struct.pack('>f', t).hex()
    r['receipt_sha256'] = hashlib.sha256(canonical_preimage(r)).hexdigest()
    return r

class CrossLanguageReceiptTests(unittest.TestCase):
    def test_swift_goldens_verbatim(self):
        old = fixture('1.0.0')
        new = fixture('1.1.0')
        self.assertEqual(old['receipt_sha256'], OLD_HASH)
        self.assertEqual(new['receipt_sha256'], NEW_HASH)
        self.assertTrue(verify_integrity(old))
        self.assertTrue(verify_integrity(new))

    def test_float32_distinction(self):
        a, b = fixture(t=0.2001), fixture(t=0.2002)
        self.assertEqual(a['temperature_milli'], b['temperature_milli'])
        self.assertNotEqual(a['receipt_sha256'], b['receipt_sha256'])
        self.assertTrue(verify_integrity(a))
        self.assertTrue(verify_integrity(b))

    def test_tampering_rejected(self):
        original = fixture()
        for k, v in [('authority_effect', 'APPROVED'), ('outcome', 'FAILED'),
                     ('provider_id', 'fake'), ('max_tokens', 33),
                     ('prompt_bytes', 4), ('temperature_milli', 101),
                     ('temperature_float_bits_hex', '7fc00000'),
                     ('temperature_float_bits_hex', '3e4cdd2e'),
                     ('schema_version', '2.0.0'), ('receipt_sha256', '0'*64)]:
            with self.subTest(k=k,v=v), self.assertRaises(InvalidReceipt):
                verify_integrity(dict(original, **{k:v}))

    def test_strict_unknown_duplicate_missing_and_types(self):
        r = fixture()
        for k, v in [('unexpected_authority', 'APPROVED'), ('max_tokens', True),
                     ('prompt_bytes', 1.0), ('temperature_float_bits_hex', '3DCCCCCD')]:
            with self.subTest(k=k), self.assertRaises(InvalidReceipt):
                verify_integrity(dict(r, **{k:v}))
        q = dict(r); del q['max_tokens']
        with self.assertRaises(InvalidReceipt): verify_integrity(q)
        with self.assertRaises(InvalidReceipt): read_receipt(b'{"a":1,"a":2}')
        with self.assertRaises(InvalidReceipt): read_receipt(b'{"x":NaN}')
        with self.assertRaises(InvalidReceipt): read_receipt(b'[' + b' '*65536 + b']')

    def test_cli_rejects_oversized_receipt_without_full_file_read(self):
        with tempfile.TemporaryDirectory() as td:
            oversized = Path(td)/'oversized.json'
            oversized.write_bytes(b' ' * 100000)
            command = [sys.executable, str(Path(__file__).with_name('verify_apple_receipt.py')), str(oversized)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn('receipt too large', result.stderr)

    def test_content_and_cli(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            rec, prompt, output = tmp/'receipt.json', tmp/'prompt.txt', tmp/'output.txt'
            rec.write_text(json.dumps(fixture()),encoding='utf-8')
            prompt.write_bytes(b'hello'); output.write_bytes(b'world')
            command=[sys.executable, str(Path(__file__).with_name('verify_apple_receipt.py')),
                     str(rec), '--prompt-file',str(prompt),'--output-file',str(output)]
            res=subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(res.returncode,0,res.stderr)
            self.assertIn('NO issuer authentication',res.stdout)
            prompt.write_bytes(b'other')
            bad=subprocess.run(command,capture_output=True,text=True)
            self.assertNotEqual(bad.returncode,0)
            self.assertIn('INVALID RECEIPT',bad.stderr)

if __name__ == '__main__':
    unittest.main()
