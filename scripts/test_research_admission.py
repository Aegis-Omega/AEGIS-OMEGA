"""Atomic single-use evidence consumption against an owner-protected local ledger."""
import concurrent.futures
from contextlib import closing
import copy
import os
import json
import subprocess
import sys
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from research_admission import admit_once, AdmissionDenied, _protected_path, main
from research_benchmark import make_packet, TEST_NOW, TRUST, TEST_KEY


class SingleUseAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = str(self.root / 'evidence.sqlite3')
        self.packet = make_packet('valid_openai_langchain', 0)

    def tearDown(self):
        self.temp.cleanup()

    def claim(self, packet=None, path=None, **kwargs):
        return admit_once(packet if packet is not None else self.packet,
                          trusted_keys=kwargs.get('trusted_keys', TRUST),
                          ledger_path=path or self.path, verified_now=TEST_NOW)

    def test_first_claim_passes_with_exact_receipt(self):
        result = self.claim()
        self.assertEqual(result['status'], 'ADMITTED_ONCE_FOR_INDEPENDENT_TEST')
        self.assertEqual(result['verified_capture_count'], 2)
        self.assertEqual(result['source_truth'], 'NOT_VERIFIED')
        self.assertEqual(result['operator_authority'], 'NOT_GRANTED')
        self.assertEqual(len(result['receipt_sha256']),64)

    def test_same_capture_same_binding_second_claim_denied(self):
        self.claim()
        with self.assertRaisesRegex(AdmissionDenied, 'EVIDENCE_ALREADY_CONSUMED'):
            self.claim()

    def test_restart_same_db_still_denies(self):
        self.claim()
        with self.assertRaisesRegex(AdmissionDenied, 'EVIDENCE_ALREADY_CONSUMED'):
            admit_once(copy.deepcopy(self.packet), trusted_keys=TRUST,
                       ledger_path=self.path, verified_now=TEST_NOW)

    def test_failed_replay_does_not_consume_new_capture(self):
        first = self.packet
        self.claim()
        second = make_packet('valid_openai_langchain',1)
        # shares no capture with the first (different task binding), so accepted
        self.claim(second)
        self.assertEqual(self.count(),4)

    def test_same_capture_referenced_twice_in_one_packet_consumed_once(self):
        p = copy.deepcopy(self.packet)
        new_proposal = copy.deepcopy(p['proposals'][0])
        new_proposal['id'] = 'second_proposal'
        p['proposals'].append(new_proposal)
        result=self.claim(p)
        self.assertEqual(result['verified_capture_count'],2)
        self.assertEqual(self.count(),2)

    def test_no_ready_proposal_never_creates_ledger(self):
        p = make_packet('two_manual_notes',0)
        with self.assertRaisesRegex(AdmissionDenied,'NOT_ALL_PROPOSALS_TEST_READY'):
            self.claim(p)
        self.assertFalse(Path(self.path).exists())

    def test_partial_mutation_preserves_entire_atomicity(self):
        self.claim()
        p = copy.deepcopy(self.packet)
        from research_attestation import sign_capture
        # A newer second receipt, authorized by the synthetic key, while the
        # first original receipt is already consumed.
        second=p['sources'][1]
        receipt={k:v for k,v in second['capture_receipt'].items() if k!='attestation'}
        receipt['captured_at']='2026-10-11T11:58:00Z'
        binding={'task_id':p['task_id'],'repo_head':p['repo_head'],'source_id':second['id']}
        second['captured_at']=receipt['captured_at']
        second['capture_receipt']=sign_capture(receipt,TEST_KEY,'synthetic.test',binding=binding)
        with self.assertRaisesRegex(AdmissionDenied,'EVIDENCE_ALREADY_CONSUMED'):
            self.claim(p)
        self.assertEqual(self.count(),2)
        # Another legitimate first-time task still succeeds (DB not poisoned).
        self.claim(make_packet('valid_openai_langchain',1))
        self.assertEqual(self.count(),4)

    def test_simulated_failure_after_first_insert_rolls_back(self):
        import research_admission as a
        insert=a._insert_claims
        def fault(connection, entries, *args):
            insert(connection, entries[:1], *args)
            raise RuntimeError('simulated worker failure after first write')
        with patch.object(a, '_insert_claims', side_effect=fault):
            with self.assertRaisesRegex(RuntimeError,'simulated worker'):
                self.claim()
        self.assertEqual(self.count(),0)
        self.claim()
        self.assertEqual(self.count(),2)

    def test_concurrent_claims_exactly_one_succeeds(self):
        def run(_):
            try:
                return self.claim()['status']
            except AdmissionDenied as error:
                return str(error)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            outcomes=list(ex.map(run, range(12)))
        self.assertEqual(outcomes.count('ADMITTED_ONCE_FOR_INDEPENDENT_TEST'),1)
        self.assertEqual(outcomes.count('EVIDENCE_ALREADY_CONSUMED'),11)
        self.assertEqual(self.count(),2)

    def test_separate_cli_processes_exactly_one_succeeds(self):
        packetfile=self.root/'packet.json'
        packetfile.write_text(json.dumps(self.packet), encoding='utf-8')
        keyfile=self.root/'verifier.key'
        keyfile.write_bytes(TEST_KEY)
        keyfile.chmod(0o600)
        args=[sys.executable, str(Path(__file__).with_name('research_admission.py')),
              str(packetfile), '--trusted-key-file', str(keyfile),
              '--trusted-key-id', 'synthetic.test', '--ledger', self.path,
              '--allow-ledger-write']
        # The fixture has a historic timestamp, so the production CLI correctly
        # rejects it against its real clock; generate an independent fixture
        # with live UTC capture timestamps and re-sign every bound record.
        from research_attestation import sign_capture
        import datetime as dt
        now=dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        self.packet['as_of_utc']=now.strftime('%Y-%m-%dT%H:%M:%SZ')
        for src in self.packet['sources']:
            snap={k:v for k,v in src['capture_receipt'].items() if k!='attestation'}
            snap['captured_at']=self.packet['as_of_utc']
            src['captured_at']=snap['captured_at']
            src['capture_receipt']=sign_capture(snap,TEST_KEY,'synthetic.test',binding={
                'task_id':self.packet['task_id'], 'repo_head':self.packet['repo_head'],
                'source_id':src['id']})
        packetfile.write_text(json.dumps(self.packet),encoding='utf-8')
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:subprocess.run(args, capture_output=True,
                                                 text=True, timeout=15), range(4)))
        self.assertEqual(sum(p.returncode==0 for p in results),1)
        self.assertEqual(sum('EVIDENCE_ALREADY_CONSUMED' in p.stderr for p in results),3)
        self.assertEqual(self.count(),2)

    def test_db_keeps_digests_not_credentials_or_excerpts(self):
        self.claim()
        raw=Path(self.path).read_bytes()
        self.assertNotIn(TEST_KEY, raw)
        self.assertNotIn(b'Documented capability claim', raw)
        self.assertNotIn(b'https://developers.openai.com/doc', raw)

    def test_reject_unprotected_parent_directory(self):
        p=self.root/'insecure'
        p.mkdir(mode=0o755)
        with self.assertRaisesRegex(AdmissionDenied,'UNTRUSTED_LEDGER_PARENT'):
            self.claim(path=str(p/'evidence.sqlite3'))

    def test_reject_symlink_database(self):
        alias=self.root/'evidence.sqlite3'
        victim=self.root/'victim.sqlite3';victim.write_bytes(b'stay')
        alias.symlink_to(victim)
        with self.assertRaises(OSError):
            self.claim()
        self.assertEqual(victim.read_bytes(),b'stay')

    def test_reject_world_readable_database(self):
        p=Path(self.path);p.write_bytes(b'');p.chmod(0o644)
        with self.assertRaisesRegex(AdmissionDenied,'UNTRUSTED_LEDGER_FILE'):
            self.claim()

    def test_ledger_mode_is_owner_only(self):
        self.claim()
        self.assertEqual(os.stat(self.path).st_mode & 0o777,0o600)

    def test_empty_verifier_trust_denied_before_file_io(self):
        with self.assertRaisesRegex(AdmissionDenied,'TRUST_ROOT_REQUIRED'):
            self.claim(trusted_keys={})
        self.assertFalse(Path(self.path).exists())

    def test_invalid_forged_capture_does_not_create_ledger(self):
        p=copy.deepcopy(self.packet)
        p['sources'][0]['capture_receipt']['attestation']['mac_sha256']='0'*64
        with self.assertRaisesRegex(AdmissionDenied,'NOT_ALL_PROPOSALS_TEST_READY'):
            self.claim(p)
        self.assertFalse(Path(self.path).exists())

    def test_cli_default_denies_ledger_mutation(self):
        with self.assertRaises(SystemExit) as caught:
            main(['does-not-exist.json','--trusted-key-file','x','--trusted-key-id','test',
                  '--ledger',self.path])
        self.assertEqual(caught.exception.code,2)
        self.assertFalse(Path(self.path).exists())

    def count(self):
        if not Path(self.path).exists():
            return 0
        with closing(sqlite3.connect(self.path)) as db:
            try:
                return db.execute('SELECT count(*) FROM consumed').fetchone()[0]
            except sqlite3.OperationalError as error:
                if 'no such table' in str(error):
                    return 0  # DDL was correctly rolled back with the inserts.
                raise

if __name__=='__main__':unittest.main()
