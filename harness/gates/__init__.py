"""Zero-discretion type gates.

The author of a construction chooses the construction. The author does not
choose which type-mandated falsifiers the construction must survive.
"""
from .gates import (  # noqa: F401
    ERROR, FAIL, PASS, SCHEMA_VERSION,
    Gate, GateVerdict, IncompleteRegistry, InvariantViolation,
    Receipt, SpectralBasis,
    admit, binary, digest, gateset, unary,
)
from .status import (  # noqa: F401
    Claim, Evidence, IllegalPromotion, ResearchStatus,
)
