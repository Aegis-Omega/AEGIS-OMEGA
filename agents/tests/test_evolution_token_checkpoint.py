"""Independent local operator checkpoint, historical replay, rollback falsifiers."""
import copy
import unittest

from agents.evolution_token_checkpoint import (
    GENESIS, verify_checkpoint, seal_checkpoint,
)
from agents.evolution_token_lifecycle import (
    digest, evaluate_lifecycle, sign_local_event,
)
from agents.tests.test_evolution_token_lifecycle import fixture, event, KEYS, S1

OP_KEY = b'checkpoint-operator-secret-not-in-agent-keyring-0001'
OTHER_KEY = b'checkpoint-other-secret-not-in-agent-keyring-000002'


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.spine = fixture()
        self.root = self.spine['receipt_hash']
        self.request = event(self.spine, 'REQUEST_REVIEW', 'builder', now=100, nonce=1)
        self.revoked = event(self.spine, 'REVOKE', 'operator', seq=1,
                             prev=digest(self.request), now=100, nonce=2)

    def seal(self, events=None, times=None, **changes):
        args = dict(trusted_spine_hash=self.root, trusted_event_keys=KEYS,
                    checkpoint_key_id='independent_operator', checkpoint_secret=OP_KEY,
                    as_of=100)
        args.update(changes)
        return seal_checkpoint(self.spine, events if events is not None else
                               [self.request, self.revoked],
                               times if times is not None else [100,100], **args)

    def verify(self, cp, events=None, times=None, **changes):
        args = dict(trusted_spine_hash=self.root, trusted_event_keys=KEYS,
                    trusted_checkpoint_keys={'independent_operator':OP_KEY},
                    trusted_checkpoint_id=cp['checkpoint_id'])
        args.update(changes)
        return verify_checkpoint(self.spine, events if events is not None else
                                 [self.request,self.revoked],
                                 times if times is not None else [100,100], cp, **args)

    def test_historic_revocation_after_event_expiry(self):
        cp=self.seal()
        self.assertEqual(self.verify(cp)['revoked_count'],1)
        with self.assertRaisesRegex(ValueError,'EVENT_EXPIRED'):
            evaluate_lifecycle(self.spine,[self.request,self.revoked],
                               trusted_spine_hash=self.root,trusted_keys=KEYS,
                               now=200)
        self.assertEqual(self.verify(cp)['status'],'LOCAL_OPERATOR_CHECKPOINT_MAC_VERIFIED')

    def test_operator_key_independent_of_event_keys(self):
        with self.assertRaisesRegex(ValueError, 'CHECKPOINT_KEY_REUSES_EVENT_SECRET'):
            self.seal(checkpoint_secret=S1)

    def test_missing_external_pinned_id_denied(self):
        cp=self.seal()
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_TRUSTED_ID_MISMATCH'):
            self.verify(cp,trusted_checkpoint_id=None)

    def test_wrong_external_pinned_id_denied(self):
        cp=self.seal()
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_TRUSTED_ID_MISMATCH'):
            self.verify(cp,trusted_checkpoint_id='0'*64)

    def test_tampered_journal_rejected(self):
        cp=self.seal()
        altered=copy.deepcopy(self.request)
        altered['evidence_sha256']='e'*64
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_DATA_BINDING_INVALID'):
            self.verify(cp,events=[altered,self.revoked])

    def test_missing_revoke_detected_by_pinned_checkpoint(self):
        cp=self.seal()
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_DATA_BINDING_INVALID'):
            self.verify(cp,events=[self.request],times=[100])

    def test_changed_observation_times_rejected(self):
        cp=self.seal()
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_DATA_BINDING_INVALID'):
            self.verify(cp,times=[99,100])

    def test_forged_checkpoint_signature_rejected(self):
        cp=self.seal()
        forged=copy.deepcopy(cp)
        forged['signature']='f'*64
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_MAC_INVALID'):
            self.verify(forged)

    def test_wrong_operator_key_rejected(self):
        cp=self.seal()
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_MAC_INVALID'):
            self.verify(cp,trusted_checkpoint_keys={'independent_operator':OTHER_KEY})

    def test_unknown_key_id_denied(self):
        cp=self.seal()
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_SIGNER_NOT_TRUSTED'):
            self.verify(cp,trusted_checkpoint_keys={})

    def test_wrong_source_spine_root_denied(self):
        cp=self.seal()
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_DATA_BINDING_INVALID'):
            self.verify(cp,trusted_spine_hash='f'*64)

    def test_time_reversal_in_events_denied(self):
        with self.assertRaisesRegex(ValueError,'EVENT_OBSERVATION_TIMES_UNTRUSTED'):
            self.seal(times=[100,99])

    def test_expired_event_cannot_be_forged_with_late_observation(self):
        with self.assertRaisesRegex(ValueError,'EVENT_EXPIRED'):
            self.seal([self.request],[200],as_of=200)

    def test_cannot_unconditionally_claim_identity(self):
        cp=self.seal()
        out=self.verify(cp)
        self.assertFalse(out['source_publisher_authenticated'])
        self.assertFalse(out['independent_reviewer_authenticated'])
        self.assertFalse(out['external_checkpoint_storage_verified'])
        self.assertEqual(out['production_admission'],'DENIED')

    def test_recomputed_untrusted_checkpoint_cannot_override_pinned_id(self):
        cp=self.seal()
        attacker_cp=self.seal(events=[self.request],times=[100])
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_TRUSTED_ID_MISMATCH'):
            self.verify(attacker_cp,events=[self.request],times=[100],
                        trusted_checkpoint_id=cp['checkpoint_id'])

    def test_successor_checkpoint_preserves_revocation(self):
        old=self.seal(events=[self.request],times=[100])
        # The old request expired long ago; independently bound observation time
        # permits a new operator REVOKE while retaining the original history.
        newer=event(self.spine,'REVOKE','operator',seq=1,prev=digest(self.request),
                    now=200,nonce=3)
        cp=self.seal(events=[self.request,newer],times=[100,200],as_of=200,
                     prior_checkpoint=old,prior_events=[self.request],
                     prior_observed_at=[100],trusted_prior_checkpoint_id=old['checkpoint_id'])
        verified=verify_checkpoint(self.spine,[self.request,newer],[100,200],cp,
            trusted_spine_hash=self.root,trusted_event_keys=KEYS,
            trusted_checkpoint_keys={'independent_operator':OP_KEY},
            trusted_checkpoint_id=cp['checkpoint_id'],
            expected_previous_id=old['checkpoint_id'])
        self.assertEqual(cp['checkpoint_sequence'],1)
        self.assertEqual(cp['previous_checkpoint_id'],old['checkpoint_id'])
        self.assertEqual(verified['revoked_count'],1)

    def test_successor_requires_externally_pinned_prior(self):
        old=self.seal(events=[self.request],times=[100])
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_PRIOR_UNANCHORED'):
            self.seal(events=[self.request,self.revoked],times=[100,100],
                prior_checkpoint=old,prior_events=[self.request],
                prior_observed_at=[100])

    def test_successor_rejects_forged_prior_id(self):
        old=self.seal(events=[self.request],times=[100])
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_TRUSTED_ID_MISMATCH'):
            self.seal(events=[self.request,self.revoked],times=[100,100],
                prior_checkpoint=old,prior_events=[self.request],
                prior_observed_at=[100],trusted_prior_checkpoint_id='f'*64)

    def test_successor_requires_strict_append(self):
        old=self.seal(events=[self.request],times=[100])
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_APPEND_ONLY_VIOLATION'):
            self.seal(events=[self.request],times=[100],prior_checkpoint=old,
                      prior_events=[self.request],prior_observed_at=[100],
                      trusted_prior_checkpoint_id=old['checkpoint_id'])

    def test_successor_cannot_rewrite_old_observation(self):
        old=self.seal(events=[self.request],times=[100])
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_APPEND_ONLY_VIOLATION'):
            self.seal(events=[self.request,self.revoked],times=[99,100],
                      prior_checkpoint=old,prior_events=[self.request],
                      prior_observed_at=[100],trusted_prior_checkpoint_id=old['checkpoint_id'])

    def test_cannot_declare_authority_in_checkpoint(self):
        cp=self.seal()
        cp['authority_effect']='D4'
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_CONTRACT_INVALID'):
            self.verify(cp)

    def test_extra_checkpoint_metadata_denied(self):
        cp=self.seal()
        cp['capability']='WRITE'
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_SCHEMA_INVALID'):
            self.verify(cp)

    def test_source_event_noneffects_persist(self):
        cp=self.seal()
        out=self.verify(cp)
        self.assertEqual(out['authority_effect'],'NONE')
        self.assertEqual(out['execution_effect'],'NONE')

    def test_empty_events_checkpoint(self):
        cp=self.seal(events=[],times=[])
        out=self.verify(cp,events=[],times=[])
        self.assertEqual(out['event_count'],0)
        self.assertEqual(out['revoked_count'],0)

    def test_expired_revoke_can_be_replayed_historically(self):
        cp=self.seal()
        self.assertEqual(self.verify(cp)['revoked_count'],1)


if __name__=='__main__': unittest.main()
