#!/bin/bash

# Push container images to registry
# Usage: ./scripts/push-images.sh [tag] [registry] [container-tool]
# Environment variables:
#   CONTAINER_TOOL: Container tool to use (docker or podman). Default: docker

set -e

# Default values
TAG=${1:-latest}
REGISTRY=${2:-quay.io/cfchase}
CONTAINER_TOOL=${3:-${CONTAINER_TOOL:-docker}}
PROJECT_NAME="pf-full-stack-fastapi"

# Validate container tool
if [[ "$CONTAINER_TOOL" != "podman" && "$CONTAINER_TOOL" != "docker" ]]; then
    echo "Error: CONTAINER_TOOL must be either 'podman' or 'docker'"
    exit 1
fi

# Check if container tool is available
if ! command -v "$CONTAINER_TOOL" &> /dev/null; then
    echo "Error: $CONTAINER_TOOL is not installed or not in PATH"
    exit 1
fi

echo "Pushing images with tag: $TAG"
echo "Registry: $REGISTRY"
echo "Container tool: $CONTAINER_TOOL"

# Push backend image
echo "Pushing backend image..."
$CONTAINER_TOOL push "${REGISTRY}/${PROJECT_NAME}-backend:${TAG}"

# Push frontend image
echo "Pushing frontend image..."
$CONTAINER_TOOL push "${REGISTRY}/${PROJECT_NAME}-frontend:${TAG}"

echo "Images pushed successfully!"
echo "Backend: ${REGISTRY}/${PROJECT_NAME}-backend:${TAG}"
echo "Frontend: ${REGISTRY}/${PROJECT_NAME}-frontend:${TAG}"