"""Falsifiers for process-local metacognitive chain integrity.

Run: python3 -m unittest -v test_chain_verifier.py
"""
import copy
import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chain_verifier import MAX_VERIFY_ENTRIES, GENESIS_HASH, verify_metacognitive_chain


def entries(n=3):
    chain = []
    prev = GENESIS_HASH
    for i in range(1, n + 1):
        layer, signal, tier = "SELF_MODEL", f"observation-{i}", "T1"
        digest = hashlib.sha256(f"{prev}|{layer}|{signal}|{tier}".encode()).hexdigest()
        chain.append({"sequence": i, "layer": layer, "signal": signal, "tier": tier,
                      "prev_hash": prev, "entry_hash": digest, "ts": 0.0})
        prev = digest
    return chain


class ChainVerifierTests(unittest.TestCase):
    def test_valid_chain(self):
        chain = entries()
        result = verify_metacognitive_chain(chain)
        self.assertIs(result["valid"], True)
        self.assertEqual(result["terminal_hash"], chain[-1]["entry_hash"])
        self.assertEqual(result["scope"], "in_process_sha256_linkage_only")

    def test_empty_chain_is_unknown(self):
        self.assertIsNone(verify_metacognitive_chain([])["valid"])

    def test_tampered_signal_fails(self):
        chain = entries()
        chain[1]["signal"] = "fabricated"
        self.assertEqual(verify_metacognitive_chain(chain)["reason"], "ENTRY_HASH_MISMATCH:2")

    def test_forged_header_hash_fails(self):
        chain = entries()
        chain[0]["entry_hash"] = "a" * 64
        self.assertIs(verify_metacognitive_chain(chain)["valid"], False)

    def test_reordered_entry_fails(self):
        chain = entries()
        chain[0], chain[1] = chain[1], chain[0]
        self.assertEqual(verify_metacognitive_chain(chain)["reason"], "SEQUENCE_INVALID:1")

    def test_truncated_chain_fails_genesis(self):
        self.assertEqual(verify_metacognitive_chain(entries()[1:])["reason"], "SEQUENCE_INVALID:1")

    def test_dropped_middle_entry_fails(self):
        chain = entries()
        del chain[1]
        self.assertIs(verify_metacognitive_chain(chain)["valid"], False)

    def test_boolean_sequence_not_accepted_as_integer(self):
        chain = entries()
        chain[0]["sequence"] = True
        self.assertEqual(verify_metacognitive_chain(chain)["reason"], "SEQUENCE_INVALID:1")

    def test_missing_fields_fail(self):
        chain = entries()
        del chain[0]["tier"]
        self.assertEqual(verify_metacognitive_chain(chain)["reason"], "ENTRY_FIELDS_INVALID:1")

    def test_oversized_chain_is_unknown_without_iteration(self):
        chain = [{}] * (MAX_VERIFY_ENTRIES + 1)
        self.assertEqual(verify_metacognitive_chain(chain)["reason"], "CHAIN_EXCEEDS_VERIFICATION_BUDGET")
        self.assertIsNone(verify_metacognitive_chain(chain)["valid"])

    def test_case_changed_digest_rejected(self):
        chain = entries(1)
        chain[0]["entry_hash"] = chain[0]["entry_hash"].upper()
        self.assertIs(verify_metacognitive_chain(chain)["valid"], False)

    def test_original_not_mutated(self):
        chain = entries()
        before = copy.deepcopy(chain)
        verify_metacognitive_chain(chain)
        self.assertEqual(chain, before)

    def test_timestamps_not_cryptographically_bound(self):
        chain = entries()
        chain[1]["ts"] = 1e200
        self.assertIs(verify_metacognitive_chain(chain)["valid"], True)
        # Honest scope: existing chain preimage excludes timestamps.


if __name__ == '__main__':
    unittest.main(verbosity=2)
