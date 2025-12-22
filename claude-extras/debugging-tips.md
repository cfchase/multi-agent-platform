# Debugging Tips

Quick reference for troubleshooting common issues in this codebase.

## Backend Issues

### Database Connection Errors

**Symptom**: `Connection refused` or `could not connect to server`

**Checklist**:
1. Is PostgreSQL running?
   ```bash
   make db-status
   ```
2. Are environment variables set correctly?
   ```bash
   # Check .env file or environment
   echo $POSTGRES_SERVER
   echo $POSTGRES_PORT
   ```
3. Is the database container accessible?
   ```bash
   make db-logs
   ```

**Common fixes**:
- Start database: `make db-start`
- Check Docker/Podman is running
- Verify credentials match

### Migration Errors

**Symptom**: `alembic.util.exc.CommandError` or table conflicts

**Checklist**:
1. Check current migration state:
   ```bash
   cd backend && uv run alembic current
   ```
2. View migration history:
   ```bash
   cd backend && uv run alembic history
   ```

**Common fixes**:
- Reset to clean state: `make db-reset && make db-init`
- Manually fix migration: Edit file in `alembic/versions/`
- Stamp to specific revision: `uv run alembic stamp <revision>`

### Import Errors

**Symptom**: `ModuleNotFoundError` or `ImportError`

**Checklist**:
1. Are you in the right directory?
   ```bash
   pwd  # Should be in backend/
   ```
2. Is the virtual environment activated?
   ```bash
   uv run python -c "import app; print(app.__file__)"
   ```
3. Did you add new files to `__init__.py`?

**Common fixes**:
- Sync dependencies: `cd backend && uv sync`
- Check `__init__.py` exports
- Use TYPE_CHECKING for circular imports

### SQLAlchemy Relationship Errors

**Symptom**: `InvalidRequestError: relationship ... failed to locate`

**Cause**: Union type annotations like `"User | None"` aren't understood by SQLAlchemy.

**Fix**: Use `Optional["User"]` instead of `"User | None"` for relationships:
```python
# Wrong
owner: "User | None" = Relationship(back_populates="items")

# Correct
from typing import Optional
owner: Optional["User"] = Relationship(back_populates="items")
```

### 401 Unauthorized Errors

**Symptom**: API returns 401 even in local development

**Checklist**:
1. Is ENVIRONMENT set to "local"?
   ```bash
   grep ENVIRONMENT .env
   ```
2. Are OAuth headers being sent?
   - In production, OAuth2-proxy sets headers
   - In local mode, dev-user is used automatically

**Common fixes**:
- Set `ENVIRONMENT=local` in `.env`
- Check deps.py `get_current_user` function

## Frontend Issues

### Vite Proxy Not Working

**Symptom**: API calls return 404 or CORS errors

**Checklist**:
1. Is the backend running?
   ```bash
   curl http://localhost:8000/api/v1/utils/health-check
   ```
2. Is vite.config.ts proxy configured?
   ```typescript
   // Should have:
   proxy: {
     '/api': 'http://localhost:8000'
   }
   ```

**Common fixes**:
- Start backend: `make dev-backend`
- Check vite.config.ts proxy settings
- Clear browser cache

### TypeScript Errors

**Symptom**: `Type 'X' is not assignable to type 'Y'`

**Checklist**:
1. Run type check:
   ```bash
   cd frontend && npm run typecheck
   ```
2. Check for missing type definitions

**Common fixes**:
- Add proper type annotations
- Use type assertions sparingly: `as SomeType`
- Never use `any` - find the correct type

### PatternFly Styling Issues

**Symptom**: Components look wrong or have no styling

**Checklist**:
1. Are PatternFly CSS files imported?
   ```typescript
   // In index.tsx or app.tsx
   import '@patternfly/react-core/dist/styles/base.css';
   ```
2. Are you using inline styles?
   - NEVER use `style={{...}}` with PatternFly
   - Use component props and variants

**Common fixes**:
- Use PatternFly layout components (Stack, Flex, Grid)
- Use CSS variables for colors: `var(--pf-v6-global--...)`
- Check PatternFly v6 documentation

### Tests Failing

**Symptom**: Tests pass locally but fail in CI

**Checklist**:
1. Are you mocking APIs correctly?
2. Are there timing issues?
   ```tsx
   // Use waitFor for async operations
   await waitFor(() => {
     expect(screen.getByText('...')).toBeInTheDocument();
   });
   ```
3. Are there hanging test processes?
   ```bash
   pkill -f vitest
   ```

**Common fixes**:
- Use `waitFor` for async assertions
- Mock all external dependencies
- Clean up after each test

## General Debugging

### Check Logs

**Backend logs**:
```bash
# If running with make dev-backend
# Logs appear in terminal

# If running in container
make db-logs
kubectl logs <pod-name>
```

**Frontend logs**:
- Open browser DevTools (F12)
- Check Console tab for errors
- Check Network tab for API calls

### Quick Health Check

```bash
# Backend health
curl http://localhost:8000/api/v1/utils/health-check

# Frontend (should show HTML)
curl http://localhost:8080

# Database
make db-status
```

### Reset Everything

If nothing works, full reset:
```bash
# Stop everything
make db-stop

# Clean up
make clean

# Fresh start
make setup
make db-start
make db-reset
make db-init
make db-seed
make dev
```
