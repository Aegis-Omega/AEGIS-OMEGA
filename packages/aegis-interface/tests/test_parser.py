import pytest

from aegis_interface.parser import ParseError, Range, parse


def test_parses_record_and_variant():
    doc = parse(
        """
        variant Tier { bronze, silver, gold }
        record Snap {
          id: string,
          tier: Tier,
        }
        """
    )
    assert [v.name for v in doc.variants] == ["Tier"]
    assert doc.variants[0].cases == ["bronze", "silver", "gold"]
    assert [r.name for r in doc.records] == ["Snap"]
    assert [f.name for f in doc.records[0].fields] == ["id", "tier"]


def test_interface_keyword_is_record_alias():
    doc = parse("interface Foo { a: string }")
    assert doc.records[0].name == "Foo"


def test_list_and_option_wrappers():
    doc = parse("record R { xs: list<string>, p: option<u64> }")
    fields = {f.name: f.type for f in doc.records[0].fields}
    assert fields["xs"].wrapper == "list"
    assert fields["xs"].inner.name == "string"
    assert fields["p"].wrapper == "option"
    assert fields["p"].inner.name == "u64"


def test_range_annotation():
    doc = parse("record R { @range(0.0, 1.0) c: f64 }")
    assert doc.records[0].fields[0].range == Range(0.0, 1.0)


def test_line_comments_ignored():
    doc = parse("// hi\nrecord R { a: string } // trailing")
    assert doc.records[0].name == "R"


def test_duplicate_field_rejected():
    with pytest.raises(ParseError):
        parse("record R { a: string, a: u32 }")


def test_unknown_keyword_rejected():
    with pytest.raises(ParseError):
        parse("klass R { a: string }")


def test_range_min_gt_max_rejected():
    with pytest.raises(ParseError):
        parse("record R { @range(1.0, 0.0) c: f64 }")
