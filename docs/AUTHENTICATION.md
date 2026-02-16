# Authentication with OAuth2 Proxy

This application uses OAuth2 Proxy for authentication, enabling integration with external identity providers like Keycloak, Google, and GitHub.

> **Why Authentication Matters:** Full functionality—including user sessions, personalized research history, document access controls, and multi-user collaboration—requires proper authentication. The mock OAuth mode provides a fully functional auth experience for local development.

## Quick Reference

| Mode | When to Use | Setup Time |
|------|-------------|------------|
| **Mock OAuth (local)** | Local development with auth (recommended) | 1 minute |
| **No auth (local)** | Quick exploration, UI development only | 1 minute |
| **Real OAuth (local)** | Testing with actual provider | 15 minutes |
| **OAuth (OpenShift)** | Production deployment | 20 minutes |

## Architecture

```
                    ┌─────────────────────┐
                    │   OpenShift Route   │
                    │  (External Access)  │
                    └──────────┬──────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                           App Pod                                │
│  ┌────────────────┐                                              │
│  │  OAuth2 Proxy  │◄── All external requests enter here          │
│  │  (Port 4180)   │                                              │
│  │                │    - Authenticates users                     │
│  │  ENTRY POINT   │    - Sets X-Forwarded-User headers           │
│  └───────┬────────┘    - Redirects to OAuth provider             │
│          │                                                       │
│          ▼                                                       │
│  ┌────────────────┐                                              │
│  │    Frontend    │    - Serves React static files               │
│  │  (Port 8080)   │    - Proxies /api/* to backend               │
│  │  Nginx Proxy   │                                              │
│  └───────┬────────┘                                              │
│          │                                                       │
│          ▼                                                       │
│  ┌────────────────┐                                              │
│  │    Backend     │    - Reads X-Forwarded-User headers          │
│  │  (Port 8000)   │    - Auto-creates users on first login       │
│  │                │    - Trusts headers (internal only)          │
│  │ INTERNAL ONLY  │◄── NOT directly accessible from outside      │
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

## Local Development with Mock OAuth (Recommended)

The easiest way to develop with full authentication is using the built-in mock OAuth server. No external credentials required.

```bash
# Start all services including mock OAuth
make services-start

# Start frontend and backend
make dev
```

The `make dev` command auto-detects OAuth and displays the access URL:
```
OAuth running - access app at: http://localhost:4180
```

**How Mock OAuth Works:**
- Uses [mock-oauth2-server](https://github.com/navikt/mock-oauth2-server) container
- Auto-starts when no real OAuth credentials are configured
- Login with any username/password (they're not validated)
- Full OAuth flow with user headers (`X-Forwarded-User`, `X-Forwarded-Email`)
- Backend auto-creates users on first login

**Ports:**
- `4180` - OAuth2 Proxy (entry point - use this URL)
- `9099` - Mock OAuth server (internal)
- `8080` - Frontend (proxied through OAuth)
- `8000` - Backend (internal)

---

## Local Development (No Auth)

For quick UI development without OAuth overhead:

```bash
# Edit config/local/.env.backend (or backend/.env after make env-setup)
ENVIRONMENT=local

# Start the app (without services-start)
make db-start && make db-init
make dev
```

In local mode:
- No authentication headers are required
- A default "dev-user" is used for all requests
- The frontend will show "dev-user@example.com" in the user menu
- Access the app directly at http://localhost:8080

---

## Real OAuth Providers

For testing with actual OAuth providers (Google, GitHub, Keycloak), configure credentials in `config/local/.env.oauth-proxy` (local) or `config/dev/.env.oauth-proxy` (cluster).

### Environment Variables

```bash
# Generic OAuth (works with any OIDC provider)
OAUTH_CLIENT_ID=your-client-id
OAUTH_CLIENT_SECRET=your-client-secret
OAUTH_ISSUER_URL=https://your-oidc-provider.com  # Optional: enables OIDC mode
OAUTH_COOKIE_SECRET=<auto-generated-if-not-set>
```

**Provider Auto-Detection:**
- If `OAUTH_ISSUER_URL` is set → Uses OIDC provider (Keycloak, Okta, etc.)
- If `OAUTH_ISSUER_URL` is not set → Uses Google provider
- If `OAUTH_CLIENT_ID` is not set → Uses mock OAuth server

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
# Set up environment from config/local/ templates
make env-setup
```

Add these values to `config/local/.env.backend`:
```bash
ENVIRONMENT=development
```

Add these values to `config/local/.env.oauth-proxy`:
```bash
OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
OAUTH_CLIENT_SECRET=your-client-secret
# OAUTH_COOKIE_SECRET is auto-generated if not set
```

**Start the Application:**
```bash
make services-start
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
# Generate config files from templates
make config-setup

# Or manually copy:
cp config/dev/.env.oauth-proxy.example config/dev/.env.oauth-proxy
# Edit with your credentials
```

Contents of `config/dev/.env.oauth-proxy`:
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

## OpenShift OAuth for Supporting Services

Langflow and MLflow are protected by OpenShift OAuth proxy sidecars. This provides SSO via OpenShift credentials and namespace-scoped access control.

### How It Works

1. User accesses service via OpenShift Route (e.g., `https://langflow-<namespace>.apps.<cluster>`)
2. OAuth proxy intercepts the request and redirects to OpenShift's built-in OAuth server
3. User authenticates with their OpenShift credentials
4. OAuth proxy performs a SubjectAccessReview (SAR) check
5. If user has `pods update` permission in the namespace, access is granted

### SAR Configuration

The SubjectAccessReview rule restricts access to namespace administrators:

```json
{"namespace":"<namespace>","resource":"pods","verb":"update"}
```

This means only users with `edit` or `admin` ClusterRole bindings in the namespace can access the services. The `namespace-admins.txt` config file controls which OpenShift users get the `edit` role.

### Configuration Files

| File | Purpose |
|------|---------|
| `config/dev/namespace-admins.txt` | OpenShift usernames granted namespace edit access |
| `helm/mlflow/values-dev.yaml` | MLflow OAuth proxy sidecar (via extraContainers) |
| `helm/langflow/post-renderer/oauth-proxy-patch.yaml` | Langflow OAuth proxy sidecar (via Kustomize patch) |

### Adding a New Admin

1. Add the OpenShift username to `config/dev/namespace-admins.txt`
2. Redeploy: `make deploy` (or run `oc adm groups add-users <namespace>-admins <username>`)

### Langfuse Authentication

Langfuse uses its built-in NextAuth authentication and cannot be configured with an external OAuth proxy. Users access Langfuse with the credentials shown by `make get-admin-credentials`.

## Troubleshooting

### User not being created

Check that OAuth2 Proxy is passing headers:
```bash
curl -H "X-Forwarded-User: test" -H "X-Forwarded-Email: test@example.com" \
  http://localhost:8000/api/v1/users/me
```

### 401 errors in development

Ensure `ENVIRONMENT=local` is set in your `config/local/.env.backend` file (or `backend/.env`).

### Cookie issues

If login loops occur, check:
- Cookie domain matches your app domain
- HTTPS is properly configured
- Cookie secret is properly set
