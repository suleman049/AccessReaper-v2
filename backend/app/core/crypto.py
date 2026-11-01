"""
Cryptographic utility module for AccessReaper v2.
Handles symmetric encryption and decryption of secrets (such as GitHub PAT tokens)
stored at rest using Fernet (AES-128-CBC + HMAC-SHA256).
"""

import logging

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

logger = logging.getLogger("accessreaper.crypto")


def _get_fernet() -> Fernet:
    key = settings.APP_ENCRYPTION_KEY
    if not key:
        raise ValueError("APP_ENCRYPTION_KEY is not configured.")
    if isinstance(key, str):
        key_bytes = key.strip().encode("utf-8")
    else:
        key_bytes = key
    return Fernet(key_bytes)


def encrypt_secret(plain_text: str) -> str:
    """
    Encrypts a plaintext secret string and returns a url-safe base64 encoded ciphertext.
    """
    if not plain_text:
        return ""
    f = _get_fernet()
    return f.encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_secret(cipher_text: str) -> str:
    """
    Decrypts a ciphertext string back to plaintext.
    """
    if not cipher_text:
        return ""
    try:
        f = _get_fernet()
        return f.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logger.error("Failed to decrypt secret: invalid token or encryption key mismatch.")
        raise ValueError("Invalid encryption key or corrupted secret ciphertext.")
