# MLFlow Kustomize Manifests (Legacy)

**NOTE**: These Kustomize manifests are kept for reference only.

The active deployment method uses Helm charts. See:
- `helm/mlflow/values-dev.yaml` - Helm values
- `scripts/deploy-mlflow.sh` - Deploy script

## Why Keep These?

These manifests provide reference for:
- Custom startup command (pip install psycopg2-binary)
- Init containers for database wait/creation
- Volume mount configurations
- PostgreSQL connection patterns
- OpenShift SCC-compatible security contexts

## Active Deployment

To deploy MLFlow, use:
```bash
./scripts/deploy-mlflow.sh dev
# or
make deploy-mlflow
```
