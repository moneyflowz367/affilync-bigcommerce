"""
Encryption utilities for BigCommerce integration.
Wraps the shared affilync-integrations-common library.
"""

from affilync_integrations.encryption import (
    TokenEncryption,
    encrypt_token as _encrypt_token,
    decrypt_token as _decrypt_token,
    mask_token,
    configure_encryption,
)

from app.config import settings

# Configure encryption with BigCommerce-specific salt
_encryption = TokenEncryption(settings.encryption_key, salt_suffix="bigcommerce")


def encrypt_token(token: str) -> str:
    """
    Encrypt an access token for storage.

    Args:
        token: Plain text token

    Returns:
        Encrypted token string
    """
    return _encryption.encrypt(token)


def decrypt_token(encrypted_token: str) -> str:
    """
    Decrypt an access token from storage.

    Args:
        encrypted_token: Encrypted token string

    Returns:
        Plain text token
    """
    return _encryption.decrypt(encrypted_token)


__all__ = [
    "encrypt_token",
    "decrypt_token",
    "mask_token",
]
