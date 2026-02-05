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
   - State management for CSRF protection
   - Authorization URL generation

2. **Token Exchange Service** (`app/services/oauth_token.py`)
   - Authorization code exchange
   - Token refresh

3. **Token Refresh Service** (`app/services/token_refresh.py`)
   - Automatic refresh before expiration
   - `get_valid_token()` for always-valid tokens

4. **Flow Token Injection** (`app/services/flow_token_injection.py`)
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

- **OAuth Type**: OAuth 2.0 with PKCE
- **Scopes**: `openid`
- **PKCE**: Required (S256)

**Setup:**
1. Contact your Dataverse administrator for OAuth credentials
2. Set environment variables:
   ```
   DATAVERSE_CLIENT_ID=your-client-id
   DATAVERSE_CLIENT_SECRET=your-client-secret
   DATAVERSE_SERVER_URL=https://your-dataverse-instance.org
   ```

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
3. **Token Refresh**: Automatic refresh 5 minutes before expiration
4. **Token Access**: `get_valid_token()` always returns a valid token

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

### Handling Missing Tokens

```python
from app.services.flow_token_injection import build_flow_tweaks, MissingTokenError

try:
    tweaks = await build_flow_tweaks(...)
except MissingTokenError as e:
    # User needs to connect the service
    return {"error": f"Please connect {e.service_name} first"}
```

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
| `DATAVERSE_CLIENT_ID` | For Dataverse | Dataverse OAuth client ID |
| `DATAVERSE_CLIENT_SECRET` | For Dataverse | Dataverse OAuth client secret |
| `DATAVERSE_SERVER_URL` | For Dataverse | Dataverse server URL |

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
