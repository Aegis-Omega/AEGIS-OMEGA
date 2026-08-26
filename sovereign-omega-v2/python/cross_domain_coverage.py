"""AEGIS Ω — prospective rule extension over the frozen coverage core.

The underlying coverage core is preserved byte-for-byte from the previously
GREEN implementation. This wrapper only admits the two frozen Prospective
Epoch V1 source-specific rule families and re-exports the core API.
"""

import cross_domain_coverage_core as _core

_core.SUPPORTED_POSITIVE_RULES.update({
    "UNICODE_GENERAL_CATEGORY_NOT_CN_V1",
    "NCBI_ESEARCH_UID_PRESENT_V1",
})
_core.SUPPORTED_NEGATIVE_RULES.update({
    "UNICODE_GENERAL_CATEGORY_CN_V1",
    "NCBI_ESEARCH_UID_ABSENT_V1",
})
_core.SUPPORTED_AMBIGUOUS_RULES.update({
    "UNICODE_OUT_OF_RANGE_NOT_ESTABLISHED_V1",
    "NCBI_ESEARCH_NOT_ESTABLISHED_V1",
})

from cross_domain_coverage_core import *  # noqa: F401,F403,E402

_probe_receipt_material = _core._probe_receipt_material
_adapter_material = _core._adapter_material
_coverage_receipt_material = _core._coverage_receipt_material
