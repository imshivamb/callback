import hashlib


def derive_seed(*parts: object) -> int:
    """Derive a stable 63-bit seed from any parts, e.g. (run_seed, scenario_id, trial).

    Uses SHA-256 rather than ``hash()`` so seeds are identical across processes and
    Python versions.
    """
    material = "\x1f".join(str(p) for p in parts).encode()
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big") >> 1
