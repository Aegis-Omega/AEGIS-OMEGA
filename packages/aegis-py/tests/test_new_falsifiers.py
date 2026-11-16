import hashlib
from aegis.adapters import lean_axioms, data_snapshot, VERIFIED, UNKNOWN

HEAD = 'a' * 40
BIND = {'verifier': {'name': 'lean', 'version': '4.34.0'}, 'environment': {'os': 'linux'}, 'source_head': HEAD}
THEOREM = 'Foo.bar'


def test_control_single_clean_report_is_verified():
    output = "'Foo.bar' depends on axioms: [propext, Classical.choice, Quot.sound]"
    assert lean_axioms(output, theorem=THEOREM, claim='unconditional', **BIND)['status'] == VERIFIED


def test_duplicate_conflicting_axiom_reports_fail_closed():
    report = "'Foo.bar' depends on axioms: [propext]"
    output = report + '\n' + "'Foo.bar' depends on axioms: [sorryAx]"
    result = lean_axioms(output, theorem=THEOREM, claim='unconditional', **BIND)
    assert result['status'] == UNKNOWN, result


def test_sorry_ax_derivative_conditional_fails_closed():
    output = "'Foo.bar' depends on axioms: [propext, sorryAx.1]"
    result = lean_axioms(output, theorem=THEOREM, claim='conditional', declared_assumptions=['sorryAx.1'], **BIND)
    assert result['status'] != VERIFIED, result


def test_error_in_lean_output_fails_closed():
    output = "error: unknown constant 'Foo'\n'Foo.bar' does not depend on any axioms"
    result = lean_axioms(output, theorem=THEOREM, claim='unconditional', **BIND)
    assert result['status'] == UNKNOWN, result


def test_unexpected_csv_columns_type_fails_closed_without_exception():
    data=b'id,name\n1,abc\n'
    result = data_snapshot(data, {'sha256':hashlib.sha256(data).hexdigest(), 'columns':17, 'rows':1}, **BIND)
    assert result['status'] == UNKNOWN


def test_strict_data_contract_rejects_boolean_row_count():
    data=b'id,name\n1,abc\n'
    result = data_snapshot(data, {'sha256':hashlib.sha256(data).hexdigest(), 'columns':['id','name'], 'rows':True}, **BIND)
    assert result['status'] == UNKNOWN, result
