# OAuth External Service Integrations

This document describes how users can connect external services (Google Drive, Dataverse) to the Multi-Agent Platform, enabling AI workflows to access their data securely.

## Overview

The platform supports OAuth 2.0 integration with external services. Users authenticate once per service, and their tokens are securely stored and automatically refreshed. AI flows can then access these services on behalf of the user.

## Architecture

```
User → Frontend → /api/v1/integrations/oauth/start/{service}
                            ↓
                  OAuth Provider (Google, Dataverse)
                            ↓
                  /api/v1/integrations/oauth/callback/{service}
                            ↓
                  Token Exchange → Encrypted Storage
```

### Components

1. **OAuth Configuration Service** (`app/services/oauth_config.py`)
   - Provider configurations (URLs, scopes, PKCE)
   - Database-backed state management for multi-replica support
   - Authorization URL generation

2. **Token Exchange Service** (`app/services/oauth_token.py`)
   - Authorization code exchange
   - Token refresh
   - Handles both static and dynamic client credentials

3. **Dataverse OAuth Service** (`app/services/dataverse_oauth.py`)
   - Dynamic client registration (RFC 7591)
   - Automatic client creation per OAuth flow

4. **Token Refresh Service** (`app/services/token_refresh.py`)
   - Automatic refresh before expiration
   - Locking mechanism for multi-replica safety
   - Rate limiting to prevent provider abuse
   - `get_valid_token()` for always-valid tokens

5. **Flow Token Injection** (`app/services/flow_token_injection.py`)
   - Injects user tokens into Langflow tweaks
   - Enables flows to access external services

## Supported Services

### Google Drive

- **OAuth Type**: Standard OAuth 2.0
- **Scopes**: `https://www.googleapis.com/auth/drive.readonly`
- **Access Type**: Offline (refresh token provided)

**Setup:**
1. Create a project at [Google Cloud Console](https://console.cloud.google.com/)
2. Enable the Google Drive API
3. Create OAuth 2.0 credentials (Web application)
4. Add redirect URI: `{YOUR_BASE_URL}/api/v1/integrations/oauth/callback/google_drive`
5. Set environment variables:
   ```
   GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your-client-secret
   ```

### Dataverse

- **OAuth Type**: OAuth 2.0 with PKCE + Dynamic Client Registration (RFC 7591)
- **Scopes**: `openid`, `offline_access` (for refresh tokens)
- **PKCE**: Required (S256)

Dataverse uses **dynamic client registration** - no static client credentials needed. A new OAuth client is registered automatically for each OAuth flow.

**Setup:**
1. Set the Dataverse auth URL:
   ```
   DATAVERSE_AUTH_URL=https://mcp.dataverse.redhat.com/auth
   ```

   The following endpoints are derived automatically:
   - Authorization: `{DATAVERSE_AUTH_URL}/authorize`
   - Token: `{DATAVERSE_AUTH_URL}/token`
   - Registration: `{DATAVERSE_AUTH_URL}/register`

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/integrations/` | List user's connected integrations |
| GET | `/api/v1/integrations/status` | Get connected/missing services |
| GET | `/api/v1/integrations/services` | List supported OAuth services |
| POST | `/api/v1/integrations/oauth/start/{service}` | Start OAuth flow |
| GET | `/api/v1/integrations/oauth/callback/{service}` | OAuth callback handler |
| DELETE | `/api/v1/integrations/{service}` | Disconnect integration |

## Token Security

### Encryption at Rest

Tokens are encrypted using Fernet (AES-128-CBC + HMAC-SHA256) before storage:

```python
# Generate key once, store securely
TOKEN_ENCRYPTION_KEY=your-fernet-key
```

Generate a key:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Token Lifecycle

1. **Initial Authorization**: User clicks Connect, redirects to provider
2. **Token Storage**: Authorization code exchanged, tokens encrypted and stored
3. **Token Refresh**: Automatic refresh when token is expired or expiring soon
4. **Token Access**: `get_valid_token()` always returns a valid token

### Token Refresh Mechanism

The refresh service includes safeguards for multi-replica deployments:

- **Locking**: A `refresh_locked_at` timestamp prevents concurrent refresh attempts
  - Lock expires after 30 seconds if not released
  - Only one replica can refresh a token at a time

- **Rate Limiting**: A `last_refresh_attempt` timestamp prevents rapid retries
  - 60-second cooldown between refresh attempts
  - Prevents hammering the OAuth provider on persistent failures

- **Service-specific thresholds**: Different services have different refresh windows
  - Google Drive: 5 minutes before expiration
  - Dataverse: 5 minutes before expiration

## Flow Integration

### Token Injection

When executing a flow that requires external service access:

```python
from app.services.flow_token_injection import build_flow_tweaks

# Configuration maps services to Langflow component fields
token_config = {
    "google_drive": "GoogleDriveLoader.credentials",
    "dataverse": "DataverseSearchTool.api_token",
}

# Build tweaks with user tokens (auto-refreshes if needed)
tweaks = await build_flow_tweaks(
    session=session,
    user_id=user.id,
    token_config=token_config,
)

# Pass to Langflow
await client.chat(message, tweaks=tweaks)
```

### Missing Tokens

The platform injects all available tokens automatically. If a user hasn't
connected a service, its token is simply omitted from `UserSettings.data`.
Flows should handle missing tokens gracefully (e.g., skip document search
if no `google_drive_token` is present).

## Frontend Integration

The Integration Settings page is available at `/settings/integrations`:

- View connection status for all services
- Click "Connect" to start OAuth flow
- Click "Disconnect" to revoke access
- See token expiry information

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TOKEN_ENCRYPTION_KEY` | Yes | Fernet key for token encryption |
| `GOOGLE_CLIENT_ID` | For Google | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | For Google | Google OAuth client secret |
| `DATAVERSE_AUTH_URL` | For Dataverse | Dataverse OAuth auth base URL (e.g., `https://mcp.dataverse.redhat.com/auth`) |

## Troubleshooting

### "Invalid state parameter"
- State is single-use and expires
- User may have taken too long or refreshed the page
- Solution: Start OAuth flow again

### "Token exchange failed"
- Authorization code may have expired
- Check OAuth credentials are correct
- Verify redirect URI matches exactly

### "Missing token for service"
- User hasn't connected the service
- Token may have expired without a refresh token
- Solution: Reconnect the service

## Development

### Testing with Mock

For development without real OAuth:
1. Create integration directly in database
2. Use mock tokens for testing flow execution

### Adding New Services

1. Add provider config in `app/services/oauth_config.py`
2. Add to `get_supported_services()` list
3. Add display name/description in `integrationService.ts`
4. Test OAuth flow end-to-end
