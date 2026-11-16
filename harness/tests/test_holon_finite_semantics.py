"""Executable finite formal-semantic tests over genuine MHP-1 lineage receipts.

The originating carrier and cultural interpretation remain fixture assumptions:
this proves truth-table claims about *exact encoded Boolean formula bytes* only.
"""
from __future__ import annotations

from dataclasses import replace
import itertools
import random
import pytest

from harness.sdk.holon_finite_semantics import (
    SCHEMA, FiniteBooleanError, FiniteFormalRelationVerifierV1,
    parse_formal_reading, finite_truth_mask, PASS, MAX_FORMULA_BYTES,
)
from harness.sdk.holon_indexed_context import ContextRelationReceiptV1
from harness.sdk.holon_meaning_bridge import (
    ContextBindingReceiptV1, ContextualReadingV1, HolonMeaningLensV1,
    HolonMeaningVerifierV1, SourceOccurrenceV1,
)
from harness.sdk.meaning_heritage import (
    ClaimRef, DeclaredAdditionEdge, DerivationProofReceiptV1,
    HeritageVerifierV13, LossType, SemanticLineageEnvelopeV1,
    TransformRelation,
)
from harness.sdk.sovereign_execution import canonical_bytes
from harness.tests.test_holon_meaning_bridge import (
    ArtifactStore, ProofStore, VerifiedStore, h, holon, issue, sha,
)


def var(name="p"):
    return {"op": "var", "name": name}


def neg(arg):
    return {"op": "not", "arg": arg}


def constant(value):
    return {"op": "const", "value": value}


def formal(formula, variables=("p",)):
    return canonical_bytes({
        "schema": SCHEMA,
        "variables": list(variables),
        "formula": formula,
    })


@pytest.fixture
def formal_case():
    return make_case()


def make_case(expressions=None, variables=("p",)):
    expressions = expressions or {
        "left-p": var(),
        "left-not-p": neg(var()),
        "right-p": var(),
        "right-not-p": neg(var()),
    }
    original = b"fixture/source: A"
    artifacts = ArtifactStore()
    occurrence = SourceOccurrenceV1(
        artifacts.put(original), original.index(b"A"),
        original.index(b"A") + 1, sha(b"A"),
    )
    source_claim = ClaimRef("carrier:A", h("FINITE_CARRIER", "A"), "fp:finite:carrier")
    source_claimset = issue(b"A", (source_claim,), "formal-source")
    claimsets, envelopes, heritage, bindings = (
        VerifiedStore(), VerifiedStore(), VerifiedStore(), VerifiedStore()
    )
    claimsets.put(source_claimset)
    proofs = ProofStore()
    readings = []
    contexts = {
        "left": artifacts.put(b"independent-formal-context:left"),
        "right": artifacts.put(b"independent-formal-context:right"),
    }
    for name, expr in sorted(expressions.items()):
        side = name.split("-", 1)[0]
        output = expr if isinstance(expr, bytes) else formal(expr, variables)
        context_root = contexts[side]
        target_claim = ClaimRef(
            name, h("FINITE_DERIVED_CLAIM", name), f"fp:finite:{name}"
        )
        target = issue(output, (target_claim,), f"formal-derived-{name}")
        claimsets.put(target)
        assert artifacts.put(output) == target.payload_root
        transform_root = h("FINITE_FORMAL_TRANSFORM", name)
        derivation = DerivationProofReceiptV1(
            derived_claim_digest=target_claim.claim_digest,
            source_claim_digests=(source_claim.claim_digest,),
            source_semantic_fingerprints=(source_claim.semantic_fingerprint,),
            derived_semantic_fingerprint=target_claim.semantic_fingerprint,
            transform_root=transform_root,
            verifier_root=h("FINITE_PROOF_VERIFIER", name),
            policy_root=h("FINITE_PROOF_POLICY", name),
        )
        proofs.derivations[derivation.root] = derivation
        envelope = SemanticLineageEnvelopeV1(
            lineage_id=f"finite-{name}",
            source_root=source_claimset.payload_root,
            source_claimset_receipt_root=source_claimset.root,
            derived_root=target.payload_root,
            derived_claimset_receipt_root=target.root,
            transform_root=transform_root,
            transform_relation=TransformRelation.LOSSY_TRANSFORM,
            loss_type=LossType.HEURISTIC_ABSTRACTION,
            preservation_edges=(),
            declared_omission_digests=(source_claim.claim_digest,),
            declared_additions=(
                DeclaredAdditionEdge(target_claim.claim_digest, derivation.root),
            ),
            uncertainty_bps=1000,
        )
        result, mhp = HeritageVerifierV13(
            verifier_root=h("FINITE_HERITAGE_VERIFIER", name),
            policy_root=h("FINITE_HERITAGE_POLICY", name),
            proof_store=proofs,
            claimset_store=claimsets,
        ).verify(envelope, source_claimset, target)
        assert result.status == "PASS" and mhp is not None
        envelopes.put(envelope)
        heritage.put(mhp)
        binding = ContextBindingReceiptV1(
            reading_id=name, holon_root=holon().root,
            occurrence_root=occurrence.root, context_root=context_root,
            envelope_root=envelope.root, transform_root=transform_root,
            derived_root=target.payload_root,
            verifier_root=h("FINITE_BIND_VERIFIER", name),
            policy_root=h("FINITE_BIND_POLICY", name),
        )
        bindings.put(binding)
        readings.append(ContextualReadingV1(
            name, context_root, envelope.root, mhp.root, binding.root
        ))
    lens = HolonMeaningLensV1(holon(), occurrence, tuple(readings))
    mhp_verifier = HolonMeaningVerifierV1(
        artifacts=artifacts, heritage=heritage, envelopes=envelopes,
        claimsets=claimsets, context_bindings=bindings,
    )
    mhp_result, receipt = mhp_verifier.verify(lens)
    assert mhp_result.status == "PASS" and receipt is not None
    receipts, lenses, relations = VerifiedStore(), VerifiedStore(), VerifiedStore()
    receipts.put(receipt)
    lenses.put(lens)
    all_pairs = []
    for a, b in itertools.product(
        [r for r in readings if r.context_root == contexts["left"]],
        [r for r in readings if r.context_root == contexts["right"]],
    ):
        da = parse_formal_reading(artifacts.fetch_verified(
            bindings.fetch_verified(a.context_binding_receipt_root).derived_root
        ))
        db = parse_formal_reading(artifacts.fetch_verified(
            bindings.fetch_verified(b.context_binding_receipt_root).derived_root
        ))
        if da.variables == db.variables and finite_truth_mask(da) & finite_truth_mask(db):
            all_pairs.append((a.reading_id, b.reading_id))
    relation = relations.put(ContextRelationReceiptV1(
        source_context_root=contexts["left"],
        target_context_root=contexts["right"],
        allowed_reading_id_pairs=tuple(sorted(all_pairs)),
        verifier_root=h("FINITE_RELATION_REVIEW", "test"),
        policy_root=h("FINITE_RELATION_POLICY", "test"),
    ))
    verifier = FiniteFormalRelationVerifierV1(
        relations=relations, meanings=receipts, lenses=lenses,
        bindings=bindings, artifacts=artifacts, meaning_verifier=mhp_verifier,
    )
    return {
        "verifier": verifier, "relation": relation, "lens": lens,
        "receipt": receipt, "artifacts": artifacts, "bindings": bindings,
        "relations": relations, "receipts": receipts, "lenses": lenses,
        "context": contexts,
    }


def deny(case, code, relation_root=None):
    check, receipt = case["verifier"].verify(
        case["receipt"].root, relation_root or case["relation"].root
    )
    assert receipt is None and check.verification_root is None
    assert check.status == "FAIL_FINITE_FORMAL_RELATION_DENIED"
    assert check.error_codes == (code,)


def test_own_truth_masks_and_complete_formal_pair_table(formal_case):
    c = formal_case
    check, receipt = c["verifier"].verify(c["receipt"].root, c["relation"].root)
    assert check.status == PASS and receipt is not None
    assert receipt.authority_class == "NONE"
    assert (receipt.valuation_count, receipt.checked_pair_count) == (2, 4)
    assert (receipt.compatible_pair_count, receipt.incompatible_pair_count) == (2, 2)
    assert set(c["relation"].allowed_reading_id_pairs) == {
        ("left-p", "right-p"), ("left-not-p", "right-not-p"),
    }
    assert dict(receipt.reading_truth_masks_hex)["left-p"] == f"{2:064x}"
    assert dict(receipt.reading_truth_masks_hex)["left-not-p"] == f"{1:064x}"
    assert receipt.verification_root == check.verification_root
    assert (check, receipt) == c["verifier"].verify(
        c["receipt"].root, c["relation"].root
    )


def test_complete_unsatisfiable_binary_pair_table_can_be_proved():
    c = make_case({"left-contradiction": constant(False), "right-tautology": constant(True)}, ())
    assert not c["relation"].allowed_reading_id_pairs
    check, certificate = c["verifier"].verify(c["receipt"].root, c["relation"].root)
    assert check.status == PASS and certificate is not None
    assert (certificate.checked_pair_count, certificate.compatible_pair_count,
            certificate.incompatible_pair_count) == (1, 0, 1)


def test_one_extra_unverified_pair_denied(formal_case):
    c = formal_case
    pairs = c["relation"].allowed_reading_id_pairs + (("left-p", "right-not-p"),)
    wrong = c["relations"].put(replace(c["relation"], allowed_reading_id_pairs=pairs))
    deny(c, "FINITE_FORMAL_RELATION_TABLE_MISMATCH", wrong.root)


def test_missing_positive_pair_denied(formal_case):
    c = formal_case
    wrong = c["relations"].put(replace(
        c["relation"], allowed_reading_id_pairs=c["relation"].allowed_reading_id_pairs[:1]
    ))
    deny(c, "FINITE_FORMAL_RELATION_TABLE_MISMATCH", wrong.root)


def test_valid_hash_but_no_source_store_entry_denied(formal_case):
    deny(formal_case, "FINITE_FORMAL_RELATION_UNTRUSTED", "0" * 64)


def test_missing_original_mhp_receipt_denied(formal_case):
    c = formal_case
    c["receipts"].data.clear()
    deny(c, "FINITE_FORMAL_MHP_RECEIPT_UNTRUSTED")


def test_missing_original_mhp_lineage_denied(formal_case):
    c = formal_case
    c["verifier"].meaning_verifier.heritage.data.clear()
    deny(c, "FINITE_FORMAL_MHP_REPLAY_FAILED")


def test_missing_exact_derived_bytes_denied(formal_case):
    c = formal_case
    reading = c["lens"].readings[0]
    binding = c["bindings"].fetch_verified(reading.context_binding_receipt_root)
    c["artifacts"].data[binding.derived_root] = b"tampered"
    deny(c, "FINITE_FORMAL_MHP_REPLAY_FAILED")


def test_identical_formula_payload_cannot_change_mhp_origin(formal_case):
    c = formal_case
    source = c["lens"].readings[0]
    binding = c["bindings"].fetch_verified(source.context_binding_receipt_root)
    c["bindings"].data[binding.root] = replace(
        binding, occurrence_root="0" * 64
    )
    deny(c, "FINITE_FORMAL_MHP_REPLAY_FAILED")


def test_distinct_formal_variable_universes_denied():
    a = formal(var("p"), ("p",))
    b = formal(var("q"), ("q",))
    c = make_case({"left-p": a, "right-q": b})
    deny(c, "FINITE_FORMAL_VARIABLE_UNIVERSE_MISMATCH")


@pytest.mark.parametrize(("raw", "message"), [
    (b'{"schema":"aegis.finite-boolean-reading.v1","variables":[],"formula":{"op":"const","value":true},"variables":[]}', "FORMULA_DUPLICATE_JSON_KEY"),
    (b'{"formula":{"op":"const","value":true}, "schema":"aegis.finite-boolean-reading.v1","variables":[]}', "FORMULA_BYTES_NONCANONICAL"),
    (formal({"op":"xor","args":[var(),neg(var())]}), "FORMULA_OPERATOR_UNSUPPORTED"),
    (formal({"op":"const","value":1}), "FORMULA_CONSTANT_INVALID"),
    (formal({"op":"var","name":"q"}), "FORMULA_VARIABLE_NOT_DECLARED"),
    (formal({"op":"and","args":[var()]}), "FORMULA_CONNECTIVE_SHAPE_INVALID"),
    (formal({"op":"not","arg":var(),"extra":0}), "FORMULA_NOT_SHAPE_INVALID"),
    (formal({"op":"var","name":"p","unused":True}), "FORMULA_VARIABLE_NOT_DECLARED"),
    (b"no-json", "FORMULA_JSON_INVALID"),
    (b"", "FORMULA_BYTES_INVALID"),
    (b"x" * (MAX_FORMULA_BYTES + 1), "FORMULA_BYTES_INVALID"),
])
def test_malformed_formal_payload_is_not_repaired_silently(raw, message):
    with pytest.raises(FiniteBooleanError, match=message):
        parse_formal_reading(raw)


@pytest.mark.parametrize("variables", [
    ["q", "p"], ["p", "p"], ["punctuation!"], list("abcdefghi"),
    [1], [None],
])
def test_noncanonical_or_unbounded_variable_universe_fails(variables):
    raw = canonical_bytes({
        "schema": SCHEMA, "variables": variables, "formula": constant(True)
    })
    with pytest.raises(FiniteBooleanError, match="FORMULA_VARIABLES_INVALID"):
        parse_formal_reading(raw)


def test_seeded_independent_truth_table_oracle():
    rng = random.Random(20261116)
    def construct(depth):
        if depth == 0 or rng.random() < 0.4:
            return rng.choice([var("p"), var("q"), constant(True), constant(False)])
        choice = rng.choice(("not", "and", "or"))
        if choice == "not":
            return neg(construct(depth - 1))
        return {"op":choice, "args":[construct(depth - 1), construct(depth - 1)]}

    def independent(node, bits):
        op = node["op"]
        if op == "var":
            return bits[{"p":0,"q":1}[node["name"]]]
        if op == "const":
            return node["value"]
        if op == "not":
            return not independent(node["arg"], bits)
        values = [independent(x,bits) for x in node["args"]]
        return (all(values) if op == "and" else any(values))

    for _ in range(250):
        tree = construct(4)
        source = formal(tree, ("p", "q"))
        formula = parse_formal_reading(source)
        got = finite_truth_mask(formula)
        expected = sum(
            (int(independent(tree,(bool(i & 1),bool(i & 2)))) << i)
            for i in range(4)
        )
        assert got == expected
        assert parse_formal_reading(source) == formula


def test_large_depth_and_node_count_rejected():
    tree = var()
    for _ in range(13):
        tree = neg(tree)
    with pytest.raises(FiniteBooleanError, match="FORMULA_AST_LIMIT_EXCEEDED"):
        parse_formal_reading(formal(tree))


def test_syntactic_ambiguity_is_not_replaced_by_unicode_normalization():
    # The strict formal profile only has ASCII variable identifiers.
    with pytest.raises(FiniteBooleanError, match="FORMULA_VARIABLES_INVALID"):
        parse_formal_reading(formal(var("p"), ("pé",)))
