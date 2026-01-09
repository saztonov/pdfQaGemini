"""Cryptographic utilities for secure storage of sensitive values.

Uses AES-256-GCM for authenticated encryption.
Master key is stored in .env as APP_SECRET_KEY.
"""

import os
import base64
import secrets
import logging
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

# Sensitive keys that must be encrypted in database
SENSITIVE_KEYS = frozenset({
    "gemini_api_key",
    "r2_secret_access_key",
    "r2_access_key_id",
})

# Prefix for encrypted values in DB
ENCRYPTED_PREFIX = "enc:v1:"


class CryptoService:
    """AES-256-GCM encryption service for sensitive values."""

    def __init__(self, master_key: str):
        """Initialize with master key from environment.

        Args:
            master_key: Base64-encoded 32-byte key (or hex string)
        """
        self._key = self._decode_key(master_key)
        self._aesgcm = AESGCM(self._key)

    @staticmethod
    def _decode_key(key_str: str) -> bytes:
        """Decode master key from string to bytes."""
        if not key_str:
            raise ValueError("APP_SECRET_KEY is not configured")

        # Try base64 first
        try:
            key_bytes = base64.b64decode(key_str)
            if len(key_bytes) == 32:
                return key_bytes
        except Exception:
            pass

        # Try hex
        try:
            key_bytes = bytes.fromhex(key_str)
            if len(key_bytes) == 32:
                return key_bytes
        except Exception:
            pass

        # Use as-is if 32 bytes
        if len(key_str) == 32:
            return key_str.encode("utf-8")

        # Hash it to 32 bytes as fallback
        import hashlib
        return hashlib.sha256(key_str.encode("utf-8")).digest()

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string value.

        Args:
            plaintext: The value to encrypt

        Returns:
            Encrypted string in format: "enc:v1:<base64(iv + ciphertext)>"
        """
        if not plaintext:
            return plaintext

        # Generate random 12-byte IV (recommended for GCM)
        iv = secrets.token_bytes(12)

        # Encrypt
        ciphertext = self._aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)

        # Combine IV + ciphertext and base64 encode
        combined = iv + ciphertext
        encoded = base64.b64encode(combined).decode("utf-8")

        return f"{ENCRYPTED_PREFIX}{encoded}"

    def decrypt(self, encrypted: str) -> str:
        """Decrypt an encrypted string value.

        Args:
            encrypted: Encrypted string from encrypt()

        Returns:
            Decrypted plaintext
        """
        if not encrypted:
            return encrypted

        # Check if actually encrypted
        if not encrypted.startswith(ENCRYPTED_PREFIX):
            # Not encrypted, return as-is (for migration)
            return encrypted

        # Remove prefix and decode
        encoded = encrypted[len(ENCRYPTED_PREFIX):]
        combined = base64.b64decode(encoded)

        # Split IV (12 bytes) and ciphertext
        iv = combined[:12]
        ciphertext = combined[12:]

        # Decrypt
        plaintext = self._aesgcm.decrypt(iv, ciphertext, None)
        return plaintext.decode("utf-8")

    def is_encrypted(self, value: str) -> bool:
        """Check if a value is already encrypted."""
        return value.startswith(ENCRYPTED_PREFIX) if value else False


# Global instance (initialized lazily)
_crypto_service: Optional[CryptoService] = None


def get_crypto_service() -> CryptoService:
    """Get the global crypto service instance."""
    global _crypto_service
    if _crypto_service is None:
        from app.config import settings
        _crypto_service = CryptoService(settings.app_secret_key)
    return _crypto_service


def encrypt_value(value: str) -> str:
    """Encrypt a sensitive value."""
    return get_crypto_service().encrypt(value)


def decrypt_value(value: str) -> str:
    """Decrypt an encrypted value."""
    return get_crypto_service().decrypt(value)


def is_sensitive_key(key: str) -> bool:
    """Check if a settings key contains sensitive data."""
    return key in SENSITIVE_KEYS


def mask_sensitive_value(value: str, key: str = "") -> str:
    """Create a masked display version of a sensitive value.

    Examples:
        "sk-abc123xyz789" -> "sk-a***789"
        "AIzaSy..." -> "AIza***..."
    """
    if not value:
        return ""

    # Don't mask already-masked values
    if "***" in value:
        return value

    # Decrypt if encrypted
    crypto = get_crypto_service()
    if crypto.is_encrypted(value):
        try:
            value = crypto.decrypt(value)
        except Exception:
            return "***encrypted***"

    # Create mask showing first 4 and last 4 chars
    if len(value) <= 8:
        return "****"

    return f"{value[:4]}***{value[-4:]}"


def generate_master_key() -> str:
    """Generate a new 32-byte master key (base64 encoded).

    Use this to generate APP_SECRET_KEY for .env file.
    """
    key_bytes = secrets.token_bytes(32)
    return base64.b64encode(key_bytes).decode("utf-8")


if __name__ == "__main__":
    # Generate a new master key
    print("Generated APP_SECRET_KEY:")
    print(generate_master_key())
