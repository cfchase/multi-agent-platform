"""
Tests for UserIntegration model and token encryption.

Following TDD: These tests are written BEFORE the implementation.
"""

import pytest
from datetime import datetime, timezone, timedelta
from sqlmodel import Session

from app.models import User


class TestTokenEncryption:
    """Tests for the token encryption service."""

    def test_encrypt_decrypt_roundtrip(self):
        """Encrypting and decrypting a token returns the original value."""
        from app.core.encryption import TokenEncryption

        encryption = TokenEncryption()
        original_token = "ya29.a0AfH6SMBx..."

        encrypted = encryption.encrypt(original_token)
        decrypted = encryption.decrypt(encrypted)

        assert decrypted == original_token
        assert encrypted != original_token.encode()  # Actually encrypted

    def test_encrypt_produces_bytes(self):
        """Encryption returns bytes for database storage."""
        from app.core.encryption import TokenEncryption

        encryption = TokenEncryption()
        encrypted = encryption.encrypt("test-token")

        assert isinstance(encrypted, bytes)

    def test_decrypt_invalid_data_raises_error(self):
        """Decrypting tampered data raises an error."""
        from app.core.encryption import TokenEncryption
        from cryptography.fernet import InvalidToken

        encryption = TokenEncryption()

        with pytest.raises(InvalidToken):
            encryption.decrypt(b"invalid-encrypted-data")

    def test_encryption_with_invalid_key_raises_error(self):
        """Invalid encryption key raises ValueError."""
        from app.core.encryption import TokenEncryption

        # Explicitly pass invalid key to test error handling
        with pytest.raises(ValueError):
            TokenEncryption(key="not-a-valid-fernet-key")


class TestUserIntegrationModel:
    """Tests for the UserIntegration database model."""

    def test_create_integration(self, session: Session):
        """Can create a user integration with encrypted tokens."""
        from app.models import UserIntegration
        from app.core.encryption import get_encryption

        # Create a user first
        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create integration with encrypted token
        encryption = get_encryption()
        access_token = "ya29.access_token_here"
        refresh_token = "1//refresh_token_here"

        integration = UserIntegration(
            user_id=user.id,
            service_name="google_drive",
            access_token_encrypted=encryption.encrypt(access_token),
            refresh_token_encrypted=encryption.encrypt(refresh_token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scopes="https://www.googleapis.com/auth/drive.readonly",
            token_type="Bearer",
        )
        session.add(integration)
        session.commit()
        session.refresh(integration)

        assert integration.id is not None
        assert integration.user_id == user.id
        assert integration.service_name == "google_drive"

    def test_unique_user_service_constraint(self, session: Session):
        """Cannot have duplicate integrations for same user+service."""
        from app.models import UserIntegration
        from app.core.encryption import get_encryption
        from sqlalchemy.exc import IntegrityError

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        encryption = get_encryption()

        # First integration
        integration1 = UserIntegration(
            user_id=user.id,
            service_name="google_drive",
            access_token_encrypted=encryption.encrypt("token1"),
        )
        session.add(integration1)
        session.commit()

        # Second integration with same user+service should fail
        integration2 = UserIntegration(
            user_id=user.id,
            service_name="google_drive",
            access_token_encrypted=encryption.encrypt("token2"),
        )
        session.add(integration2)

        with pytest.raises(IntegrityError):
            session.commit()

    def test_user_relationship(self, session: Session):
        """Integration has relationship to User."""
        from app.models import UserIntegration
        from app.core.encryption import get_encryption

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        encryption = get_encryption()
        integration = UserIntegration(
            user_id=user.id,
            service_name="google_drive",
            access_token_encrypted=encryption.encrypt("token"),
        )
        session.add(integration)
        session.commit()
        session.refresh(integration)

        # Access user through relationship
        assert integration.user.email == "test@example.com"

    def test_user_has_integrations_list(self, session: Session):
        """User has list of integrations."""
        from app.models import UserIntegration
        from app.core.encryption import get_encryption

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        encryption = get_encryption()

        # Add multiple integrations
        for service in ["google_drive", "dataverse"]:
            integration = UserIntegration(
                user_id=user.id,
                service_name=service,
                access_token_encrypted=encryption.encrypt(f"token-{service}"),
            )
            session.add(integration)
        session.commit()
        session.refresh(user)

        assert len(user.integrations) == 2
        service_names = {i.service_name for i in user.integrations}
        assert service_names == {"google_drive", "dataverse"}

    def test_token_expiry_check(self, session: Session):
        """Can check if token is expired."""
        from app.models import UserIntegration
        from app.core.encryption import get_encryption

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        encryption = get_encryption()

        # Expired token
        expired_integration = UserIntegration(
            user_id=user.id,
            service_name="google_drive",
            access_token_encrypted=encryption.encrypt("token"),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        assert expired_integration.is_expired() is True

        # Valid token
        valid_integration = UserIntegration(
            user_id=user.id,
            service_name="dataverse",
            access_token_encrypted=encryption.encrypt("token"),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        assert valid_integration.is_expired() is False

        # No expiry set (never expires)
        no_expiry_integration = UserIntegration(
            user_id=user.id,
            service_name="other",
            access_token_encrypted=encryption.encrypt("token"),
            expires_at=None,
        )

        assert no_expiry_integration.is_expired() is False

    def test_cascade_delete_with_user(self, session: Session):
        """Deleting user deletes their integrations."""
        from app.models import UserIntegration
        from app.core.encryption import get_encryption
        from sqlmodel import select

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        encryption = get_encryption()
        integration = UserIntegration(
            user_id=user.id,
            service_name="google_drive",
            access_token_encrypted=encryption.encrypt("token"),
        )
        session.add(integration)
        session.commit()

        integration_id = integration.id

        # Delete user
        session.delete(user)
        session.commit()

        # Integration should be deleted too
        result = session.exec(
            select(UserIntegration).where(UserIntegration.id == integration_id)
        ).first()
        assert result is None
