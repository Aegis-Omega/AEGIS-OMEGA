"""AEGIS-Ω Python SDK — governed multi-agent AI with constitutional audit trail."""
from .client import AegisClient, AegisError, CollaborationResult, PlatformStatus
from .async_client import AsyncAegisClient

__version__ = "1.0.0"
__all__ = ["AegisClient", "AsyncAegisClient", "AegisError", "CollaborationResult", "PlatformStatus"]
