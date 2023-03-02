#!/bin/bash
set -ex

# Image name
_IMAGE_NAME="ghcr.io/ansys/ensight_dev"

# Remove all dangling images
containers=$(docker container ls -aq)
if [ ! -z "$containers" ]; then
    docker container stop $containers
fi
docker container prune -f
docker image prune -f

# Pull nexus image based on tag
docker pull $_IMAGE_NAME