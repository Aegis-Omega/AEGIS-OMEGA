from harness.sdk.guinand_weil_arb import ArbGalerkinSpecV1
from harness.sdk.guinand_weil_crosscheck import verify_closed_form_crosscheck


def test_independent_closed_form_route_lands_inside_arb_entry_balls():
    result = verify_closed_form_crosscheck(
        ArbGalerkinSpecV1(c=5, N=1, prec_bits=192),
        decimal_digits=70,
    )
    assert result.valid is True
    assert result.entry_count == 6
    assert result.all_entries_agree is True
    assert result.mismatch_count == 0
    assert result.route_independence_claimed is False
    assert result.galerkin_semantics_verified is False
    assert result.global_weil_positivity_proven is False
    assert result.rh_proven is False


def test_crosscheck_receipt_is_deterministic_for_same_inputs():
    spec = ArbGalerkinSpecV1(c=5, N=1, prec_bits=192)
    first = verify_closed_form_crosscheck(spec, decimal_digits=70)
    second = verify_closed_form_crosscheck(spec, decimal_digits=70)
    assert first.comparison_root == second.comparison_root
    assert first.receipt_root == second.receipt_root
