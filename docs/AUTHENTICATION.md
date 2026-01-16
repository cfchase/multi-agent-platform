# Authentication with OAuth2 Proxy

This application uses OAuth2 Proxy for authentication, enabling integration with external identity providers like Keycloak, Google, and GitHub.

> **Why Authentication Matters:** Full functionality—including user sessions, personalized research history, document access controls, and multi-user collaboration—requires proper authentication. While you can run in "local" mode for quick exploration, setting up OAuth unlocks the complete feature set.

## Quick Reference

| Mode | When to Use | Setup Time |
|------|-------------|------------|
| **Local (no auth)** | Quick exploration, UI development | 1 minute |
| **Google OAuth (local)** | Full local development with auth | 15 minutes |
| **Google OAuth (OpenShift)** | Production deployment | 20 minutes |

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

## Local Development (No Auth)

For quick exploration without setting up OAuth:

```bash
# Edit backend/.env
ENVIRONMENT=local

# Start the app
make db-start && make db-init
make dev
```

In local mode:
- No authentication headers are required
- A default "dev-user" is used for all requests
- The frontend will show "dev-user@example.com" in the user menu
- Access the app at http://localhost:8080

---

## Google OAuth Setup

This section provides step-by-step instructions for setting up Google OAuth for both local development and OpenShift deployment.

**Official Documentation:**
- [Setting up OAuth 2.0](https://support.google.com/cloud/answer/6158849) - Google Cloud support guide
- [Using OAuth 2.0 for Web Server Applications](https://developers.google.com/identity/protocols/oauth2/web-server) - Developer guide
- [OAuth 2.0 Scopes for Google APIs](https://developers.google.com/identity/protocols/oauth2/scopes) - Available scopes

### Step 1: Create Google Cloud OAuth Credentials

1. **Go to Google Cloud Console**
   - Open [Google Cloud Console - Credentials](https://console.cloud.google.com/apis/credentials)
   - Sign in with your Google account

2. **Select or Create a Project**
   - Click the project dropdown at the top
   - Select an existing project or click "New Project"
   - If creating new: Enter a project name (e.g., "Deep Research Dev")

3. **Configure OAuth Consent Screen** (first time only)
   - In the left sidebar, click "OAuth consent screen"
   - Choose "External" (unless you have Google Workspace)
   - Fill in required fields:
     - **App name**: Deep Research
     - **User support email**: Your email
     - **Developer contact email**: Your email
   - Click "Save and Continue" through the remaining steps
   - Add your email as a test user if in "Testing" mode

4. **Create OAuth 2.0 Credentials**
   - Go back to "Credentials" in the left sidebar
   - Click "+ CREATE CREDENTIALS" → "OAuth client ID"
   - Select **Application type**: "Web application"
   - **Name**: "Deep Research Local" (or "Deep Research Production")
   - **Authorized JavaScript origins**: (see environment-specific sections below)
   - **Authorized redirect URIs**: (see environment-specific sections below)
   - Click "Create"

5. **Copy Your Credentials**
   - A dialog will show your **Client ID** and **Client Secret**
   - Save these securely—you'll need them for configuration

![Google OAuth setup diagram](assets/Google%20Auth.png)

---

### Step 2a: Local Development with OAuth

After creating Google OAuth credentials, configure them for local development.

**Authorized Origins & Redirect URIs** (in Google Console):
```
Authorized JavaScript origins:
  http://localhost:4180

Authorized redirect URIs:
  http://localhost:4180/oauth2/callback
```

**Configure the Application:**

```bash
# Edit backend/.env with your credentials
cp backend/.env.example backend/.env
```

Add these values to `backend/.env`:
```bash
ENVIRONMENT=development
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret

# Generate a cookie secret:
# python -c "import secrets; print(secrets.token_urlsafe(32))"
OAUTH_COOKIE_SECRET=your-generated-secret
```

**Start the Application:**
```bash
make db-start && make db-init
make dev
```

**Access the App:**
- Open http://localhost:4180 (OAuth proxy port)
- You'll be redirected to Google sign-in
- After authentication, you'll return to the app

---

### Step 2b: OpenShift Deployment with OAuth

After creating Google OAuth credentials, configure them for cluster deployment.

**Authorized Origins & Redirect URIs** (in Google Console):

Get your route URL first:
```bash
# After initial deploy, or estimate based on cluster:
# https://multi-agent-platform-<namespace>.apps.<cluster-domain>
```

Then add to Google Console:
```
Authorized JavaScript origins:
  https://multi-agent-platform-multi-agent-platform-dev.apps.your-cluster.com

Authorized redirect URIs:
  https://multi-agent-platform-multi-agent-platform-dev.apps.your-cluster.com/oauth2/callback
```

**Configure the OAuth Secret:**

```bash
# Copy the example file
cp k8s/app/overlays/dev/oauth-proxy-secret.env.example \
   k8s/app/overlays/dev/oauth-proxy-secret.env

# Edit with your credentials
```

Contents of `oauth-proxy-secret.env`:
```bash
# Generate cookie secret: python -c "import secrets; print(secrets.token_urlsafe(32))"
cookie-secret=your-generated-cookie-secret

# From Google Cloud Console
client-id=your-client-id.apps.googleusercontent.com
client-secret=your-client-secret
```

**Deploy:**
```bash
oc login --server=https://your-cluster
make deploy
```

**Update Google Console** (if redirect URL changed):
- After deployment, get the actual route URL:
  ```bash
  oc get route multi-agent-platform -n multi-agent-platform-dev -o jsonpath='{.spec.host}'
  ```
- Update the authorized redirect URI in Google Console if needed

---

## Alternative OAuth Providers

### Keycloak / Red Hat SSO

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

### GitHub OAuth

1. Go to [GitHub Settings > Developer settings > OAuth Apps](https://github.com/settings/developers)
2. Click "New OAuth App"
3. Fill in:
   - **Application name**: Deep Research
   - **Homepage URL**: Your app URL
   - **Authorization callback URL**: `https://your-app.example.com/oauth2/callback`
4. Copy the Client ID and generate a Client Secret

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
