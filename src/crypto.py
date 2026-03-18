"""Fernet-based encryption helpers."""
from cryptography.fernet import Fernet

from src import config

_fernet = Fernet(
    config.FERNET_KEY.encode()
    if isinstance(config.FERNET_KEY, str)
    else config.FERNET_KEY
)


def encrypt_text(value: str) -> bytes:
    """Encrypt a plaintext string to bytes."""
    return _fernet.encrypt(value.encode("utf-8"))


def decrypt_text(blob: bytes) -> str:
    """Decrypt bytes back to a plaintext string."""
    return _fernet.decrypt(blob).decode("utf-8")
