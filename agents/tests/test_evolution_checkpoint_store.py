"""Real filesystem adversarial test of local compare-and-swap checkpoint pin."""
import json
import os
import pathlib
import stat
import tempfile
import unittest
from unittest import mock

from agents.evolution_checkpoint_store import publish, read_pinned
from agents.tests import test_evolution_token_checkpoint as fixture_mod
OP_KEY, KEYS = fixture_mod.OP_KEY, fixture_mod.KEYS
from agents.tests.test_evolution_token_lifecycle import event, digest
from agents.evolution_token_checkpoint import GENESIS


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.base = fixture_mod.CheckpointTests()
        self.base.setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name) / "operator_private"
        self.cp0 = self.base.seal(events=[self.base.request], times=[100])
        self.params = dict(trusted_spine_hash=self.base.root, trusted_event_keys=KEYS,
                           trusted_checkpoint_keys={'independent_operator': OP_KEY})

    def publish(self, cp=None, *, events=None, times=None, expected=None):
        return publish(self.root, self.base.spine, events if events is not None else [self.base.request],
                       times if times is not None else [100], cp or self.cp0,
                       expected_current_id=expected or GENESIS, **self.params)

    def current(self, checkpoint_id=None):
        return read_pinned(self.root, self.base.spine,
                           trusted_head_id=checkpoint_id or self.cp0['checkpoint_id'], **self.params)

    def successor(self):
        revoke = event(self.base.spine, 'REVOKE', 'operator', seq=1,
                       prev=digest(self.base.request), now=200, nonce=8)
        return (self.base.seal(events=[self.base.request, revoke], times=[100, 200],
                               as_of=200, prior_checkpoint=self.cp0,
                               prior_events=[self.base.request], prior_observed_at=[100],
                               trusted_prior_checkpoint_id=self.cp0['checkpoint_id']), revoke)

    def test_genesis_publish_exact_root(self):
        result = self.publish()
        self.assertEqual(result['checkpoint_id'], self.cp0['checkpoint_id'])
        self.assertFalse(result['external_anchor_verified'])
        self.assertEqual(self.current()['checkpoint_verdict']['event_count'], 1)
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((self.root/'HEAD.json').stat().st_mode), 0o600)

    def test_stale_writer_denied_even_if_checkpoint_valid(self):
        self.publish()
        newer, revoke = self.successor()
        with self.assertRaisesRegex(ValueError, 'ANCHOR_COMPARE_AND_SWAP_CONFLICT'):
            self.publish(newer, events=[self.base.request, revoke], times=[100,200], expected=GENESIS)

    def test_successor_replays_prior_and_commits(self):
        self.publish()
        new, revoke = self.successor()
        self.publish(new, events=[self.base.request,revoke], times=[100,200], expected=self.cp0['checkpoint_id'])
        got = self.current(new['checkpoint_id'])
        self.assertEqual(got['checkpoint_verdict']['revoked_count'], 1)
        self.assertFalse(got['external_anchor_verified'])

    def test_stale_pin_cannot_read_latest_after_successor(self):
        self.publish()
        cp, revoke = self.successor()
        self.publish(cp, events=[self.base.request,revoke], times=[100,200], expected=self.cp0['checkpoint_id'])
        with self.assertRaisesRegex(ValueError, 'ANCHOR_PIN_MISMATCH'):
            self.current()

    def test_bad_history_rewrite_denied_even_when_resigned(self):
        self.publish()
        # Different complete journal after the old head has already been pinned:
        # the local store itself checks prefix and prevents a re-signed reset.
        altered = event(self.base.spine, 'REQUEST_REVIEW', 'builder', now=100, nonce=987)
        tampered_revoke = event(self.base.spine,'REVOKE','operator',seq=1,
                               prev=digest(altered),now=200,nonce=8)
        forged = self.base.seal(events=[altered,tampered_revoke],times=[100,200],as_of=200)
        # Create a legitimate signed checkpoint successor around the wrong history
        # using internal test signer, but store must deny regardless.
        forged = dict(forged, previous_checkpoint_id=self.cp0['checkpoint_id'], checkpoint_sequence=1)
        # New signature invalid as well, but prefix rejection comes first.
        with self.assertRaisesRegex(ValueError, 'ANCHOR_HISTORY_REWRITE_OR_NON_APPEND'):
            self.publish(forged,events=[altered,tampered_revoke],times=[100,200],expected=self.cp0['checkpoint_id'])

    def test_missing_revocation_history_with_old_spine_denied(self):
        self.publish()
        new, revoke = self.successor()
        self.publish(new,events=[self.base.request,revoke],times=[100,200],expected=self.cp0['checkpoint_id'])
        # Replacing the entire private directory is possible to same-user attackers,
        # but an independently retained newest ID still rejects the old snapshot.
        (self.root/'HEAD.json').write_bytes(json.dumps({
            'schema':'AEGIS_LOCAL_EVOLUTION_CHECKPOINT_ANCHOR_V1',
            'checkpoint_id':self.cp0['checkpoint_id'], 'sequence':0
        }).encode())
        os.chmod(self.root/'HEAD.json',0o600)
        with self.assertRaisesRegex(ValueError, 'ANCHOR_PIN_MISMATCH'):
            self.current(new['checkpoint_id'])

    def test_changed_object_on_disk_denied(self):
        self.publish()
        snap = self.root/'objects'/(self.cp0['checkpoint_id']+'.json')
        data=json.loads(snap.read_bytes())
        data['observed_at']=[101]
        snap.write_bytes(json.dumps(data).encode())
        with self.assertRaisesRegex(ValueError, 'CHECKPOINT_DATA_BINDING_INVALID'):
            self.current()

    def test_symlink_root_rejected(self):
        target=pathlib.Path(self.tmp.name)/'target'
        target.mkdir(mode=0o700)
        self.root.symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'ANCHOR_DIRECTORY_UNSAFE'):
            self.publish()

    def test_group_writable_directory_rejected(self):
        self.root.mkdir(mode=0o700)
        self.root.chmod(0o770)
        with self.assertRaisesRegex(ValueError,'ANCHOR_DIRECTORY_UNSAFE'):
            self.publish()

    def test_symlink_head_rejected(self):
        self.publish()
        head=self.root/'HEAD.json'; head.unlink(); head.symlink_to(self.root/'.anchor.lock')
        with self.assertRaises(OSError):
            self.current()

    def test_wrong_file_mode_rejected(self):
        self.publish()
        head=self.root/'HEAD.json'
        head.chmod(0o644)
        with self.assertRaisesRegex(ValueError,'ANCHOR_FILE_UNSAFE'):
            self.current()

    def test_object_hardlink_rejected(self):
        self.publish()
        obj=self.root/'objects'/(self.cp0['checkpoint_id']+'.json')
        os.link(obj,self.root/'copy.json')
        with self.assertRaisesRegex(ValueError,'ANCHOR_FILE_UNSAFE'):
            self.current()

    def test_unpublished_object_recovery_after_crash(self):
        # Simulate failure after immutable object fsync/link but before HEAD.
        import agents.evolution_checkpoint_store as impl
        with mock.patch.object(impl.os,'replace', side_effect=OSError('synthetic failure')):
            with self.assertRaisesRegex(OSError,'synthetic failure'):
                self.publish()
        self.assertFalse((self.root/'HEAD.json').exists())
        self.assertTrue((self.root/'objects'/(self.cp0['checkpoint_id']+'.json')).exists())
        self.publish()
        self.assertEqual(self.current()['checkpoint_id'],self.cp0['checkpoint_id'])

    def test_existing_orphan_mismatch_denied(self):
        import agents.evolution_checkpoint_store as impl
        with mock.patch.object(impl.os,'replace',side_effect=OSError('simulated')):
            with self.assertRaises(OSError): self.publish()
        obj=self.root/'objects'/(self.cp0['checkpoint_id']+'.json')
        obj.write_text('{}')
        with self.assertRaisesRegex(ValueError,'ANCHOR_OBJECT_COLLISION_OR_TAMPER'):
            self.publish()

    def test_atomic_cas_rejects_unauthorized_genesis_reset(self):
        self.publish()
        with self.assertRaisesRegex(ValueError,'ANCHOR_COMPARE_AND_SWAP_CONFLICT'):
            self.publish()

    def test_read_requires_external_expected_id(self):
        self.publish()
        with self.assertRaisesRegex(ValueError,'ANCHOR_TRUSTED_HEAD_MISSING'):
            self.current(checkpoint_id='bogus')

    def test_wrong_event_mac_not_publishable(self):
        fake=dict(self.base.request,signature='0'*64)
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_DATA_BINDING_INVALID'):
            self.publish(events=[fake])
        self.assertFalse((self.root/'HEAD.json').exists())

    def test_refuse_relative_store_path(self):
        with self.assertRaisesRegex(ValueError,'ANCHOR_ROOT_MUST_BE_ABSOLUTE'):
            publish(pathlib.Path('relative'),self.base.spine,[self.base.request],[100],self.cp0,
                    expected_current_id=GENESIS,**self.params)

    def test_cross_spine_mismatch_denied(self):
        with self.assertRaises(ValueError):
            self.publish(expected=GENESIS, cp=dict(self.cp0, spine_receipt='f'*64))

    def test_empty_genesis_snapshot(self):
        cp=self.base.seal(events=[],times=[])
        result=self.publish(cp,events=[],times=[])
        self.assertEqual(result['checkpoint_id'],cp['checkpoint_id'])

    def test_no_dispatch_capability_or_onchain(self):
        self.publish()
        obj=self.current()
        self.assertEqual(obj['admission'],'DENIED')
        self.assertEqual(obj['authority_effect'],'NONE')
        self.assertEqual(obj['execution_effect'],'NONE')
        self.assertFalse(obj['external_anchor_verified'])


    def test_read_does_not_modify_snapshot_files(self):
        self.publish()
        snapshot = self.root/'objects'/(self.cp0['checkpoint_id']+'.json')
        old = snapshot.read_bytes(), (self.root/'HEAD.json').read_bytes()
        self.current()
        self.assertEqual(old, (snapshot.read_bytes(), (self.root/'HEAD.json').read_bytes()))

    def test_unsafe_head_id_path_rejected(self):
        self.publish()
        with self.assertRaisesRegex(ValueError, 'ANCHOR_TRUSTED_HEAD_MISSING'):
            self.current(checkpoint_id='../' + 'a'*61)

    def test_missing_object_under_valid_head_denied(self):
        self.publish()
        path=self.root/'objects'/(self.cp0['checkpoint_id']+'.json')
        path.unlink()
        with self.assertRaises(FileNotFoundError):
            self.current()

    def test_symlink_snapshot_object_denied(self):
        self.publish()
        obj=self.root/'objects'/(self.cp0['checkpoint_id']+'.json')
        obj.unlink()
        obj.symlink_to(self.root/'HEAD.json')
        with self.assertRaises(OSError):
            self.current()

    def test_head_loss_cannot_bypass_separately_retained_current_id(self):
        self.publish()
        (self.root/'HEAD.json').unlink()
        with self.assertRaisesRegex(ValueError, 'ANCHOR_COMPARE_AND_SWAP_CONFLICT'):
            self.publish(expected=self.cp0['checkpoint_id'])

    def test_competing_writers_single_genesis_commit(self):
        # Two independent open() descriptions contend on the same fcntl lock.
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        start=Barrier(2)
        def attempt(_):
            start.wait(timeout=5)
            try:
                self.publish()
                return 'COMMITTED'
            except ValueError as exc:
                return str(exc)
        with ThreadPoolExecutor(max_workers=2) as pool:
            result=list(pool.map(attempt, (1,2)))
        self.assertCountEqual(result,['COMMITTED','ANCHOR_COMPARE_AND_SWAP_CONFLICT'])
        self.assertEqual(self.current()['checkpoint_id'],self.cp0['checkpoint_id'])

    def test_recovery_preserves_old_head_on_snapshot_write_failure(self):
        self.publish()
        next_cp,revoke=self.successor()
        import agents.evolution_checkpoint_store as impl
        with mock.patch.object(impl.os,'link',side_effect=OSError('out of space')):
            with self.assertRaisesRegex(OSError,'out of space'):
                self.publish(next_cp,events=[self.base.request,revoke],
                             times=[100,200],expected=self.cp0['checkpoint_id'])
        self.assertEqual(self.current()['checkpoint_id'],self.cp0['checkpoint_id'])


if __name__ == '__main__': unittest.main()
