"""RS256 keypair loader — loads PEM keys once, caches in-process.

The keys live outside the image (mounted read-only from the host or a k8s Secret).
We use the `cryptography` library to validate them at boot and re-export PEM strings
to python-jose, which is happy with either the parsed object or the PEM bytes.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from django.conf import settings


class KeyMaterialError(RuntimeError):
    """Raised when JWT key material is missing or malformed."""


@lru_cache(maxsize=1)
def private_key_pem() -> bytes:
    return _load(settings.cfg.JWT_PRIVATE_KEY_PATH, expected_class=RSAPrivateKey)


@lru_cache(maxsize=1)
def public_key_pem() -> bytes:
    return _load(settings.cfg.JWT_PUBLIC_KEY_PATH, expected_class=RSAPublicKey)


def _load(path: str, *, expected_class: type) -> bytes:
    p = Path(path)
    if not p.exists():
        raise KeyMaterialError(
            f"JWT key not found at {path}. "
            f"Run `make keys` (locally) or mount a k8s Secret with the keypair in production."
        )
    pem = p.read_bytes()
    try:
        key = (
            serialization.load_pem_private_key(pem, password=None)
            if expected_class is RSAPrivateKey
            else serialization.load_pem_public_key(pem)
        )
    except Exception as exc:
        raise KeyMaterialError(f"Failed to parse PEM at {path}: {exc}") from exc
    if not isinstance(key, expected_class):
        raise KeyMaterialError(f"PEM at {path} is not an {expected_class.__name__}")
    return pem
