from aegis_cstar.receipts import canonical_sha256

def test_canonical_receipt_hash_is_order_independent():
    a = {"b": 2, "a": 1}
    b = {"a": 1, "b": 2}
    assert canonical_sha256(a) == canonical_sha256(b)
