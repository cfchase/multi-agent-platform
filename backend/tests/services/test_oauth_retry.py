"""
Tests for OAuth 401 retry logic.

Validates automatic token refresh and retry on 401 responses from external services.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from sqlmodel import Session
import httpx

from app.models import User


class TestWithOAuthRetry:
    """Tests for the with_oauth_retry decorator/utility."""

    @pytest.mark.asyncio
    async def test_returns_response_on_success(self, session: Session):
        """Returns response directly when request succeeds."""
        from app.services.oauth_retry import with_oauth_retry
        from app.crud.integration import create_or_update_integration

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create a valid integration
        create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="valid-token",
            refresh_token="refresh-token",
            expires_in=3600,
        )

        # Mock a successful request function
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_request = AsyncMock(return_value=mock_response)

        result = await with_oauth_retry(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            request_func=mock_request,
        )

        assert result.status_code == 200
        mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_retries_on_401_after_token_refresh(self, session: Session):
        """Refreshes token and retries request on 401 response."""
        from app.services.oauth_retry import with_oauth_retry
        from app.crud.integration import create_or_update_integration

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create integration
        create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="expired-token",
            refresh_token="refresh-token",
            expires_in=3600,
        )

        # First call returns 401, second returns 200
        mock_401_response = MagicMock()
        mock_401_response.status_code = 401

        mock_200_response = MagicMock()
        mock_200_response.status_code = 200

        call_count = 0

        async def mock_request(token: str):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_401_response
            return mock_200_response

        # Mock the token refresh
        with patch("app.services.oauth_retry.refresh_integration_token") as mock_refresh:
            mock_refresh.return_value = True

            result = await with_oauth_retry(
                session=session,
                user_id=user.id,
                service_name="google_drive",
                request_func=mock_request,
            )

            assert result.status_code == 200
            assert call_count == 2  # Called twice
            mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_401_when_refresh_fails(self, session: Session):
        """Returns 401 response when token refresh fails."""
        from app.services.oauth_retry import with_oauth_retry
        from app.crud.integration import create_or_update_integration

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create integration
        create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="expired-token",
            refresh_token="invalid-refresh-token",
            expires_in=3600,
        )

        # Request returns 401
        mock_401_response = MagicMock()
        mock_401_response.status_code = 401
        mock_request = AsyncMock(return_value=mock_401_response)

        # Mock token refresh failure
        with patch("app.services.oauth_retry.refresh_integration_token") as mock_refresh:
            mock_refresh.return_value = False

            result = await with_oauth_retry(
                session=session,
                user_id=user.id,
                service_name="google_drive",
                request_func=mock_request,
            )

            # Should return the 401 response
            assert result.status_code == 401
            mock_refresh.assert_called_once()
            # Should NOT retry after failed refresh
            assert mock_request.call_count == 1

    @pytest.mark.asyncio
    async def test_does_not_retry_on_other_errors(self, session: Session):
        """Does not retry on non-401 errors."""
        from app.services.oauth_retry import with_oauth_retry
        from app.crud.integration import create_or_update_integration

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create integration
        create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="valid-token",
            refresh_token="refresh-token",
            expires_in=3600,
        )

        # Request returns 403 (forbidden)
        mock_403_response = MagicMock()
        mock_403_response.status_code = 403
        mock_request = AsyncMock(return_value=mock_403_response)

        result = await with_oauth_retry(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            request_func=mock_request,
        )

        # Should return the 403 without retry
        assert result.status_code == 403
        mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_only_retries_once(self, session: Session):
        """Only retries once, even if retry also returns 401."""
        from app.services.oauth_retry import with_oauth_retry
        from app.crud.integration import create_or_update_integration

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create integration
        create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="bad-token",
            refresh_token="refresh-token",
            expires_in=3600,
        )

        # Both calls return 401
        mock_401_response = MagicMock()
        mock_401_response.status_code = 401
        mock_request = AsyncMock(return_value=mock_401_response)

        # Mock the token refresh as successful
        with patch("app.services.oauth_retry.refresh_integration_token") as mock_refresh:
            mock_refresh.return_value = True

            result = await with_oauth_retry(
                session=session,
                user_id=user.id,
                service_name="google_drive",
                request_func=mock_request,
            )

            # Should return 401 after one retry
            assert result.status_code == 401
            assert mock_request.call_count == 2  # Called exactly twice
            mock_refresh.assert_called_once()  # Refresh only called once


class TestMakeAuthorizedRequest:
    """Tests for make_authorized_request helper."""

    @pytest.mark.asyncio
    async def test_makes_request_with_token(self, session: Session):
        """Makes HTTP request with authorization header."""
        from app.services.oauth_retry import make_authorized_request
        from app.crud.integration import create_or_update_integration

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        # Create integration
        create_or_update_integration(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            access_token="test-access-token",
            refresh_token="refresh-token",
            expires_in=3600,
        )

        # Mock httpx
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200

            mock_instance = AsyncMock()
            mock_instance.request.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await make_authorized_request(
                session=session,
                user_id=user.id,
                service_name="google_drive",
                method="GET",
                url="https://www.googleapis.com/drive/v3/files",
            )

            assert result.status_code == 200

            # Verify authorization header was set
            call_kwargs = mock_instance.request.call_args.kwargs
            assert "Bearer test-access-token" in str(call_kwargs.get("headers", {}))

    @pytest.mark.asyncio
    async def test_returns_none_when_no_integration(self, session: Session):
        """Returns None when user has no integration."""
        from app.services.oauth_retry import make_authorized_request

        user = User(email="test@example.com", username="testuser")
        session.add(user)
        session.commit()
        session.refresh(user)

        result = await make_authorized_request(
            session=session,
            user_id=user.id,
            service_name="google_drive",
            method="GET",
            url="https://www.googleapis.com/drive/v3/files",
        )

        assert result is None
