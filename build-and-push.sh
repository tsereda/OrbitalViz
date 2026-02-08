#!/bin/bash
# Build and push OrbitalViz Docker images for Linux

set -e

DOCKER="/Applications/Docker.app/Contents/Resources/bin/docker"
REGISTRY="gitlab-registry.nrp-nautilus.io/timothy.sereda/ov"
PLATFORM="linux/amd64"

echo "=== Building and Pushing OrbitalViz Images ==="
echo "Registry: $REGISTRY"
echo "Platform: $PLATFORM"
echo

# Build and push backend
echo "Building backend..."
cd backend
$DOCKER buildx build --platform $PLATFORM -t $REGISTRY/backend:latest --push .
echo "✓ Backend pushed to $REGISTRY/backend:latest"
cd ..

# Build and push frontend
echo
echo "Building frontend..."
cd frontend
$DOCKER buildx build --platform $PLATFORM -t $REGISTRY/frontend:latest --push .
echo "✓ Frontend pushed to $REGISTRY/frontend:latest"
cd ..

echo
echo "=== Build Complete ==="
echo "Images pushed:"
echo "  - $REGISTRY/backend:latest"
echo "  - $REGISTRY/frontend:latest"
echo
echo "To delete old images from registry, visit:"
echo "https://gitlab.nrp-nautilus.io/timothy.sereda/ov/container_registry"
