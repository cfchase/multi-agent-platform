# LangFlow Kustomize Manifests (Legacy)

**NOTE**: These Kustomize manifests are kept for reference only.

The active deployment method uses Helm charts. See:
- `helm/langflow/values-dev.yaml` - Helm values
- `scripts/deploy-langflow.sh` - Deploy script

## Why Keep These?

These manifests provide reference for:
- Custom init containers (database wait/creation)
- Volume mount configurations
- Environment variable patterns
- OpenShift SCC-compatible security contexts

## Active Deployment

To deploy LangFlow, use:
```bash
./scripts/deploy-langflow.sh dev
# or
make deploy-langflow
```
