"""Verifier-issued challenge, signed endorsements, and atomic one-use consumption."""
import concurrent.futures
import copy
import datetime as dt
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from research_attestation import sign_capture
from research_benchmark import TEST_KEY, TEST_NOW, TRUST, make_packet
from research_challenge import (issue_challenge, endorse_capture, admit_challenged_once,
                                AdmissionDenied)


class ChallengeTests(unittest.TestCase):
    def setUp(self):
        # Existing tests exercise nonce mechanics with a mocked approved
        # Automaton-3 decision, not an actual production authorization.
        authority = patch('research_challenge._central_authority_decision',
                          return_value={'outcome': 'ADMITTED',
                                        'decision_root': 'b'*64})
        authority.start()
        self.addCleanup(authority.stop)
        self.root = tempfile.TemporaryDirectory()
        self.ledger = str(Path(self.root.name) / 'ledger.sqlite3')
        self.packet = make_packet('valid_openai_langchain', 0)
        self.now = TEST_NOW + dt.timedelta(seconds=4)
        self.issued = TEST_NOW
        self.challenge = self.issue()
        self.freshen(self.packet, TEST_NOW + dt.timedelta(seconds=1))
        self.endorsements = self.endorse(self.packet)

    def tearDown(self):
        self.root.cleanup()

    def issue(self, **overrides):
        settings = dict(ledger_path=self.ledger, task_id=self.packet['task_id'],
                        repo_head=self.packet['repo_head'], source_ids=['one','two'],
                        verified_now=self.issued, ttl_seconds=60)
        settings.update(overrides)
        return issue_challenge(**settings)

    def freshen(self, packet, at):
        iso = at.strftime('%Y-%m-%dT%H:%M:%SZ')
        packet['as_of_utc'] = self.now.strftime('%Y-%m-%dT%H:%M:%SZ')
        for src in packet['sources']:
            snap = {k:v for k,v in src['capture_receipt'].items() if k!='attestation'}
            snap['captured_at'] = iso
            src['captured_at'] = iso
            src['capture_receipt'] = sign_capture(snap, TEST_KEY, 'synthetic.test',
                binding={'task_id':packet['task_id'],'repo_head':packet['repo_head'],
                         'source_id':src['id']})

    def endorse(self, packet, challenge=None):
        ch = challenge if challenge is not None else self.challenge
        return {s['id']:endorse_capture(s['capture_receipt'],challenge=ch,
                            source_id=s['id'],key_id='synthetic.test',signing_key=TEST_KEY)
                for s in packet['sources']}

    def admit(self, packet=None, challenge=None, endorsements=None, now=None):
        return admit_challenged_once(packet or self.packet,
            challenge=challenge or self.challenge,
            endorsements=endorsements if endorsements is not None else self.endorsements,
            trusted_keys=TRUST, ledger_path=self.ledger,
            verified_now=now or self.now)

    def test_01_happy_path_never_claims_execution(self):
        r = self.admit()
        self.assertEqual(r['status'], 'CHALLENGE_CONSUMED_FOR_INDEPENDENT_TEST')
        self.assertEqual(r['verified_capture_count'], 2)
        self.assertEqual(r['actual_execution'], 'NOT_INDEPENDENTLY_OBSERVED')
        self.assertEqual(r['authority_effect'], 'NONE')

    def test_02_issued_challenge_uses_unpredictable_256_bit_nonce(self):
        a = self.issue()
        self.assertNotEqual(a['challenge_nonce'], self.challenge['challenge_nonce'])
        self.assertEqual(len(bytes.fromhex(a['challenge_nonce'])), 32)

    def test_03_replay_same_response_fails(self):
        self.admit()
        with self.assertRaisesRegex(AdmissionDenied,'CHALLENGE_ALREADY_CONSUMED'):
            self.admit()

    def test_04_previous_capture_predating_issue_rejected(self):
        original = make_packet('valid_openai_langchain', 0)
        original['as_of_utc'] = self.packet['as_of_utc']
        endorsements = self.endorse(original)
        with self.assertRaisesRegex(AdmissionDenied, 'CAPTURE_PREDATES_CHALLENGE'):
            self.admit(packet=original, endorsements=endorsements)

    def test_05_endorsement_rebound_to_different_challenge_denied(self):
        other = self.issue()
        with self.assertRaisesRegex(AdmissionDenied, 'CHALLENGE_RESPONSE_MAC_MISMATCH'):
            self.admit(challenge=other)

    def test_06_unknown_nonce_no_ledger_row_denied(self):
        forged = copy.deepcopy(self.challenge)
        forged['challenge_nonce'] = 'f'*64
        with self.assertRaisesRegex(AdmissionDenied, 'UNKNOWN_VERIFIER_CHALLENGE'):
            self.admit(challenge=forged)

    def test_07_expired_challenge_denied(self):
        with self.assertRaisesRegex(AdmissionDenied, 'CHALLENGE_EXPIRED_OR_NOT_STARTED'):
            self.admit(now=self.issued + dt.timedelta(seconds=61))

    def test_08_mismatch_task_rejected(self):
        wrong = copy.deepcopy(self.challenge)
        wrong['task_id'] = 'untrusted'
        with self.assertRaisesRegex(AdmissionDenied, 'CHALLENGE_BINDING_MISMATCH'):
            self.admit(challenge=wrong)

    def test_09_modified_stored_issued_at_rejected(self):
        wrong = copy.deepcopy(self.challenge)
        wrong['issued_at'] = '1999-01-01T00:00:00+00:00'
        with self.assertRaisesRegex(AdmissionDenied, 'CHALLENGE_LEDGER_MISMATCH'):
            self.admit(challenge=wrong)

    def test_10_modified_source_mac_rejected(self):
        tampered = copy.deepcopy(self.endorsements)
        tampered['one']['mac_sha256'] = '0'*64
        with self.assertRaisesRegex(AdmissionDenied,'CHALLENGE_RESPONSE_MAC_MISMATCH'):
            self.admit(endorsements=tampered)

    def test_11_missing_endorsement_denied(self):
        with self.assertRaisesRegex(AdmissionDenied,'CHALLENGE_BINDING_MISMATCH'):
            self.admit(endorsements={'one':self.endorsements['one']})

    def test_12_wrong_endorser_denied(self):
        wrong = copy.deepcopy(self.endorsements)
        wrong['one']['key_id']='attacker'
        with self.assertRaisesRegex(AdmissionDenied,'UNTRUSTED_ENDORSER'):
            self.admit(endorsements=wrong)

    def test_13_concurrent_single_winner(self):
        def attempt(_):
            try:
                self.admit()
                return 'PASS'
            except AdmissionDenied as exc:
                return str(exc)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(attempt, range(12)))
        self.assertEqual(results.count('PASS'), 1)
        self.assertEqual(results.count('CHALLENGE_ALREADY_CONSUMED'),11)

    def test_14_no_partial_consumption_after_failure(self):
        with self.assertRaisesRegex(AdmissionDenied,'CHALLENGE_RESPONSE_MAC_MISMATCH'):
            self.admit(endorsements={'one':self.endorsements['one'],
                    'two':dict(self.endorsements['two'], mac_sha256='f'*64)})
        self.admit()

    def test_15_different_challenge_cannot_reuse_original_receipts(self):
        self.admit()
        ch2 = self.issue(verified_now=self.issued+dt.timedelta(seconds=2))
        endorsed = self.endorse(self.packet,challenge=ch2)
        with self.assertRaisesRegex(AdmissionDenied,'CAPTURE_PREDATES_CHALLENGE'):
            self.admit(challenge=ch2,endorsements=endorsed)

    def test_16_ttl_bounds(self):
        for ttl in [0,-1,301,True,1.5]:
            with self.subTest(ttl=ttl), self.assertRaisesRegex(AdmissionDenied,'INVALID_CHALLENGE_TTL'):
                self.issue(ttl_seconds=ttl)

    def test_17_no_replay_with_altered_source_id(self):
        altered = copy.deepcopy(self.packet)
        altered['sources'][0]['id']='alternate'
        altered['proposals'][0]['source_ids'][0]='alternate'
        with self.assertRaises(AdmissionDenied):
            self.admit(packet=altered)

    def test_18_key_does_not_appear_in_persistent_ledger(self):
        self.admit()
        raw = Path(self.ledger).read_bytes()
        self.assertNotIn(TEST_KEY, raw)
        self.assertNotIn(self.challenge['challenge_nonce'].encode(), raw)

    def test_19_existing_simple_admission_still_works(self):
        # Distinct explicit policy paths; no silent privilege promotion.
        from research_admission import admit_once
        other = str(Path(self.root.name)/'legacy.sqlite3')
        self.assertEqual(admit_once(self.packet,trusted_keys=TRUST,
          ledger_path=other,verified_now=self.now)['status'],
          'ADMITTED_ONCE_FOR_INDEPENDENT_TEST')

    def test_20_cross_process_race_single_consumer(self):
        # A separate verifier process must share the same fixed ledger.
        import subprocess, sys, json
        packetfile = Path(self.root.name)/'packet.json'
        challengefile = Path(self.root.name)/'challenge.json'
        endorsementsfile = Path(self.root.name)/'responses.json'
        for path, payload in [(packetfile,self.packet), (challengefile,self.challenge),
                              (endorsementsfile,self.endorsements)]:
            path.write_text(json.dumps(payload), encoding='utf-8')
        script = """import sys, json, datetime as dt
from research_challenge import admit_challenged_once, AdmissionDenied
from research_benchmark import TEST_KEY
p,ch,r = [json.load(open(x)) for x in sys.argv[1:4]]
try:
    admit_challenged_once(p,challenge=ch,endorsements=r,
        trusted_keys={'synthetic.test':TEST_KEY},ledger_path=sys.argv[4],
        verified_now=dt.datetime.fromisoformat(sys.argv[5]))
    print('ACCEPTED')
except AdmissionDenied as exc:
    print(str(exc))
"""
        args = [sys.executable,'-c',script,str(packetfile),str(challengefile),
                str(endorsementsfile),self.ledger,self.now.isoformat()]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            done=list(pool.map(lambda _:subprocess.run(args,text=True,capture_output=True,
                    timeout=15, env={**os.environ, "PYTHONPATH": str(Path(__file__).parent)}),range(4)))
        self.assertTrue(all(x.returncode==0 for x in done),[x.stderr for x in done])
        outcomes=[x.stdout.strip() for x in done]
        self.assertEqual(outcomes.count('ACCEPTED'),1)
        self.assertEqual(outcomes.count('CHALLENGE_ALREADY_CONSUMED'),3)

    def test_21_new_nonce_cannot_reconsume_same_capture(self):
        # A second nonce issued before the snapshot does not reset a spent
        # evidence fingerprint, even if its endorsement MAC is otherwise valid.
        earlier = self.issue(verified_now=self.issued)
        self.admit()
        newer_mac = self.endorse(self.packet, challenge=earlier)
        with self.assertRaisesRegex(AdmissionDenied, 'EVIDENCE_ALREADY_CONSUMED'):
            self.admit(challenge=earlier, endorsements=newer_mac)

    def test_22_malformed_nonce_rejected(self):
        forged=copy.deepcopy(self.challenge)
        forged['challenge_nonce']='AAAA'
        with self.assertRaisesRegex(AdmissionDenied,'INVALID_CHALLENGE_NONCE'):
            self.admit(challenge=forged)

if __name__ == '__main__':
    unittest.main()
