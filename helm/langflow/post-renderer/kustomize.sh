#!/bin/bash
# Helm post-renderer that applies Kustomize patches to inject OAuth proxy sidecar
# Used by: helm install/upgrade --post-renderer ./helm/langflow/post-renderer/kustomize.sh
#
# How it works:
# 1. Helm pipes rendered chart YAML to this script's stdin
# 2. We save it to a temp file, run kustomize build to apply patches
# 3. The patched YAML is output to stdout for Helm to apply

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Save Helm's rendered output as a resource for Kustomize
cat - > "$DIR/helm-output.yaml"

# Run Kustomize to apply patches and output result
cd "$DIR" && kustomize build .

# Clean up the temporary file
rm -f "$DIR/helm-output.yaml"
