# Authentication with OAuth2 Proxy

This application uses OAuth2 Proxy for authentication, enabling integration with external identity providers like Keycloak, Google, and GitHub.

## Architecture

```
                    ┌─────────────────────┐
                    │   OpenShift Route   │
                    │  (External Access)  │
                    └──────────┬──────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                           App Pod                                 │
│  ┌────────────────┐                                              │
│  │  OAuth2 Proxy  │◄── All external requests enter here         │
│  │  (Port 4180)   │                                              │
│  │                │    - Authenticates users                     │
│  │  ENTRY POINT   │    - Sets X-Forwarded-User headers           │
│  └───────┬────────┘    - Redirects to OAuth provider             │
│          │                                                        │
│          ▼                                                        │
│  ┌────────────────┐                                              │
│  │    Frontend    │    - Serves React static files               │
│  │  (Port 8080)   │    - Proxies /api/* to backend               │
│  │  Nginx Proxy   │                                              │
│  └───────┬────────┘                                              │
│          │                                                        │
│          ▼                                                        │
│  ┌────────────────┐                                              │
│  │    Backend     │    - Reads X-Forwarded-User headers          │
│  │  (Port 8000)   │    - Auto-creates users on first login       │
│  │                │    - Trusts headers (internal only)          │
│  │ INTERNAL ONLY  │◄── NOT directly accessible from outside     │
│  └────────────────┘                                              │
└──────────────────────────────────────────────────────────────────┘
```

**SECURITY NOTE:** The backend trusts `X-Forwarded-*` headers because it is only
accessible through the OAuth2 Proxy. Never expose the backend directly to external traffic.

## How It Works

1. **User accesses the application** via the OpenShift route
2. **OAuth2 Proxy intercepts requests** and checks for valid authentication
3. **Unauthenticated users** are redirected to the OAuth provider (Keycloak/Google/GitHub)
4. **After successful login**, OAuth2 Proxy sets headers:
   - `X-Forwarded-User`: Username from OAuth provider
   - `X-Forwarded-Email`: User's email address
   - `X-Forwarded-Preferred-Username`: Preferred username
5. **Backend reads these headers** and auto-creates users on first login
6. **Logout** redirects to `/oauth2/sign_out` which clears the session

## Local Development

For local development without OAuth2 Proxy, the backend runs in "local" mode:

```bash
# Set ENVIRONMENT=local in .env
ENVIRONMENT=local

# Start the backend
make dev-backend
```

In local mode:
- No authentication headers are required
- A default "dev-user" is used for all requests
- The frontend will show "dev-user@example.com" in the user menu

## Kubernetes Deployment

### Prerequisites

1. **Create OAuth2 Proxy Secret**

   ```bash
   # Copy the example secret
   cp k8s/base/oauth2-proxy-secret.yaml.example k8s/base/oauth2-proxy-secret.yaml

   # Generate a cookie secret
   openssl rand -base64 32 | tr -- '+/' '-_'

   # Edit the secret with your provider credentials
   vim k8s/base/oauth2-proxy-secret.yaml
   ```

2. **Configure your OAuth provider** (see provider-specific sections below)

3. **Update kustomization.yaml** to include OAuth2 proxy resources

### Provider Configuration

#### Keycloak / Red Hat SSO

1. Create a new client in your Keycloak realm
2. Set Access Type to "confidential"
3. Add valid redirect URI: `https://your-app.example.com/oauth2/callback`
4. Copy the client ID and secret

```yaml
# oauth2-proxy-secret.yaml
stringData:
  OAUTH2_PROXY_PROVIDER: "oidc"
  OAUTH2_PROXY_OIDC_ISSUER_URL: "https://keycloak.example.com/realms/your-realm"
  OAUTH2_PROXY_CLIENT_ID: "your-client-id"
  OAUTH2_PROXY_CLIENT_SECRET: "your-client-secret"
  OAUTH2_PROXY_COOKIE_SECRET: "<generated-secret>"
```

#### Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create OAuth 2.0 credentials
3. Add authorized redirect URI: `https://your-app.example.com/oauth2/callback`

```yaml
# oauth2-proxy-secret.yaml
stringData:
  OAUTH2_PROXY_PROVIDER: "google"
  OAUTH2_PROXY_CLIENT_ID: "your-id.apps.googleusercontent.com"
  OAUTH2_PROXY_CLIENT_SECRET: "your-secret"
  OAUTH2_PROXY_COOKIE_SECRET: "<generated-secret>"
```

#### GitHub OAuth

1. Go to GitHub Settings > Developer settings > OAuth Apps
2. Create a new OAuth App
3. Set Authorization callback URL: `https://your-app.example.com/oauth2/callback`

```yaml
# oauth2-proxy-secret.yaml
stringData:
  OAUTH2_PROXY_PROVIDER: "github"
  OAUTH2_PROXY_CLIENT_ID: "your-github-client-id"
  OAUTH2_PROXY_CLIENT_SECRET: "your-github-client-secret"
  OAUTH2_PROXY_COOKIE_SECRET: "<generated-secret>"
  # Optional: Restrict to organization members
  OAUTH2_PROXY_GITHUB_ORG: "your-org"
```

## Backend Configuration

The backend reads authentication mode from the `ENVIRONMENT` variable:

| ENVIRONMENT | Behavior |
|-------------|----------|
| `local` | No auth required, uses dev-user fallback |
| `development` | Reads OAuth headers, auto-creates users |
| `production` | Reads OAuth headers, auto-creates users |

### User Auto-Creation

When a user authenticates via OAuth2 Proxy:

1. Backend checks for existing user by username
2. If not found, creates a new user with:
   - `username`: From `X-Forwarded-Preferred-Username` or `X-Forwarded-User`
   - `email`: From `X-Forwarded-Email`
   - `active`: `true`
   - `admin`: `false` (can be changed via admin panel)
3. Updates `last_login` timestamp

## Frontend Integration

The frontend handles authentication through:

1. **AppContext**: Fetches current user from `/api/v1/users/me`
2. **User Menu**: Displays username with logout option
3. **API Client**: Intercepts 401 responses and redirects to OAuth login
4. **Logout**: Redirects to `/oauth2/sign_out`

## Security Considerations

1. **Never commit OAuth2 proxy secrets** to version control
2. **Use HTTPS** for all OAuth callbacks
3. **Restrict email domains** if needed via `OAUTH2_PROXY_EMAIL_DOMAINS`
4. **Set appropriate cookie security** flags in production
5. **Validate OAuth headers** only come from the proxy (not user-supplied)

### Admin Panel Security

The SQLAdmin panel (`/admin`) provides database management capabilities. In production:

- **Network Policy**: Restrict `/admin` access via OpenShift NetworkPolicy or OAuth2 proxy skip rules
- **Admin Role**: Consider requiring `is_admin=True` for admin panel access
- **Audit Logging**: Admin actions are logged via request middleware

**Example: Restrict admin access to specific users:**
```yaml
# In oauth2-proxy config, add skip rule with user restriction
OAUTH2_PROXY_SKIP_AUTH_ROUTES: "/api/v1/utils/health-check"
# Admin is NOT in skip routes, so it requires authentication
```

### GraphQL Endpoint Security

The GraphQL endpoint (`/api/graphql`) has built-in security:

- **Authentication Required**: All queries require OAuth authentication (except in local dev mode)
- **Query Depth Limit**: Maximum depth of 10 prevents deeply nested attacks
- **Token Limit**: Maximum 2000 tokens per query prevents DoS
- **GraphiQL Playground**: Enabled but protected by OAuth (safe in production)

**Production Considerations:**
- Consider disabling GraphQL introspection for additional security
- Monitor query complexity via logging middleware

## Troubleshooting

### User not being created

Check that OAuth2 Proxy is passing headers:
```bash
curl -H "X-Forwarded-User: test" -H "X-Forwarded-Email: test@example.com" \
  http://localhost:8000/api/v1/users/me
```

### 401 errors in development

Ensure `ENVIRONMENT=local` is set in your `.env` file.

### Cookie issues

If login loops occur, check:
- Cookie domain matches your app domain
- HTTPS is properly configured
- Cookie secret is properly set
