"""RPES Immutable Hash Module (EI-004)"""

import hashlib

def compute_hash(canonical_string: str) -> str:
    if not isinstance(canonical_string, str):
        raise TypeError(f"Hash module expects a canonical UTF-8 string, got {type(canonical_string).__name__}")
    canonical_bytes = canonical_string.encode("utf-8")
    hash_object = hashlib.sha256(canonical_bytes)
    return hash_object.hexdigest()
