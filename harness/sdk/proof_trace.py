"""AEGIS proof trace utilities.

Proof trace module for semantic lineage verification and hash validation.
"""
import re

# SHA256 hex digest pattern: exactly 64 hexadecimal characters
SHA256_RE = re.compile(r'^[a-f0-9]{64}$')
