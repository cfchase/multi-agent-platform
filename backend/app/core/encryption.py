"""
Token encryption service for secure storage of OAuth tokens.

Uses Fernet symmetric encryption (AES-128-CBC with HMAC).
Tokens are encrypted before database storage and decrypted on retrieval.

Usage:
    from app.core.encryption import get_encryption

    encryption = get_encryption()
    encrypted = encryption.encrypt("my-oauth-token")
    decrypted = encryption.decrypt(encrypted)
"""

from functools import lru_cache

from cryptography.fernet import Fernet

from app.core.config import settings


class TokenEncryption:
    """
    Encrypt and decrypt OAuth tokens for secure database storage.

    Uses Fernet symmetric encryption which provides:
    - AES-128-CBC encryption
    - HMAC-SHA256 authentication
    - Automatic IV generation
    - Timestamp for key rotation (optional)
    """

    def __init__(self, key: str | None = None):
        """
        Initialize encryption with a Fernet key.

        Args:
            key: Base64-encoded 32-byte key. If not provided,
                 reads from TOKEN_ENCRYPTION_KEY setting.

        Raises:
            ValueError: If no key is provided or found in settings.
        """
        if key is None:
            key = settings.TOKEN_ENCRYPTION_KEY

        if not key:
            raise ValueError(
                "TOKEN_ENCRYPTION_KEY environment variable is required. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )

        self.fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, plaintext: str) -> bytes:
        """
        Encrypt a token string.

        Args:
            plaintext: The token to encrypt.

        Returns:
            Encrypted bytes suitable for database storage.
        """
        return self.fernet.encrypt(plaintext.encode())

    def decrypt(self, ciphertext: bytes) -> str:
        """
        Decrypt an encrypted token.

        Args:
            ciphertext: The encrypted bytes from database.

        Returns:
            Original token string.

        Raises:
            cryptography.fernet.InvalidToken: If data is corrupted or tampered.
        """
        return self.fernet.decrypt(ciphertext).decode()


@lru_cache(maxsize=1)
def get_encryption() -> TokenEncryption:
    """
    Get the singleton TokenEncryption instance.

    Uses LRU cache to ensure only one instance is created.
    The instance is cached for the lifetime of the application.

    Returns:
        TokenEncryption instance configured from environment.
    """
    return TokenEncryption()
