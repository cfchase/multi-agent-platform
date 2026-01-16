#!/bin/bash
# Generate Langfuse Helm secrets file with random values
# Admin credentials are generated separately via admin-credentials K8s secret

set -e

SECRETS_FILE="helm/langfuse/secrets-dev.yaml"
NAMESPACE="${HELM_NAMESPACE:-deep-research-dev}"
ROUTE_NAME="langfuse"

if [ -f "$SECRETS_FILE" ]; then
    echo "$SECRETS_FILE already exists, skipping"
    exit 0
fi

echo "Generating $SECRETS_FILE with random secrets..."

# Generate random secrets for services
REDIS_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")
CH_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")
MINIO_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")
LF_SALT=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
NEXTAUTH_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
ENCRYPT_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# Pre-compute the route URL
NEXTAUTH_URL=""
if command -v oc &> /dev/null; then
    APPS_DOMAIN=$(oc get ingresses.config.openshift.io cluster -o jsonpath='{.spec.domain}' 2>/dev/null || true)
    if [ -n "$APPS_DOMAIN" ]; then
        NEXTAUTH_URL="https://${ROUTE_NAME}-${NAMESPACE}.${APPS_DOMAIN}"
        echo "Pre-computed route URL: $NEXTAUTH_URL"
    fi
fi

if [ -z "$NEXTAUTH_URL" ]; then
    echo "Warning: Could not determine cluster apps domain. NEXTAUTH_URL will need to be set manually."
fi

cat > "$SECRETS_FILE" <<EOF
# Auto-generated Langfuse secrets - DO NOT COMMIT
# Generated on: $(date)
# Admin credentials come from shared 'admin-credentials' K8s secret

# Redis authentication
redis:
  auth:
    password: "${REDIS_PASS}"

# ClickHouse authentication
clickhouse:
  auth:
    password: "${CH_PASS}"

# MinIO/S3 credentials
s3:
  accessKeyId:
    value: "minio"
  secretAccessKey:
    value: "${MINIO_SECRET}"

# Langfuse application secrets
langfuse:
  salt:
    value: "${LF_SALT}"
  encryptionKey:
    value: "${ENCRYPT_KEY}"
  nextauth:
    url: "${NEXTAUTH_URL}"
    secret:
      value: "${NEXTAUTH_SECRET}"
EOF

echo "Created $SECRETS_FILE"
